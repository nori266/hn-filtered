import tempfile
import logging
import os
import random
import wave
from io import BytesIO

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from piper import PiperVoice
    from piper.voice import SynthesisConfig
    PIPER_AVAILABLE = True
except ImportError:
    logger.warning("piper-tts not installed. Install with: pip install piper-tts")
    PIPER_AVAILABLE = False


# List of English voices (both US and GB variants)
# These need to be downloaded first using: python3 -m piper.download_voices <voice_name>
all_voices = [
    # "en_US-hfc_male-medium",       # Male, clear
    # "en_US-amy-medium",          # Female, clear
    "en_US-ryan-high",          # Male, clear
    # "en_GB-jenny_dioco-medium",    # Female, British accent
    # "en_GB-northern_english_male-medium",    # Male, Northern British accent
]

def generate_audio(text: str) -> tuple[bytes, str]:
    """Generate audio from text using the Piper TTS engine.
    
    Args:
        text: The text to synthesize
        
    Returns:
        tuple[bytes, str]: A tuple containing the audio bytes and the voice name used.
    """
    if not PIPER_AVAILABLE:
        logger.error("Piper TTS is not available. Install with: pip install piper-tts")
        return b"", ""
    
    try:
        # Choose a random voice
        voice_name = random.choice(all_voices)
        
        # Construct the model path
        model_path = os.path.join("tts_utils", "piper_voices", f"{voice_name}.onnx")
        
        # Check if model exists
        if not os.path.exists(model_path):
            logger.error(f"Voice model not found: {model_path}")
            logger.error(f"Download it using: python3 -m piper.download_voices {voice_name}")
            return b"", ""
        
        # Load the voice model
        logger.info(f"Loading voice model: {voice_name}")
        voice = PiperVoice.load(model_path)
        
        # Configure synthesis settings
        # Speed 0.85 means slower, so length_scale should be 1/0.85 ≈ 1.18
        # (length_scale > 1.0 makes speech slower)
        syn_config = SynthesisConfig(
            length_scale=1.18,  # Slower speech (equivalent to speed 0.85)
            noise_scale=0.667,  # Audio variation
            noise_w_scale=0.8,  # Speaking variation
        )
        
        # Create a BytesIO buffer to hold the WAV file
        wav_buffer = BytesIO()
        
        # Synthesize speech to the buffer
        with wave.open(wav_buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)
        
        # Get the audio bytes
        audio_bytes = wav_buffer.getvalue()
        
        logger.info(f"Successfully generated audio with voice: {voice_name}")
        
        return audio_bytes, voice_name
        
    except Exception as e:
        logger.error(f"Error generating audio from Piper: {e}", exc_info=True)
        return b"", ""
