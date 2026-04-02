import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io
import re
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_bytes: bytes) -> List[Dict]:
    logger.info("Starting text extraction from PDF")
    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text is None or len(text.strip()) < 30:
                logger.warning(f"Page {page_num} has no text, attempting OCR")
                images = convert_from_bytes(pdf_bytes, first_page=page_num, last_page=page_num, dpi=200)
                if images:
                    text = pytesseract.image_to_string(images[0])
            if text:
                # Clean text
                text = re.sub(r'\n{3,}', '\n\n', text)
                text = re.sub(r'[^\x20-\x7E\n]', '', text).strip()
                if text:
                    pages.append({"page": page_num, "text": text})
                else:
                    logger.info(f"Page {page_num} still empty after cleaning, skipping")
    return pages

def chunk_text(pages: List[Dict], chunk_size: int = 400, overlap: int = 80) -> List[Dict]:
    logger.info(f"Starting text chunking with chunk_size={chunk_size}, overlap={overlap}")
    if not pages:
        return []
    
    # Combine texts and track page boundaries
    combined_text = ''.join(page['text'] for page in pages)
    page_boundaries = []
    current_offset = 0
    for page in pages:
        page_boundaries.append((page['page'], current_offset, current_offset + len(page['text'])))
        current_offset += len(page['text'])
    
    # Split into words
    words = re.findall(r'\S+', combined_text)
    if not words:
        return []
    
    # Calculate word positions
    word_positions = []
    pos = 0
    for word in words:
        word_positions.append(pos)
        pos += len(word) + 1  # +1 for space
    
    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        start_word_idx = i
        end_word_idx = min(i + chunk_size, len(words))
        chunk_words = words[start_word_idx:end_word_idx]
        chunk_text = ' '.join(chunk_words)
        char_start = word_positions[start_word_idx] if start_word_idx < len(word_positions) else 0
        char_end = (word_positions[end_word_idx-1] + len(words[end_word_idx-1])) if end_word_idx > 0 else len(combined_text)
        
        # Determine page
        page = 1
        for p_num, p_start, p_end in page_boundaries:
            if char_start >= p_start and char_start < p_end:
                page = p_num
                break
        
        chunks.append({
            "chunk_index": len(chunks),
            "text": chunk_text,
            "word_count": len(chunk_words),
            "page": page,
            "char_start": char_start,
            "char_end": char_end
        })
    
    return chunks

def process_pdf(pdf_bytes: bytes) -> Tuple[List[Dict], int]:
    logger.info("Starting PDF processing")
    pages = extract_text_from_pdf(pdf_bytes)
    logger.info(f"Extracted text from {len(pages)} pages")
    chunks = chunk_text(pages)
    logger.info(f"Created {len(chunks)} chunks")
    return chunks, len(pages)

def detect_document_type(chunks: List[Dict]) -> str:
    logger.info("Detecting document type")
    if not chunks:
        return "Financial Document"
    
    text = ' '.join(chunk['text'] for chunk in chunks[:3])
    
    if re.search(r'loan agreement|term loan|home loan', text, re.I):
        return "Loan Agreement"
    elif re.search(r'credit card|card member agreement', text, re.I):
        return "Credit Card Agreement"
    elif re.search(r'insurance policy|policy document|sum insured', text, re.I):
        return "Insurance Policy"
    elif re.search(r'brokerage|demat|trading account', text, re.I):
        return "Brokerage Agreement"
    elif re.search(r'mutual fund|scheme information', text, re.I):
        return "Mutual Fund Document"
    elif re.search(r'fixed deposit|FD receipt', text, re.I):
        return "Fixed Deposit Document"
    else:
        return "Financial Document"

def extract_key_terms(chunks: List[Dict]) -> List[str]:
    logger.info("Extracting key terms")
    if not chunks:
        return []
    
    combined_text = ' '.join(chunk['text'] for chunk in chunks)
    terms = []
    financial_terms = [
        'APR', 'Annual Percentage Rate', 'Interest Rate', 'Late Payment Fee', 'Late Fee',
        'Annual Fee', 'Grace Period', 'Processing Fee', 'Prepayment Penalty',
        'Foreclosure Charges', 'EMI', 'Lock-in Period', 'Auto-renewal', 'Arbitration',
        'Deductible', 'Premium', 'Coverage Limit'
    ]
    
    for term in financial_terms:
        # Try to find with value
        match = re.search(rf'{re.escape(term)}\s*[:\-]?\s*(\d+(?:\.\d+)?%?)', combined_text, re.I)
        if match:
            terms.append(f"{term}: {match.group(1)}")
        elif re.search(rf'\b{re.escape(term)}\b', combined_text, re.I):
            terms.append(term)
    
    # Deduplicate and limit to 8
    unique_terms = list(set(terms))
    return unique_terms[:8]
