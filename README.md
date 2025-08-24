# Hacker News Filter

This application is a Streamlit web app designed to fetch and filter news articles from Hacker News based on user-defined topics of interest. It uses a two-stage filtering approach combining embedding-based similarity search with Large Language Model (LLM) verification for accurate content filtering, helping users discover relevant articles efficiently.

## How It Works

The application follows a multi-step process to fetch and filter news:

1.  **Topic Input**: The user provides a list of topics of interest. This can be done by typing directly into a text area, uploading a `.txt` file, or using the default `topics.txt` file included in the project.

2.  **News Fetching**: The app fetches the latest top stories from Hacker News API (up to 100 articles by default). The `newspaper3k` library is used to extract the main content from each article's URL when content-based filtering is enabled.

3.  **Two-Stage Filtering Process**: 
   - **Stage 1 - Embedding Matching**: The application performs initial filtering using sentence embeddings. It converts both the user's topics and the article content into numerical vectors (embeddings) and calculates cosine similarity. Articles that meet the similarity threshold (0.7 by default) proceed to the next stage.
   - **Stage 2 - LLM Verification**: Articles that pass initial filtering are sent to an LLM for final verification. The LLM analyzes each article against all matching topics in a single batch request and determines true relevance.

4.  **LLM Support**: The application supports multiple LLM providers:
   - **Groq** (default): Uses Moonshot AI's Kimi-K2-Instruct model via Groq's OpenAI-compatible API
   - **Google Gemini**: Uses Gemini-1.5-flash-latest model
   - **Ollama**: For local LLM deployment

5.  **Real-time Display**: Results are displayed in real-time as articles are processed, showing article title, source, matched topics, and relevance scores. Users can download the filtered results as a Markdown file with matched topics and relevance information.

6.  **Database Persistence**: The application uses a SQLite database (`articles.db`) to store processed articles, preventing reprocessing of the same content and maintaining a history of relevant finds.

## Key Files

-   `app.py`: The main Streamlit application file with real-time UI updates.
-   `config.py`: Contains configuration for API keys, LLM settings, and filtering parameters.
-   `news_fetcher.py`: Handles fetching articles from Hacker News API with content extraction.
-   `llm_processor.py`: Core logic implementing two-stage filtering (embeddings + LLM verification).
-   `database.py`: Manages the SQLite database for article persistence and deduplication.
-   `embedding_matcher.py`: Responsible for sentence embeddings and similarity calculations.
-   `topics.txt`: Default list of topics for filtering.
-   `requirements.txt`: All Python dependencies including Streamlit, sentence-transformers, and LLM clients.

## Setup and Usage

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up environment variables**:
    -   Create a `.env` file in the root of the project.
    -   Add your API keys to the `.env` file. Required keys depend on your chosen LLM provider:
        -   For Groq (default): `GROQ_API_KEY`
        -   For Google Gemini: `GEMINI_API_KEY`
        -   For News API (optional): `NEWS_API_KEY`

4.  **Run the application**:
    ```bash
    streamlit run app.py
    ```

5.  **Use the application**:
    -   Open the provided URL in your browser (typically `http://localhost:8501`).
    -   Enter your topics of interest in the text area or upload a file.
    -   Click the "Fetch and Filter News" button.
    -   Watch as articles are processed in real-time with results appearing immediately.
    -   Download the filtered results as a Markdown file with matched topics and relevance scores.

## Configuration

Key configuration options in `config.py`:

-   **LLM_TYPE**: Choose between "groq" (default), "gemini", or "ollama"
-   **GROQ_MODEL**: Currently set to "moonshotai/kimi-k2-instruct" 
-   **MAX_ARTICLES_PER_SOURCE**: Number of articles to fetch (default: 100)
-   **EMBEDDING_SIMILARITY_THRESHOLD**: Similarity threshold for initial filtering (default: 0.7)
-   **USE_CONTENT_FOR_FILTERING**: Whether to use article content for embedding matching (default: True)
-   **USE_CONTENT_FOR_LLM_FILTERING**: Whether to include content in LLM verification (default: False)
