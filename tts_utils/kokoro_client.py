import subprocess
import tempfile
import logging
import os
import random

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


all_voices = [
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", 
    "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", 
    "bm_fable", "bm_george", "bm_lewis"
    ]


def generate_audio(text: str) -> tuple[bytes, str]:
    """Generate audio from text using the Kokoro TTS engine.
    
    Returns:
        tuple[bytes, str]: A tuple containing the audio bytes and the voice name used.
    """
    try:
        # Create a temporary file for the input text
        with tempfile.NamedTemporaryFile(mode='w+', suffix=".txt", delete=False) as temp_text_file:
            text_path = temp_text_file.name
            temp_text_file.write(text)
            temp_text_file.flush()

        # Create a temporary file for the output audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
            out_path = temp_audio_file.name

        # Choose a random voice
        voice = random.choice(all_voices)
        
        cmd = [
            "kokoro-tts",
            text_path,  # Pass the text file path
            out_path,
            "--model", "tts_utils/kokoro_model/kokoro-v1.0.onnx",
            "--voices", "tts_utils/kokoro_model/voices-v1.0.bin",
            "--voice", voice,
            "--lang", "en-us",
            "--speed", "0.7",
            "--debug"
        ]

        process = subprocess.run(cmd)

        if process.returncode != 0:
            logger.error(f"Error generating audio from Kokoro TTS: {process.stderr}")
            return b"", ""

        with open(out_path, "rb") as f:
            return f.read(), voice

    except Exception as e:
        logger.error(f"Error generating audio from Kokoro: {e}")
        return b"", ""
    finally:
        # Clean up the temporary files
        if 'text_path' in locals() and os.path.exists(text_path):
            os.remove(text_path)
        if 'out_path' in locals() and os.path.exists(out_path):
            os.remove(out_path)
