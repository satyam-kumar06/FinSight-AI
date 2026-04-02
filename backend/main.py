from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import logging
import traceback
from api.routes import router
from core.market_knowledge import initialize_market_knowledge
from core.news_crawler import initialize_news_db

load_dotenv()

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level), format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="FinSight AI", version="1.0.0")

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
origins = [frontend_url, "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("FinSight AI backend starting...")
    try:
        initialize_market_knowledge()
        logger.info("Market knowledge initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize market knowledge: {e}")
    try:
        initialize_news_db()
        logger.info("News DB initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize news DB: {e}")
    logger.info("FinSight AI backend ready")

app.include_router(router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok", "model": "llama-3.1-70b-versatile", "version": "1.0.0"}

@app.get("/")
def root():
    return {"message": "FinSight AI backend is running"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {traceback.format_exc()}")
    return JSONResponse(
        content={"error": "Something went wrong", "detail": str(exc)},
        status_code=500
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
