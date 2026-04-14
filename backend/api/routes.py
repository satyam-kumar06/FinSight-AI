from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query, Depends, Request
from fastapi.responses import StreamingResponse

import logging
import uuid
import time
import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from api.models import UploadResponse, ChatRequest, ClausesResponse, MarketExplainResponse, NewsResponse, NewsExplainRequest
from core.document_processor import process_pdf, detect_document_type, extract_key_terms
from core.embeddings import embed_and_store, semantic_search, delete_session, search_collection
from core.rag_chain import stream_rag_answer, get_document_type_and_terms, get_comparison_summary, explain_market_query
from core.clause_detector import detect_risky_clauses, format_clauses_for_response
from core.product_rag import semantic_product_search, stream_product_answer
from core.market_knowledge import MARKET_COLLECTION
from core.news_crawler import get_recent_news, crawl_and_store
from core.historical_patterns import analyze_patterns

router = APIRouter()
logger = logging.getLogger(__name__)

# Request logging dependency
async def log_request(request: Request):
    start_time = time.time()
    logger.info(f"Request: {request.method} {request.url.path}")
    try:
        yield
    finally:
        process_time = time.time() - start_time
        logger.info(f"Request completed in {process_time:.3f}s")

# Pydantic models for requests
class ProductSearchRequest(BaseModel):
    query: str

