import logging
import os
import uuid
from contextlib import asynccontextmanager
from tempfile import NamedTemporaryFile

import boto3
import torchaudio
import google.generativeai as genai
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
API_KEY = os.getenv("API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


async def verify_api_key(authorization: str = Header(None)):
    if not authorization:
        logger.warning("No API key provided")
        raise HTTPException(status_code=401, detail="API key is missing")

    if authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
    else:
        token = authorization

    if token != API_KEY:
        logger.warning("Invalid API key provided")
        raise HTTPException(status_code=401, detail="Invalid API key")

    return token


def get_s3_client():
    client_kwargs = {'region_name': os.getenv("AWS_REGION", "us-east-1")}

    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        client_kwargs.update({
            'aws_access_key_id': os.getenv("AWS_ACCESS_KEY_ID"),
            'aws_secret_access_key': os.getenv("AWS_SECRET_ACCESS_KEY")
        })

    return boto3.client('s3', **client_kwargs)


s3_client = get_s3_client()

S3_PREFIX = os.getenv("S3_PREFIX", "seedvc-outputs")
S3_BUCKET = os.getenv("S3_BUCKET", "elevenlabs-clone")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Seed-VC API")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        logger.warning("GEMINI_API_KEY not found. TTS functionality will not work.")
    yield
    logger.info("Shutting down Seed-VC API")

app = FastAPI(title="Seed-VC API",
              lifespan=lifespan)

SUPPORTED_GEMINI_VOICES = ["echo", "alloy", "fable", "onyx", "nova", "shimmer"]


class TextToSpeechRequest(BaseModel):
    text: str
    voice: str


async def generate_gemini_tts(text: str, voice: str) -> bytes:
    """Generates speech from text using Gemini TTS and returns audio bytes."""
    try:
        logger.info(f"Generating TTS for text: '{text[:30]}...' with voice: {voice}")
        # Note: The actual API call might differ. This is a placeholder based on common patterns.
        # You'll need to replace this with the correct SDK usage for Gemini TTS.
        # For example, it might be something like:
        # response = genai.generate_text_to_speech(model="gemini-2.5-flash-preview-tts", text=text, voice_settings={"name": voice})
        # audio_content = response.audio_content
        
        # Placeholder for actual Gemini API call
        # This is a simulated audio output for now.
        # Replace with actual API call to `gemini-2.5-flash-preview-tts`
        tts_model_name = "models/tts-004" # Example model, adjust if specific for 2.5-flash
        if voice not in SUPPORTED_GEMINI_VOICES: # Basic validation
            raise ValueError(f"Voice '{voice}' is not supported by Gemini TTS in this application.")

        response = genai.generate_text_to_speech(
            model=tts_model_name, # Or the specific identifier for gemini-2.5-flash-preview-tts
            text=text,
            voice_name=voice, # Parameter might be different, e.g., voice_settings={"name": voice}
            # output_format="wav" # Assuming WAV output, check API docs
        )
        # Assuming response.audio_content contains the audio bytes
        if hasattr(response, 'audio_content'):
            audio_bytes = response.audio_content
        else:
            # This is a fallback if the structure is different or if it returns a filepath
            # For example, if it saves to a file and returns the path:
            # with open(response.audio_file_path, "rb") as f:
            #     audio_bytes = f.read()
            # os.remove(response.audio_file_path) # Clean up temp file
            raise NotImplementedError("Actual Gemini TTS response handling needs to be implemented based on SDK.")

        logger.info(f"Successfully generated TTS audio bytes using voice {voice}")
        return audio_bytes

    except Exception as e:
        logger.error(f"Error generating Gemini TTS: {e}")
        raise


@app.post("/convert", dependencies=[Depends(verify_api_key)])
async def text_to_speech(request: TextToSpeechRequest, background_tasks: BackgroundTasks):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="TTS service not configured (missing GEMINI_API_KEY)")

    if request.voice not in SUPPORTED_GEMINI_VOICES:
        raise HTTPException(
            status_code=400, detail=f"Target voice not supported. Choose from: {', '.join(SUPPORTED_GEMINI_VOICES)}")

    try:
        logger.info(
            f"Generating speech for text: '{request.text[:30]}...' with voice: {request.voice}")

        audio_bytes = await generate_gemini_tts(text=request.text, voice=request.voice)

        audio_id = str(uuid.uuid4())
        # Gemini might return MP3 or other formats, ensure WAV for torchaudio or handle format directly
        # For now, assuming WAV or a format torchaudio can handle if direct byte saving is an issue.
        # If Gemini returns WAV directly, we might not need torchaudio.save if we can upload bytes.
        output_filename = f"{audio_id}.wav" # Consider changing to .mp3 if Gemini outputs mp3
        local_path = f"/tmp/{output_filename}"

        # Save audio bytes to a temporary file
        with open(local_path, "wb") as f:
            f.write(audio_bytes)
        
        # If torchaudio is strictly for WAV and Gemini provides WAV, this step might be redundant
        # or could be used for format validation/conversion if needed.
        # For now, we assume audio_bytes are directly writable as a WAV file or compatible.

        # Upload to S3
        s3_key = f"{S3_PREFIX}/{output_filename}"
        s3_client.upload_file(local_path, S3_BUCKET, s3_key)

        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': s3_key},
            ExpiresIn=3600
        )

        background_tasks.add_task(os.remove, local_path)

        return {
            "audio_url": presigned_url,
            "s3_key": s3_key
        }
    except Exception as e:
        logger.error(f"Error in voice conversion: {e}")
        raise HTTPException(
            status_code=500, detail="Error in voice conversion")


@app.get("/voices", dependencies=[Depends(verify_api_key)])
async def list_voices():
    return {"voices": SUPPORTED_GEMINI_VOICES}


@app.get("/health", dependencies=[Depends(verify_api_key)])
async def health_check():
    # Updated health check: Check if Gemini API key is present
    if GEMINI_API_KEY and genai._is_configured:
        # Could add a simple test call to Gemini here if needed
        return {"status": "healthy", "tts_service": "gemini_configured"}
    elif GEMINI_API_KEY:
        return {"status": "unhealthy", "tts_service": "gemini_api_key_present_but_not_configured"}
    else:
        return {"status": "unhealthy", "tts_service": "gemini_api_key_missing"}
