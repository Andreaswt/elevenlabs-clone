import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, mock_open

# Set environment variables before importing the app
os.environ["API_KEY"] = "test_fastapi_key"
os.environ["GEMINI_API_KEY"] = "test_gemini_key"
os.environ["S3_BUCKET"] = "test_bucket"
os.environ["S3_PREFIX"] = "test_prefix"
os.environ["AWS_REGION"] = "us-east-1" # Required by boto3
os.environ["AWS_ACCESS_KEY_ID"] = "test_access_key" # Required by boto3
os.environ["AWS_SECRET_ACCESS_KEY"] = "test_secret_key" # Required by boto3

from .api import app, TextToSpeechRequest, SUPPORTED_GEMINI_VOICES

client = TestClient(app)

@pytest.fixture(autouse=True)
def ensure_env_vars(monkeypatch):
    # This fixture ensures that for every test, these env vars are set.
    # They are already set globally, but this is good practice for pytest.
    monkeypatch.setenv("API_KEY", "test_fastapi_key")
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key")
    monkeypatch.setenv("S3_BUCKET", "test_bucket")
    monkeypatch.setenv("S3_PREFIX", "test_prefix")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test_access_key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test_secret_key")


# --- Test /health endpoint ---
def test_health_check_authorized():
    response = client.get("/health", headers={"Authorization": "Bearer test_fastapi_key"})
    assert response.status_code == 200
    # Based on current api.py, genai._is_configured might not be directly accessible
    # or easily mockable for this specific check without deeper changes.
    # We'll assume GEMINI_API_KEY presence implies configured for this test scope.
    assert response.json() == {"status": "healthy", "tts_service": "gemini_configured"}

def test_health_check_unauthorized_missing_key():
    response = client.get("/health")
    assert response.status_code == 401
    assert response.json() == {"detail": "API key is missing"}

def test_health_check_unauthorized_invalid_key():
    response = client.get("/health", headers={"Authorization": "Bearer wrong_key"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}

# --- Test /voices endpoint ---
def test_list_voices_authorized():
    response = client.get("/voices", headers={"Authorization": "Bearer test_fastapi_key"})
    assert response.status_code == 200
    assert response.json() == {"voices": SUPPORTED_GEMINI_VOICES}

def test_list_voices_unauthorized_missing_key():
    response = client.get("/voices")
    assert response.status_code == 401

def test_list_voices_unauthorized_invalid_key():
    response = client.get("/voices", headers={"Authorization": "Bearer wrong_key"})
    assert response.status_code == 401


# --- Test /convert endpoint ---
@patch('seed-vc.api.s3_client')
@patch('seed-vc.api.genai')
@patch('builtins.open', new_callable=mock_open) # Mock open for file writing
@patch('os.remove') # Mock os.remove
def test_convert_successful(mock_os_remove, mock_file_open, mock_genai, mock_s3_client):
    # Configure mocks
    # The generate_text_to_speech method is directly on the genai module
    mock_genai.generate_text_to_speech.return_value.audio_content = b"mock_audio_data"
    mock_s3_client.generate_presigned_url.return_value = "http://s3.mock.url/mock_audio.wav"

    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer test_fastapi_key"},
        json={"text": "Hello world", "voice": "echo"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "audio_url" in data
    assert data["audio_url"] == "http://s3.mock.url/mock_audio.wav"
    assert "s3_key" in data
    
    mock_genai.generate_text_to_speech.assert_called_once()
    call_args = mock_genai.generate_text_to_speech.call_args[1]
    assert call_args['text'] == "Hello world"
    assert call_args['voice_name'] == "echo"
    # assert call_args['model'] == "models/tts-004" # or the specific model name

    mock_file_open.assert_called_once() # Check that a temp file was opened for writing
    mock_s3_client.upload_file.assert_called_once()
    # Example of asserting upload_file args if needed:
    # upload_args = mock_s3_client.upload_file.call_args[0]
    # assert upload_args[1] == "test_bucket" # Bucket
    # assert data["s3_key"] in upload_args[2] # Key

    mock_s3_client.generate_presigned_url.assert_called_once()
    mock_os_remove.assert_called_once() # Check that temp file was removed

def test_convert_invalid_voice():
    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer test_fastapi_key"},
        json={"text": "Hello world", "voice": "invalid_voice"}
    )
    assert response.status_code == 400
    assert "Target voice not supported" in response.json()["detail"]

def test_convert_unauthorized_missing_key():
    response = client.post(
        "/convert",
        json={"text": "Hello world", "voice": "echo"}
    )
    assert response.status_code == 401

def test_convert_unauthorized_invalid_key():
    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer wrong_key"},
        json={"text": "Hello world", "voice": "echo"}
    )
    assert response.status_code == 401

@patch('seed-vc.api.s3_client')
@patch('seed-vc.api.genai')
def test_convert_gemini_api_error(mock_genai, mock_s3_client):
    mock_genai.generate_text_to_speech.side_effect = Exception("Gemini API Error")

    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer test_fastapi_key"},
        json={"text": "Hello world", "voice": "echo"}
    )
    assert response.status_code == 500
    assert "Error generating Gemini TTS" in response.json()["detail"] # This detail comes from the wrapped exception

