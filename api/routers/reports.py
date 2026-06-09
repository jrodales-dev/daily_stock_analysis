from fastapi import APIRouter, Depends, HTTPException, Body
from api.schemas.reports import ReportRequest, ReportResponse
from ingestion.market_data.router import MarketDataRouter
from ingestion.news.newsapi import NewsConnector
from processing.sentiment.nlp_pipeline import SentimentPipeline
from processing.technical.indicators import add_all_indicators
from processing.signals.engine import SignalEngine
from processing.reports.market_report import ReportEngine
from alerts.telegram_bot import TelegramBot
from alerts.discord_bot import DiscordBot
from datetime import datetime, timedelta
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Instances
market_connector = MarketDataRouter()
news_connector = NewsConnector()
nlp_pipeline = SentimentPipeline()
report_engine = ReportEngine()
telegram_bot = TelegramBot()
discord_bot = DiscordBot()

@router.post("/generate_daily", response_model=ReportResponse)
async def generate_daily_report(request: ReportRequest = Body(...)):
    """
    Generates a comprehensive daily report (Market Data, Technicals, News & NLP)
    and exports it as a PDF. Optionally sends it to bots.
    """
    try:
        # 1. Fetch Market Data and generate Signal
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        df = await market_connector.get_ohlcv(request.ticker, start_date, end_date)
        if df.empty:
            raise HTTPException(status_code=404, detail="No market data found")
            
        df_ind = add_all_indicators(df)
        signal_engine = SignalEngine()
        signal_data = signal_engine.calculate_unified_signal(df_ind, "neutral") # Start neutral
        
        # 2. Fetch News and NLP Sentiment
        articles = []
        try:
            if news_connector.health_check():
                articles = news_connector.get_company_news(request.ticker, days=3)
                if articles:
                    titles = [a["title"] for a in articles]
                    sentiments = nlp_pipeline.analyze(titles)
                    for i, sent in enumerate(sentiments):
                        articles[i]["sentiment"] = sent
                    
                    # Update signal based on the first article's sentiment as a mock aggregate
                    # In a real scenario we'd aggregate all sentiments
                    avg_sentiment_label = sentiments[0]["label"]
                    signal_data = signal_engine.calculate_unified_signal(df_ind, avg_sentiment_label)
        except Exception as e:
            logger.warning(f"Failed to fetch news for report: {e}")
            
        # 3. Compile context for Jinja
        context = {
            "ticker": request.ticker,
            "date": end_date.strftime("%Y-%m-%d %H:%M"),
            "close_price": signal_data.get("close_price"),
            "action": signal_data.get("action"),
            "unified_score": signal_data.get("unified_score"),
            "technical_score": signal_data.get("technical_score"),
            "sentiment_score": signal_data.get("sentiment_score"),
            "news": articles[:5] # Top 5 news
        }
        
        # 4. Generate PDF
        filename = f"{request.ticker}_daily_report_{end_date.strftime('%Y%m%d')}.pdf"
        pdf_path = report_engine.generate_daily_pdf(context, filename)
        
        # 5. Send Alerts
        caption = f"📊 Daily Report for {request.ticker} is ready! Action: {signal_data.get('action')}"
        if request.send_telegram:
            await telegram_bot.send_document(pdf_path, caption)
            
        if request.send_discord:
            await discord_bot.send_document(pdf_path, caption)
            
        return ReportResponse(
            ticker=request.ticker,
            status="SUCCESS",
            message="Report generated successfully",
            file_path=pdf_path
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
