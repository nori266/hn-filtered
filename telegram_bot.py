import os
import logging
from pathlib import Path
from typing import Dict, List
import io
import httpx
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.error import NetworkError, TimedOut, TelegramError
from telegram.request import HTTPXRequest

from news_fetcher import NewsFetcher
from llm_processor import ArticleMatcher, summarize_article
import config
from tts_utils.piper_client import generate_audio


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

AUDIO_FORMAT = 'audio/wav'
AUDIO_EXTENSION = 'wav'
VOICE_DIR = Path("tts_utils/piper_voices")

if not VOICE_DIR.exists():
    logger.info("Downloading TTS model...")
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created directory: {VOICE_DIR.absolute()}")
    try:
        result = subprocess.run(
            ["python3", "-m", "piper.download_voices", "en_US-ryan-high"],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(VOICE_DIR)
        )
        logger.info(f"TTS model downloaded successfully: {result.stdout}")
        logger.info(f"TTS model files saved to: {VOICE_DIR.absolute()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to download TTS model: {e.stderr}")
        raise


class TelegramHNBot:
    def __init__(self):
        self.application = None
        self.user_topics = {}  # Store topics per user
        self.user_articles = {}  # Store processed articles per user
        self.user_summaries = {}  # Store summaries per user
        self.user_audio = {}  # Store audio files per user
        self.fetcher = NewsFetcher()
        
        # Load default topics
        self.default_topics = self._load_default_topics()
        
        # Parse allowed user IDs
        self.allowed_user_ids = self._parse_allowed_user_ids()
    
    def _load_default_topics(self) -> str:
        """Load default topics from topics.txt if it exists"""
        topics_file = Path(__file__).with_name("topics.txt")
        if topics_file.exists():
            return topics_file.read_text(encoding="utf-8")
        return ""
    
    def _parse_allowed_user_ids(self) -> set:
        """Parse allowed user IDs from config"""
        if not config.ALLOWED_USER_IDS:
            return set()
        try:
            return set(int(uid.strip()) for uid in config.ALLOWED_USER_IDS.split(',') if uid.strip())
        except ValueError as e:
            logger.error(f"Error parsing ALLOWED_USER_IDS: {e}")
            return set()
    
    def _is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot"""
        # If no restrictions are set, allow everyone
        if not self.allowed_user_ids:
            return True
        return user_id in self.allowed_user_ids
    
    def _sanitize_filename(self, title: str, max_length: int = 50) -> str:
        """Sanitize article title to create a valid filename"""
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', title)
        sanitized = re.sub(r'[_\s]+', '_', sanitized)
        sanitized = sanitized.strip('_ ')
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip('_')
        return sanitized if sanitized else "hn_article"
    
    def _escape_markdown(self, text: str) -> str:
        """Escape special Markdown characters for Telegram"""
        import re
        # Escape special characters: _ * [ ] ( ) ~ ` > # + - = | { } . !
        special_chars = r'_*[]()~`>#+-=|{}.!'
        return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        user_id = update.effective_user.id
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized access. This bot is restricted to specific users only.")
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            return
        
        welcome_text = """
🤖 **Hacker News Filter Bot**

I can help you filter Hacker News articles based on your interests!

**Available Commands:**
• `/start` - Show this welcome message
• `/topics` - View or set your topics of interest
• `/fetch` - Fetch and filter news articles
• `/help` - Show help information

**How to use:**
1. Set your topics with `/topics` or send me a text file with topics
2. Use `/fetch` to get filtered articles
3. Click buttons to summarize articles or generate audio

Ready to get started? Use `/topics` to set your interests!
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send help information"""
        user_id = update.effective_user.id
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized access. This bot is restricted to specific users only.")
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            return
        
        help_text = """
📖 **Help - How to Use the Bot**

**Step 1: Set Your Topics**
• Use `/topics` to set topics of interest
• Or send me a .txt file with topics (one per line)
• Topics are used to filter relevant articles

**Step 2: Fetch Articles**
• Use `/fetch` to get filtered Hacker News articles
• The bot will show articles matching your topics

**Step 3: Interact with Articles**
• Click "📄 Summarize" to get an AI summary
• Click "🎵 Audio" to generate a podcast-style audio summary
• Click "🔗 View" to open the original article

