import streamlit as st
from news_fetcher import NewsFetcher
from llm_processor import ArticleMatcher
from database import ArticleDatabase
import datetime
from pathlib import Path

# Load default topics from topics.txt if it exists in the project root
TOPICS_FILE = Path(__file__).with_name("topics.txt")
default_topics_text = ""
if TOPICS_FILE.exists():
    default_topics_text = TOPICS_FILE.read_text(encoding="utf-8")

st.title("Hacker News Filter")

# Initialize session state
if 'processed_articles' not in st.session_state:
    st.session_state.processed_articles = []

# File uploader for topics
uploaded_file = st.file_uploader("Or upload a file with topics (one per line)", type=['txt'])

# Text area for user to input topics
user_input = st.text_area("Enter topics of interest (one per line)", height=150, value=default_topics_text)

if st.button("Fetch and Filter News"):
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
    else:
        with st.spinner("Fetching and filtering news..."):
            fetcher = NewsFetcher()
            matcher = ArticleMatcher(input_text=topics_text)
            articles = fetcher.fetch_all_articles()
            st.write(f"Fetched {len(articles)} articles.")
            st.session_state.processed_articles = list(matcher.process_articles(articles))

# Display articles if they exist in session state
if st.session_state.processed_articles:
    st.success(f"Found {len(st.session_state.processed_articles)} relevant articles:")
    for article in st.session_state.processed_articles:
        st.markdown(f"### [{article['title']}]({article['url']})")
        st.write(f"**Source:** {article['source']}")
        st.write(f"**Matched Topics:**")
        for match in article['matches']:
            st.write(f"- {match['question']} ({match['relevance']})")
        st.markdown("---")

    # Prepare markdown content for download
    md_content = ""
    for article in st.session_state.processed_articles:
        md_content += f"- [{article['title']}]({article['url']})\n"
        if article.get('matches'):
            for match in article['matches']:
                md_content += f"  - Matched Topic: {match['question']} ({match['relevance']})\n"
    
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    st.download_button(
        label="Download Links as MD",
        data=md_content,
        file_name=f"hacker_news_links_{today_str}.md",
        mime="text/markdown"
    )
elif st.session_state.get('fetch_clicked_and_no_results', False):
    st.info("No relevant articles found for the given topics.")

