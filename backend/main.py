from contextlib import asynccontextmanager

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
import models.database

@asynccontextmanager
async def lifespan(app: FastAPI):
    await models.database.init_db()
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    yield

app = FastAPI(lifespan=lifespan)
logger = logging.getLogger(__name__)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Include API router
app.include_router(router)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )

# H13: Rate limiting — deliberate won't-fix
# Conduit is a single-user localhost app (no public exposure, no auth).
# Per DESIGN_SPEC §2/§11, rate limiting is unnecessary and out of scope.
# If the deployment model ever changes, add a reverse proxy or rate-limiter.

# Health endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}
