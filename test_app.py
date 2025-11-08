from pathlib import Path
import subprocess

import streamlit as st
from llm_processor import summarize_article

from tts_utils.piper_client import generate_audio
AUDIO_FORMAT = 'audio/wav'

VOICE_DIR = Path("tts_utils/piper_voices")

if not VOICE_DIR.exists():
    print("Downloading TTS model...")
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Created directory: {VOICE_DIR.absolute()}")
    try:
        result = subprocess.run(
            ["python3", "-m", "piper.download_voices", "en_US-ryan-high"],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(VOICE_DIR)
        )
        print(f"TTS model downloaded successfully: {result.stdout}")
        print(f"TTS model files saved to: {VOICE_DIR.absolute()}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to download TTS model: {e.stderr}")
        raise


# Dummy data mimicking the structure of fetched articles
dummy_articles = [
    {
        'title': 'The future of AI in coding',
        'url': 'https://geohot.github.io//blog/jekyll/update/2025/09/12/ai-coding.html',
        'source': 'geohot blog',
        'matches': [
            {'question': 'Dummy topic', 'llm_response': 'Dummy response'}
        ]
    },
    {
        'title': 'AI benchmarks are a bad joke – and LLM makers are the ones laughing',
        'url': 'https://www.theregister.com/2025/11/07/measuring_ai_models_hampered_by/',
        'source': 'theregister',
        'matches': [
            {'question': 'What are some tips for a balanced diet?', 'llm_response': 'The article provides a comprehensive guide to nutrition and meal planning.'}
        ]
    },
    {
        'title': 'Dummy Article 3: Traveling the World on a Budget',
        'url': 'https://example.com/article3',
        'source': 'Nomadic Matt',
        'matches': [
            {'question': 'How can I travel without breaking the bank?', 'llm_response': 'The article shares practical tips for budget-friendly travel.'}
        ]
    }
]



st.title("Test App for Widgets")

# Initialize session state
if 'summaries' not in st.session_state:
    st.session_state.summaries = {}
if 'audio' not in st.session_state:
    st.session_state.audio = {}
if 'audio_summaries' not in st.session_state:
    st.session_state.audio_summaries = {}
if 'voice_info' not in st.session_state:
    st.session_state.voice_info = {}

# Display dummy articles and widgets
st.success(f"Found {len(dummy_articles)} relevant articles:")
for a in dummy_articles:
    st.markdown(f"### [{a['title']}]({a['url']})")
    st.write(f"**Source:** {a['source']}")
    st.write(f"**Matched Topics:**")
    for match in a['matches']:
        st.write(f"- {match['question']} (LLM: {match['llm_response']})")

    # Create columns for buttons to display them side by side
    col1, col2 = st.columns(2)
    
    # Summarize button (first column)
    with col1:
        if st.button("Summarize", key=f"summarize_{a['url']}"):
            with st.spinner("Generating summary..."):
                summary = summarize_article(a['url'])
                st.session_state.summaries[a['url']] = summary
                st.rerun()
    
    # Play Audio button (second column) - always visible
    with col2:
        if st.button("Play Audio", key=f"play_{a['url']}"):
            with st.spinner("Generating podcast-style summary..."):
                # Generate a new summary in podcast format
                audio_summary = summarize_article(a['url'], audio_format=True)
                st.session_state.audio_summaries[a['url']] = audio_summary
                
                # Generate and store the audio and voice info
                audio_bytes, voice = generate_audio(audio_summary)
                if audio_bytes:
                    st.session_state.audio[a['url']] = audio_bytes
                    st.session_state.voice_info[a['url']] = voice
                else:
                    st.error("Could not generate audio.")
                st.rerun()

    # Display the regular summary if it exists
    if a['url'] in st.session_state.summaries:
        with st.expander("View Summary"):
            st.markdown(st.session_state.summaries[a['url']])
    
    # Display the audio player if audio is available
    if a['url'] in st.session_state.audio:
        st.audio(st.session_state.audio[a['url']], format=AUDIO_FORMAT)
        
        # Add a collapsible section for the podcast summary text
        with st.expander("Show Podcast Text"):
            if a['url'] in st.session_state.voice_info:
                st.write(f"**Voice used:** {st.session_state.voice_info[a['url']]}")
            if a['url'] in st.session_state.audio_summaries:
                st.write(st.session_state.audio_summaries[a['url']])
            else:
                st.write("No podcast text available.")

    st.markdown("---")