**Current Configuration:**
• LLM Provider: {llm_type}
• TTS Provider: {tts_provider}
• Max Articles: {max_articles}

Need help? Just ask! 😊
        """.format(
            llm_type=config.LLM_TYPE,
            tts_provider=config.TTS_PROVIDER,
            max_articles=config.MAX_ARTICLES_PER_SOURCE
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def topics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle topics command - show current topics or instructions to set new ones"""
        user_id = update.effective_user.id
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized access. This bot is restricted to specific users only.")
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            return
        
        current_topics = self.user_topics.get(user_id, self.default_topics)
        
        if current_topics:
            topics_list = current_topics.strip().split('\n')
            topics_display = '\n'.join([f"• {topic.strip()}" for topic in topics_list if topic.strip()])
            message = f"**Your Current Topics:**\n{topics_display}\n\n📝 Send me new topics (one per line) or upload a .txt file to update them."
        else:
            message = "**No topics set yet.**\n\n📝 Send me your topics of interest (one per line) or upload a .txt file."
        
        await update.message.reply_text(message, parse_mode='Markdown')

    async def fetch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fetch and filter news articles"""
        user_id = update.effective_user.id
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized access. This bot is restricted to specific users only.")
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            return
        
        topics = self.user_topics.get(user_id, self.default_topics)
        
        if not topics.strip():
            await update.message.reply_text(
                "❌ No topics set! Please use `/topics` to set your interests first.",
                parse_mode='Markdown'
            )
            return
        
        # Send initial message
        processing_msg = await update.message.reply_text("🔄 Fetching and filtering news... This may take a moment.")
        
        try:
            # Fetch and process articles
            fetcher = self.fetcher
            matcher = ArticleMatcher(input_text=topics)
            articles = fetcher.fetch_all_articles()
            
            # Initialize storage for this user
            self.user_articles[user_id] = []
            processed_urls = set()
            article_count = 0
            
            # Process and send articles one by one as they are verified
            for article in matcher.process_articles(articles):
                if article['url'] not in processed_urls and article.get('matches'):
                    # Add to user's article list
                    self.user_articles[user_id].append(article)
                    processed_urls.add(article['url'])
                    
                    # Cache the summary if it was generated during filtering
                    if 'summary' in article and article['summary']:
                        if user_id not in self.user_summaries:
                            self.user_summaries[user_id] = {}
                        self.user_summaries[user_id][article['url']] = article['summary']
                        logger.info(f"Cached summary for article: {article['title']}")
                    
                    # Send the article immediately
                    await self._send_article(update, article, article_count)
                    article_count += 1
                    
                    # Update the processing message with current progress
                    try:
                        msg_text = f"🔄 Processing articles... Found {article_count} relevant article{'s' if article_count != 1 else ''} so far..."
                        if fetcher.hn_stats:
                            msg_text += f"\n\n📊 {fetcher.hn_stats}"
                        await processing_msg.edit_text(msg_text)
                    except Exception:
                        # Ignore edit errors (message might be too old to edit)
                        pass
            
            # Final status update - Always send completion message
            completion_message = ""
            if article_count > 0:
                completion_message = f"✅ **Processing complete!** Found and sent {article_count} relevant article{'s' if article_count != 1 else ''} matching your topics."
            else:
                completion_message = "🔍 **Processing complete!** No relevant articles found for your topics. Try adjusting your topic list with `/topics`."
            
            if fetcher.hn_stats:
                completion_message += f"\n\n📊 {fetcher.hn_stats}"
            
            # Try to edit the processing message first
            try:
                await processing_msg.edit_text(completion_message, parse_mode='Markdown')
            except Exception:
                # If we can't edit the message, send a new one
                await update.message.reply_text(completion_message, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error fetching articles: {str(e)}")
            try:
                await processing_msg.edit_text(f"❌ Error fetching articles: {str(e)}")
            except Exception:
                await update.message.reply_text(f"❌ Error fetching articles: {str(e)}")

    async def _send_article(self, update: Update, article: Dict, idx: int):
        """Send a single article with action buttons"""
        # Format matches
        matches_text = ""
        for match in article['matches']:
            matches_text += f"• {match['question']} (Match: {match['llm_response']})\n"
        
        # Create article message
        message_text = f"""
