from groq import Groq, APIConnectionError, RateLimitError
import os
import logging
import time
import json
from typing import List, Dict, Generator, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "llama-3.3-70b-versatile"
MAX_TOKENS = 1024
TEMPERATURE = 0.3

FINANCIAL_ASSISTANT_PROMPT = """
You are FinSight AI, a financial literacy assistant. Your only job is to help 
people understand financial documents, products, concepts, and markets in plain 
English.

Rules you must never break:
1. Never recommend buying or selling any stock, mutual fund, or financial product
2. Never tell a user what financial decision to make
3. Never predict market movements or future prices
4. If asked for advice, say: "I can only explain — for personalized advice, 
   please consult a SEBI-registered financial advisor"
5. Always base your answers on the context provided below
6. If the answer is not in the context, say so clearly — do not guess
7. Use simple language. Avoid jargon. If you must use a term, explain it immediately
8. Be concise. Most answers should be 3-5 sentences unless the user asks for detail
9. When explaining a risky clause or fee, be direct and clear about what it means 
   for the user financially
10. Always cite which part of the document you're referring to when possible

You are not a lawyer, CA, or financial advisor. You are an explainer.
"""

COMPARISON_PROMPT = """
You are FinSight AI. You are comparing two financial products.

Rules:
1. Describe which product suits which type of user based on their profile — 
   do NOT say "choose product A" or "product B is better"
2. Frame everything as: "Product A may suit someone who... while Product B may 
   suit someone who..."
3. Highlight gaps neutrally — missing features are facts, not judgements
4. Maximum 150 words
5. No investment advice. No recommendations.
"""

MARKET_EXPLAINER_PROMPT = """
You are FinSight AI, a market literacy assistant.

Rules:
1. Explain market events and movements in plain English
2. Always provide historical context when available
3. Never predict future market movements
4. Never say what to buy, sell, or hold
5. If the user asks for a prediction, explain why markets are unpredictable instead
6. Structure your response clearly with the causes, context, and what signals 
   to monitor — purely for educational awareness, not action
"""

CALCULATOR_EXPLAINER_PROMPT = """
You are FinSight AI. A user has just run a financial calculation.
Explain the result in plain English. Cover:
1. What the number actually means in real life
2. What assumptions drive this result (interest rate, time, frequency)
3. What real-world factors could make the actual result higher or lower
4. One concrete analogy or comparison to make the number feel tangible
Keep it under 5 sentences. No investment advice.
"""

_groq_client = None

def get_groq_client() -> Groq:
    """Get or initialize the Groq client singleton."""
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set in .env")
        _groq_client = Groq(api_key=GROQ_API_KEY)
        logger.info("Groq client initialized")
    return _groq_client

def stream_rag_answer(question: str, context_chunks: List[Dict], session_id: str) -> Generator[str, None, None]:
    """Stream a RAG-based answer to a user question using retrieved document chunks."""
    try:
        client = get_groq_client()
        context_parts = [f"[Page {chunk['page']}]\n{chunk['text']}" for chunk in context_chunks]
        context = '\n---\n'.join(context_parts)
        words = context.split()
        if len(words) > 6000:
            context = ' '.join(words[:6000])
            logger.warning(f"Truncated context to 6000 words for session {session_id}")
        
        messages = [
            {"role": "system", "content": FINANCIAL_ASSISTANT_PROMPT},
            {"role": "user", "content": f"DOCUMENT CONTEXT:\n{context}\n\nQUESTION: {question}"}
        ]
        
        logger.info(f"Streaming answer for session {session_id}, question length: {len(question)}")
        start_time = time.time()
        
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            stream=True
        )
        
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
        
        logger.info(f"Stream completed in {time.time() - start_time:.2f}s for session {session_id}")
    
    except APIConnectionError:
        yield "Error: Could not connect to AI service."
    except RateLimitError:
        yield "Error: Rate limit reached. Please wait a moment."
    except Exception as e:
        logger.error(f"Error in stream_rag_answer for session {session_id}: {e}")
        yield f"Error: {str(e)}"