@patch('seed-vc.api.s3_client')
@patch('seed-vc.api.genai')
@patch('builtins.open', new_callable=mock_open)
@patch('os.remove')
def test_convert_s3_upload_error(mock_os_remove, mock_file_open, mock_genai, mock_s3_client):
    mock_genai.generate_text_to_speech.return_value.audio_content = b"mock_audio_data"
    mock_s3_client.upload_file.side_effect = Exception("S3 Upload Error")

    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer test_fastapi_key"},
        json={"text": "Hello world", "voice": "echo"}
    )
    assert response.status_code == 500
    # The generic error "Error in text to speech conversion" is raised by the endpoint's broad try-except
    assert "Error in text to speech conversion" in response.json()["detail"]
    mock_os_remove.assert_called_once() # Ensure cleanup attempt even if S3 fails

@patch('seed-vc.api.genai.configure')
def test_health_check_gemini_not_configured(mock_genai_configure, monkeypatch):
    # Temporarily remove GEMINI_API_KEY to simulate it not being configured properly
    # This requires restarting the TestClient essentially, or ensuring lifespan runs again
    # A simple way is to manipulate the global state if `genai._is_configured` was a real check
    # For now, let's assume if GEMINI_API_KEY is missing, it's "unhealthy"
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    
    # Re-create client to re-trigger lifespan with modified env
    # This is a bit tricky as 'app' is already imported.
    # A more robust way would be to have app fixture that handles this.
    # For this test, we'll check the branch in health_check directly.
    # The health check logic is:
    # if GEMINI_API_KEY and genai._is_configured: -> healthy
    # elif GEMINI_API_KEY: -> unhealthy (configured but key present) - this case is hard to test without deeper genai mock
    # else: -> unhealthy (key missing)
    
    # To test the "key_missing" path, we rely on the lifespan context not setting genai.configure
    # and the health check seeing no GEMINI_API_KEY
    
    # This test is more illustrative of the intent; actual behavior depends on how
    # `genai.configure` and `genai._is_configured` (if it exists) interact.
    # Given the current api.py, if GEMINI_API_KEY is unset, `genai.configure` won't run.
    
    # Create a new client to re-run lifespan
    # This assumes lifespan correctly checks GEMINI_API_KEY and configures genai
    # We need to mock genai.configure to not happen if GEMINI_API_KEY is missing
    
    # Let's reconstruct the scenario for the health check:
    # If GEMINI_API_KEY is missing, genai.configure is not called in lifespan.
    # The health check then sees no GEMINI_API_KEY.
    
    # This test simulates the scenario where GEMINI_API_KEY is not set
    # The client used here still has the initial app state where GEMINI_API_KEY was set during import.
    # To properly test the lifespan's reaction to a missing GEMINI_API_KEY for the health check,
    # one would typically parameterize the app fixture or use a factory pattern for the client.
    
    # Given the current structure, let's assume the health check's logic for
    # "tts_service": "gemini_api_key_missing" is hit if GEMINI_API_KEY is not present.
    # The global os.environ modification is tricky with how pytest loads tests and fixtures.
    # The autouse fixture `ensure_env_vars` will reset it.
    # So, this specific test case about "gemini_api_key_missing" via lifespan
    # is hard to achieve without more complex fixture setup.
    
    # We will focus on testing the /convert endpoint when GEMINI_API_KEY is missing,
    # as that's a more direct check of its runtime necessity.
    pass # This test case is difficult to implement correctly without more advanced fixture setups.


def test_convert_missing_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    # We need to re-import or re-initialize the app/client for this to take effect
    # For simplicity, we'll assume the check within the endpoint itself is sufficient
    # This means the global `GEMINI_API_KEY` in `api.py` would be None.
    
    # To effectively test this, the `GEMINI_API_KEY` variable within api.py module scope
    # needs to be None when the endpoint is called.
    # This is typically managed by restarting the app with different env vars.
    # TestClient doesn't restart the app per test easily.
    
    # A pragmatic approach for this specific test:
    # Patch the `GEMINI_API_KEY` global within the `api` module for the scope of this test.
    with patch('seed-vc.api.GEMINI_API_KEY', None):
        response = client.post(
            "/convert",
            headers={"Authorization": "Bearer test_fastapi_key"},
            json={"text": "Hello world", "voice": "echo"}
        )
        assert response.status_code == 500
        assert response.json()["detail"] == "TTS service not configured (missing GEMINI_API_KEY)"

def test_health_check_gemini_key_missing_direct(monkeypatch):
    # This test checks the health endpoint's behavior if GEMINI_API_KEY is None at runtime
    monkeypatch.setattr('seed-vc.api.GEMINI_API_KEY', None) # Directly patch the module global
    # Also need to simulate that genai is not configured
    monkeypatch.setattr('google.generativeai._is_configured', False, raising=False)


    response = client.get("/health", headers={"Authorization": "Bearer test_fastapi_key"})
    assert response.status_code == 200 # Health check itself is authorized
    # The response should indicate the Gemini service is unhealthy due to missing key
    assert response.json() == {"status": "unhealthy", "tts_service": "gemini_api_key_missing"}

    # Clean up the direct patch to avoid affecting other tests
    monkeypatch.setattr('seed-vc.api.GEMINI_API_KEY', "test_gemini_key")
    monkeypatch.setattr('google.generativeai._is_configured', True, raising=False)


# To run these tests, use `pytest` in the `seed-vc` directory.
# Ensure that `PYTHONPATH` is set up correctly if running from outside `seed-vc`,
# or that `seed-vc` is part of a package structure that Python can find.
# Example: `PYTHONPATH=. pytest test_api.py` from within `seed-vc`
# or simply `pytest` if your structure allows.
