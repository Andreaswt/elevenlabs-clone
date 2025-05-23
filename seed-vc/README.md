# Seed-VC - Gemini Text-to-Speech (TTS) Service

This service provides a Text-to-Speech (TTS) API endpoint that leverages Google's Gemini API (specifically, a model like `models/tts-004` or the intended `gemini-2.5-flash-preview-tts`) to generate speech from text.

It is designed to be a backend component for applications requiring TTS capabilities.

## Key Features
*   **Text-to-Speech Conversion**: Converts input text into spoken audio.
*   **Gemini Powered**: Utilizes Google's Generative AI models for high-quality speech synthesis.
*   **Simple API**: Offers a straightforward API endpoint for TTS requests.
*   **S3 Integration**: Uploads generated audio files to an AWS S3 bucket and returns a presigned URL.

## Installation & Setup

1.  **Clone the repository (if part of a larger project, this step might be done already):**
    ```bash
    # git clone ...
    cd seed-vc
    ```

2.  **Install dependencies:**
    Python 3.10 or higher is recommended.
    ```bash
    pip install -r requirements.txt
    ```
    (Ensure `requirements.txt` includes `google-generativeai`, `fastapi`, `uvicorn`, `boto3`, `python-dotenv`, etc.)

3.  **Environment Variables:**
    Create a `.env` file in the `seed-vc` directory with the following variables:

    ```env
    # FastAPI Backend API Key (used to secure the /convert endpoint)
    API_KEY="your_strong_backend_api_key"

    # Gemini API Key (for authenticating with Google's Generative AI services)
    GEMINI_API_KEY="your_google_gemini_api_key"

    # AWS S3 Configuration (for storing generated audio)
    AWS_REGION="your_aws_s3_bucket_region" # e.g., us-east-1
    AWS_ACCESS_KEY_ID="your_aws_access_key_id"
    AWS_SECRET_ACCESS_KEY="your_aws_secret_access_key"
    S3_BUCKET="your_s3_bucket_name"
    S3_PREFIX="seedvc-outputs" # Optional: prefix for S3 keys
    ```

    *   `API_KEY`: A secret key you define. Client applications (like `elevenlabs-clone-frontend`) must send this key in the `Authorization` header to use the API.
    *   `GEMINI_API_KEY`: **This is crucial.** You need to obtain this key from Google AI Studio or your Google Cloud project that has the Generative Language API enabled.
    *   AWS credentials are required for uploading the generated audio to S3.

## Usage

1.  **Run the FastAPI application:**
    ```bash
    uvicorn api:app --host 0.0.0.0 --port 8000
    ```
    (Or your preferred port. Ensure the port matches `SEED_VC_API_ROUTE` in the frontend's `.env` if applicable.)

2.  **API Endpoint:**
    The service exposes the following endpoint:
    *   `POST /convert`
        *   **Purpose**: Converts text to speech.
        *   **Headers**:
            *   `Authorization: Bearer <your_API_KEY>` (where `<your_API_KEY>` is the value from your `.env` file).
        *   **Request Body (JSON)**:
            ```json
            {
              "text": "Hello, this is a test of the Gemini Text-to-Speech service.",
              "voice": "echo" 
            }
            ```
            Supported voices (from `SUPPORTED_GEMINI_VOICES` in `api.py`): "echo", "alloy", "fable", "onyx", "nova", "shimmer".
        *   **Response (JSON)**:
            ```json
            {
              "audio_url": "presigned_s3_url_to_audio.wav",
              "s3_key": "s3_key_of_the_audio.wav"
            }
            ```

    *   `GET /voices`
        *   **Purpose**: Lists available voices.
        *   **Headers**:
            *   `Authorization: Bearer <your_API_KEY>`
        *   **Response (JSON)**:
            ```json
            {
              "voices": ["echo", "alloy", "fable", "onyx", "nova", "shimmer"]
            }
            ```
            
    *   `GET /health`
        *   **Purpose**: Health check for the service.
        *   **Headers**:
            *   `Authorization: Bearer <your_API_KEY>`

## Important Notes
*   **Gemini API Key**: The `GEMINI_API_KEY` is essential. Without it, the TTS generation will fail. Ensure it's correctly set in your environment or `.env` file.
*   **Model Used**: The service is configured to use a Gemini TTS model (e.g., `models/tts-004`). Refer to Google's documentation for the latest model identifiers and capabilities.
*   **Error Handling**: The API includes basic error handling for missing API keys, invalid voice selections, and issues during TTS generation or S3 upload.

This service is no longer a voice conversion tool but a dedicated Text-to-Speech provider using Google Gemini.
The previous voice conversion models, command-line tools for voice conversion, and training scripts are not applicable to this version of the service.