def get_document_type_and_terms(context_chunks: List[Dict]) -> Dict:
    """Use LLM to classify document type and extract key terms as fallback."""
    try:
        client = get_groq_client()
        combined_text = ' '.join([chunk['text'] for chunk in context_chunks[:3]])[:7500]  # approx 1500 words
        
        messages = [
            {"role": "system", "content": "You are a financial document classifier. Respond only in JSON."},
            {"role": "user", "content": f"""
Analyze this text from the beginning of a financial document.
Return a JSON object with exactly these fields:
- "document_type": one of ["Loan Agreement", "Credit Card Agreement", 
  "Insurance Policy", "Brokerage Agreement", "Mutual Fund Document", 
  "Fixed Deposit Document", "Financial Document"]
- "key_terms": list of up to 8 strings, each being a key financial term 
  found in this document with its value if present 
  (e.g. "Interest Rate: 12.5% p.a.", "Late Fee: ₹500")

Document text:
{combined_text}

Return only valid JSON. No explanation.
"""}
        ]
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=300,
            temperature=0.1
        )
        
        result = json.loads(response.choices[0].message.content.strip())
        return result
    
    except Exception as e:
        logger.error(f"Error in get_document_type_and_terms: {e}")
        return {"document_type": "Financial Document", "key_terms": []}

def get_comparison_summary(product_a: Dict, product_b: Dict, product_type: str, comparison_rows: List[Dict], gaps: List[str]) -> str:
    """Generate a neutral comparison summary using LLM."""
    try:
        client = get_groq_client()
        
        key_diffs = [f"- {r['attribute']}: A={r['value_a']}, B={r['value_b']}" 
                     for r in comparison_rows if r['winner'] != 'tie']
        
        messages = [
            {"role": "system", "content": COMPARISON_PROMPT},
            {"role": "user", "content": f"""
Product Type: {product_type}

Product A: {product_a.get('name', 'Product A')}
Product B: {product_b.get('name', 'Product B')}

Key differences:
{chr(10).join(key_diffs)}

Gaps:
{chr(10).join(gaps) if gaps else 'None identified'}

Write a neutral 2-paragraph summary. No recommendations.
"""}
        ]
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=300,
            temperature=0.4
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        logger.error(f"Error in get_comparison_summary: {e}")
        return "Summary unavailable."

def explain_calculation(calc_type: str, params: Dict, result: float, yearly_breakdown: List[Dict]) -> tuple[str, List[str]]:
    """Explain a financial calculation result using LLM."""
    try:
        client = get_groq_client()
        
        duration = params.get('duration_years', params.get('tenure_months', 'N/A'))
        duration_unit = 'years' if 'duration_years' in params else 'months'
        
        messages = [
            {"role": "system", "content": CALCULATOR_EXPLAINER_PROMPT},
            {"role": "user", "content": f"""
Calculation type: {calc_type}
Input parameters: {params}
Final result: ₹{result:,.0f}
Duration: {duration} {duration_unit}

Respond in JSON with exactly these fields:
- "explanation": string (3-5 sentences)
- "risk_notes": list of exactly 3 short strings (max 15 words each)

Return only valid JSON.
"""}
        ]
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=400,
            temperature=0.2
        )
        
        result_data = json.loads(response.choices[0].message.content.strip())
        return result_data["explanation"], result_data["risk_notes"]
    
    except Exception as e:
        logger.error(f"Error in explain_calculation: {e}")
        return ("Calculation complete. See the breakdown above.", 
                ["Returns may vary with market conditions",
                 "Inflation reduces real purchasing power", 
                 "Past rates do not guarantee future returns"])

def explain_market_query(query: str, context_chunks: List[Dict]) -> Dict:
    """Explain a market-related query using retrieved context."""
    try:
        client = get_groq_client()
        
        context_parts = [f"[Source: {chunk.get('metadata', {}).get('source', 'Unknown')}]\n{chunk['text']}" 
                        for chunk in context_chunks]
        context = '\n---\n'.join(context_parts)
        words = context.split()
        if len(words) > 6000:
            context = ' '.join(words[:6000])
        
        messages = [
            {"role": "system", "content": MARKET_EXPLAINER_PROMPT},
            {"role": "user", "content": f"""
Context from knowledge base:
{context}

User question: {query}

Respond in JSON with exactly these fields:
- "possible_reasons": list of 2-4 strings (if query is about why something happened)
- "background": string (2 sentences of context)
- "historical_context": string (one real historical parallel, or empty string)
- "what_to_watch": list of 2-3 short monitoring signals (informational only)
- "sources_used": list of source names from the context metadata

Return only valid JSON.
"""}
        ]
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=600,
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content.strip())
        return result
    
    except Exception as e:
        logger.error(f"Error in explain_market_query: {e}")
        return {
            "possible_reasons": [],
            "background": "",
            "historical_context": "",
            "what_to_watch": [],
            "sources_used": []
        }
