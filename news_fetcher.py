import requests
from typing import List, Dict, Set
import config
from newspaper import Article
from datetime import datetime, timedelta



class NewsFetcher:
    def __init__(self):
        self.news_api_key = config.NEWS_API_KEY
        self.hn_api_url = config.HN_API_BASE_URL
        self.hn_stats = None
        self._seen_urls: Set[str] = set()

    def reset_session(self) -> None:
        self._seen_urls.clear()

    def _mark_if_new(self, url: str) -> bool:
        normalized = (url or "").strip()
        if not normalized:
            return False
        if normalized in self._seen_urls:
            return False
        self._seen_urls.add(normalized)
        return True

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
            results: List[Dict] = []
            for article in articles:
                article_url = article.get("url", "")
                if not self._mark_if_new(article_url):
                    continue
                results.append({
                    "title": article["title"],
                    "url": article_url,
                    "source": source,
                    "date": article.get("publishedAt", ""),
                    "content": self._get_article_content(article_url) if config.USE_CONTENT_FOR_FILTERING else ""
                })
            return results
        except Exception as e:
            print(f"Error fetching from {source}: {str(e)}")
            return []

    def fetch_hacker_news(self, min_comments: int = 10) -> List[Dict]:
        """Fetch hottest stories from Hacker News (by comment count) from the last 7 days"""
        try:
            # Use Algolia HN Search API - no API key required!
            # Search for stories from the last 7 days, sorted by number of comments
            algolia_url = "https://hn.algolia.com/api/v1/search"
            
            # Calculate 7-day cutoff timestamp
            cutoff_time = datetime.now() - timedelta(days=7)
            cutoff_timestamp = int(cutoff_time.timestamp())
            
            # Algolia params:
            # - tags=story: only get stories (not comments, polls, etc.)
            # - numericFilters: filter by created_at_i (unix timestamp) and num_comments
            # - hitsPerPage: number of results per page
            params = {
                "tags": "story",
                "numericFilters": f"created_at_i>{cutoff_timestamp},num_comments>={min_comments}",
                "hitsPerPage": 200,  # Fetch more to get good coverage
            }
            
            all_stories = []
            page = 0
            total_hits = 0
            
            # Paginate through results to get all qualifying stories
            while True:
                params["page"] = page
                response = requests.get(algolia_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                hits = data.get("hits", [])
                total_hits = data.get("nbHits", 0)
                
                if not hits:
                    break
                    
                all_stories.extend(hits)
                
                # Stop if we've fetched enough or no more pages
                if len(all_stories) >= total_hits or page >= data.get("nbPages", 1) - 1:
                    break
                    
                page += 1
                
                # Limit pagination to avoid excessive API calls
                if page >= 5:  # Max 1000 stories (5 pages * 200)
                    break
            
            # Sort by number of comments (descending) to get hottest first
            all_stories.sort(key=lambda x: x.get("num_comments", 0), reverse=True)
            
            # Filter out stories without URLs
            qualifying_stories = [s for s in all_stories if s.get("url")]
            
            earliest_time = float('inf')
            for story in qualifying_stories:
                story_time = story.get("created_at_i", 0)
                if story_time < earliest_time:
                    earliest_time = story_time
            
            earliest_time_str = "N/A"
            if earliest_time != float('inf'):
                earliest_time_str = datetime.fromtimestamp(earliest_time).strftime('%Y-%m-%d %H:%M:%S')

            # Take the top N stories by comment count
            articles_to_process = qualifying_stories[:config.MAX_ARTICLES_PER_SOURCE]
            articles = []
            
            for story_data in articles_to_process:
                date = datetime.fromtimestamp(story_data.get("created_at_i", 0)).isoformat()
                story_url = story_data.get("url")
                if not self._mark_if_new(story_url):
                    continue
                articles.append({
                    "title": story_data.get("title", ""),
                    "url": story_url,
                    "source": "hacker-news",
                    "date": date,
                    "content": self._get_article_content(
                        story_url) if config.USE_CONTENT_FOR_FILTERING else "",
                    "hn_comments": story_data.get("num_comments", 0),
                    "hn_discussion_url": f"https://news.ycombinator.com/item?id={story_data.get('objectID')}"
                })
            
            stats_msg = f"HN Stats (last 7 days): {total_hits} stories with >={min_comments} comments (earliest: {earliest_time_str})\nCoverage: {len(articles)}/{len(qualifying_stories)} ({100*len(articles)/max(len(qualifying_stories),1):.1f}%)"
            print(stats_msg)
            self.hn_stats = stats_msg
            
            if articles:
                top_comments = articles[0].get("hn_comments", 0)
                bottom_comments = articles[-1].get("hn_comments", 0) if len(articles) > 1 else top_comments
                print(f"Fetched {len(articles)} hottest articles (comments range: {bottom_comments}-{top_comments}, Limit: {config.MAX_ARTICLES_PER_SOURCE})")
            
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
