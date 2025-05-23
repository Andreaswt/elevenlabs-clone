import logging
import os
import uuid
from contextlib import asynccontextmanager
# from tempfile import NamedTemporaryFile # Not needed for direct byte saving

# import boto3 # Removed
# import torchaudio # Keep if saving .wav from raw PCM, remove if Gemini provides encoded audio directly
import google.generativeai as genai
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles # Added
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
API_KEY = os.getenv("API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Default local path, configurable via environment variable
LOCAL_AUDIO_PATH = os.getenv("SEEDVC_AUDIO_PATH", "/app/generated_audio")


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

# Removed get_s3_client, s3_client, S3_PREFIX, S3_BUCKET

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Seed-VC API")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini API configured.")
    else:
        logger.warning("GEMINI_API_KEY not found. TTS functionality will not work.")
    
    # Ensure the base audio directory exists
    os.makedirs(LOCAL_AUDIO_PATH, exist_ok=True)
    logger.info(f"Local audio storage path: {LOCAL_AUDIO_PATH}")
    
    yield
    logger.info("Shutting down Seed-VC API")

app = FastAPI(title="Seed-VC API",
              lifespan=lifespan)

# Mount static files directory
# This will serve files from LOCAL_AUDIO_PATH under the /audio URL path
# e.g., a file at LOCAL_AUDIO_PATH/user123/audio.wav will be accessible via /audio/user123/audio.wav
app.mount("/audio", StaticFiles(directory=LOCAL_AUDIO_PATH), name="audio_files")


SUPPORTED_GEMINI_VOICES = ["echo", "alloy", "fable", "onyx", "nova", "shimmer"]


class TextToSpeechRequest(BaseModel):
    text: str
    voice: str
    user_id: str # Added user_id


async def generate_gemini_tts(text: str, voice: str) -> bytes:
    """Generates speech from text using Gemini TTS and returns audio bytes (assumed to be encoded, e.g., MP3 or WAV)."""
    try:
        logger.info(f"Generating TTS for text: '{text[:30]}...' with voice: {voice}")
        # Note: The actual API call might differ. This is a placeholder based on common patterns.
        # You'll need to replace this with the correct SDK usage for Gemini TTS.
        # For example, it might be something like:
        # response = genai.generate_text_to_speech(model="gemini-2.5-flash-preview-tts", text=text, voice_settings={"name": voice})
        # audio_content = response.audio_content
        
        # Placeholder for actual Gemini API call.
        # Assuming Gemini's `generate_text_to_speech` returns an object with `audio_content`
        # which are the bytes of an already encoded audio file (e.g., MP3 or WAV).
        tts_model_name = "models/tts-004" # Or "models/gemini-2.5-flash-preview-tts" if available and compatible
        if voice not in SUPPORTED_GEMINI_VOICES:
            raise ValueError(f"Voice '{voice}' is not supported.")

        response = genai.generate_text_to_speech(
            model=tts_model_name,
            text=text,
            voice_name=voice,
            # output_format="wav" # If API supports specifying, otherwise determine from response
        )
        
        if not hasattr(response, 'audio_content'):
            raise NotImplementedError("Gemini TTS response structure changed or audio_content missing.")
            
        audio_bytes = response.audio_content
        logger.info(f"Successfully generated TTS audio bytes using voice {voice}")
        return audio_bytes

    except Exception as e:
        logger.error(f"Error generating Gemini TTS: {e}")
        # Consider more specific error handling or re-raising if needed by caller
        raise Exception(f"Gemini TTS generation failed: {str(e)}")


@app.post("/convert", dependencies=[Depends(verify_api_key)])
async def text_to_speech(request: TextToSpeechRequest, background_tasks: BackgroundTasks):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="TTS service not configured (missing GEMINI_API_KEY)")

    if request.voice not in SUPPORTED_GEMINI_VOICES:
        raise HTTPException(
            status_code=400, detail=f"Target voice not supported. Choose from: {', '.join(SUPPORTED_GEMINI_VOICES)}")

    if not request.user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        logger.info(
            f"Generating speech for text: '{request.text[:30]}...' with voice: {request.voice} for user: {request.user_id}")

        audio_bytes = await generate_gemini_tts(text=request.text, voice=request.voice)

        audio_id = str(uuid.uuid4())
        # Assuming Gemini returns WAV bytes or MP3. For now, save as .wav.
        # If Gemini directly provides MP3, filename should be .mp3 and content-type accordingly.
        output_filename = f"{audio_id}.wav" 
        
        user_audio_dir = os.path.join(LOCAL_AUDIO_PATH, request.user_id)
        os.makedirs(user_audio_dir, exist_ok=True)
        
        full_path = os.path.join(user_audio_dir, output_filename)

        # Save audio bytes directly to file
        with open(full_path, "wb") as f:
            f.write(audio_bytes)
        
        logger.info(f"Audio file saved locally at: {full_path}")

        # The URL path should correspond to how StaticFiles serves it
        # If LOCAL_AUDIO_PATH is "/app/generated_audio" and mounted at "/audio",
        # then a file at "/app/generated_audio/user123/file.wav" is served at "/audio/user123/file.wav"
        audio_url_path = f"/audio/{request.user_id}/{output_filename}"
        
        # No temporary file to remove with background tasks if writing directly

        return {
            "audio_url": audio_url_path, # This is now a relative path for the client
            "local_path": full_path # For potential internal use, e.g., Inngest function
        }
    except Exception as e:
        logger.error(f"Error in text to speech conversion: {e}")
        # Clean up partially created file if error occurs after file creation attempt
        if 'full_path' in locals() and os.path.exists(full_path):
            try:
                os.remove(full_path)
                logger.info(f"Cleaned up partially created file: {full_path}")
            except OSError:
                logger.error(f"Error cleaning up file: {full_path}")
        raise HTTPException(
            status_code=500, detail=f"Error in text to speech conversion: {str(e)}")


@app.get("/voices", dependencies=[Depends(verify_api_key)])
async def list_voices():
    return {"voices": SUPPORTED_GEMINI_VOICES}


@app.get("/health", dependencies=[Depends(verify_api_key)])
async def health_check():
    # Updated health check: Check if Gemini API key is present and genai is configured
    # The genai._is_configured check might be internal to the library.
    # A more robust check would be to see if genai.configure() was called successfully,
    # or if GEMINI_API_KEY is present, assume configuration attempt was made.
    if GEMINI_API_KEY and getattr(genai, '_is_configured', True): # Fallback if _is_configured doesn't exist
        # Ideally, a light test call to Gemini, or a flag set during lifespan if configure() succeeds
        return {"status": "healthy", "tts_service": "gemini_configured"}
    elif GEMINI_API_KEY: # Key is present, but genai might not be configured (e.g. bad key)
        return {"status": "unhealthy", "tts_service": "gemini_api_key_present_but_not_fully_configured"}
    else: # Key is missing
        return {"status": "unhealthy", "tts_service": "gemini_api_key_missing"}
