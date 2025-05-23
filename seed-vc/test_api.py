import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, mock_open

# Set environment variables before importing the app
os.environ["API_KEY"] = "test_fastapi_key"
os.environ["GEMINI_API_KEY"] = "test_gemini_key"
os.environ["SEEDVC_AUDIO_PATH"] = "/tmp/test_generated_audio" # For local storage

# The following are no longer needed for S3
# os.environ["S3_BUCKET"] = "test_bucket"
# os.environ["S3_PREFIX"] = "test_prefix"
# os.environ["AWS_REGION"] = "us-east-1"
# os.environ["AWS_ACCESS_KEY_ID"] = "test_access_key"
# os.environ["AWS_SECRET_ACCESS_KEY"] = "test_secret_key"

from .api import app, TextToSpeechRequest, SUPPORTED_GEMINI_VOICES, LOCAL_AUDIO_PATH

client = TestClient(app)

@pytest.fixture(autouse=True)
def ensure_env_vars_and_setup(monkeypatch):
    # This fixture ensures that for every test, these env vars are set.
    monkeypatch.setenv("API_KEY", "test_fastapi_key")
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key")
    monkeypatch.setenv("SEEDVC_AUDIO_PATH", "/tmp/test_generated_audio")
    
    # Ensure the test audio directory exists and is clean for relevant tests
    # This might be better handled per-test if tests interfere with each other's files
    if os.path.exists(LOCAL_AUDIO_PATH):
        # Simple cleanup: remove the dir and recreate.
        # For more complex scenarios, consider shutil.rmtree or per-test cleanup.
        # For now, just ensure it exists as per lifespan.
        pass
    os.makedirs(LOCAL_AUDIO_PATH, exist_ok=True)


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
@patch('os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('seed-vc.api.genai')
@patch('os.path.exists') # To mock exists check if used in cleanup
@patch('os.remove') # To mock cleanup on error
def test_convert_successful(mock_os_remove, mock_path_exists, mock_genai, mock_file_open, mock_os_makedirs, monkeypatch):
    # Configure mocks
    mock_genai.generate_text_to_speech.return_value.audio_content = b"mock_audio_data"
    
    # Ensure LOCAL_AUDIO_PATH is using the test path for this test
    monkeypatch.setattr('seed-vc.api.LOCAL_AUDIO_PATH', "/tmp/test_generated_audio")
    test_user_id = "user123"
    test_text = "Hello world from test"
    test_voice = "echo"

    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer test_fastapi_key"},
        json={"text": test_text, "voice": test_voice, "user_id": test_user_id}
    )

    assert response.status_code == 200
    data = response.json()
    
    assert "audio_url" in data
    assert data["audio_url"].startswith(f"/audio/{test_user_id}/")
    assert data["audio_url"].endswith(".wav")
    
    assert "local_path" in data
    expected_dir = f"/tmp/test_generated_audio/{test_user_id}"
    mock_os_makedirs.assert_called_with(expected_dir, exist_ok=True)
    
    # Check that the file was opened for writing in the correct path
    # The actual filename is uuid-based, so check parts
    mock_file_open.assert_called_once()
    actual_file_path_opened = mock_file_open.call_args[0][0]
    assert actual_file_path_opened.startswith(expected_dir)
    assert actual_file_path_opened.endswith(".wav")
    
    # Check that audio_bytes were written
    mock_file_open().write.assert_called_once_with(b"mock_audio_data")

    mock_genai.generate_text_to_speech.assert_called_once()
    call_args = mock_genai.generate_text_to_speech.call_args[1]
    assert call_args['text'] == test_text
    assert call_args['voice_name'] == test_voice
    
    # os.remove should not be called in successful case if no temp file is used
    mock_os_remove.assert_not_called()


def test_convert_missing_user_id():
    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer test_fastapi_key"},
        json={"text": "Hello world", "voice": "echo"} # Missing user_id
    )
    assert response.status_code == 422 # FastAPI's default for validation errors
    # Or 400 if we add a specific check and raise HTTPException for missing user_id before Pydantic
    # Current api.py raises HTTPException(status_code=400, detail="user_id is required")
    # So, let's check for 400
    assert response.status_code == 400 
    assert response.json()["detail"] == "user_id is required"


def test_convert_invalid_voice():
    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer test_fastapi_key"},
        json={"text": "Hello world", "voice": "invalid_voice", "user_id": "user123"}
    )
    assert response.status_code == 400
    assert "Target voice not supported" in response.json()["detail"]

def test_convert_unauthorized_missing_key():
    response = client.post(
        "/convert",
        json={"text": "Hello world", "voice": "echo", "user_id": "user123"}
    )
    assert response.status_code == 401

def test_convert_unauthorized_invalid_key():
    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer wrong_key"},
        json={"text": "Hello world", "voice": "echo", "user_id": "user123"}
    )
    assert response.status_code == 401

