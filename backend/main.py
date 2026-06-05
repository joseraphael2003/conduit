from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from dotenv import load_dotenv
import os
import logging

# Load .env file if present
load_dotenv()

from routers import router

app = FastAPI()
logger = logging.getLogger(__name__)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred. Please try again later."},
    )

# Startup validation
@app.on_event("startup")
async def startup():
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

# Health endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}
