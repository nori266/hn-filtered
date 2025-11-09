import requests
from typing import List, Dict
import config
from newspaper import Article
from datetime import datetime, timedelta

class NewsFetcher:
    def __init__(self):
        self.news_api_key = config.NEWS_API_KEY
        self.hn_api_url = config.HN_API_BASE_URL

    def fetch_news_api_articles(self, source: str) -> List[Dict]:
        """Fetch articles from News API sources"""
        url = f"{config.NEWS_API_BASE_URL}/everything"
        params = {
            "sources": source,
            "apiKey": self.news_api_key,
            "pageSize": config.MAX_ARTICLES_PER_SOURCE
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            articles = response.json().get("articles", [])
            return [{
                "title": article["title"],
                "url": article["url"],
                "source": source,
                "date": article.get("publishedAt", ""),
                "content": self._get_article_content(article["url"]) if config.USE_CONTENT_FOR_FILTERING else ""
            } for article in articles]
        except Exception as e:
            print(f"Error fetching from {source}: {str(e)}")
            return []

    def fetch_hacker_news(self, min_comments: int = 10) -> List[Dict]:
        """Fetch stories from Hacker News with optional comment filter"""
        try:
            # get newstories instead of topstories for chronological order
            response = requests.get(f"{self.hn_api_url}/newstories.json")
            response.raise_for_status()
            story_ids = response.json()
            
            # calculate 24h cutoff
            cutoff_time = datetime.now() - timedelta(hours=24)
            cutoff_timestamp = int(cutoff_time.timestamp())
            
            articles = []
            total_in_24h = 0
            total_with_min_comments = 0
            
            for story_id in story_ids:
                story_response = requests.get(f"{self.hn_api_url}/item/{story_id}.json")
                story_data = story_response.json()
                
                if not story_data:
                    continue
                    
                story_time = story_data.get("time", 0)
                
                # stop when we reach stories older than 24h
                if story_time < cutoff_timestamp:
                    break
                
                total_in_24h += 1
                comments = story_data.get("descendants", 0)
                
                if comments >= min_comments:
                    total_with_min_comments += 1
                    
                    if story_data.get("url"):
                        date = datetime.fromtimestamp(story_time).isoformat()
                        articles.append({
                            "title": story_data.get("title", ""),
                            "url": story_data.get("url"),
                            "source": "hacker-news",
                            "date": date,
                            "content": self._get_article_content(
                                story_data.get("url")) if config.USE_CONTENT_FOR_FILTERING else "",
                            "hn_comments": comments,
                            "hn_discussion_url": f"https://news.ycombinator.com/item?id={story_id}"
                        })
                        
                        if len(articles) >= config.MAX_ARTICLES_PER_SOURCE:
                            break
            
            print(f"HN Stats (last 24h): {total_in_24h} total stories, {total_with_min_comments} with >={min_comments} comments, fetched {len(articles)}")
            print(f"Coverage: {len(articles)}/{total_with_min_comments} ({100*len(articles)/max(total_with_min_comments,1):.1f}%)")
            
            return articles
        except Exception as e:
            print(f"Error fetching Hacker News: {str(e)}")
            return []

    def _get_article_content(self, url: str) -> str:
        """Extract article content using newspaper3k"""
        try:
            article = Article(url)
            article.download()
            article.parse()
            return article.text
        except Exception as e:
            print(f"Error extracting content from {url}: {str(e)}")
            return ""

    def fetch_all_articles(self) -> List[Dict]:
        """Fetch articles from all configured sources"""
        all_articles = []
        
        # fetch from News API sources
        for source in config.SOURCES:
            if source != "hacker-news":
                articles = self.fetch_news_api_articles(source)
                all_articles.extend(articles)
        
        # fetch from Hacker News
        hn_articles = self.fetch_hacker_news(min_comments=10)
        all_articles.extend(hn_articles)
        
        return all_articles