**📰 [{article['title']}]({article['url']})**

**Source:** {article['source']}
"""
        
        # Show comment count for Hacker News articles
        if article['source'] == 'hacker-news' and 'hn_comments' in article:
            comment_count = article['hn_comments']
            comment_text = "comment" if comment_count == 1 else "comments"
            message_text += f"**Comments:** {comment_count} {comment_text}\n"
        
        message_text += f"""**Matched Topics:**
{matches_text}
        """
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("📄 Summarize", callback_data=f"summarize_{idx}"),
                InlineKeyboardButton("🎵 Audio", callback_data=f"audio_{idx}"),
            ]
        ]
        
        # Add HN discussion button for Hacker News articles
        if article['source'] == 'hacker-news' and 'hn_discussion_url' in article:
            keyboard.append([InlineKeyboardButton("💬 HN Discussion", url=article['hn_discussion_url'])])
        
        # keyboard.append([InlineKeyboardButton("🔗 View Article", url=article['url'])])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (topic updates)"""
        user_id = update.effective_user.id
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized access. This bot is restricted to specific users only.")
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            return
        
        text = update.message.text.strip()
        
        if text:
            # Store topics for this user
            self.user_topics[user_id] = text
            topics_list = text.split('\n')
            topics_display = '\n'.join([f"• {topic.strip()}" for topic in topics_list if topic.strip()])
            
            await update.message.reply_text(
                f"✅ **Topics updated!**\n{topics_display}\n\nUse `/fetch` to get filtered articles.",
                parse_mode='Markdown'
            )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document uploads (topic files)"""
        user_id = update.effective_user.id
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ Unauthorized access. This bot is restricted to specific users only.")
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            return
        
        document = update.message.document
        
        if document.mime_type == 'text/plain' or document.file_name.endswith('.txt'):
            try:
                # Download and read the file
                file = await context.bot.get_file(document.file_id)
                file_content = await file.download_as_bytearray()
                topics_text = file_content.decode('utf-8')
                
                # Store topics for this user
                self.user_topics[user_id] = topics_text
                topics_list = topics_text.strip().split('\n')
                topics_display = '\n'.join([f"• {topic.strip()}" for topic in topics_list if topic.strip()])
                
                await update.message.reply_text(
                    f"✅ **Topics loaded from file!**\n{topics_display}\n\nUse `/fetch` to get filtered articles.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                await update.message.reply_text(f"❌ Error reading file: {str(e)}")
        else:
            await update.message.reply_text("❌ Please send a .txt file with your topics.")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if not self._is_user_allowed(user_id):
            await query.message.reply_text("❌ Unauthorized access. This bot is restricted to specific users only.")
            logger.warning(f"Unauthorized access attempt by user {user_id}")
            return
        
        data = query.data
        
        if user_id not in self.user_articles:
            await query.edit_message_text("❌ No articles found. Please use `/fetch` first.")
            return
        
        try:
            if data.startswith("summarize_"):
                idx = int(data.split("_")[1])
                await self._handle_summarize(query, user_id, idx)
            elif data.startswith("audio_"):
                idx = int(data.split("_")[1])
                await self._handle_audio(query, user_id, idx)
        except (IndexError, ValueError) as e:
            logger.error(f"Error handling button callback: {str(e)}")
            await query.edit_message_text("❌ Error processing request.")

    async def _handle_summarize(self, query, user_id: int, idx: int):
        """Handle summarize button click"""
        articles = self.user_articles.get(user_id, [])
        if idx >= len(articles):
            await query.message.reply_text("❌ Article not found.")
            return
        
        article = articles[idx]
        article_url = article['url']
        
        # Check if summary already exists
        if user_id not in self.user_summaries:
            self.user_summaries[user_id] = {}
        
        if article_url in self.user_summaries[user_id]:
            summary = self.user_summaries[user_id][article_url]
        else:
            # Show processing status by editing the message
            try:
                # Format matches for the original article info
                matches_text = ""
                for match in article['matches']:
                    matches_text += f"• {match['question']} (Match: {match['llm_response']})\n"
                
                # Create processing message with original article info
                processing_text = f"""**📰 [{article['title']}]({article['url']})**

