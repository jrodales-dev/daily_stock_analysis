from newsapi import NewsApiClient
from core.config import settings
from typing import List, Dict, Any
from datetime import datetime, timedelta

class NewsConnector:
    """
    Connector for NewsAPI to fetch financial news.
    """
    def __init__(self):
        self.api_key = settings.NEWS_API_KEY
        if self.api_key:
            self.client = NewsApiClient(api_key=self.api_key)
        else:
            self.client = None

    def get_company_news(self, ticker: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Fetch news articles related to a specific ticker/company.
        """
        if not self.client:
            raise ValueError("NewsAPI key not configured")
            
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            # We search for the ticker symbol in business news
            response = self.client.get_everything(
                q=ticker,
                from_param=start_date.strftime("%Y-%m-%d"),
                to=end_date.strftime("%Y-%m-%d"),
                language='en',
                sort_by='relevancy',
                page_size=20
            )
            
            if response.get("status") == "ok":
                articles = response.get("articles", [])
                results = []
                for article in articles:
                    results.append({
                        "title": article.get("title"),
                        "description": article.get("description"),
                        "content": article.get("content"),
                        "url": article.get("url"),
                        "source": article.get("source", {}).get("name"),
                        "published_at": article.get("publishedAt"),
                        "ticker": ticker
                    })
                return results
            return []
        except Exception as e:
            raise Exception(f"NewsAPI Error: {e}")

    def health_check(self) -> bool:
        return self.client is not None
