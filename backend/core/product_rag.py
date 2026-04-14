import httpx
import asyncio
import logging
import time
import re
import hashlib
from typing import List, Dict, Optional, Generator
from bs4 import BeautifulSoup
from core.embeddings import store_in_collection, search_collection
from core.rag_chain import get_groq_client, MODEL_NAME
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

PRODUCTS_COLLECTION = "products_knowledge"
MAX_CRAWL_PAGES = 30
CHUNK_SIZE = 350
OVERLAP = 60

# ─── Crawl targets ────────────────────────────────────────────────────────────

CRAWL_TARGETS = [

    {
    "name": "Zerodha Varsity",
    "base_url": "https://zerodha.com",
    "crawl_urls": [
        "https://zerodha.com/varsity/",
    ],
    "category": "education",
},

{
    "name": "SEBI Investor Education",
    "base_url": "https://www.sebi.gov.in",
    "crawl_urls": [
        "https://www.sebi.gov.in/sebiweb/investor-charter.html",
        "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=7&ssid=0&smid=0",
    ],
    "category": "investments",
},

    {
        "name": "RBI Financial Education",
        "base_url": "https://www.rbi.org.in",
        "crawl_urls": [
            "https://www.rbi.org.in/financialeducation/",
        ],
        "category": "education",
    },

    {
        "name": "IRDAI Policyholder Education",
        "base_url": "https://policyholder.gov.in",
        "crawl_urls": [
            "https://policyholder.gov.in/",
        ],
        "category": "insurance",
    },

    {
        "name": "ET Money Learn",
        "base_url": "https://www.etmoney.com",
        "crawl_urls": [
            "https://www.etmoney.com/learn/",
        ],
        "category": "investments",
    },

    {
        "name": "Groww Learn",
        "base_url": "https://groww.in",
        "crawl_urls": [
            "https://groww.in/blog",
        ],
        "category": "investments",
    },

    {
        "name": "BankBazaar Guides",
        "base_url": "https://www.bankbazaar.com",
        "crawl_urls": [
            "https://www.bankbazaar.com/credit-card.html",
            "https://www.bankbazaar.com/personal-loan.html",
            "https://www.bankbazaar.com/health-insurance.html",
        ],
        "category": "credit_cards",
    },

]
# ─── Crawling functions ───────────────────────────────────────────────────────