**Source:** {article['source']}
"""
                
                # Show comment count for Hacker News articles
                if article['source'] == 'hacker-news' and 'hn_comments' in article:
                    comment_count = article['hn_comments']
                    comment_text = "comment" if comment_count == 1 else "comments"
                    processing_text += f"**Comments:** {comment_count} {comment_text}\n"
                
                processing_text += f"""**Matched Topics:**
{matches_text}

🔄 Generating summary..."""
                
                # Keep the original buttons
                keyboard = [
                    [
                        InlineKeyboardButton("📄 Summarize", callback_data=f"summarize_{idx}"),
                        InlineKeyboardButton("🎵 Audio", callback_data=f"audio_{idx}"),
                    ],
                    [InlineKeyboardButton("🔗 View Discussion", callback_data=f"view_discussion_{idx}_{article_url[:50]}", url=article['hn_discussion_url'])]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    processing_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
                
                # Generate summary
                summary = summarize_article(article_url)
                self.user_summaries[user_id][article_url] = summary
                
            except Exception as e:
                logger.error(f"Error generating summary: {str(e)}")
                await query.message.reply_text(f"❌ Error generating summary: {str(e)}")
                return
        
        # Edit the original message to include the summary
        try:
            # Format matches
            matches_text = ""
            for match in article['matches']:
                matches_text += f"• {match['question']} (Match: {match['llm_response']})\n"
            
            # Create updated message with article info and summary
            message_text = f"""**📰 [{article['title']}]({article['url']})**

**Source:** {article['source']}
"""
            
            # Show comment count for Hacker News articles
            if article['source'] == 'hacker-news' and 'hn_comments' in article:
                comment_count = article['hn_comments']
                comment_text = "comment" if comment_count == 1 else "comments"
                message_text += f"**Comments:** {comment_count} {comment_text}\n"
            
            message_text += f"""**Matched Topics:**
{matches_text}

