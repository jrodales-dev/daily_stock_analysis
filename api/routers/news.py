from fastapi import APIRouter, Depends, Query, Body, HTTPException
from typing import List
from api.schemas.news import NewsListResponse, NewsArticle, AnalyzeTextRequest, AnalyzeTextResponse, SentimentScore
from ingestion.news.newsapi import NewsConnector
from processing.sentiment.nlp_pipeline import SentimentPipeline
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Singletons for dependency injection
news_connector_instance = NewsConnector()
# We instantiate pipeline lazily so it doesn't block startup too much, but we'll init it when needed
# or keep it as a global instance that self-initializes
nlp_pipeline_instance = SentimentPipeline()

def get_news_connector():
    return news_connector_instance

def get_nlp_pipeline():
    return nlp_pipeline_instance

@router.get("/list", response_model=NewsListResponse)
async def get_news(
    ticker: str = Query(..., description="Stock ticker symbol"),
    days: int = Query(7, description="Number of past days to search"),
    connector: NewsConnector = Depends(get_news_connector),
    pipeline: SentimentPipeline = Depends(get_nlp_pipeline)
):
    """
    Fetch news for a ticker and automatically run sentiment analysis on their titles.
    """
    try:
        if not connector.health_check():
            raise HTTPException(status_code=503, detail="NewsAPI not configured")
            
        articles_data = connector.get_company_news(ticker, days=days)
        
        articles = []
        titles_to_analyze = []
        
        for article in articles_data:
            news_obj = NewsArticle(**article)
            articles.append(news_obj)
            titles_to_analyze.append(article.get("title", ""))
            
        if titles_to_analyze:
            sentiments = pipeline.analyze(titles_to_analyze)
            for i, sentiment_data in enumerate(sentiments):
                articles[i].sentiment = SentimentScore(**sentiment_data)
                
        return NewsListResponse(ticker=ticker, articles=articles)
        
    except ValueError as ve:
        raise HTTPException(status_code=503, detail=str(ve))
    except Exception as e:
        logger.error(f"Error fetching/analyzing news: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/analyze", response_model=AnalyzeTextResponse)
async def analyze_sentiment(
    request: AnalyzeTextRequest = Body(...),
    pipeline: SentimentPipeline = Depends(get_nlp_pipeline)
):
    """
    On-demand sentiment analysis for arbitrary texts.
    """
    try:
        sentiments = pipeline.analyze(request.texts)
        results = [SentimentScore(**s) for s in sentiments]
        return AnalyzeTextResponse(results=results)
    except Exception as e:
        logger.error(f"Error analyzing text: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
