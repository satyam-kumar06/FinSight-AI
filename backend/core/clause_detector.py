import re
import logging
import time
from typing import List, Dict, Tuple, Optional
from core.rag_chain import get_groq_client, MODEL_NAME
import json

logger = logging.getLogger(__name__)

# SECTION 1 — RISKY CLAUSE PATTERN DICTIONARY

RISKY_PATTERNS = {
    "Prepayment Penalty": {
        "patterns": ["prepayment.*penalty", "early.*repayment.*fee", "foreclosure.*charge", "part.*payment.*charge"],
        "risk_level": "high",
        "plain_explanation": "You will be charged a fee if you repay your loan before the agreed tenure. This can cost you 1-4% of the outstanding amount."
    },
    "Auto-Renewal": {
        "patterns": ["auto.*renew", "automatic.*renewal", "automatically.*renewed", "renew.*unless.*cancel"],
        "risk_level": "high",
        "plain_explanation": "This plan renews automatically and charges you again unless you explicitly cancel before the renewal date."
    },
    "Arbitration Clause": {
        "patterns": ["arbitration", "binding.*arbitration", "dispute.*arbitration", "waive.*right.*court"],
        "risk_level": "high",
        "plain_explanation": "You may be giving up your right to take this company to court. Disputes must go through a private arbitration process instead."
    },
    "Variable Interest Rate": {
        "patterns": ["variable.*rate", "floating.*rate", "rate.*may.*change", "rate.*subject.*change", "linked.*to.*repo", "linked.*to.*base rate"],
        "risk_level": "high",
        "plain_explanation": "Your interest rate is not fixed. It can increase based on RBI repo rate changes or lender policy, raising your EMI without notice."
    },
    "Automatic Fee Increase": {
        "patterns": ["fee.*increase", "charges.*revised", "rates.*subject.*revision", "fees.*change.*notice"],
        "risk_level": "medium",
        "plain_explanation": "The lender can increase fees or charges with advance notice. Your costs may go up during the loan or policy tenure."
    },
    "Cross-Default Clause": {
        "patterns": ["cross.*default", "default.*on.*any.*loan", "event of default.*other"],
        "risk_level": "high",
        "plain_explanation": "If you default on any other loan anywhere, this lender can immediately declare your account in default too — even if you are current on this loan."
    },
    "Cancellation Penalty": {
        "patterns": ["cancellation.*fee", "surrender.*charge", "exit.*load", "termination.*penalty", "early.*exit.*fee"],
        "risk_level": "medium",
        "plain_explanation": "Cancelling or exiting this product before a set period will cost you a fee, reducing the amount you get back."
    },
    "Negative Amortization": {
        "patterns": ["negative.*amortiz", "deferred.*interest", "interest.*added.*principal", "minimum.*payment.*interest"],
        "risk_level": "high",
        "plain_explanation": "Your loan balance can actually grow even when you make payments. Unpaid interest gets added to your principal, meaning you owe more over time."
    },
    "Unilateral Amendment": {
        "patterns": ["sole.*discretion", "right.*to.*amend", "modify.*terms.*notice", "change.*agreement.*notice", "amend.*without.*consent"],
        "risk_level": "medium",
        "plain_explanation": "The company can change the terms of this agreement without needing your approval — just by giving you notice."
    },
    "Lien on Assets": {
        "patterns": ["lien.*on", "charge.*on.*property", "hypothecation", "pledge.*assets", "security.*interest"],
        "risk_level": "medium",
        "plain_explanation": "The lender has a legal claim on your assets (property, savings, investments) as security. They can seize these if you default."
    },
    "Personal Guarantee": {
        "patterns": ["personal.*guarantee", "personal.*liability", "guarantor.*personally", "unlimited.*liability"],
        "risk_level": "high",
        "plain_explanation": "You are personally liable beyond just the collateral. The lender can pursue your personal assets if the primary borrower defaults."
    },
    "Force Majeure Exclusion": {
        "patterns": ["force majeure", "act of god", "circumstances.*beyond.*control", "epidemic.*excluded", "pandemic.*not.*covered"],
        "risk_level": "medium",
        "plain_explanation": "Claims arising from events like pandemics, natural disasters, or war may not be covered under this policy."
    },
    "Grace Period Restriction": {
        "patterns": ["no.*grace.*period", "grace.*period.*does.*not", "immediate.*default", "payment.*due.*immediately"],
        "risk_level": "medium",
        "plain_explanation": "There is little or no grace period after a missed payment. You can be declared in default very quickly."
    }
}

