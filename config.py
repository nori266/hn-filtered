import os
from dotenv import load_dotenv

load_dotenv()

# News API configuration
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_BASE_URL = "https://newsapi.org/v2"

# Hacker News API configuration
HN_API_BASE_URL = "https://hacker-news.firebaseio.com/v0"

# LLM Configuration
LLM_TYPE = "gemini"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-1.5-flash-latest"

# News sources
SOURCES = [
    "hacker-news"
]

# Number of articles to fetch per source
MAX_ARTICLES_PER_SOURCE = 50

# Embedding Matcher configuration
EMBEDDING_SIMILARITY_THRESHOLD = 0.7  # Minimum similarity score for initial article filtering