@router.post("/upload", response_model=UploadResponse, dependencies=[Depends(log_request)])
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and process a PDF document.
    
    Validates file type and size, extracts text, detects document type,
    and stores embeddings for later retrieval.
    """
    try:
        # Validate file type
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Validate file size (20MB limit)
        file_size = 0
        content = await file.read()
        file_size = len(content)
        if file_size > 20 * 1024 * 1024:  # 20MB
            raise HTTPException(status_code=400, detail="File size must be less than 20MB")
        
        start_time = time.time()
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Process PDF
        chunks, page_count = process_pdf(content)
        if not chunks:
            raise HTTPException(status_code=400, detail="Could not extract text from the document")
        
        # Store embeddings
        embed_and_store(chunks, session_id)
        
        # Detect document type
        document_type = detect_document_type(chunks)
        if document_type == "Financial Document":
            # Use LLM for more precise classification
            document_type = get_document_type_and_terms(chunks).get("document_type", document_type)
        
        # Extract key terms
        key_terms = extract_key_terms(chunks)
        
        processing_time = time.time() - start_time
        logger.info(f"Document processed in {processing_time:.2f}s")
        
        return UploadResponse(
            session_id=session_id,
            document_type=document_type,
            page_count=page_count,
            key_terms=key_terms,
            message="Document processed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during document processing")

@router.post("/chat", dependencies=[Depends(log_request)])
async def chat_with_document(request: ChatRequest):
    """
    Answer questions about an uploaded document using RAG.
    
    Performs semantic search on document chunks and streams
    the AI-generated answer.
    """
    try:
        if not request.session_id:
            raise HTTPException(status_code=400, detail="Session ID is required")
        
        # Search for relevant chunks
        chunks = semantic_search(request.question, request.session_id, k=5)
        
        if not chunks:
            async def no_results_generator():
                yield "I couldn't find relevant information in your document for this question."
            return StreamingResponse(no_results_generator(), media_type="text/plain")
        
        # Stream RAG answer
        generator = stream_rag_answer(request.question, chunks, request.session_id)
        return StreamingResponse(generator, media_type="text/plain")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during chat processing")

@router.get("/clauses", response_model=ClausesResponse, dependencies=[Depends(log_request)])
async def get_risky_clauses(session_id: str = Query(..., description="Session ID of the uploaded document")):
    """
    Detect and analyze risky clauses in a financial document.
    
    Uses semantic search to find policy-relevant sections and
    identifies potential risk clauses.
    """
    try:
        # Search for policy-relevant chunks
        chunks = semantic_search("penalty fee risk clause obligation", session_id, k=15)
        
        # Detect risky clauses
        clauses = detect_risky_clauses(chunks)
        
        # Format for response
        formatted_clauses = format_clauses_for_response(clauses)
        
        return ClausesResponse(
            session_id=session_id,
            clauses=formatted_clauses,
            total_found=len(formatted_clauses)
        )
        
    except Exception as e:
        logger.error(f"Clause detection failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during clause analysis")

@router.post("/products/search", dependencies=[Depends(log_request)])
async def search_products(body: ProductSearchRequest):
    """
    Search for financial products using semantic search.
    
    Finds relevant product information and streams AI-generated
    explanations and comparisons.
    """
    try:
        if len(body.query) < 5 or len(body.query) > 500:
            raise HTTPException(status_code=400, detail="Query must be between 5 and 500 characters")
        
        # Search product knowledge base
        chunks = semantic_product_search(body.query, k=6)
        
        if not chunks:
            async def loading_message_generator():
                yield "The product knowledge base is still loading. Please try again in a moment."
            return StreamingResponse(loading_message_generator(), media_type="text/plain")
        
        # Stream product answer
        generator = stream_product_answer(body.query, chunks)
        return StreamingResponse(generator, media_type="text/plain")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Product search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during product search")

@router.get("/market/explain", response_model=MarketExplainResponse, dependencies=[Depends(log_request)])
async def explain_market_concept(query: str = Query(..., min_length=3, description="Market concept or question to explain")):
    """
    Explain market concepts using the financial knowledge base.
    
    Searches market knowledge and provides AI-generated explanations
    of financial terms, concepts, and market mechanics.
    """
    try:
        # Search market knowledge base
        chunks = search_collection(query, MARKET_COLLECTION, k=3)
        
        # Get explanation
        explanation = explain_market_query(query, chunks)
        
        return MarketExplainResponse(**explanation)
        
    except Exception as e:
        logger.error(f"Market explanation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during market explanation")

@router.get("/market/patterns", dependencies=[Depends(log_request)])
async def get_market_patterns(query: str = Query(..., description="Query to find historical market patterns")):
    """
    Analyze historical market patterns for similar events.
    
    Finds past market events similar to the current situation
    and provides historical context and patterns.
    """
    try:
        patterns = analyze_patterns(query)
        return patterns
        
    except Exception as e:
        logger.error(f"Pattern analysis failed: {e}")
        return {
            "error": "Pattern analysis unavailable",
            "disclaimer": "This is historical analysis only and not financial advice. Past performance does not guarantee future results."
        }

@router.get("/news", response_model=NewsResponse, dependencies=[Depends(log_request)])
async def get_news_feed(
    limit: int = Query(30, ge=1, le=100, description="Number of articles to return"),
    category: Optional[str] = Query(None, description="Filter by news category")
):
    """
    Get recent financial news articles.
    
    Retrieves the latest news from RSS feeds and NewsAPI,
    filtered by category if specified.
    """
    try:
        articles = get_recent_news(limit, category)
        
        return NewsResponse(
            articles=articles,
            total=len(articles),
            last_updated=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"News retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during news retrieval")

@router.post("/news/explain", response_model=MarketExplainResponse, dependencies=[Depends(log_request)])
async def explain_news_event(body: NewsExplainRequest):
    """
    Explain a news event in market context.
    
    Combines news content with market knowledge to provide
    context and implications of current events.
    """
    try:
        # Build search query
        query = body.headline
        if body.url:
            query += f" {body.url}"
        
        # Search both collections
        news_chunks = search_collection(query, "news_articles", k=3)
        market_chunks = search_collection(query, MARKET_COLLECTION, k=2)
        combined_chunks = news_chunks + market_chunks
        
        # Get explanation
        explanation = explain_market_query(body.headline, combined_chunks)
        
        return MarketExplainResponse(**explanation)
        
    except Exception as e:
        logger.error(f"News explanation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during news analysis")

@router.delete("/session", dependencies=[Depends(log_request)])
async def delete_user_session(session_id: str = Query(..., description="Session ID to delete")):
    """
    Delete a user session and all associated data.
    
    Removes document embeddings and session data from the system.
    """
    try:
        delete_session(session_id)
        
        return {
            "message": "Session deleted",
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Session deletion failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during session deletion")
