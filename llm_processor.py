from typing import List, Dict, Generator
import logging
import time
import requests
import config
from database import ArticleDatabase
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from newspaper import Article as NewspaperArticle

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def summarize_article(url: str, retry_count: int = 3, audio_format: bool = False) -> str:
    """Summarize an article from a URL.
    
    Args:
        url: The URL of the article to summarize
        retry_count: Number of retry attempts for the LLM call
        audio_format: If True, generates a conversational podcast-style summary
    """
    try:
        article = NewspaperArticle(url)
        article.download()
        article.parse()
    except Exception as e:
        logger.error(f"Error fetching article from {url}: {e}")
        return f"Error: Could not fetch article content from URL."

    if audio_format:
        prompt = f"""Create a serious, conversational, podcast-style summary of the following article. Make it sound natural and engaging, 
        as if a single host is speaking directly to the audience. Keep the tone professional, without excessive humor. Do not include stage directions, 
        sound effects, multiple speakers, or any markup—only the plain text that the host would say. Keep it under 2 minutes when spoken.

        Article text:
        {article.text}"""
    else:
        prompt = f"""Please provide a concise summary of the following article text:

{article.text}"""

    # This part is a simplified version of the LLM call logic in _verify_with_llm.
    # In a real-world scenario, this would be refactored into a shared function.
    last_exception = None
    for attempt in range(retry_count):
        try:
            if config.LLM_TYPE == "groq":
                headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": config.GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0
                }
                response = requests.post(f"{config.GROQ_BASE_URL}/chat/completions", json=payload, headers=headers, timeout=120)
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            elif config.LLM_TYPE == "gemini":
                genai.configure(api_key=config.GEMINI_API_KEY)
                model = genai.GenerativeModel(config.GEMINI_MODEL)
                response = model.generate_content(prompt)
                return response.text

        except Exception as e:
            last_exception = e
            logger.warning(f"LLM summarization failed on attempt {attempt + 1}/{retry_count}: {e}")
            time.sleep(5)
            continue

    error_msg = str(last_exception) if last_exception else "Unknown error"
    return f"Error: Could not summarize the article after {retry_count} attempts. Last error: {error_msg}"


