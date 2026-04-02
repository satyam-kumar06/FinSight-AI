import httpx
import asyncio
import logging
import time
import re
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
from core.embeddings import store_in_collection, search_collection
from core.rag_chain import get_groq_client, MODEL_NAME
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# CONSTANTS
PRODUCTS_COLLECTION = "products_knowledge"
MAX_CRAWL_PAGES = 30   # per domain, to avoid hammering servers
CHUNK_SIZE = 350        # words per chunk
OVERLAP = 60            # word overlap between chunks

# SECTION 1 — TARGET WEBSITES CONFIG

CRAWL_TARGETS = [
    {
        "name": "Finshots",
        "base_url": "https://finshots.in",
        "crawl_urls": [
            "https://finshots.in/archive/",
            "https://finshots.in/tag/insurance/",
            "https://finshots.in/tag/personal-finance/"
        ],
        "category": "education",
        "respect_robots": True
    },
    {
        "name": "Zerodha Varsity",
        "base_url": "https://zerodha.com/varsity",
        "crawl_urls": [
            "https://zerodha.com/varsity/module/personalfinance/",
            "https://zerodha.com/varsity/module/insurance/",
            "https://zerodha.com/varsity/module/mutualfunds/"
        ],
        "category": "education",
        "respect_robots": True
    },
    {
        "name": "IRDAI Consumer Education",
        "base_url": "https://irdai.gov.in",
        "crawl_urls": [
            "https://irdai.gov.in/consumer-education",
            "https://irdai.gov.in/faqs"
        ],
        "category": "insurance",
        "respect_robots": True
    },
    {
        "name": "RBI Financial Education",
        "base_url": "https://rbi.org.in",
        "crawl_urls": [
            "https://rbi.org.in/scripts/FS_FinancialEducation.aspx"
        ],
        "category": "education",
        "respect_robots": True
    },
    {
        "name": "SEBI Investor Education",
        "base_url": "https://investor.sebi.gov.in",
        "crawl_urls": [
            "https://investor.sebi.gov.in/"
        ],
        "category": "investments",
        "respect_robots": True
    },
    {
        "name": "NPS Trust",
        "base_url": "https://www.npstrust.org.in",
        "crawl_urls": [
            "https://www.npstrust.org.in/content/about-nps"
        ],
        "category": "investments",
        "respect_robots": True
    }
]

# SECTION 2 — CRAWLING FUNCTIONS

async def fetch_page(url: str, client: httpx.AsyncClient) -> Optional[str]:
    """
    Fetches a webpage asynchronously with proper headers and error handling.
    """
    logger.info(f"Fetching page: {url}")
    headers = {"User-Agent": "FinSightAI-Educational-Crawler/1.0 (educational project; contact: finsight@example.com)"}
    try:
        response = await client.get(url, headers=headers, timeout=15.0)
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
    """
    Extracts and chunks text content from HTML.
    """
    logger.info(f"Extracting text from {url}")
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove unwanted tags
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    
    # Find main content
    content = None
    selectors = ["article", "main", ".content", ".post-content", "#content", "body"]
    for selector in selectors:
        content = soup.select_one(selector)
        if content:
            break
    
    if not content:
        content = soup
    
    # Extract paragraphs and headings
    paragraphs = [p.get_text() for p in content.find_all("p")]
    headings = [h.get_text() for h in content.find_all(["h1", "h2", "h3"])]
    combined_text = " ".join(paragraphs + headings)
    
    # Clean text
    combined_text = re.sub(r'\s+', ' ', combined_text).strip()
    lines = combined_text.split('\n')
    cleaned_lines = [line for line in lines if len(line.strip()) >= 30]
    combined_text = ' '.join(cleaned_lines)
    # Remove non-ASCII except ₹ and punctuation
    combined_text = re.sub(r'[^\x00-\x7F₹]', '', combined_text)
    
    if len(combined_text) < 200:
        return []
    
    # Chunk the text
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
            "category": "",  # filled by caller
            "chunk_index": len(chunks),
            "content_hash": hashlib.md5(chunk_text.encode()).hexdigest()
        })
        i += CHUNK_SIZE - OVERLAP
    
    return chunks

async def crawl_target(target: Dict) -> List[Dict]:
    """
    Crawls a single target website and extracts chunks.
    """
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
            await asyncio.sleep(2)  # Polite delay
    logger.info(f"Got {len(all_chunks)} chunks from {target['name']}")
    return all_chunks

