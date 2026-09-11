# AI Customer Support & Resolution Agent

An intelligent, production-ready Customer Support & Resolution Assistant built with **Python 3.11+**, **FastAPI**, **LangGraph**, **ChromaDB (RAG)**, and **SQLite**.

Designed specifically as an interview-ready project demonstrating practical **Generative AI**, **Tool Calling**, **State Graph Workflows**, and **Grounding / Anti-Hallucination** engineering.

---

## 1. Project Overview

Modern customer service organizations deal with repetitive inquiries such as order tracking, refund eligibility, order cancellations, and company policy FAQs. Traditional rule-based chatbots fail to understand context, while unconstrained LLMs frequently hallucinate policies or lack real-time database access.

This project implements an autonomous customer support agent that bridges that gap:
- **Understands user intent** through conversational AI.
- **Queries and updates an SQLite database** in real-time via safe tool calling.
- **Retrieves official company policies** using Retrieval-Augmented Generation (RAG) with ChromaDB.
- **Orchestrates deterministic decision trees** with LangGraph.
- **Provides an interactive, modern web chat UI** connected to a clean FastAPI backend.

---

## 2. Problem Statement

Standard generative AI models have two critical limitations in enterprise settings:
1. **No access to private/mutable business data** (e.g., customer orders, active shipments).
2. **Hallucination risk** (e.g., fabricating a 90-day return policy when company policy is strictly 30 days).

This project solves both problems:
- Real-time order queries and updates are routed strictly through **deterministic database tools**.
- Policy questions are grounded exclusively on **vector-indexed company documentation**.
- Unhandled situations gracefully escalate to **human support tickets** without crashing.

---

## 3. Architecture

```text
User / Browser
      │
      ▼ (HTTP POST /chat)
┌─────────────────────────┐
│     FastAPI Backend     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│     LangGraph Agent     │
│  (StateGraph Workflow)  │
└────────────┬────────────┘
             │
      ┌──────┴──────────────────────┐
      ▼                             ▼
┌──────────────┐             ┌──────────────┐
│  RAG Search  │             │   DB Tools   │
│  (ChromaDB)  │             │   (SQLite)   │
└──────┬───────┘             └──────┬───────┘
       │                            │
       └──────────────┬─────────────┘
                      │
                      ▼
┌─────────────────────────┐
│     Response Synthesis  │
│          (LLM)          │
└────────────┬────────────┘
             │
             ▼
       Final Response
```

---

## 4. Key Features

- 📦 **Real-Time Order Tracking**: Resolves queries like *"Where is my order 1001?"* by extracting order IDs and querying live database records.
- ❌ **Policy-Governed Order Cancellation**: Cancels orders in `Processing` status; politely rejects cancellation if the package has already `Shipped` and provides return guidance.
- 💸 **Automated Refund Eligibility Verification**: Calculates days since delivery (30-day window) and registers formal refund tickets for eligible purchases.
- 📚 **Grounded Policy RAG**: Searches indexed policy files (`refund_policy.txt`, `shipping_policy.txt`, `cancellation_policy.txt`, `return_policy.txt`) using vector similarity embeddings.
- 🙋 **Human Agent Escalation**: Automatically opens support tickets in SQLite when users request a human or encounter edge-case issues.
- 🛡️ **Defensive Error Handling**: Rejects empty queries, handles non-existent or invalid order IDs, and protects against API/database crashes.
- 💻 **Interactive Chat Interface**: Includes prompt suggestion chips, live status indicators, intent tags, and responsive CSS styling.

---

## 5. Technologies Used

| Category | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.11+ | Core application runtime |
| **Backend Framework** | FastAPI | High-performance asynchronous REST API |
| **Server** | Uvicorn | ASGI production server |
| **Agent Workflow** | LangGraph | Graph-based state machine for agent decisions |
| **LLM Orchestration** | LangChain / LangChain-OpenAI | Model interfacing & tool bindings |
| **Vector Database** | ChromaDB | Local vector store for policy document embeddings |
| **Relational Database** | SQLite + SQLAlchemy | Persistent order, customer, and support ticket store |
| **Validation & Settings** | Pydantic v2 + Pydantic-Settings | Data models and `.env` parsing |
| **Testing** | Pytest + FastAPI TestClient | Automated unit and integration testing |
| **Frontend** | Vanilla HTML5, CSS3, JavaScript | Lightweight, zero-dependency chat UI |

