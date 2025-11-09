import streamlit as st
import psutil
import os
import logging
import threading
import time
import re
from news_fetcher import NewsFetcher
from llm_processor import ArticleMatcher, summarize_article
from tts_utils.piper_client import generate_audio
from pathlib import Path

def log_mem():
    while True:
        rss_mb = psutil.Process(os.getpid()).memory_info().rss / (1024**2)
        logging.info("process_rss_mb=%.1f", rss_mb)
        time.sleep(30)

# Start memory logging in a daemon thread
memory_thread = threading.Thread(target=log_mem, daemon=True)
memory_thread.start()

AUDIO_FORMAT = 'audio/wav'
AUDIO_EXTENSION = 'wav'

# Load default topics from topics.txt if it exists in the project root
TOPICS_FILE = Path(__file__).with_name("topics.txt")
default_topics_text = ""
if TOPICS_FILE.exists():
    default_topics_text = TOPICS_FILE.read_text(encoding="utf-8")

def sanitize_filename(title, max_length=50):
    """
    Sanitize article title to create a valid filename
    """
    # Remove or replace invalid characters for filenames
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', title)
    # Replace multiple spaces/underscores with single underscore
    sanitized = re.sub(r'[_\s]+', '_', sanitized)
    # Remove leading/trailing underscores and spaces
    sanitized = sanitized.strip('_ ')
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip('_')
    return sanitized if sanitized else "hn_article"

def escape_markdown(text: str) -> str:
    """
    Escape special Markdown characters for display
    """
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)

st.title("Hacker News Filter")

# Initialize session state
if 'processed_articles' not in st.session_state:
    st.session_state.processed_articles = []
if 'summaries' not in st.session_state:
    st.session_state.summaries = {}
if 'audio' not in st.session_state:
    st.session_state.audio = {}
if 'audio_summaries' not in st.session_state:
    st.session_state.audio_summaries = {}
if 'voice_info' not in st.session_state:
    st.session_state.voice_info = {}
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'article_count' not in st.session_state:
    st.session_state.article_count = 0

# File uploader for topics
uploaded_file = st.file_uploader("Or upload a file with topics (one per line)", type=['txt'])

# Text area for user to input topics
user_input = st.text_area("Enter topics of interest (one per line)", height=150, value=default_topics_text)

if 'fetch_clicked' not in st.session_state:
    st.session_state.fetch_clicked = False

# Handle the fetch button click
if st.button("Fetch and Filter News"):
    st.session_state.fetch_clicked = True
    st.session_state.processing_complete = False
    st.session_state.article_count = 0
    topics_text = ""
    if uploaded_file is not None:
        topics_text = uploaded_file.read().decode("utf-8")
    elif user_input.strip():
        topics_text = user_input
    elif default_topics_text.strip():
        topics_text = default_topics_text

    if not topics_text.strip():
        st.warning("Please enter at least one topic or upload a file.")
        st.session_state.processed_articles = []
        st.session_state.processing_complete = True
    else:
        # Create a placeholder for status updates
        status_placeholder = st.empty()
        status_placeholder.info("🔄 Fetching and filtering news... This may take a moment.")
        
        # Create a container for progressive article display
        articles_container = st.container()
        
        try:
            fetcher = NewsFetcher()
            matcher = ArticleMatcher(input_text=topics_text)
            articles = fetcher.fetch_all_articles()
            
            # Process articles progressively
            processed_urls = set()
            st.session_state.processed_articles = []  # Clear previous results
            st.session_state.summaries = {}  # Clear previous summaries
            st.session_state.audio = {}  # Clear previous audio
            st.session_state.audio_summaries = {}  # Clear previous audio summaries
            st.session_state.voice_info = {}  # Clear previous voice info
            
            for article in matcher.process_articles(articles):
                if article['url'] not in processed_urls and article.get('matches'):
                    st.session_state.processed_articles.append(article)
                    processed_urls.add(article['url'])
                    st.session_state.article_count += 1
                    
                    # Cache the summary if it was generated during filtering
                    if 'summary' in article and article['summary']:
                        st.session_state.summaries[article['url']] = article['summary']
                        logging.info(f"Cached summary for article: {article['title']}")
                    
                    # Update status
                    status_placeholder.info(f"🔄 Processing articles... Found {st.session_state.article_count} relevant article{'s' if st.session_state.article_count != 1 else ''} so far...")
            
            # Mark processing as complete
            st.session_state.processing_complete = True
            
            # Final status update
            if st.session_state.article_count > 0:
                status_placeholder.success(f"✅ Processing complete! Found {st.session_state.article_count} relevant article{'s' if st.session_state.article_count != 1 else ''} matching your topics.")
            else:
                status_placeholder.info("🔍 Processing complete! No relevant articles found for your topics. Try adjusting your topic list.")
                
        except Exception as e:
            logging.error(f"Error fetching articles: {str(e)}")
            status_placeholder.error(f"❌ Error fetching articles: {str(e)}")
            st.session_state.processing_complete = True
        
        st.rerun()