@patch('seed-vc.api.genai')
def test_convert_gemini_api_error(mock_genai):
    mock_genai.generate_text_to_speech.side_effect = Exception("Gemini API Error")

    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer test_fastapi_key"},
        json={"text": "Hello world", "voice": "echo", "user_id": "user123"}
    )
    assert response.status_code == 500
    # The detail now includes the original exception string
    assert "Gemini TTS generation failed: Gemini API Error" in response.json()["detail"]


@patch('os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('seed-vc.api.genai')
@patch('os.path.exists')
@patch('os.remove')
def test_convert_file_write_error(mock_os_remove, mock_path_exists, mock_genai, mock_file_open, mock_os_makedirs, monkeypatch):
    monkeypatch.setattr('seed-vc.api.LOCAL_AUDIO_PATH', "/tmp/test_generated_audio")
    mock_genai.generate_text_to_speech.return_value.audio_content = b"mock_audio_data"
    mock_file_open.side_effect = IOError("Failed to write file") # Simulate write error
    
    # Simulate that the file might exist before os.remove is called in the except block
    mock_path_exists.return_value = True 

    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer test_fastapi_key"},
        json={"text": "Hello world", "voice": "echo", "user_id": "user123"}
    )
    assert response.status_code == 500
    assert "Error in text to speech conversion: Failed to write file" in response.json()["detail"]
    
    # Check if cleanup was attempted
    mock_os_makedirs.assert_called_once() # Attempted to make directory
    mock_file_open.assert_called_once() # Attempted to open file
    
    # Check if os.remove was called on the path that failed to be written
    # The path is constructed inside the endpoint, so we need to be careful here.
    # For this test, it's enough that os.remove was called.
    # The actual path depends on uuid.uuid4()
    mock_os_remove.assert_called_once() 


@patch('seed-vc.api.genai.configure') # Mock genai.configure for health check tests
def test_health_check_gemini_not_configured(mock_genai_configure, monkeypatch):
    # This test aims to simulate the scenario where GEMINI_API_KEY is provided,
    # but genai.configure might have failed or genai is not properly initialized.
    # The health check has a branch for this:
    # elif GEMINI_API_KEY: return {"status": "unhealthy", "tts_service": "gemini_api_key_present_but_not_fully_configured"}
    
    # We need GEMINI_API_KEY to be set (which it is by ensure_env_vars_and_setup)
    # And we need genai._is_configured to be False (or not exist, and getattr returns False)
    monkeypatch.setattr('google.generativeai._is_configured', False, raising=False) # Simulate not configured

    response = client.get("/health", headers={"Authorization": "Bearer test_fastapi_key"})
    assert response.status_code == 200
    assert response.json() == {"status": "unhealthy", "tts_service": "gemini_api_key_present_but_not_fully_configured"}

    monkeypatch.setattr('google.generativeai._is_configured', True, raising=False) # Reset for other tests


def test_convert_missing_gemini_api_key(monkeypatch):
    # Patch the GEMINI_API_KEY global within the api module for the scope of this test.
    monkeypatch.setattr('seed-vc.api.GEMINI_API_KEY', None)
    
    response = client.post(
        "/convert",
        headers={"Authorization": "Bearer test_fastapi_key"},
        json={"text": "Hello world", "voice": "echo", "user_id": "user123"}
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "TTS service not configured (missing GEMINI_API_KEY)"
    
    # Reset GEMINI_API_KEY for other tests if it was changed directly in the module
    # The ensure_env_vars_and_setup fixture should handle this by resetting env var for next test
    # but direct module patching needs cleanup if not using monkeypatch.undo or similar.
    # monkeypatch.setattr will handle cleanup automatically.


def test_health_check_gemini_key_missing_runtime(monkeypatch):
    # This test checks the health endpoint's behavior if GEMINI_API_KEY is None at runtime
    # It also simulates that genai is not configured as a consequence
    monkeypatch.setattr('seed-vc.api.GEMINI_API_KEY', None) 
    monkeypatch.setattr('google.generativeai._is_configured', False, raising=False) 

    response = client.get("/health", headers={"Authorization": "Bearer test_fastapi_key"})
    assert response.status_code == 200 # Health check itself is authorized
    assert response.json() == {"status": "unhealthy", "tts_service": "gemini_api_key_missing"}

    # monkeypatch automatically cleans up changes to seed-vc.api.GEMINI_API_KEY and google.generativeai._is_configured


# To run these tests, use `pytest` in the `seed-vc` directory.
# Ensure that `PYTHONPATH` is set up correctly if running from outside `seed-vc`,
# or that `seed-vc` is part of a package structure that Python can find.
# Example: `PYTHONPATH=. pytest test_api.py` from within `seed-vc`
# or simply `pytest` if your structure allows.
