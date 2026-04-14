import yfinance as yf
import pandas as pd
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from core.embeddings import search_collection
from core.rag_chain import get_groq_client, MODEL_NAME

logger = logging.getLogger(__name__)

NEWS_COLLECTION = "news_articles"
INDICES = {
    "Nifty 50": "^NSEI",
    "Sensex": "^BSESN",
    "Bank Nifty": "^NSEBANK",
}

def get_price_movement(ticker: str, event_date_str: str) -> Optional[Dict]:
    try:
        event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
        start_date = event_date - timedelta(days=5)
        end_date = event_date + timedelta(days=25)
        data = yf.download(ticker, start=start_date, end=end_date)
        if data.empty:
            return None
        # Find closest date to event_date
        data.index = pd.to_datetime(data.index)
        closest_idx = data.index.get_indexer([event_date], method='nearest')[0]
        base_price = data.iloc[closest_idx]['Close']
        base_date = data.index[closest_idx].strftime("%Y-%m-%d")
        
        movement_1d = None
        movement_1w = None
        movement_1m = None
        
        if closest_idx + 1 < len(data):
            price_1d = data.iloc[closest_idx + 1]['Close']
            movement_1d = ((price_1d - base_price) / base_price) * 100
        if closest_idx + 5 < len(data):
            price_1w = data.iloc[closest_idx + 5]['Close']
            movement_1w = ((price_1w - base_price) / base_price) * 100
        if closest_idx + 21 < len(data):
            price_1m = data.iloc[closest_idx + 21]['Close']
            movement_1m = ((price_1m - base_price) / base_price) * 100
        
        return {
            "ticker": ticker,
            "base_price": float(base_price),
            "movement_1d": float(movement_1d) if movement_1d is not None else None,
            "movement_1w": float(movement_1w) if movement_1w is not None else None,
            "movement_1m": float(movement_1m) if movement_1m is not None else None,
            "base_date": base_date
        }
    except Exception as e:
        logger.error(f"Error in get_price_movement: {e}")
        return None

def find_similar_past_events(query: str, k: int = 5) -> List[Dict]:
    try:
        results = search_collection(query, NEWS_COLLECTION, k=k)
        if not results:
            return []
        similar_events = []
        for result in results:
            published_at = result["metadata"].get("published_at", "")
            movement = None
            if published_at:
                movement = get_price_movement("^NSEI", published_at)
            event = {
                "headline": result["text"][:120],
                "source": result["metadata"].get("source", ""),
                "published_at": published_at,
                "similarity_score": result.get("similarity_score", 0),
                "nifty_1d": movement["movement_1d"] if movement else None,
                "nifty_1w": movement["movement_1w"] if movement else None,
                "nifty_1m": movement["movement_1m"] if movement else None,
            }
            similar_events.append(event)
        return similar_events
    except Exception as e:
        logger.error(f"Error in find_similar_past_events: {e}")
        return []

def get_current_market_signals() -> Dict:
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        nifty_data = yf.download("^NSEI", start=start_date, end=end_date)
        vix_data = yf.download("^INDIAVIX", start=start_date, end=end_date)
        
        if nifty_data.empty or vix_data.empty:
            return {}
        
        current_price = nifty_data['Close'].iloc[-1]
        prev_price = nifty_data['Close'].iloc[-2] if len(nifty_data) > 1 else current_price
        change_1d = ((current_price - prev_price) / prev_price) * 100
        ma_50 = nifty_data['Close'].rolling(window=50).mean().iloc[-1]
        above_below_50ma = "above" if current_price > ma_50 else "below"
        
        vix_value = vix_data['Close'].iloc[-1]
        if vix_value < 15:
            vix_level = "low"
        elif 15 <= vix_value <= 20:
            vix_level = "moderate"
        else:
            vix_level = "elevated"
        
        return {
            "nifty_current": float(current_price),
            "nifty_1d_change": float(change_1d),
            "nifty_50ma": float(ma_50),
            "nifty_vs_50ma": above_below_50ma,
            "vix_value": float(vix_value),
            "vix_level": vix_level
        }
    except Exception as e:
        logger.error(f"Error in get_current_market_signals: {e}")
        return {}

def analyze_patterns(query: str) -> Dict:
    try:
        similar_events = find_similar_past_events(query, k=5)
        market_signals = get_current_market_signals()
        
        events_text = ""
        for event in similar_events:
            events_text += f"- {event['headline']} ({event['published_at']}): Nifty 1D: {event['nifty_1d']}%, 1W: {event['nifty_1w']}%, 1M: {event['nifty_1m']}%\n"
        
        signals_text = f"Nifty current: {market_signals.get('nifty_current', 'N/A')}, 1D change: {market_signals.get('nifty_1d_change', 'N/A')}%, vs 50MA: {market_signals.get('nifty_vs_50ma', 'N/A')}, VIX: {market_signals.get('vix_value', 'N/A')} ({market_signals.get('vix_level', 'N/A')})"
        
        client = get_groq_client()
        system_message = """You are FinSight AI. You show historical market patterns
similar to a user's query. You NEVER predict future prices.
You NEVER say what to buy or sell. Always end with a disclaimer
that past patterns do not guarantee future outcomes.
Respond only in valid JSON."""
        user_message = f"""
Query: {query}

Similar past events:
{events_text}

Current market signals:
{signals_text}

Return JSON with exactly these fields:
- "similar_events": list of up to 5 objects with
  headline (str), date (str), nifty_1d (str), nifty_1w (str)
- "pattern_summary": str (2-3 sentences on what typically happened)
- "key_factors": list of 3 strings
- "what_to_watch": list of 3 short monitoring signals
- "disclaimer": "Past market patterns do not guarantee future outcomes.
                 This is historical context only, not financial advice."

Return only valid JSON.
"""
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            max_tokens=800,
            temperature=0.2
        )
        response_text = response.choices[0].message.content.strip()
        result = json.loads(response_text)
        return result
    except Exception as e:
        logger.error(f"Error in analyze_patterns: {e}")
        return {
            "similar_events": [],
            "pattern_summary": "Not enough historical data available for this query.",
            "key_factors": [],
            "what_to_watch": [],
            "disclaimer": "Past market patterns do not guarantee future outcomes. This is historical context only, not financial advice."
        }
