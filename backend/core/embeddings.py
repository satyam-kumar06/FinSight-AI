import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os
import logging
import time
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
MARKET_COLLECTION = "market_knowledge"
NEWS_COLLECTION = "news_articles"

_embedding_model = None

def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model {EMBEDDING_MODEL_NAME}...")
        try:
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            logger.info("Embedding model loaded")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    return _embedding_model

_chroma_client = None

def get_chroma_client() -> chromadb.Client:
    global _chroma_client
    if _chroma_client is None:
        try:
            _chroma_client = chromadb.PersistentClient(
                path=CHROMA_PERSIST_DIR,
                settings=Settings(anonymized_telemetry=False)
            )
            logger.info(f"ChromaDB client initialized at {CHROMA_PERSIST_DIR}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise
    return _chroma_client

def embed_and_store(chunks: List[Dict], session_id: str) -> str:
    try:
        model = get_embedding_model()
        client = get_chroma_client()
        collection = client.get_or_create_collection(session_id, metadata={"hnsw:space": "cosine"})
        texts = [chunk["text"] for chunk in chunks]
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False).tolist()
        ids = [f"{session_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"page": chunk["page"], "chunk_index": chunk["chunk_index"], "word_count": chunk["word_count"]} for chunk in chunks]
        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        logger.info(f"Stored {len(chunks)} chunks for session {session_id}")
        return session_id
    except Exception as e:
        logger.error(f"Failed to embed and store chunks for session {session_id}: {e}")
        raise ValueError(f"Failed to store document chunks: {str(e)}")

def semantic_search(query: str, session_id: str, k: int = 5) -> List[Dict]:
    try:
        model = get_embedding_model()
        client = get_chroma_client()
        try:
            collection = client.get_collection(session_id)
        except Exception:
            raise ValueError(f"Session {session_id} not found. Please upload a document first.")
        query_embedding = model.encode([query]).tolist()
        n_results = min(k, collection.count())
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        res_list = []
        for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
            res_list.append({
                "text": doc,
                "page": meta["page"],
                "chunk_index": meta["chunk_index"],
                "similarity_score": round(1 - dist, 4)
            })
        res_list.sort(key=lambda x: x["similarity_score"], reverse=True)
        logger.info(f"Found {len(res_list)} chunks for query in session {session_id}")
        return res_list
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to perform semantic search for session {session_id}: {e}")
        return []

def store_in_collection(texts: List[str], metadatas: List[Dict], collection_name: str, id_prefix: str) -> int:
    try:
        model = get_embedding_model()
        client = get_chroma_client()
        collection = client.get_or_create_collection(collection_name, metadata={"hnsw:space": "cosine"})
        embeddings = model.encode(texts, batch_size=64, show_progress_bar=False).tolist()
        ids = [f"{id_prefix}_{i}" for i in range(len(texts))]
        try:
            collection.delete(ids=ids)
        except Exception:
            pass
        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        logger.info(f"Stored {len(texts)} documents in collection {collection_name}")
        return len(texts)
    except Exception as e:
        logger.error(f"Failed to store in collection {collection_name}: {e}")
        return 0

def search_collection(query: str, collection_name: str, k: int = 3) -> List[Dict]:
    try:
        model = get_embedding_model()
        client = get_chroma_client()
        try:
            collection = client.get_collection(collection_name)
        except Exception:
            logger.warning(f"Collection {collection_name} not found")
            return []
        query_embedding = model.encode([query]).tolist()
        n_results = min(k, collection.count())
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        res_list = []
        for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
            res_list.append({
                "text": doc,
                "metadata": meta,
                "similarity_score": round(1 - dist, 4)
            })
        return res_list
    except Exception as e:
        logger.error(f"Failed to search collection {collection_name}: {e}")
        return []

def delete_session(session_id: str) -> bool:
    try:
        client = get_chroma_client()
        client.delete_collection(session_id)
        logger.info(f"Deleted collection {session_id}")
        return True
    except Exception as e:
        logger.warning(f"Collection {session_id} not found for deletion")
        return False
