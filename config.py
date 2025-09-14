import os
from dotenv import load_dotenv

load_dotenv()

# News API configuration
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_BASE_URL = "https://newsapi.org/v2"

# Hacker News API configuration
HN_API_BASE_URL = "https://hacker-news.firebaseio.com/v0"

# LLM Configuration
# Supported values: "groq", "gemini", "ollama"
LLM_TYPE = "groq"  # Using Groq's Llama-3.3-70B-versatile model by default

# Groq (OpenAI-compatible) configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "moonshotai/kimi-k2-instruct"

# TTS Configuration
# Supported values: "kokoro", "elevenlabs"
TTS_PROVIDER = "kokoro"

# ElevenLabs configuration
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Gemini configuration (kept for backward compatibility)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-1.5-flash-latest"

# News sources
SOURCES = [
    "hacker-news"
]

# Number of articles to fetch per source
MAX_ARTICLES_PER_SOURCE = 100

# Embedding Matcher configuration
EMBEDDING_SIMILARITY_THRESHOLD = 0.7  # Minimum similarity score for initial article filtering
USE_CONTENT_FOR_FILTERING = True # Whether to use article content for filtering
USE_CONTENT_FOR_LLM_FILTERING = False # Whether to use article content for LLM filtering
