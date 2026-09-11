from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database.database import init_db
from app.rag.ingest import ingest_documents
from app.api.routes import router as api_router

BASE_DIR = Path(__file__).resolve().parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    print("🚀 Initializing AI Customer Support System...")
    # 1. Initialize and seed SQLite database
    init_db()
    # 2. Ensure knowledge base is indexed
    try:
        persist_dir = Path(settings.CHROMA_PERSIST_DIR)
        if not persist_dir.exists() or not any(persist_dir.iterdir()):
            print("📚 Indexing policy knowledge base...")
            ingest_documents()
    except Exception as e:
        print(f"⚠️ Knowledge base indexing notice: {e}")
    print(" AI Customer Support Agent is ready!")
    yield
    print("👋 Shutting down AI Customer Support Agent.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "An intelligent customer support and resolution agent utilizing LangGraph, "
        "ChromaDB RAG, and SQLite tool execution."
    ),
    lifespan=lifespan
)

# Enable CORS for frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API endpoints
app.include_router(api_router)

# Mount frontend directory for static assets (CSS, JS)
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

@app.get("/", tags=["Frontend"])
async def serve_frontend():
    """Serve the customer support web interface."""
    index_path = BASE_DIR / "frontend" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "AI Customer Support API is running. Visit /docs for Swagger documentation."}
