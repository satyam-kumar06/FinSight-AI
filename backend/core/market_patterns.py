import yfinance as yf
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from core.embeddings import search_collection
from core.rag_chain import get_groq_client, MODEL_NAME
import spacy
import json
import time

NEWS_COLLECTION = "news_articles"

INDICES = {
    "Nifty 50": "^NSEI",
    "Sensex": "^BSESN",
    "Bank Nifty": "^NSEBANK",
    "India VIX": "^INDIAVIX",
}

def extract_entities(query: str) -> Dict:
    """Extract entities from query using spaCy and manual keyword matching."""
    try:
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(query.lower())
        
        companies = []
        indices = []
        keywords = []
        event_type = "general"
        
        # Extract companies (ORG entities)
        for ent in doc.ents:
            if ent.label_ == "ORG":
                companies.append(ent.text.title())
        
        # Check for indices mentioned
        for index_name in INDICES.keys():
            if index_name.lower() in query.lower():
                indices.append(index_name)
        
        # Manual keyword checking
        manual_keywords = ["rate_hike", "inflation", "earnings", "budget", "fii", "crude", "rupee", "geopolitical"]
        for keyword in manual_keywords:
            if keyword in query.lower():
                keywords.append(keyword)
                if keyword == "rate_hike":
                    event_type = "monetary_policy"
                elif keyword == "inflation":
                    event_type = "economic_data"
                elif keyword == "earnings":
                    event_type = "corporate_results"
                elif keyword == "budget":
                    event_type = "fiscal_policy"
                elif keyword in ["fii", "crude", "rupee"]:
                    event_type = "market_event"
                elif keyword == "geopolitical":
                    event_type = "global_event"
        
        return {
            "companies": companies,
            "indices": indices,
            "event_type": event_type,
            "keywords": keywords
        }
        
    except Exception as e:
        logging.error(f"Entity extraction failed: {e}")
        return {
            "companies": [],
            "indices": [],
            "event_type": "general",
            "keywords": []
        }

def get_price_movement(ticker: str, event_date: str, days_after: List[int] = [1, 5, 21]) -> Dict:
    """Get price movements after an event date."""
    try:
        event_dt = datetime.strptime(event_date, "%Y-%m-%d")
        start_date = event_dt - timedelta(days=5)
        end_date = event_dt + timedelta(days=25)
        
        # Download data
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if data.empty:
            return {"error": "No data available for the given date range"}
        
        # Find closest trading day to event_date
        data.index = pd.to_datetime(data.index)
        event_date_dt = pd.Timestamp(event_dt)
        
        # Get dates after event_date
        future_dates = data.index[data.index >= event_date_dt]
        if future_dates.empty:
            return {"error": "No trading days after event date"}
        
        base_date = future_dates[0]  # First trading day on or after event
        base_price = data.loc[base_date, 'Close']
        
        movements = {}
        for days in days_after:
            target_date = base_date + timedelta(days=days)
            # Find closest trading day
            available_dates = data.index[data.index >= target_date]
            if not available_dates.empty:
                actual_date = available_dates[0]
                actual_price = data.loc[actual_date, 'Close']
                pct_change = ((actual_price - base_price) / base_price) * 100
                movements[f"{days}d"] = round(pct_change, 2)
            else:
                movements[f"{days}d"] = None
        
        return {
            "base_date": base_date.strftime("%Y-%m-%d"),
            "base_price": round(base_price, 2),
            "movements": movements
        }
        
    except Exception as e:
        logging.error(f"Price movement calculation failed: {e}")
        return {"error": str(e)}

def find_similar_events(query: str, limit: int = 5) -> List[Dict]:
    """Find similar historical events using semantic search."""
    try:
        entities = extract_entities(query)
        
        # Create search query from entities
        search_terms = []
        if entities["companies"]:
            search_terms.extend(entities["companies"])
        if entities["keywords"]:
            search_terms.extend(entities["keywords"])
        if entities["event_type"] != "general":
            search_terms.append(entities["event_type"])
        
        search_query = " ".join(search_terms) if search_terms else query
        
        # Search news collection
        results = search_collection(search_query, NEWS_COLLECTION, n_results=limit)
        
        similar_events = []
        for result in results:
            metadata = result.get("metadata", {})
            similar_events.append({
                "headline": result.get("document", ""),
                "date": metadata.get("published_at", ""),
                "source": metadata.get("source", ""),
                "sentiment": metadata.get("sentiment", ""),
                "category": metadata.get("category", "")
            })
        
        return similar_events
        
    except Exception as e:
        logging.error(f"Similar events search failed: {e}")
        return []

