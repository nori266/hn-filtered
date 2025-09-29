# Hacker News Telegram Bot

A Telegram bot that provides the same functionality as the Streamlit app (`app.py`) for filtering and summarizing Hacker News articles based on your interests.

## Features

- 🔍 **Smart Filtering**: Filter Hacker News articles based on your topics of interest
- 📄 **AI Summaries**: Generate concise summaries of articles using LLM
- 🎵 **Podcast Audio**: Create podcast-style audio summaries with TTS
- 📱 **Mobile-Friendly**: Works seamlessly on mobile devices through Telegram
- 👥 **Multi-User**: Supports multiple users with individual topic preferences
- 📁 **File Upload**: Upload topic files for easy configuration

## Setup Instructions

### 1. Prerequisites

- Python environment with all dependencies from `requirements.txt`
- All existing configuration (API keys for LLM and TTS providers)
- Telegram bot token

### 2. Create Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Copy the bot token you receive

### 3. Configure Environment

Add your Telegram bot token to your `.env` file:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 4. Run the Bot

```bash
python telegram_bot.py
```

The bot will start polling for messages and be ready to use!

## Usage Guide

### Getting Started

1. Start a chat with your bot on Telegram
2. Send `/start` to see the welcome message
3. Use `/topics` to set your topics of interest
4. Send `/fetch` to get filtered articles

### Available Commands

- `/start` - Welcome message and basic instructions
- `/topics` - View current topics or set new ones
- `/fetch` - Fetch and filter Hacker News articles
- `/help` - Detailed help and usage information

### Setting Topics

You can set topics in two ways:

1. **Text Message**: Send a message with your topics (one per line)
   ```
   AI agents
   machine learning
   python programming
   ```

2. **File Upload**: Upload a `.txt` file with topics (one per line)

### Interacting with Articles

Once you fetch articles, each article will have buttons:

- **📄 Summarize** - Generate an AI summary of the article
- **🎵 Audio** - Create a podcast-style audio summary
- **🔗 View Article** - Open the original article in browser

## Technical Details

### Architecture

The bot reuses all existing components:
- `news_fetcher.py` - Article fetching from Hacker News
- `llm_processor.py` - Article matching and summarization
- TTS utilities - Audio generation (ElevenLabs/Kokoro)
- `config.py` - All existing configuration settings

### User Data Storage

- **Topics**: Stored per user in memory
- **Articles**: Cached per user session
- **Summaries**: Cached to avoid regeneration
- **Audio**: Cached to avoid regeneration

### Error Handling

- Graceful error messages for users
- Detailed logging for debugging
- Retry mechanisms for API calls
- Input validation for files and text

## Configuration

The bot uses the same configuration as the Streamlit app:

- **LLM Provider**: Groq/Gemini (from `config.LLM_TYPE`)
- **TTS Provider**: ElevenLabs/Kokoro (from `config.TTS_PROVIDER`)
- **Article Limits**: Same as web app (from `config.MAX_ARTICLES_PER_SOURCE`)

## Troubleshooting

### Bot Not Responding
- Check if `TELEGRAM_BOT_TOKEN` is set correctly
- Ensure the bot is running (`python telegram_bot.py`)
- Check logs for error messages

### API Errors
- Verify your LLM API keys (Groq/Gemini)
- Check TTS API keys (ElevenLabs if configured)
- Monitor API rate limits in logs

### No Articles Found
- Review your topics - they might be too specific
- Check if Hacker News API is accessible
- Verify your topics match article content

### Audio Generation Issues
- Ensure TTS provider is configured correctly
- Check TTS API keys and quotas
- Review TTS provider logs for specific errors

## Comparison with Streamlit App

| Feature | Streamlit App | Telegram Bot |
|---------|---------------|--------------|
| Article Filtering | ✅ | ✅ |
| AI Summaries | ✅ | ✅ |
| Audio Generation | ✅ | ✅ |
| Topic Management | ✅ | ✅ |
| File Upload | ✅ | ✅ |
| Multi-User Support | ❌ | ✅ |
| Mobile-Friendly | Limited | ✅ |
| Always Available | Server Required | ✅ |
| Push Notifications | ❌ | Possible |

## Development Notes

- The bot runs independently from the Streamlit app
- All business logic is reused without duplication
- Memory-based storage (consider database for production)
- Supports async operations for better performance
- Extensible architecture for additional features

## Future Enhancements

- **Scheduled Fetching**: Automatic periodic article fetching
- **Push Notifications**: Alert users about relevant articles
- **Database Storage**: Persistent user data and article history
- **Advanced Filtering**: More sophisticated matching algorithms
- **Analytics**: Usage statistics and popular topics
