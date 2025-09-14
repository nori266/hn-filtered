import config
from elevenlabs.client import ElevenLabs
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_audio(text: str) -> tuple[bytes, str]:
    """Generate audio from text using the ElevenLabs API.
    
    Returns:
        tuple[bytes, str]: A tuple containing the audio bytes and the voice ID used.
    """
    if not config.ELEVENLABS_API_KEY:
        logger.error("ElevenLabs API key not found. Please set it in your .env file.")
        return b"", ""

    try:
        client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

        # Using a sample voice ID. This can be changed or made configurable.
        voice_id = "iNwc1Lv2YQLywnCvjfn1"  # A sample voice ID
        audio_stream = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
            voice_settings={"speed": 0.8}
        )

        # Concatenate the audio chunks into a single bytes object
        audio_bytes = b"".join(chunk for chunk in audio_stream)
        return audio_bytes, voice_id

    except Exception as e:
        logger.error(f"Error generating audio from ElevenLabs: {e}")
        return b""
