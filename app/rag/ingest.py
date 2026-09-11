import os
from pathlib import Path
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import FakeEmbeddings
from app.config import settings

def get_embedding_function():
    """Return OpenAIEmbeddings if API key is present, otherwise fallback to deterministic embeddings for local offline testing."""
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.startswith("sk-"):
        return OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL
        )
    else:
        # 1536-dimensional deterministic fake embeddings for offline/testing mode
        return FakeEmbeddings(size=1536)

def ingest_documents(force_reload: bool = False) -> int:
    """
    Read policy files from data/knowledge_base, split into chunks,
    and persist into ChromaDB vector store.
    """
    kb_path = Path(settings.KNOWLEDGE_BASE_DIR)
    if not kb_path.exists():
        raise FileNotFoundError(f"Knowledge base directory not found at {kb_path}")

    # Load all .txt files from knowledge base directory
    loader = DirectoryLoader(
        str(kb_path),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"}
    )
    docs = loader.load()

    if not docs:
        print("⚠️ No policy documents found in knowledge base directory.")
        return 0

    # Text Splitting
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_documents(docs)

    # Initialize Chroma vector store
    persist_dir = settings.CHROMA_PERSIST_DIR
    os.makedirs(persist_dir, exist_ok=True)
    embeddings = get_embedding_function()

    # Re-create / update collection
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name="company_policies",
        persist_directory=persist_dir
    )

    print(f" Successfully indexed {len(chunks)} chunks from {len(docs)} documents into ChromaDB.")
    return len(chunks)

if __name__ == "__main__":
    print("🚀 Starting Knowledge Base Ingestion...")
    count = ingest_documents()
    print(f" Ingestion complete: {count} chunks indexed.")