**📄 Summary:**
{summary}"""
            
            # Truncate if too long for Telegram (max 4096 characters)
            if len(message_text) > 4000:
                message_text = message_text[:4000] + "..."
            
            # Keep the original buttons
            keyboard = [
                [
                    InlineKeyboardButton("📄 Summarize", callback_data=f"summarize_{idx}"),
                    InlineKeyboardButton("🎵 Audio", callback_data=f"audio_{idx}"),
                ],
                [InlineKeyboardButton("🔗 View Discussion", callback_data=f"view_discussion_{idx}_{article_url[:50]}", url=article['hn_discussion_url'])]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message_text,
                parse_mode='Markdown',
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Error editing message with summary: {str(e)}")
            await query.message.reply_text(f"❌ Error displaying summary: {str(e)}")

    async def _handle_audio(self, query, user_id: int, idx: int):
        """Handle audio button click"""
        articles = self.user_articles.get(user_id, [])
        if idx >= len(articles):
            await query.message.reply_text("❌ Article not found.")
            return
        
        article = articles[idx]
        article_url = article['url']
        
        # Initialize user audio storage
        if user_id not in self.user_audio:
            self.user_audio[user_id] = {}
        
        # Check if audio already exists
        if article_url in self.user_audio[user_id]:
            audio_data = self.user_audio[user_id][article_url]
            # Send audio file directly if it already exists
            try:
                filename = f"{self._sanitize_filename(article['title'])}.{AUDIO_EXTENSION}"
                audio_file = io.BytesIO(audio_data['audio_bytes'])
                audio_file.name = filename
                
                caption = f"🎵 **Podcast Summary:** {self._escape_markdown(article['title'])}"
                if 'voice' in audio_data and audio_data['voice']:
                    caption += f"\n**Voice:** {self._escape_markdown(audio_data['voice'])}"
                
                await query.message.reply_audio(
                    audio=audio_file,
                    caption=caption,
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                logger.error(f"Error sending audio: {str(e)}")
                await query.message.reply_text(f"❌ Error sending audio: {str(e)}")
        else:
            # Show processing message as new message to preserve original article
            processing_msg = await query.message.reply_text("🔄 Generating podcast-style summary and audio...")
            
            try:
                # Generate podcast-style summary
                audio_summary = summarize_article(article_url, audio_format=True)
                
                # Generate audio
                audio_bytes, voice = generate_audio(audio_summary)
                
                if not audio_bytes:
                    await processing_msg.edit_text("❌ Could not generate audio.")
                    return
                
                audio_data = {
                    'audio_bytes': audio_bytes,
                    'voice': voice,
                    'summary': audio_summary
                }
                self.user_audio[user_id][article_url] = audio_data
                
                # Send audio file
                filename = f"{self._sanitize_filename(article['title'])}.{AUDIO_EXTENSION}"
                audio_file = io.BytesIO(audio_data['audio_bytes'])
                audio_file.name = filename
                
                caption = f"🎵 **Podcast Summary:** {self._escape_markdown(article['title'])}"
                if 'voice' in audio_data and audio_data['voice']:
                    caption += f"\n**Voice:** {self._escape_markdown(audio_data['voice'])}"
                
                await query.message.reply_audio(
                    audio=audio_file,
                    caption=caption,
                    parse_mode='Markdown'
                )
                
                # Update processing message to show completion
                await processing_msg.edit_text(f"✅ Audio generated for: {self._escape_markdown(article['title'])}", parse_mode='Markdown')
                
            except Exception as e:
                logger.error(f"Error generating audio: {str(e)}")
                await processing_msg.edit_text(f"❌ Error generating audio: {str(e)}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors caused by updates"""
        logger.error(f"Update {update} caused error: {context.error}")
        
        # Handle network errors specifically
        if isinstance(context.error, NetworkError):
            logger.error(f"Network error occurred: {context.error}")
            # Try to notify user if possible
            if update and update.effective_message:
                try:
                    await update.effective_message.reply_text(
                        "❌ Network error occurred. Please try again in a moment.",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass  # Ignore if we can't send the message
                    
        elif isinstance(context.error, TimedOut):
            logger.error(f"Request timed out: {context.error}")
            if update and update.effective_message:
                try:
                    await update.effective_message.reply_text(
                        "⏱️ Request timed out. Please try again.",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass
        else:
            # Log other errors
            logger.error(f"Unhandled error: {context.error}")
            if update and update.effective_message:
                try:
                    await update.effective_message.reply_text(
                        "❌ An error occurred while processing your request. Please try again.",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass
    
    def run(self):
        """Start the bot"""
        if not config.TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not found in config!")
            return
        
        # Log access control status
        if self.allowed_user_ids:
            logger.info(f"Bot access restricted to {len(self.allowed_user_ids)} user(s): {sorted(self.allowed_user_ids)}")
        else:
            logger.info("Bot access is open to all users (no restrictions set)")
        
        # Create HTTP client with custom SSL context for better compatibility
        # This helps with certificate verification issues
        httpx_kwargs = {
            "timeout": httpx.Timeout(
                connect=30.0,
                read=30.0,
                write=30.0,
                pool=10.0
            ),
            "limits": httpx.Limits(
                max_connections=100,
                max_keepalive_connections=10,
                keepalive_expiry=30.0
            ),
            # If SSL verification is causing issues, we can optionally disable it
            # Note: This should only be done in development or if you understand the risks
            "verify": False  # Disable SSL verification as a workaround
        }
        
        # Check for proxy settings (optional)
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy_url:
            httpx_kwargs["proxies"] = {"https://": proxy_url}
            logger.info(f"Using proxy: {proxy_url}")
        
        # Create custom request object
        request = HTTPXRequest(
            read_timeout=30,
            write_timeout=30,
            connect_timeout=10,
            pool_timeout=10
        )
        
        # Create application with custom request and proper timeout configuration
        self.application = (
            Application.builder()
            .token(config.TELEGRAM_BOT_TOKEN)
            .request(request)
            .build()
        )
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("topics", self.topics_command))
        self.application.add_handler(CommandHandler("fetch", self.fetch_command))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        
        # Button callback handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
        
        # Start the bot with retry configuration
        logger.info("Starting Telegram bot...")
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Drop pending updates on restart
            poll_interval=2.0,  # Poll interval in seconds
            timeout=10  # Timeout for long polling
        )


if __name__ == '__main__':
    bot = TelegramHNBot()
    bot.run()
