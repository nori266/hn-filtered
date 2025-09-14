import subprocess
import tempfile
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os

def generate_audio(text: str) -> bytes:
    """Generate audio from text using the Kokoro TTS engine."""
    try:
        # Create a temporary file for the input text
        with tempfile.NamedTemporaryFile(mode='w+', suffix=".txt", delete=False) as temp_text_file:
            text_path = temp_text_file.name
            temp_text_file.write(text)
            temp_text_file.flush()

        # Create a temporary file for the output audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
            out_path = temp_audio_file.name

        cmd = [
            "kokoro-tts",
            text_path,  # Pass the text file path
            out_path,
            "--model", "tts_utils/kokoro_model/kokoro-v1.0.onnx",
            "--voices", "tts_utils/kokoro_model/voices-v1.0.bin",
            "--voice", "am_liam",
            "--lang", "en-us",
            "--speed", "0.7",
        ]

        process = subprocess.run(cmd)

        if process.returncode != 0:
            logger.error(f"Error generating audio from Kokoro TTS: {process.stderr}")
            return b""

        with open(out_path, "rb") as f:
            audio_bytes = f.read()
        
        return audio_bytes

    except Exception as e:
        logger.error(f"Error generating audio from Kokoro: {e}")
        return b""
    finally:
        # Clean up the temporary files
        if 'text_path' in locals() and os.path.exists(text_path):
            os.remove(text_path)
        if 'out_path' in locals() and os.path.exists(out_path):
            os.remove(out_path)
