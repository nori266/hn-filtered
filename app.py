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
            st.session_state.processed_articles = []
            
            results_placeholder = st.empty()

            for article in matcher.process_articles(articles):
                st.session_state.processed_articles.append(article)
                with results_placeholder.container():
                    st.success(f"Found {len(st.session_state.processed_articles)} relevant articles:")
                    for a in st.session_state.processed_articles:
                        st.markdown(f"### [{a['title']}]({a['url']})")
                        st.write(f"**Source:** {a['source']}")
                        st.write(f"**Matched Topics:**")
                        for match in a['matches']:
                            st.write(f"- {match['question']} (LLM: {match['llm_response']})")
                        st.markdown("---")

    # Prepare markdown content for download
    md_content = ""
    if st.session_state.processed_articles:
        md_content = "# Verified Hacker News Links\n\n"
        for article in st.session_state.processed_articles:
            md_content += f"- [{article['title']}]({article['url']})\n"
            if article.get('matches'):
                for match in article['matches']:
                    md_content += f"  - Matched Topic: {match['question']} ({match['relevance']})\n"

    if md_content:
        st.download_button(
            label="Download as Markdown",
            data=md_content,
            file_name=f"hacker_news_links_{datetime.date.today()}.md",
            mime="text/markdown"
        )
elif st.session_state.get('fetch_clicked_and_no_results', False):
    st.info("No relevant articles found for the given topics.")