---

## 6. Folder Structure

```text
ai_customer_support/
│
├── app/
│   ├── main.py                # FastAPI app initialization, static assets, and lifecycle
│   ├── config.py              # Environment configuration and path management
│   │
│   ├── agents/
│   │   ├── graph.py           # LangGraph workflow (Understand -> Action -> Tool/RAG -> Response)
│   │   └── state.py           # AgentState definition with message history and detected intent
│   │
│   ├── tools/
│   │   ├── order_tools.py     # get_order_status, get_customer_orders, cancel_order
│   │   ├── refund_tools.py    # check_refund_eligibility, create_refund_request
│   │   └── support_tools.py   # create_support_ticket
│   │
│   ├── rag/
│   │   ├── ingest.py          # Document loader, text chunking, and ChromaDB indexing
│   │   └── retriever.py       # Knowledge base similarity search and tool wrapper
│   │
│   ├── database/
│   │   ├── database.py        # SQLite engine, session generator, and auto-seeding
│   │   └── models.py          # SQLAlchemy models (Customer, Order, SupportTicket)
│   │
│   └── api/
│       └── routes.py          # REST endpoints (/chat, /orders, /support/ticket, /health)
│
├── data/
│   ├── knowledge_base/        # Official store policy text documents
│   │   ├── refund_policy.txt
│   │   ├── return_policy.txt
│   │   ├── shipping_policy.txt
│   │   └── cancellation_policy.txt
│   └── support.db             # Auto-generated SQLite database (gitignored)
│
├── frontend/
│   ├── index.html             # Clean customer support web interface
│   ├── style.css              # Modern dark-mode responsive design
│   └── script.js              # Fetch requests, message rendering, and auto-scroll
│
├── tests/
│   └── test_tools.py          # 16 unit and integration pytest tests
│
├── .env                       # Local environment secrets (gitignored)
├── .env.example               # Template for required environment variables
├── .gitignore                 # Excludes .venv, db files, and cached vectors
├── requirements.txt           # Clean dependencies manifest
└── README.md                  # Project documentation
```

---

## 7. How RAG (Retrieval-Augmented Generation) Works

1. **Document Loading**: Policy files in `data/knowledge_base/` are loaded using text loaders.
2. **Chunking**: `RecursiveCharacterTextSplitter` segments policy text into 400-character passages with 50-character overlaps to maintain semantic context.
3. **Embedding**: Passages are vectorized using OpenAI embeddings (`text-embedding-3-small`).
4. **Vector Store**: Vectors are indexed inside a local ChromaDB collection (`company_policies`).
5. **Retrieval**: When a customer asks a policy question, ChromaDB executes a similarity search, retrieving the top matching excerpts.
6. **Grounding**: The LLM reads only the retrieved excerpts to answer the inquiry. If the knowledge base does not contain the answer, the agent states that it does not have enough information rather than guessing.

---

## 8. How LangGraph Works

Instead of relying on uncontrolled agent loops, LangGraph models the conversation as a **StateGraph**:

```text
[START]
   │
   ▼
[Understand Request Node]
   │  (Classifies intent & checks for required tool calls)
   ▼
<Should Continue Edge?>
   ├─► Has Tool Calls ────────► [Tools Node (Execute Tools / RAG)]
   │                                     │
   │                                     ▼
   └─► No Tool Calls ─────────► [Generate Response Node]
                                         │
                                         ▼
                                       [END]
```

- **`AgentState`**: A typed dictionary tracking conversation history (`messages`), detected intent (`intent`), and customer ID.
- **Node 1 (`understand_request`)**: Determines intent and binds tools (`get_order_status`, `lookup_company_policy`, etc.) to the model.
- **Edge (`should_continue`)**: Checks if the model emitted `tool_calls`.
- **Node 2 (`tools_node`)**: Executes the tool functions against SQLite or ChromaDB and appends `ToolMessage`s.
- **Node 3 (`generate_response`)**: Synthesizes the final grounded answer for the customer.

---

## 9. How Tools Work

