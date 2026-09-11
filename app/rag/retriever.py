import os
from pathlib import Path
from langchain_chroma import Chroma
from langchain_core.tools import tool
from app.config import settings
from app.rag.ingest import get_embedding_function, ingest_documents

_vector_store = None

def get_vector_store():
    """Lazily load or initialize the Chroma vector store."""
    global _vector_store
    if _vector_store is not None:
        return _vector_store

    persist_dir = settings.CHROMA_PERSIST_DIR
    embeddings = get_embedding_function()

    if not os.path.exists(persist_dir) or not os.listdir(persist_dir):
        # Auto-ingest if vector store directory is empty
        print("⚡ Initializing and populating knowledge base vector store...")
        ingest_documents()

    try:
        _vector_store = Chroma(
            collection_name="company_policies",
            embedding_function=embeddings,
            persist_directory=persist_dir
        )
    except Exception as e:
        print(f"⚠️ Warning loading ChromaDB: {e}. Re-ingesting...")
        ingest_documents()
        _vector_store = Chroma(
            collection_name="company_policies",
            embedding_function=embeddings,
            persist_directory=persist_dir
        )
    return _vector_store


def fallback_keyword_search(query: str) -> str:
    """Fallback keyword search across policy text files for offline/test environments."""
    kb_path = Path(settings.KNOWLEDGE_BASE_DIR)
    if not kb_path.exists():
        return ""

    query_lower = query.lower()
    matched_sections = []

    # Map keywords to policy files
    file_keywords = {
        "refund_policy.txt": ["refund", "money back", "reimburse", "30 days"],
        "return_policy.txt": ["return", "packaging", "defective", "label"],
        "shipping_policy.txt": ["shipping", "delivery", "dispatch", "track", "transit", "days to ship"],
        "cancellation_policy.txt": ["cancel", "cancellation", "abort", "stop order"]
    }

    for filename, keywords in file_keywords.items():
        if any(k in query_lower for k in keywords):
            file_path = kb_path / filename
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    matched_sections.append(f"--- From {filename} ---\n{content}")

    if matched_sections:
        return "\n\n".join(matched_sections[:2])
    return ""


def query_knowledge_base(query: str, k: int = 3) -> str:
    """Search company policy knowledge base using Chroma similarity search with keyword fallback."""
    if not query or not query.strip():
        return "No search query provided."

    results_text = ""
    try:
        store = get_vector_store()
        # Perform similarity search
        docs = store.similarity_search(query, k=k)
        if docs:
            chunks = [f"[Policy Excerpt]: {doc.page_content.strip()}" for doc in docs if doc.page_content.strip()]
            if chunks:
                results_text = "\n\n".join(chunks)
    except Exception as e:
        print(f"⚠️ Similarity search error: {e}. Attempting keyword fallback.")

    # If Chroma returned nothing or in offline mode, use keyword fallback
    if not results_text:
        results_text = fallback_keyword_search(query)

    if not results_text:
        return (
            "I checked the company knowledge base, but could not find relevant policy information "
            "for this inquiry. Please consult our support staff directly or create a support ticket."
        )

    return results_text


@tool
def lookup_company_policy(query: str) -> str:
    """Search the company knowledge base for policy information such as refund policy, return policy, shipping policy, or cancellation policy."""
    return query_knowledge_base(query)