class ArticleMatcher:
    def __init__(self, input_text=""):
        if config.USE_EMBEDDING_FILTER:
            from embedding_matcher import EmbeddingMatcher
            self.matcher = EmbeddingMatcher()
        else:
            self.matcher = None
        self.db = ArticleDatabase()
        self.input_text = input_text
        
        if config.LLM_TYPE == "gemini":
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.llm_model = genai.GenerativeModel(config.GEMINI_MODEL)
        elif config.LLM_TYPE == "groq":
            # Groq provides an OpenAI-compatible HTTP API
            self.llm_url = f"{config.GROQ_BASE_URL}/chat/completions"
            self.llm_model = config.GROQ_MODEL
        
        logger.info(f"Initialized ArticleMatcher with {config.LLM_TYPE} LLM and database persistence")

    def _get_questions(self) -> List[str]:
        """Get questions and topics from the provided input text."""
        try:
            if not self.input_text:
                logger.warning("No input text provided for topics.")
                return []

            questions = [line.strip("- ").strip() for line in self.input_text.split("\n") if line.strip()]
            logger.info(f"Loaded {len(questions)} total items for matching")
            return questions
        except Exception as e:
            logger.error(f"Error processing input: {str(e)}")
            return []

    def _verify_with_llm(self, article: Dict, questions: List[str], retry_count: int = 3) -> List[Dict]:
        """Verify article relevance against multiple questions/topics with a single LLM call"""
        if not questions:
            return []
            
        # Create a numbered list of questions for the prompt
        questions_list = '\n'.join([f"{i+1}. {q}" for i, q in enumerate(questions)])
        
        prompt_content = f"Article Content: {article['content'][:2000]}\n" if config.USE_CONTENT_FOR_LLM_FILTERING else ""

        prompt = f"""Analyze if this article is relevant to each of the following questions/topics. 
For each question, respond with a single line containing the question number followed by 'yes' or 'no'.

Article Title: {article['title']}
{prompt_content}
Questions/Topics:
{questions_list}

For each question above, respond with the question number followed by 'yes' or 'no' on separate lines. 
Example:
1. yes
2. no
3. no"""

        last_exception = None
        for attempt in range(retry_count):
            try:
                if config.LLM_TYPE == "ollama":
                    try:
                        response = requests.post(
                            self.llm_url,
                            json={
                                "model": self.llm_model,
                                "prompt": prompt,
                                "stream": False
                            },
                            timeout=60  # Add timeout to prevent hanging
                        )
                        response.raise_for_status()
                        result = response.json()
                        response_text = result.get("response", "")
                    except requests.exceptions.RequestException as e:
                        if hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 429 and attempt < retry_count - 1:
                            wait_time = 60  # Wait for 60 seconds
                            logger.warning(f"Rate limited (429). Waiting for {wait_time} seconds before retry (attempt {attempt + 1}/{retry_count})")
                            time.sleep(wait_time)
                            last_exception = e
                            continue
                        raise
                elif config.LLM_TYPE == "groq":
                    try:
                        headers = {
                            "Authorization": f"Bearer {config.GROQ_API_KEY}",
                            "Content-Type": "application/json"
                        }
                        payload = {
                            "model": self.llm_model,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0
                        }
                        response = requests.post(self.llm_url, json=payload, headers=headers, timeout=60)
                        response.raise_for_status()
                        response_json = response.json()
                        response_text = response_json["choices"][0]["message"]["content"]
                    except requests.exceptions.RequestException as e:
                        if hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 429 and attempt < retry_count - 1:
                            wait_time = 60
                            logger.warning(f"Groq rate limited (429). Waiting {wait_time}s before retry (attempt {attempt + 1}/{retry_count})")
                            time.sleep(wait_time)
                            last_exception = e
                            continue
                        raise
                else:  # Gemini
                    try:
                        response = self.llm_model.generate_content(prompt)
                        response_text = response.text
                    except google_exceptions.ResourceExhausted as e:
                        if "quota" in str(e).lower() and attempt < retry_count - 1:
                            wait_time = 60  # Wait for 60 seconds
                            logger.warning(f"Quota exceeded. Waiting for {wait_time} seconds before retry (attempt {attempt + 1}/{retry_count})")
                            time.sleep(wait_time)
                            last_exception = e
                            continue
                        raise
                    except Exception as e:
                        logger.error(f"Gemini API error: {str(e)}")
                        last_exception = e
                        if attempt < retry_count - 1:
                            time.sleep(5)  # Shorter delay for non-quota related errors
                            continue
                        raise

                # Parse the response into a dictionary of {question: answer}
                answers = {}
                for line in response_text.split('\n'):
                    line = line.strip()
                    if not line or not line[0].isdigit():
                        continue
                    try:
                        # Extract question number and answer (e.g., "1. yes" -> (0, "yes"))
                        parts = line.split('.', 1)
                        if len(parts) == 2:
                            q_num = int(parts[0].strip()) - 1  # Convert to 0-based index
                            answer = parts[1].strip().lower()
                            if 0 <= q_num < len(questions):
                                answers[questions[q_num]] = answer
                    except (ValueError, IndexError):
                        continue
                
                # Log the LLM's response
                logger.info(f"LLM verification for article '{article['title']}' completed with {len(answers)} answers")
                
                # Return list of results in the same order as input questions
                results = []
                for q in questions:
                    answer = answers.get(q, 'no')  # Default to 'no' if answer not found
                    results.append({
                        'question': q,
                        'is_relevant': answer == 'yes',
                        'llm_response': answer
                    })
                
                return results
                
            except Exception as e:
                last_exception = e
                if attempt == retry_count - 1:  # Last attempt
                    logger.error(f"Error verifying with {config.LLM_TYPE} after {retry_count} attempts: {str(e)}")
                    break
                time.sleep(5)  # Default delay between retries
                continue
        
        # If we get here, all retries failed
        error_msg = str(last_exception) if last_exception else "Unknown error"
        return [{
            'question': q,
            'is_relevant': False,
            'llm_response': f"Error: {error_msg}"
        } for q in questions]

    def process_article(self, article: Dict) -> Dict:
        """Process an article to find matching questions and topics using optional two-stage filtering"""
        # Check if the article has already been processed
        if self.db.article_exists(article['url']):
            logger.info(f"Skipping already processed article: {article['title']}")
            return None  # Return None to indicate it was skipped

        questions = self._get_questions()
        if not questions:
            logger.warning("No questions/topics available for matching")
            return None
        
        try:
            logger.info(f"Processing article: {article['title']}")
            
            if config.USE_EMBEDDING_FILTER:
                # Two-stage filtering: First with embeddings, then with LLM
                similar_matches = self.matcher.find_similar(article["content"], questions)
                
                if not similar_matches:
                    logger.debug(f"No similar matches found for article: {article['title']}")
                    return None
                    
                # Process all matches in a single batch
                matched_questions = [m["text"] for m in similar_matches]
                verifications = self._verify_with_llm(article, matched_questions)
                
                verified_matches = []
                for match, verification in zip(similar_matches, verifications):
                    if verification["is_relevant"]:
                        verified_matches.append({
                            "question": match["text"],
                            "relevance": f"Verified match (similarity: {match['score']:.2f})",
                            "llm_response": verification["llm_response"],
                            "type": "match"
                        })
            else:
                # Skip embedding filtering and verify all questions with LLM
                logger.debug("Skipping embedding filter, verifying all questions with LLM")
                verifications = self._verify_with_llm(article, questions)
                
                verified_matches = [
                    {
                        "question": verification["question"],
                        "relevance": "Match (embedding filter disabled)",
                        "llm_response": verification["llm_response"],
                        "type": "match"
                    }
                    for verification in verifications 
                    if verification["is_relevant"]
                ]
            
            processed_article = {
                "title": article["title"],
                "url": article["url"],
                "source": article["source"],
                "content": article.get("content", ""),
                "date": article.get("date", ""),
                "matches": verified_matches
            }
            
            # Preserve hn_comments field if it exists
            if "hn_comments" in article:
                processed_article["hn_comments"] = article["hn_comments"]
            
            # Save to database if there are verified matches
            if verified_matches:
                self.db.save_article(processed_article)
                logger.info(f"Saved article '{article['title']}' to database")
            
            return processed_article
            
        except Exception as e:
            logger.error(f"Error processing article {article['title']}: {str(e)}")
            return {
                "title": article["title"],
                "url": article["url"],
                "source": article["source"],
                "matches": []
            }

    def process_articles(self, articles: List[Dict]) -> Generator[Dict, None, None]:
        """Process multiple articles and yield results one by one"""
        for article in articles:
            processed_article = self.process_article(article)
            if processed_article and processed_article["matches"]:  # Only yield articles with verified matches
                yield processed_article