Every tool is implemented as a modular Python function decorated with LangChain's `@tool` and backed by real SQLite transactions:

1. **`get_order_status(order_id)`**: Queries the `orders` table. Returns order details, product name, price, and shipment status.
2. **`get_customer_orders(customer_id)`**: Returns all active and historical orders for a given customer.
3. **`cancel_order(order_id)`**: Atomically updates order status from `Processing` to `Cancelled`. If the order is already `Shipped`, rejects the cancellation and advises on returns.
4. **`check_refund_eligibility(order_id)`**: Enforces the 30-day return window on `Delivered` orders.
5. **`create_refund_request(order_id)`**: Verifies eligibility and registers an official refund ticket.
6. **`create_support_ticket(customer_id, issue)`**: Inserts a new support ticket into SQLite and returns the assigned ticket ID.
7. **`lookup_company_policy(query)`**: Performs similarity retrieval against ChromaDB.

---

## 10. Installation & Setup

### Prerequisites
- Python 3.11 or higher installed on your system.
- Git (optional).

### 1. Clone or Open the Repository
```bash
cd ai_customer_support
```

### 2. Create and Activate a Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 11. `.env` Configuration

Copy `.env.example` to create your local `.env` file:
```bash
cp .env.example .env
```

Open `.env` in any text editor and configure your OpenAI API key:
```env
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
DATABASE_URL=sqlite:///./data/support.db
CHROMA_PERSIST_DIR=./data/chroma_db
```

> **Note**: The application includes a fallback deterministic mode. If you run the app before adding an OpenAI key, the SQLite tools, API endpoints, and policy fallbacks will still function for local evaluation!

---

## 12. Running the Application

### 1. Populate the Knowledge Base (Optional — auto-runs on startup)
```bash
python -m app.rag.ingest
```

### 2. Start the FastAPI Server
```bash
uvicorn app.main:app --reload
```

The application will start at:
- **Interactive Chat UI**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 13. Running Automated Tests

Run the complete test suite with `pytest`:
```bash
pytest tests/test_tools.py -v
```

All 16 tests will execute against an isolated SQLite test database and verify:
- Order status retrieval & error states
- Invalid order ID handling
- Order cancellation rules (processing vs. shipped)
- Refund window calculation (delivered <= 30 days)
- Human support ticket creation
- RAG knowledge base search
- FastAPI `/chat`, `/orders/{id}`, and `/health` endpoints

---

## 14. Example Questions to Try

| Question | Expected Agent Behavior |
| :--- | :--- |
| *"Where is my order 1001?"* | Calls `get_order_status(1001)`, reports status as `Shipped`. |
| *"What is your refund policy?"* | Calls `lookup_company_policy`, explains 30-day window and requirements. |
| *"Can I cancel order 1003?"* | Calls `cancel_order(1003)`, successfully cancels `Processing` order. |
| *"Can I cancel order 1001?"* | Calls `cancel_order(1001)`, informs user it is already `Shipped` and cannot be cancelled. |
| *"Can I get a refund for order 1002?"* | Calls `check_refund_eligibility(1002)`, verifies it was delivered within 30 days. |
| *"How long does shipping take?"* | Queries shipping policy: 3–7 business days standard, 1–2 days express. |
| *"I want to talk to a human."* | Calls `create_support_ticket`, returns created ticket ID. |

---

## 15. Technical Talking Points for Interviews

When discussing this project during an internship interview, emphasize these design choices:
1. **LangGraph vs. ReAct Loops**: Explain why a structured state graph provides more reliability than open-ended agent loops for regulated customer workflows.
2. **Defensive Anti-Hallucination**: Explain how separating deterministic database queries from generative text synthesis guarantees truthful order updates.
3. **Chunking & Vector Store Strategy**: Explain why smaller chunk sizes (400 chars) were selected for policy documents to avoid injecting irrelevant policy clauses into LLM context.
4. **Resilience Without Paid Keys**: Highlight how the application degrades gracefully when API keys are absent, ensuring testing and demoability anywhere.

---

## 16. Future Improvements

- Add OAuth2 / JWT authentication for customer portal login.
- Add multi-language translation support for global customers.
- Integrate WebSockets for streaming token responses to the UI.
- Add sentiment analysis to automatically prioritize urgent support tickets.