def analyze_historical_patterns(similar_events: List[Dict]) -> Dict:
    """Analyze patterns from similar historical events."""
    try:
        patterns = {
            "total_events": len(similar_events),
            "sentiment_distribution": {},
            "categories": set(),
            "time_range": {"earliest": None, "latest": None}
        }
        
        for event in similar_events:
            # Sentiment distribution
            sentiment = event.get("sentiment", "neutral")
            patterns["sentiment_distribution"][sentiment] = patterns["sentiment_distribution"].get(sentiment, 0) + 1
            
            # Categories
            category = event.get("category", "")
            if category:
                patterns["categories"].add(category)
            
            # Time range
            date_str = event.get("date", "")
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    if patterns["time_range"]["earliest"] is None or date < patterns["time_range"]["earliest"]:
                        patterns["time_range"]["earliest"] = date
                    if patterns["time_range"]["latest"] is None or date > patterns["time_range"]["latest"]:
                        patterns["time_range"]["latest"] = date
                except:
                    pass
        
        patterns["categories"] = list(patterns["categories"])
        if patterns["time_range"]["earliest"]:
            patterns["time_range"]["earliest"] = patterns["time_range"]["earliest"].strftime("%Y-%m-%d")
        if patterns["time_range"]["latest"]:
            patterns["time_range"]["latest"] = patterns["time_range"]["latest"].strftime("%Y-%m-%d")
        
        return patterns
        
    except Exception as e:
        logging.error(f"Pattern analysis failed: {e}")
        return {"error": str(e)}

def get_market_context_for_event(event: Dict) -> Dict:
    """Get market movements for a specific historical event."""
    try:
        event_date = event.get("date", "")
        if not event_date:
            return {}
        
        # Extract date
        try:
            date_obj = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
            date_str = date_obj.strftime("%Y-%m-%d")
        except:
            return {}
        
        # Get Nifty movements
        nifty_movement = get_price_movement("^NSEI", date_str)
        
        return {
            "headline": event.get("headline", ""),
            "date": date_str,
            "nifty_1d": nifty_movement.get("movements", {}).get("1d"),
            "nifty_1w": nifty_movement.get("movements", {}).get("5d"),
            "nifty_1m": nifty_movement.get("movements", {}).get("21d"),
            "sentiment": event.get("sentiment", "")
        }
        
    except Exception as e:
        logging.error(f"Market context retrieval failed: {e}")
        return {}

def generate_historical_context_prompt(signals_text: str, similar_events: List[Dict], patterns: Dict) -> str:
    """Generate prompt for LLM to analyze historical context."""
    
    events_text = "\n".join([
        f"- {event['headline']} ({event.get('date', 'Unknown date')}) - Nifty 1D: {event.get('nifty_1d', 'N/A')}%, 1W: {event.get('nifty_1w', 'N/A')}%"
        for event in similar_events[:5]  # Limit to 5 events
    ])
    
    prompt = f"""Analyze the following market signals and provide historical context based on similar past events. Focus on patterns and outcomes, not predictions.

Current market signals:
{signals_text}

Similar historical events found:
{events_text}

Pattern analysis:
- Total similar events: {patterns.get('total_events', 0)}
- Sentiment distribution: {patterns.get('sentiment_distribution', {})}
- Categories: {', '.join(patterns.get('categories', []))}
- Time range: {patterns.get('time_range', {}).get('earliest', 'N/A')} to {patterns.get('time_range', {}).get('latest', 'N/A')}

Provide a JSON response with:
- similar_events: list of {{headline, date, nifty_1d, nifty_1w}}
- pattern_summary: str (2-3 sentences on what typically happened)
- key_factors: list of 3 strings (factors that drove outcomes)
- what_to_watch: list of 3 monitoring signals (not advice)
- disclaimer: always include standard disclaimer

Response must be valid JSON only."""
    
    return prompt

def get_historical_context(query: str, signals_text: str) -> Dict:
    """Main function to get historical context for current market situation."""
    try:
        # Find similar events
        similar_events_raw = find_similar_events(query, limit=10)
        
        # Get market context for each event
        similar_events = []
        for event in similar_events_raw:
            context = get_market_context_for_event(event)
            if context:
                similar_events.append(context)
        
        # Analyze patterns
        patterns = analyze_historical_patterns(similar_events)
        
        # Generate LLM prompt
        prompt = generate_historical_context_prompt(signals_text, similar_events, patterns)
        
        # Get LLM response
        client = get_groq_client()
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        
        # Parse JSON response
        content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        result = json.loads(content)
        
        # Ensure required fields
        if "similar_events" not in result:
            result["similar_events"] = similar_events[:5]
        if "pattern_summary" not in result:
            result["pattern_summary"] = "Historical patterns show varied market responses to similar events."
        if "key_factors" not in result:
            result["key_factors"] = ["Market sentiment", "Economic conditions", "External factors"]
        if "what_to_watch" not in result:
            result["what_to_watch"] = ["Market volatility", "Economic indicators", "Global events"]
        if "disclaimer" not in result:
            result["disclaimer"] = "This is historical analysis only and not financial advice. Past performance does not guarantee future results."
        
        return result
        
    except Exception as e:
        logging.error(f"Historical context generation failed: {e}")
        return {
            "similar_events": [],
            "pattern_summary": "Unable to analyze historical patterns at this time.",
            "key_factors": ["Data unavailable", "Analysis error", "Technical issues"],
            "what_to_watch": ["Market conditions", "Economic data", "Global developments"],
            "disclaimer": "This is historical analysis only and not financial advice. Past performance does not guarantee future results."
        }