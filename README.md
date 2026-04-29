# ASCK Chatbot — v1.0.0

A RAG-enabled Q&A chatbot. Uses Weaviate (embedded) for vector search, Pydantic AI for the agent layer, and Ant Design X for the chat UI.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vite + React + TypeScript + Ant Design X |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Agent | Pydantic AI (RAG tool, streaming) |
| Vector DB | Weaviate (embedded, port 8090) |
| Embeddings | VoyageAI `voyage-4` (via Weaviate `text2vec-voyageai` module) |
| LLM | OpenAI-compatible API |

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ (via Anaconda or Homebrew) |
| Node.js | 18+ |
| pnpm | any — `npm install -g pnpm` |

## Quick Start

### 1. Clone

```bash
git clone https://github.com/yourusername/ASCASK.git
cd ASCASK
```

### 2. Initialize (first time only)

```bash
make init
```

This creates `backend/.venv`, installs all Python + frontend dependencies, and creates `.env` files from examples.

### 3. Configure API keys

Edit `backend/.env`:

```env
OPENAI_API_KEY=sk-...
VOYAGEAI_APIKEY=pa-...
```

### 4. Start

```bash
make dev
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Weaviate (embedded) | port 8090 (internal, auto-started by backend) |

Logs: `logs/backend.log` and `logs/frontend.log`.

### 5. Stop

```bash
make stop
```

## Indexing Documents

Place `.md` files under `structured_docs/`. Then run:

```bash
make index
```

Available indexing commands:

| Command | Description |
|---------|-------------|
| `make index` | Index everything (structured docs + WMX manual) |
| `make index-structured` | Structured docs only |
| `make index-wmx` | WMX manual only |
| `make index-reset` | Reset schema, then re-index everything |

The indexer scans for new/changed files, generates HTML sidecars, and upserts content into Weaviate. Re-run whenever documents are added or updated.

## Project Structure

```
ASCASK/
├── backend/
│   ├── server.py        # FastAPI app, CORS, static file mount, health/version
│   ├── config.py        # Settings from environment variables
│   ├── agent.py         # Pydantic AI agent + system prompt
│   ├── search.py        # Weaviate client singleton + RAG search tool
│   ├── chat.py          # POST /api/chat endpoint (streaming + non-streaming)
│   ├── .env             # Your secrets (not committed)
│   ├── .env.example     # Template
│   └── requirements.txt
│
├── indexer/             # Offline document indexing CLI (python -m indexer)
│   ├── __main__.py      # CLI entry point
│   ├── weaviate_client.py
│   ├── scanner.py       # File scanner + change detection + HTML generation
│   ├── chunker.py       # Token counting + content splitting
│   ├── structured.py    # Weaviate schema + batch insert for structured docs
│   └── wmx_manual.py    # WMX Manual knowledge graph builder
│
├── frontend/
│   └── src/
│       ├── App.tsx
│       └── components/chat/
│           ├── ChatLayout.tsx   # Main component — all state and hooks
│           ├── Sidebar.tsx      # Conversation list and management
│           ├── MessageList.tsx  # Bubble list, Markdown rendering, message footer
│           ├── ChatInput.tsx    # Input box, search engines, file attachments
│           ├── WelcomeScreen.tsx# Welcome + hot topic shortcuts
│           ├── context.ts       # Shared ChatContext
│           ├── types.ts         # ChatMessage type
│           └── config.ts        # Static constants (prompts, search engines, etc.)
│
├── structured_docs/     # Markdown source files for the knowledge base
├── unstructured_docs/   # Unstructured docs (WMX manual, sample codes)
├── graph_vis/           # Jupyter notebook for Weaviate graph visualization
├── Makefile             # All developer commands
├── docker-compose.yml   # Weaviate Docker config (currently using embedded mode)
├── VERSION              # Canonical version string
└── DEV_LOG.md           # Development log
```

## How RAG Works

```
User prompt
  → Frontend (Ant Design X chat UI)
  → POST /api/chat (streaming SSE)
  → Pydantic AI Agent
      ├─ Decides: search docs or answer directly
      └─ rag_search_tool(query)
            → Weaviate hybrid search (75% vector / 25% BM25)
            → VoyageAI embeddings (via text2vec-voyageai module, transparent)
            → Returns top-5 chunks with source URLs
  → Agent composes response with citations
  → Streams back to frontend
```

## Environment Variables

### `backend/.env`

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI (or compatible) API key |
| `VOYAGEAI_APIKEY` | Yes | — | VoyageAI key (used by Weaviate internally) |
| `OPENAI_BASE_URL` | No | OpenAI default | Override for local models |
| `WEAVIATE_URL` | No | `http://localhost:8090` | Weaviate URL |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Comma-separated allowed origins |

### `frontend/.env`

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_URL` | No | `http://localhost:8000/api/chat` | Backend chat endpoint |

## Changelog

### v1.0.0 (2026-04-06)
- **Major restructure**: flattened `backend/app/` hierarchy → flat files directly in `backend/`
- **Indexer extracted**: standalone `indexer/` package, run with `python -m indexer`
- **`unstructured_docs/`** moved from `backend/` to project root
- **Frontend split**: `Independent.tsx` (1013 lines) → 5 focused components + shared context/types/config
- **Makefile**: replaces `_init.sh`, `_start.sh`, `_stop.sh`, `_scandocs.sh`
- **Vercel removed**: dropped `vercel.json` and `backend/api/index.py`
- **Cleaned `requirements.txt`**: removed unused deps (logfire, ddgs, trafilatura, PyYAML, etc.)

### v0.1.0
- Initial skeleton: FastAPI backend + Weaviate RAG + Ant Design X chat UI

## License

MIT