# Display results if we have any
if st.session_state.fetch_clicked:
    if st.session_state.processed_articles:
        st.success(f"Found {len(st.session_state.processed_articles)} relevant articles:")
        
        # Display each article
        for idx, a in enumerate(st.session_state.processed_articles):
            with st.container():
                st.markdown(f"### [{a['title']}]({a['url']})")
                st.write(f"**Source:** {a['source']}")
                # Show comment count for Hacker News articles
                if a['source'] == 'hacker-news' and 'hn_comments' in a:
                    comment_count = a['hn_comments']
                    comment_text = "comment" if comment_count == 1 else "comments"
                    st.write(f"**Comments:** {comment_count} {comment_text}")
                st.write(f"**Matched Topics:**")
                for match in a['matches']:
                    st.write(f"- {match['question']} (LLM: {match['llm_response']})")

            # Create columns for buttons to display them side by side
            col1, col2, col3 = st.columns(3)
            
            # Use a unique key based on the index and URL
            button_key = f"summarize_{idx}_{a['url'][:50]}"
            
            # Summarize button (first column)
            with col1:
                if st.button("Summarize", key=button_key):
                    # Check if summary already exists (cached)
                    if a['url'] not in st.session_state.summaries:
                        with st.spinner("Generating summary..."):
                            try:
                                summary = summarize_article(a['url'])
                                st.session_state.summaries[a['url']] = summary
                            except Exception as e:
                                logging.error(f"Error generating summary: {str(e)}")
                                st.error(f"❌ Error generating summary: {str(e)}")
                    st.rerun()
            
            # Play Audio button (second column)
            with col2:
                audio_key = f"play_{idx}_{a['url'][:50]}"
                if st.button("Play Audio", key=audio_key):
                    # Check if audio already exists
                    if a['url'] not in st.session_state.audio:
                        with st.spinner("Generating podcast-style summary and audio..."):
                            try:
                                # Generate a new summary in podcast format
                                audio_summary = summarize_article(a['url'], audio_format=True)
                                st.session_state.audio_summaries[a['url']] = audio_summary
                                
                                # Generate and store the audio and voice info
                                audio_bytes, voice = generate_audio(audio_summary)
                                if audio_bytes:
                                    st.session_state.audio[a['url']] = audio_bytes
                                    st.session_state.voice_info[a['url']] = voice
                                else:
                                    st.error("❌ Could not generate audio.")
                            except Exception as e:
                                logging.error(f"Error generating audio: {str(e)}")
                                st.error(f"❌ Error generating audio: {str(e)}")
                    st.rerun()
            with col3:
                if st.button("View Discussion", key=f"view_discussion_{idx}_{a['url'][:50]}") and a['source'] == 'hacker-news':
                    st.session_state.view_clicked = True
                    st.session_state.view_url = a['hn_discussion_url']
                    st.rerun()

            # Display the regular summary if it exists
            if a['url'] in st.session_state.summaries:
                with st.expander("View Summary"):
                    st.markdown(st.session_state.summaries[a['url']])
            
            # Display the audio player if audio is available
            if a['url'] in st.session_state.audio:
                st.audio(st.session_state.audio[a['url']], format=AUDIO_FORMAT)
                
                # Add download button for the audio
                filename = f"{sanitize_filename(a['title'])}.{AUDIO_EXTENSION}"
                mime_type = AUDIO_FORMAT
                
                st.download_button(
                    label="Download Audio",
                    data=st.session_state.audio[a['url']],
                    file_name=filename,
                    mime=mime_type,
                    key=f"download_audio_{idx}_{a['url'][:50]}"
                )
                
                # Add a collapsible section for the podcast summary text
                with st.expander("Show Podcast Text"):
                    if a['url'] in st.session_state.voice_info:
                        st.write(f"**Voice used:** {st.session_state.voice_info[a['url']]}")
                    if a['url'] in st.session_state.audio_summaries:
                        st.write(st.session_state.audio_summaries[a['url']])
                    else:
                        st.write("No podcast text available.")

            st.markdown("---")

if not st.session_state.processed_articles and st.session_state.fetch_clicked and st.session_state.processing_complete:
    st.info("No relevant articles found for the given topics.")
