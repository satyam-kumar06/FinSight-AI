import feedparser
import httpx
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import time
from datetime import datetime
import os
import json
from typing import List, Dict, Optional, Tuple
from transformers import pipeline
import torch
from core.embeddings import store_in_collection
from dotenv import load_dotenv

load_dotenv()

NEWS_DB_PATH = os.getenv("NEWS_DB_PATH", "./news.db")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
NEWS_COLLECTION = "news_articles"
MAX_ARTICLES_DB = 500 

RSS_FEEDS = [
    {"name": "Economic Times Markets",
     "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
     "category": "markets"},
    {"name": "Moneycontrol News",
     "url": "https://www.moneycontrol.com/rss/latestnews.xml",
     "category": "general"},
    {"name": "LiveMint Markets",
     "url": "https://www.livemint.com/rss/markets",
     "category": "markets"},
    {"name": "Reuters India Business",
     "url": "https://feeds.reuters.com/reuters/INbusinessNews",
     "category": "business"},
    {"name": "RBI Press Releases",
     "url": "https://www.rbi.org.in/Scripts/RSSFeedsHandler.aspx?Id=103",
     "category": "rbi"}
]

Base = declarative_base()

class NewsArticle(Base):
    __tablename__ = 'news_articles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    headline = Column(String, nullable=False)
    source = Column(String)
    url = Column(String, unique=True)
    published_at = Column(String)
    category = Column(String)
    sentiment = Column(String, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Sentiment model singleton
_sentiment_pipeline = None

def get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        start_time = time.time()
        logging.info("Loading FinBERT sentiment analysis model...")
        _sentiment_pipeline = pipeline("text-classification", 
                                    model="ProsusAI/finbert", 
                                    top_k=1)
        load_time = time.time() - start_time
        logging.info(f"FinBERT model loaded in {load_time:.2f} seconds")
    return _sentiment_pipeline

def initialize_news_db():
    try:
        engine = create_engine(f"sqlite:///{NEWS_DB_PATH}")
        Base.metadata.create_all(engine)
        logging.info(f"News database initialized at {NEWS_DB_PATH}")
    except Exception as e:
        logging.error(f"Failed to initialize news database: {e}")
        raise

def analyze_sentiment(text: str) -> Tuple[str, float]:
    try:
        pipeline = get_sentiment_pipeline()
        # Truncate to FinBERT max length
        truncated_text = text[:512]
        results = pipeline(truncated_text)
        if results and len(results[0]) > 0:
            result = results[0][0]
            label = result['label'].lower()
            score = float(result['score'])
            return (label, score)
        else:
            return ("neutral", 0.5)
    except Exception as e:
        logging.error(f"Sentiment analysis failed: {e}")
        return ("neutral", 0.5)

def fetch_rss_news() -> List[Dict]:
    articles = []
    try:
        engine = create_engine(f"sqlite:///{NEWS_DB_PATH}")
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Get existing URLs for deduplication
        existing_urls = {row[0] for row in session.query(NewsArticle.url).all()}
        session.close()
        
        for feed in RSS_FEEDS:
            try:
                parsed = feedparser.parse(feed["url"])
                for entry in parsed.entries:
                    url = entry.link
                    if url in existing_urls:
                        continue
                    
                    article = {
                        "headline": entry.title,
                        "summary": getattr(entry, 'summary', ''),
                        "url": url,
                        "published_at": getattr(entry, 'published', datetime.utcnow().isoformat()),
                        "source": feed["name"],
                        "category": feed["category"]
                    }
                    articles.append(article)
            except Exception as e:
                logging.error(f"Failed to fetch RSS feed {feed['name']}: {e}")
                continue
                
    except Exception as e:
        logging.error(f"Database error in fetch_rss_news: {e}")
    
    return articles

def fetch_newsapi_news() -> List[Dict]:
    if not NEWSAPI_KEY:
        return []
    
    articles = []
    try:
        with httpx.Client() as client:
            # Top headlines
            headlines_url = "https://newsapi.org/v2/top-headlines"
            params = {
                "country": "in",
                "category": "business",
                "pageSize": 50,
                "apiKey": NEWSAPI_KEY
            }
            response = client.get(headlines_url, params=params)
            if response.status_code == 200:
                data = response.json()
                for article in data.get("articles", []):
                    articles.append({
                        "headline": article.get("title", ""),
                        "summary": article.get("description", ""),
                        "url": article.get("url", ""),
                        "published_at": article.get("publishedAt", ""),
                        "source": article.get("source", {}).get("name", "NewsAPI"),
                        "category": "business"
                    })
            
            # Everything query
            everything_url = "https://newsapi.org/v2/everything"
            params = {
                "q": "stock market OR RBI OR Nifty OR Sensex",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 50,
                "apiKey": NEWSAPI_KEY
            }
            response = client.get(everything_url, params=params)
            if response.status_code == 200:
                data = response.json()
                for article in data.get("articles", []):
                    articles.append({
                        "headline": article.get("title", ""),
                        "summary": article.get("description", ""),
                        "url": article.get("url", ""),
                        "published_at": article.get("publishedAt", ""),
                        "source": article.get("source", {}).get("name", "NewsAPI"),
                        "category": "markets"
                    })
        
        # Deduplicate by URL
        seen_urls = set()
        deduped_articles = []
        for article in articles:
            if article["url"] and article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                deduped_articles.append(article)
        
        return deduped_articles
        
    except Exception as e:
        logging.error(f"Failed to fetch NewsAPI news: {e}")
        return []

def crawl_and_store() -> int:
    try:
        # Fetch articles
        rss_articles = fetch_rss_news()
        newsapi_articles = fetch_newsapi_news()
        all_articles = rss_articles + newsapi_articles
        
        if not all_articles:
            logging.info("No new articles to process")
            return 0
        
        engine = create_engine(f"sqlite:///{NEWS_DB_PATH}")
        Session = sessionmaker(bind=engine)
        session = Session()
        
        new_articles = []
        chroma_texts = []
        chroma_metadatas = []
        
        for article in all_articles:
            try:
                # Check if URL already exists
                existing = session.query(NewsArticle).filter_by(url=article["url"]).first()
                if existing:
                    continue
                
                # Analyze sentiment
                sentiment_text = article["headline"]
                if article.get("summary"):
                    sentiment_text += " " + article["summary"][:200]
                sentiment, score = analyze_sentiment(sentiment_text)
                
                # Create DB record
                db_article = NewsArticle(
                    headline=article["headline"],
                    source=article["source"],
                    url=article["url"],
                    published_at=article["published_at"],
                    category=article["category"],
                    sentiment=sentiment,
                    sentiment_score=score,
                    summary=article.get("summary")
                )
                
                session.add(db_article)
                new_articles.append(db_article)
                
                # Prepare for ChromaDB
                chroma_texts.append(f"{article['headline']}\n{article.get('summary', '')}")
                chroma_metadatas.append({
                    "source": article["source"],
                    "url": article["url"],
                    "published_at": article["published_at"],
                    "category": article["category"],
                    "sentiment": sentiment
                })
                
            except Exception as e:
                logging.error(f"Error processing article {article.get('url', 'unknown')}: {e}")
                continue
        
        # Commit DB changes
        session.commit()
        
        # Store in ChromaDB
        if chroma_texts:
            try:
                store_in_collection(chroma_texts, chroma_metadatas, NEWS_COLLECTION, "news")
            except Exception as e:
                logging.error(f"Failed to store in ChromaDB: {e}")
        
        # Rolling window: delete oldest if over limit
        total_count = session.query(NewsArticle).count()
        if total_count > MAX_ARTICLES_DB:
            excess = total_count - MAX_ARTICLES_DB
            oldest = session.query(NewsArticle).order_by(NewsArticle.created_at).limit(excess).all()
            for old_article in oldest:
                session.delete(old_article)
            session.commit()
            logging.info(f"Deleted {excess} oldest articles to maintain rolling window")
        
        session.close()
        
        new_count = len(new_articles)
        logging.info(f"Crawl complete: {new_count} new articles stored")
        return new_count
        
    except Exception as e:
        logging.error(f"Crawl and store failed: {e}")
        return 0

def get_recent_news(limit: int = 30, category: Optional[str] = None) -> List[Dict]:
    try:
        engine = create_engine(f"sqlite:///{NEWS_DB_PATH}")
        Session = sessionmaker(bind=engine)
        session = Session()
        
        query = session.query(NewsArticle).order_by(NewsArticle.created_at.desc())
        if category:
            query = query.filter_by(category=category)
        
        articles = query.limit(limit).all()
        
        result = []
        for article in articles:
            result.append({
                "id": article.id,
                "headline": article.headline,
                "source": article.source,
                "url": article.url,
                "published_at": article.published_at,
                "category": article.category,
                "sentiment": article.sentiment,
                "sentiment_score": article.sentiment_score,
                "summary": article.summary,
                "created_at": article.created_at.isoformat() if article.created_at else None
            })
        
        session.close()
        return result
        
    except Exception as e:
        logging.error(f"Failed to get recent news: {e}")
        return []

def initialize_news_scheduler():
    try:
        scheduler = BackgroundScheduler()
        
        # Add job to run every 4 hours
        scheduler.add_job(crawl_and_store, 'interval', hours=4, id='news_crawl')
        
        # Run once immediately at startup
        import threading
        threading.Thread(target=crawl_and_store).start()
        
        scheduler.start()
        logging.info("News crawler scheduled every 4 hours")
        
    except Exception as e:
        logging.error(f"Failed to initialize news scheduler: {e}")
        raise
