# 🤖 AI Support & Resolution Agent

> **Production-oriented GenAI support system combining RAG, deterministic tools, LangGraph workflows, and a FastAPI backend.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi)](https://fastapi.tiangolo.com/) [![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Workflow-orange)](https://www.langchain.com/langgraph) [![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-purple)](https://www.trychroma.com/) [![Pytest](https://img.shields.io/badge/Tests-Pytest-yellow?logo=pytest)](https://pytest.org/)

## 🎯 Why this project?

Generic LLM chatbots can answer questions, but enterprise support needs more than text generation. An effective support agent must access **live business data**, follow **company policies**, perform **safe actions**, and escalate cases it cannot resolve.

This project demonstrates that architecture in one application:

- 📦 **Live order operations** through deterministic SQLite tools
- 📚 **Policy-grounded answers** through Retrieval-Augmented Generation (RAG)
- 🧠 **Structured agent orchestration** with LangGraph
- 🛡️ **Reduced hallucination risk** by separating facts/actions from generation
- 🙋 **Human escalation** through support-ticket creation
- ⚡ **FastAPI backend** with an interactive web interface
- 🧪 **Automated testing** for tools and API behavior

## 🏗️ Architecture

```text
                         ┌──────────────────┐
                         │   User / Browser  │
                         └────────┬─────────┘
                                  │ HTTP /chat
                                  ▼
                         ┌──────────────────┐
                         │  FastAPI Backend │
                         └────────┬─────────┘
                                  ▼
                         ┌──────────────────┐
                         │ LangGraph Agent  │
                         │   StateGraph     │
                         └───────┬──────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
             ┌──────────────┐          ┌──────────────┐
             │   RAG Layer  │          │  Tool Layer  │
             │  ChromaDB   │          │   SQLite     │
             └──────┬───────┘          └──────┬───────┘
                    │                         │
                    └────────────┬────────────┘
                                 ▼
                         ┌──────────────────┐
                         │  Response Layer  │
                         │       LLM        │
                         └────────┬─────────┘
                                  ▼
                           Grounded Answer
```

## 🔄 Agent Flow

```text
START
  ↓
Understand Request
  ↓
Detect intent / required action
  ↓
┌───────────────────────┐
│ Tool or RAG required? │
└──────────┬────────────┘
      Yes  │       │ No
           ▼       ▼
     Execute Tool  Generate Response
      / Retrieve         │
           │             │
           └──────┬──────┘
                  ▼
                 END
```

The important engineering principle is **not letting the LLM invent business facts**. Order status, cancellation rules, refund eligibility, and support-ticket creation are handled by explicit application tools. Policy answers are grounded in retrieved company documents.

## ✨ Core Capabilities

| Capability | Implementation |
|---|---|
| Order tracking | SQLite + deterministic tool |
| Order cancellation | Business-rule validation + SQLite update |
| Refund eligibility | Delivery date + policy rules |
| Policy questions | RAG + ChromaDB |
| Human escalation | Support-ticket tool |
| Agent orchestration | LangGraph StateGraph |
| API | FastAPI |
| UI | HTML/CSS/JavaScript |
| Testing | Pytest + FastAPI TestClient |

## 📚 RAG Pipeline

The policy knowledge base contains documents such as refund, return, shipping, and cancellation policies.

```text
Policy Documents
      ↓
Load + Chunk
      ↓
Generate Embeddings
      ↓
ChromaDB Collection
      ↓
Similarity Search
      ↓
Relevant Context
      ↓
LLM Response
```

The application uses retrieved policy context rather than asking the LLM to rely only on its pretrained knowledge. If the knowledge base does not contain sufficient information, the agent should avoid fabricating a policy.

## 🧰 Tool Layer

The main tools represent actions the model should **request**, not invent:

- `get_order_status(order_id)`
- `get_customer_orders(customer_id)`
- `cancel_order(order_id)`
- `check_refund_eligibility(order_id)`
- `create_refund_request(order_id)`
- `create_support_ticket(customer_id, issue)`
- `lookup_company_policy(query)`

This separation is a key part of the project's reliability design: **the LLM decides which capability is needed; application code performs the actual business operation.**

## 🗂️ Project Structure

```text
app/
├── main.py                 # FastAPI application + lifecycle
├── config.py               # Environment configuration
├── agents/
│   ├── graph.py            # LangGraph workflow
│   └── state.py            # Agent state
├── tools/
│   ├── order_tools.py      # Order operations
│   ├── refund_tools.py     # Refund operations
│   └── support_tools.py    # Human escalation
├── rag/
│   ├── ingest.py           # Knowledge-base ingestion
│   └── retriever.py        # Retrieval logic
├── database/
│   ├── database.py         # SQLite setup
│   └── models.py            # SQLAlchemy models
└── api/
    └── routes.py           # REST endpoints

data/
└── knowledge_base/         # Company policy documents

frontend/
├── index.html
├── style.css
└── script.js

tests/
└── test_tools.py
```

## 🛠️ Tech Stack

**Python 3.11+** · **FastAPI** · **LangGraph** · **LangChain** · **ChromaDB** · **SQLite** · **SQLAlchemy** · **Pydantic** · **Pytest** · **HTML/CSS/JavaScript**

## 🚀 Run Locally

```bash
git clone https://github.com/juneja711/ai-support-resolution-agent.git
cd ai-support-resolution-agent

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Create `.env` from `.env.example`, configure the required model credentials, then run:

```bash
python -m app.rag.ingest
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the application and `/docs` for the interactive FastAPI documentation.

## 🧪 Testing

```bash
pytest -v
```

The test suite covers database-backed tools, business rules, RAG behavior, invalid inputs, and API endpoints.

## 💬 Demo Scenarios

Try questions such as:

- **“Where is my order 1001?”** → retrieves the order through a database tool.
- **“What is your refund policy?”** → retrieves relevant policy context through RAG.
- **“Can I cancel order 1003?”** → evaluates cancellation rules and updates the database when permitted.
- **“I want to talk to a human.”** → creates a support ticket.

## 🎤 Interview Talking Points

### Why LangGraph?
A graph-based workflow makes the agent's state transitions explicit and easier to control, test, and extend than an uncontrolled agent loop.

### Why RAG?
Company policies change and are not reliable model knowledge. Retrieval provides current application-specific context at inference time.

### How do you reduce hallucinations?
Business facts and mutations are handled by deterministic tools. Policy responses are grounded in retrieved documents. The LLM is primarily responsible for understanding requests and presenting results naturally.

### Why separate tools from the LLM?
The model should not directly manipulate business data. Tools provide a controlled interface with validation and business rules around sensitive operations.

### What would you improve for production?
Authentication and authorization, observability/tracing, evaluation datasets, stronger retrieval evaluation, rate limiting, audit logs, PostgreSQL, background jobs, and deployment with CI/CD.

## 🔮 Roadmap

- [ ] Authentication and role-based access
- [ ] PostgreSQL for production persistence
- [ ] Retrieval/evaluation metrics
- [ ] Observability and tracing
- [ ] Streaming responses
- [ ] Multi-language support
- [ ] Sentiment-based ticket prioritization
- [ ] CI/CD pipeline

## 👨‍💻 Author

**Mayank Juneja**  
B.Tech CSE | AI/ML & Generative AI

[GitHub](https://github.com/juneja711) · [LinkedIn](https://www.linkedin.com/in/mayank-juneja-a806b837)
