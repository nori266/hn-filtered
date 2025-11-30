import requests
from typing import List, Dict
import config
from newspaper import Article
from datetime import datetime, timedelta
import concurrent.futures


class NewsFetcher:
    def __init__(self):
        self.news_api_key = config.NEWS_API_KEY
        self.hn_api_url = config.HN_API_BASE_URL
        self.hn_stats = None

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
            
            total_in_24h = 0
            total_with_min_comments = 0
            qualifying_stories = []
            
            def fetch_story_details(story_id):
                try:
                    resp = requests.get(f"{self.hn_api_url}/item/{story_id}.json", timeout=10)
                    if resp.status_code == 200:
                        return resp.json()
                except Exception:
                    pass
                return None

            # Fetch stories in parallel to speed up the scanning process
            # We scan up to 200 stories or all returned IDs, whichever is smaller, to be reasonable
            # But to be accurate we should scan until we hit the time barrier.
            # Since we don't know which ID corresponds to which time without checking, 
            # and IDs are roughly chronological, we can process them in batches or just all of them.
            # newstories returns ~500 IDs. Fetching 500 small JSONs in parallel is fine.
            
            earliest_time = float('inf')
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                # Map returns results in order
                results = executor.map(fetch_story_details, story_ids)
                
                for story_data in results:
                    if not story_data:
                        continue
                        
                    story_time = story_data.get("time", 0)
                    
                    # stop when we reach stories older than 24h
                    # Note: Since we fetch in parallel, we might process a slightly older story 
                    # before a newer one if we didn't preserve order, but map preserves order.
                    # However, if one request hangs, it blocks. 

                    if story_time < cutoff_timestamp:
                        continue
                    
                    total_in_24h += 1
                    if story_time < earliest_time:
                        earliest_time = story_time
                        
                    comments = story_data.get("descendants", 0)
                    
                    if comments >= min_comments:
                        total_with_min_comments += 1
                        if story_data.get("url"):
                            qualifying_stories.append(story_data)

            earliest_time_str = "N/A"
            if earliest_time != float('inf'):
                earliest_time_str = datetime.fromtimestamp(earliest_time).strftime('%Y-%m-%d %H:%M:%S')

            stats_msg = f"HN Stats: {total_in_24h} total stories (earliest: {earliest_time_str}), {total_with_min_comments} with >={min_comments} comments"
            print(stats_msg)
            self.hn_stats = stats_msg
            
            # Now take only the top N qualifying stories
            articles_to_process = qualifying_stories[:config.MAX_ARTICLES_PER_SOURCE]
            articles = []
            
            for story_data in articles_to_process:
                date = datetime.fromtimestamp(story_data.get("time")).isoformat()
                articles.append({
                    "title": story_data.get("title", ""),
                    "url": story_data.get("url"),
                    "source": "hacker-news",
                    "date": date,
                    "content": self._get_article_content(
                        story_data.get("url")) if config.USE_CONTENT_FOR_FILTERING else "",
                    "hn_comments": story_data.get("descendants", 0),
                    "hn_discussion_url": f"https://news.ycombinator.com/item?id={story_data.get('id')}"
                })
            
            print(f"Fetched content for {len(articles)} articles (Limit: {config.MAX_ARTICLES_PER_SOURCE})")
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