async def crawl_all_targets() -> int:
    """
    Crawls all target websites and stores chunks in ChromaDB.
    """
    logger.info("Starting full product knowledge crawl")
    start_time = time.time()
    all_chunks = []
    for target in CRAWL_TARGETS:
        try:
            chunks = await crawl_target(target)
            all_chunks.extend(chunks)
            logger.info(f"Completed {target['name']}, total chunks so far: {len(all_chunks)}")
        except Exception as e:
            logger.error(f"Failed to crawl {target['name']}: {e}")
    
    # Deduplicate
    before = len(all_chunks)
    seen_hashes = set()
    unique_chunks = []
    for chunk in all_chunks:
        if chunk["content_hash"] not in seen_hashes:
            seen_hashes.add(chunk["content_hash"])
            unique_chunks.append(chunk)
    all_chunks = unique_chunks
    logger.info(f"Deduplication: {before} → {len(all_chunks)} chunks")
    
    if not all_chunks:
        logger.error("No chunks crawled — check network and target URLs")
        return 0
    
    texts = [c["text"] for c in all_chunks]
    metadatas = [{"source": c["source_name"], "url": c["url"], 
                  "category": c["category"], "chunk_index": c["chunk_index"]} 
                 for c in all_chunks]
    
    try:
        store_in_collection(
            texts=texts,
            metadatas=metadatas,
            collection_name=PRODUCTS_COLLECTION,
            id_prefix="product"
        )
    except Exception as e:
        logger.error(f"Failed to store in ChromaDB: {e}")
        return 0
    
    elapsed = time.time() - start_time
    logger.info(f"Crawl complete: {len(all_chunks)} chunks stored in {elapsed:.1f}s")
    return len(all_chunks)

async def initialize_product_knowledge() -> bool:
    """
    Initializes the product knowledge base at server startup.
    """
    logger.info("Initializing product knowledge base")
    try:
        from core.embeddings import get_chroma_client
        client = get_chroma_client()
        collection = client.get_collection(PRODUCTS_COLLECTION)
        count = collection.count()
        if count > 500:
            logger.info(f"Product knowledge base already populated ({count} chunks), skipping crawl")
            return True
        else:
            logger.info("Product knowledge base empty, starting initial crawl")
            await crawl_all_targets()
            return True
    except Exception as e:
        logger.error(f"Failed to initialize product knowledge: {e}")
        return False

# SECTION 3 — RAG QUERY FUNCTION

def answer_product_question(
    question: str,
    category_filter: Optional[str] = None
) -> Dict:
    """
    Answers a natural language question about financial products using RAG.
    """
    logger.info(f"Product question received: {question[:80]}")
    try:
        search_query = question
        k = 6
        results = search_collection(
            query=search_query,
            collection_name=PRODUCTS_COLLECTION,
            k=k
        )
        
        if not results:
            return {
                "answer": "I don't have enough product information to answer this yet. The knowledge base may still be loading. Please try again in a few minutes.",
                "sources": [],
                "category": category_filter or "general",
                "disclaimer": "This is educational information only, not financial advice."
            }
        
        # Filter by category if provided
        if category_filter:
            filtered = [r for r in results if r["metadata"].get("category") == category_filter]
            if len(filtered) >= 2:
                results = filtered
        
        # Build context
        context_parts = []
        sources = []
        for r in results:
            context_parts.append(f"[Source: {r['metadata']['source']}]\n{r['text']}")
            source = {"name": r["metadata"]["source"], "url": r["metadata"]["url"]}
            if source not in sources:
                sources.append(source)
        
        context = "\n\n---\n\n".join(context_parts)
        
        client = get_groq_client()
        system_prompt = """
You are FinSight AI, a financial product education assistant for Indian users.

Your job is to help users understand financial products — insurance plans,
loans, investments — based on the retrieved knowledge below.

Rules:
1. Base your answer ONLY on the provided context. If context is insufficient,
   say so clearly and suggest the user visit the source websites directly.
2. For questions like "which insurance is best for my child" — describe the
   types of plans that typically suit that profile based on the context.
   Never say "buy X" or "choose Y". Say "plans that typically cover this 
   profile include..." or "based on IRDAI guidelines, plans with these 
   features would be relevant..."
3. Always mention coverage amounts, premium ranges, or key conditions 
   when the context contains them.
4. End every answer with the disclaimer:
   "This is educational information. Please consult a SEBI/IRDAI-registered 
   advisor before purchasing any financial product."
5. Cite your sources at the end as: Sources: [source names]
6. Write in plain English. Use ₹ for amounts. Keep answer under 200 words.
"""
        
        user_message = f"""
Retrieved context from financial knowledge base:
{context}

User question: {question}

Answer the question based only on the context above.
"""
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        answer_text = response.choices[0].message.content.strip()
        
        return {
            "answer": answer_text,
            "sources": sources,
            "category": category_filter or "general",
            "chunks_used": len(results),
            "disclaimer": "Educational only. Not financial advice."
        }
    except Exception as e:
        logger.error(f"Failed to answer product question: {e}")
        return {
            "answer": "Sorry, I encountered an error while processing your question. Please try again later.",
            "sources": [],
            "category": category_filter or "general",
            "disclaimer": "This is educational information only, not financial advice."
        }

def get_knowledge_base_stats() -> Dict:
    """
    Returns statistics about the product knowledge base.
    """
    logger.info("Getting knowledge base stats")
    try:
        from core.embeddings import get_chroma_client
        client = get_chroma_client()
        collection = client.get_collection(PRODUCTS_COLLECTION)
        count = collection.count()
        return {
            "total_chunks": count,
            "collection_name": PRODUCTS_COLLECTION,
            "status": "ready" if count > 100 else "loading"
        }
    except Exception as e:
        logger.error(f"Failed to get knowledge base stats: {e}")
        return {"total_chunks": 0, "status": "unavailable"}