async def fetch_page(url: str, client: httpx.AsyncClient) -> Optional[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FinSightAI-Educational/1.0; +https://finsight.ai)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    try:
        response = await client.get(url, headers=headers, timeout=20.0)
        if response.status_code != 200:
            logger.warning(f"HTTP {response.status_code} for {url}")
            return None
        if "text/html" not in response.headers.get("content-type", ""):
            return None
        return response.text
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def extract_text_from_html(html: str, source_name: str, url: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()

    content = None
    for selector in ["article", "main", ".content", ".post-content", "#content", ".article-body", "body"]:
        content = soup.select_one(selector)
        if content:
            break
    if not content:
        content = soup

    paragraphs = [p.get_text(separator=" ") for p in content.find_all("p")]
    headings = [h.get_text(separator=" ") for h in content.find_all(["h1", "h2", "h3"])]
    list_items = [li.get_text(separator=" ") for li in content.find_all("li")]
    combined_text = " ".join(paragraphs + headings + list_items)
    combined_text = re.sub(r'\s+', ' ', combined_text).strip()
    combined_text = re.sub(r'[^\x00-\x7F₹%.,\-()]', '', combined_text)

    if len(combined_text) < 200:
        return []

    words = combined_text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + CHUNK_SIZE]
        chunk_text = " ".join(chunk_words)
        chunks.append({
            "text": chunk_text,
            "source_name": source_name,
            "url": url,
            "category": "",
            "chunk_index": len(chunks),
            "content_hash": hashlib.md5(chunk_text.encode()).hexdigest(),
        })
        i += CHUNK_SIZE - OVERLAP

    return chunks


async def crawl_target(target: Dict) -> List[Dict]:
    logger.info(f"Crawling {target['name']} ({len(target['crawl_urls'])} URLs)")
    all_chunks = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for url in target["crawl_urls"]:
            html = await fetch_page(url, client)
            if html:
                chunks = extract_text_from_html(html, target["name"], url)
                for chunk in chunks:
                    chunk["category"] = target["category"]
                all_chunks.extend(chunks)
            await asyncio.sleep(2)
    logger.info(f"Got {len(all_chunks)} chunks from {target['name']}")
    return all_chunks


async def crawl_all_targets() -> int:
    logger.info("Starting full product knowledge crawl")
    start_time = time.time()
    all_chunks = []

    for target in CRAWL_TARGETS:
        try:
            chunks = await crawl_target(target)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.error(f"Failed to crawl {target['name']}: {e}")

    # Deduplicate
    seen = set()
    unique = []
    for c in all_chunks:
        if c["content_hash"] not in seen:
            seen.add(c["content_hash"])
            unique.append(c)
    logger.info(f"Deduplication: {len(all_chunks)} → {len(unique)} chunks")

    if not unique:
        logger.error("No chunks crawled — check network and target URLs")
        return 0

    texts = [c["text"] for c in unique]
    metadatas = [{
        "source": c["source_name"],
        "url": c["url"],
        "category": c["category"],
        "chunk_index": c["chunk_index"],
    } for c in unique]

    try:
        store_in_collection(
            texts=texts,
            metadatas=metadatas,
            collection_name=PRODUCTS_COLLECTION,
            id_prefix="product",
        )
    except Exception as e:
        logger.error(f"Failed to store in ChromaDB: {e}")
        return 0

    elapsed = time.time() - start_time
    logger.info(f"Crawl complete: {len(unique)} chunks stored in {elapsed:.1f}s")
    return len(unique)


async def initialize_product_knowledge() -> bool:
    logger.info("Initializing product knowledge base")
    try:
        from core.embeddings import get_chroma_client
        client = get_chroma_client()
        collection = client.get_collection(PRODUCTS_COLLECTION)
        count = collection.count()
        if count > 500:
            logger.info(f"Product knowledge already populated ({count} chunks), skipping crawl")
            return True
        logger.info("Product knowledge empty, starting crawl…")
        await crawl_all_targets()
        return True
    except Exception as e:
        logger.info(f"Collection not found or empty, crawling: {e}")
        await crawl_all_targets()
        return True


# ─── Profile parser ───────────────────────────────────────────────────────────

def parse_user_profile(query: str) -> str:
    """
    Detects profile signals in the query and prepends a structured summary
    so the LLM can use it for profile-based recommendations.
    """
    q = query.lower()

    profile_parts = []

    # Occupation
    if any(w in q for w in ["student", "college", "university", "btech", "mba"]):
        profile_parts.append("occupation: student")
    elif any(w in q for w in ["salaried", "job", "employee", "working"]):
        profile_parts.append("occupation: salaried employee")
    elif any(w in q for w in ["self employed", "freelancer", "business", "entrepreneur"]):
        profile_parts.append("occupation: self-employed")
    elif any(w in q for w in ["retired", "senior", "pensioner"]):
        profile_parts.append("occupation: retired")

    # Income
    income_match = re.search(
        r'(?:income|salary|earn|earning|package)[^\d]*?(\d[\d,\.]*)\s*(lakh|l|k|thousand|crore)?',
        q
    )
    if income_match:
        profile_parts.append(f"income: ₹{income_match.group(1)} {income_match.group(2) or ''}".strip())

    # Age
    age_match = re.search(r'(\d{1,2})\s*(?:year|yr)s?\s*old|age\s*(\d{1,2})', q)
    if age_match:
        age = age_match.group(1) or age_match.group(2)
        profile_parts.append(f"age: {age}")

    # Dependents
    if any(w in q for w in ["child", "kid", "son", "daughter", "baby", "family"]):
        profile_parts.append("has dependents: yes")

    # Intent
    if any(w in q for w in ["credit card", "card"]):
        profile_parts.append("intent: credit card")
    if any(w in q for w in ["insurance", "cover", "policy"]):
        profile_parts.append("intent: insurance")
    if any(w in q for w in ["mutual fund", "sip", "invest", "fd", "fixed deposit"]):
        profile_parts.append("intent: investment")
    if any(w in q for w in ["loan", "emi", "borrow"]):
        profile_parts.append("intent: loan")

    if profile_parts:
        return f"[User Profile Detected: {' | '.join(profile_parts)}]\n\nQuery: {query}"
    return query


# ─── RAG functions ────────────────────────────────────────────────────────────

def semantic_product_search(query: str, k: int = 8) -> List[Dict]:
    try:
        enriched_query = parse_user_profile(query)
        results = search_collection(enriched_query, PRODUCTS_COLLECTION, k)
        return results
    except Exception as e:
        logger.error(f"Error in semantic_product_search: {e}")
        return []
PRODUCT_SYSTEM_PROMPT = """You are FinSight AI, a financial product education assistant for Indian users.

Your task is to help users understand which types of financial products suit their profile using the retrieved knowledge below AND commonly known example Indian financial products for educational illustration.

PROFILE-BASED RECOMMENDATIONS:
- When the user gives you their profile (student, income, age, family), tailor your response to that profile.
- For students: focus on zero-fee credit cards, beginner SIP options, low-premium insurance plans.
- For salaried users: focus on cashback/rewards credit cards, health insurance, term insurance, SIP investments.
- For self-employed users: focus on flexible insurance plans, business credit cards, tax-saving investments.
- For retirees: focus on health insurance, fixed deposits, pension plans.

CREDIT CARD GUIDANCE:
- Mention annual fee, key benefits (cashback, rewards, lounge access), and income eligibility.
- Provide 2–4 example Indian credit cards that typically suit the user’s profile.
- Do NOT present any single card as “the best”.
- Use phrasing like:
  "Cards that typically suit this profile include..."

INSURANCE GUIDANCE:
- Mention coverage amount, premium range, and claim settlement ratio if available.
- Clearly distinguish between term insurance, health insurance, ULIP, and endowment plans.
- Provide 2–4 example Indian plans where relevant.
- For children: include example education plans such as:
  LIC Jeevan Tarun,
  SBI Smart Scholar,
  HDFC Life YoungStar Udaan,
  ICICI Pru Smart Kid Solution.

INVESTMENT GUIDANCE:
- For students/beginners: suggest SIP in index funds or ELSS.
- Provide example categories like Nifty 50 index funds or tax-saving ELSS funds.
- Never recommend specific stocks or promise returns.

STRICT RULES:
1. Base your answer primarily on the provided context. If context is limited, you may include well-known example Indian financial products for educational illustration.
2. Never say "buy X" or "I recommend Y product".
3. Use wording like:
   "Products that typically suit this profile include..."
4. Always end with:
   "This is educational information only. Please consult a SEBI/IRDAI-registered advisor before purchasing any financial product."
5. Cite sources at the end as:
   Sources: [source names]
6. Use ₹ for amounts.
7. Keep response under 300 words.
8. Use bullet points for product features. Keep the response clear and scannable.
"""

def stream_product_answer(query: str, context_chunks: List[Dict]) -> Generator:
    try:
        client = get_groq_client()

        # Build context with source attribution
        context_parts = []
        for chunk in context_chunks:
            source = chunk.get('metadata', {}).get('source', 'Unknown')
            url = chunk.get('metadata', {}).get('url', '')
            context_parts.append(f"[Source: {source} | {url}]\n{chunk['text']}")
        context = "\n\n---\n\n".join(context_parts)

        # Enrich query with profile signals
        enriched_query = parse_user_profile(query)

        user_message = f"RETRIEVED PRODUCT KNOWLEDGE:\n{context}\n\nUSER QUERY:\n{enriched_query}"

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": PRODUCT_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            stream=True,
            max_tokens=1024,
            temperature=0.3,
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

        # Append sources
        sources = list({
            chunk.get('metadata', {}).get('source', 'Unknown')
            for chunk in context_chunks
        })
        yield f"\n\n**Sources:** {', '.join(sources)}"

    except Exception as e:
        logger.error(f"Error in stream_product_answer: {e}")
        yield "Error: Could not generate response. Please try again."


def get_knowledge_base_stats() -> Dict:
    try:
        from core.embeddings import get_chroma_client
        client = get_chroma_client()
        collection = client.get_collection(PRODUCTS_COLLECTION)
        count = collection.count()
        return {
            "total_chunks": count,
            "collection_name": PRODUCTS_COLLECTION,
            "status": "ready" if count > 100 else "loading",
        }
    except Exception as e:
        logger.error(f"Failed to get knowledge base stats: {e}")
        return {"total_chunks": 0, "status": "unavailable"}