def regex_scan(chunks: List[Dict]) -> List[Dict]:
    """
    Scans the provided chunks for risky clauses using regex patterns.

    Combines all chunk texts into a single string while tracking chunk indices.
    For each clause type in RISKY_PATTERNS, checks regex patterns against the combined text.
    If a match is found, extracts a 150-character excerpt, cleans it, and records the clause details.
    Returns a list of found clauses sorted by risk level (high first, then medium, then low).
    Never crashes; returns empty list if chunks is empty or no matches found.
    """
    if not chunks:
        return []
    
    # Combine texts, tracking positions
    combined_text = ""
    chunk_positions = []
    current_pos = 0
    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        combined_text += text
        chunk_positions.append((current_pos, current_pos + len(text), i, chunk.get("page", 1)))
        current_pos += len(text)
    
    found_clauses = []
    for clause_type, data in RISKY_PATTERNS.items():
        for pattern in data["patterns"]:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                start = max(0, match.start() - 75)
                end = min(len(combined_text), match.end() + 75)
                excerpt = combined_text[start:end]
                # Clean excerpt
                excerpt = re.sub(r'\s+', ' ', excerpt).strip()
                # Find which chunk this is in
                chunk_index = None
                page = None
                for pos_start, pos_end, idx, pg in chunk_positions:
                    if pos_start <= match.start() < pos_end:
                        chunk_index = idx
                        page = pg
                        break
                found_clauses.append({
                    "clause_type": clause_type,
                    "excerpt": excerpt,
                    "risk_level": data["risk_level"],
                    "plain_explanation": data["plain_explanation"],
                    "detection_method": "regex",
                    "chunk_index": chunk_index,
                    "page": page
                })
                break  # Don't double-count same clause type
    
    # Sort by risk level
    risk_order = {"high": 0, "medium": 1, "low": 2}
    found_clauses.sort(key=lambda x: risk_order[x["risk_level"]])
    return found_clauses

def llm_scan(chunks: List[Dict], already_found: List[str]) -> List[Dict]:
    """
    Uses LLM to scan for risky clauses that regex may have missed.

    Combines text from chunks up to 3000 words, builds a prompt for the LLM,
    calls Groq API, parses the JSON response, and returns additional clauses.
    Adds detection_method, chunk_index, and page fields.
    Validates risk_level and handles exceptions by returning empty list.
    """
    try:
        client = get_groq_client()
        # Combine text up to 3000 words
        combined_text = ""
        word_count = 0
        for chunk in chunks:
            text = chunk.get("text", "")
            words = text.split()
            if word_count + len(words) > 3000:
                remaining = 3000 - word_count
                combined_text += " ".join(words[:remaining])
                break
            combined_text += text + " "
            word_count += len(words)
        
        system_prompt = "You are a financial contract analyst. Find risky clauses in financial documents. Respond only in valid JSON."
        user_prompt = f"""
Analyze this financial document text for risky or unfavorable clauses.

Already detected (do NOT repeat these): {already_found}

Look specifically for:
- Hidden fees not mentioned upfront
- Clauses that limit the customer's legal rights
- Conditions that could cause unexpected costs
- Terms that heavily favor the lender/insurer
- Any clause a reasonable person would object to if explained clearly

Document text:
{combined_text}

Return a JSON array. Each item must have:
- "clause_type": string (short name for this clause)
- "excerpt": string (the exact problematic text, max 120 chars)
- "risk_level": "high" | "medium" | "low"
- "plain_explanation": string (explain in plain English what this means for the user, max 40 words)

If no additional risky clauses found, return empty array [].
Return only valid JSON array. No explanation outside the JSON.
"""
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=800,
            temperature=0.2
        )
        
        content = response.choices[0].message.content.strip()
        llm_results = json.loads(content)
        
        for item in llm_results:
            item["detection_method"] = "llm"
            item["chunk_index"] = 0
            item["page"] = 1
            if item["risk_level"] not in ["high", "medium", "low"]:
                item["risk_level"] = "medium"  # Default if invalid
        
        return llm_results
    except Exception as e:
        logger.error(f"LLM scan failed: {e}")
        return []

def detect_risky_clauses(chunks: List[Dict]) -> List[Dict]:
    """
    Main entry point for detecting risky clauses in document chunks.

    Performs regex scan first, then LLM scan for additional clauses,
    combines results, sorts by risk level and detection method,
    caps at 12 clauses, and logs the process.
    """
    logger.info(f"Starting clause detection on {len(chunks)} chunks")
    start_time = time.time()
    
    regex_results = regex_scan(chunks)
    logger.info(f"Regex scan found {len(regex_results)} clauses")
    
    already_found = [r["clause_type"] for r in regex_results]
    llm_results = llm_scan(chunks, already_found)
    logger.info(f"LLM scan found {len(llm_results)} additional clauses")
    
    all_clauses = regex_results + llm_results
    
    # Sort: high risk first, then within same risk, regex before llm
    risk_order = {"high": 0, "medium": 1, "low": 2}
    method_order = {"regex": 0, "llm": 1}
    all_clauses.sort(key=lambda x: (risk_order[x["risk_level"]], method_order[x["detection_method"]]))
    
    # Cap at 12
    all_clauses = all_clauses[:12]
    
    logger.info(f"Clause detection complete: {len(all_clauses)} clauses in {time.time() - start_time:.2f}s")
    return all_clauses

def format_clauses_for_response(clauses: List[Dict]) -> List[Dict]:
    """
    Formats clause dictionaries for the API response.

    Cleans and truncates excerpts to 120 characters, returns only
    the required fields for ClausesResponse model.
    """
    formatted = []
    for clause in clauses:
        formatted.append({
            "clause_type": clause["clause_type"],
            "excerpt": clause["excerpt"][:120],
            "risk_level": clause["risk_level"],
            "plain_explanation": clause["plain_explanation"]
        })
    return formatted
