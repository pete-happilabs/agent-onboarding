# DOST Agent Onboarding

Three ways to create agents for the DOST ecosystem. Every agent speaks the same language — **dostEvent in, dostEvent out** — and plugs into DAS (DOST Agent Store) so clients can discover and talk to them.

**All 3 ways produce the same thing:** an async `talk()` function with an identical signature - dostEvent!

```python
async def talk(dostEvent) -> (dostEvent, metrics)
```

- **Input:** a dostEvent with the user's message
- **Output:** a dostEvent response (with text + structured dostObjects) and LLM token metrics

This is the universal contract. No matter which way you build the agent — MCP, Generic, or Custom — the `talk()` function is what gets wrapped in a WebSocket, hosted, and registered in DAS.

```
agent-onboarding/
├── shared/     # Shared dost protocol + TalkMetrics (pip-installable)
├── mcp/        # Way 1: MCP Server Bridge
├── generic/    # Way 2: Generic Agent (just data + prompt)
└── custom/     # Way 3: Custom REST API Agent + prompt
```

---

## Shared Module

All three templates import from a single `shared/dost` package — no more duplicate protocol.py or metrics.py files.

```
shared/dost/
├── protocol.py   # DOST Event Spec v00.01.01 (create_dost_event, extract_query_text, etc.)
└── metrics.py    # TalkMetrics class (per-model token tracking in DPA billing format)
```

**Install:** Each template's `requirements.txt` includes `-e ../shared` so `from dost.protocol import ...` and `from dost.metrics import TalkMetrics` work everywhere.

**TalkMetrics** tracks per-model token counts for billing:
```python
metrics = TalkMetrics()
metrics.add_llm("gpt-4o-mini", input_tokens=1834, output_tokens=44)
metrics.to_dict()
# → {"models": {"gpt-4o-mini": {"input_tokens": 1834, "output_tokens": 44}}}
```

---

## The 3 Ways

### Way 1: MCP — "I have an MCP server"

**For:** Developers who already have a service exposed as an MCP (Model Context Protocol) server — Zomato, Linear, Sentry, Airbnb, any MCP-compatible tool.

**How it works:** We bridge the MCP server into DOST. The bridge connects to the MCP server, discovers its tools automatically, and wraps them with a ReAct agent that understands natural language. User says "find me a place in Goa" and the agent figures out which MCP tools to call.

**What the developer provides:**
- An MCP server (remote URL, local command, or SSE endpoint)
- OAuth credentials if needed

**What we provide:**
- MCP-to-dostEvent bridge
- `talk()` function — same signature as all other agents
- ReAct agent for natural language understanding
- Automatic tool discovery from MCP server
- OAuth handling via `mcp-remote`

```
User (dostEvent) → talk() → MCP Bridge → MCP Server (tools) → dostEvent response + metrics
```

**Config example:**
```yaml
mcp:
  transport: remote
  url: "https://mcp.zomato.com/sse"
agent:
  entity_id: "agent.mcp.zomato"
  name: "Zomato"
```

**Test it:**
```bash
cd mcp
pip install -r requirements.txt
python3 playground.py --config configs/airbnb.yaml -v
```

---

### Way 2: Generic — "I just have data"

**For:** Someone with no technical resources — no APIs, no MCP server. They just have data (a database, documents, spreadsheets, a catalog) and want an AI agent that can answer questions about it.

**How it works:** Change the system prompt and point to a database. The agent becomes whatever you describe in the prompt — a restaurant guide, a real estate assistant, a product catalog. No code changes needed, just configuration via `.env`.

**What the developer provides:**
- Data (database, CSV, documents)
- A description of what the agent should do (the prompt)

**What we provide:**
- A ready-made agent with pre-defined tools (search, lookup, filter)
- Configurable system prompt that defines the agent's personality and behavior
- Database connectors (MongoDB + ChromaDB vector search)
- Both `talk()` and REST API (`POST /uc-agent`) interfaces

```
User (dostEvent) → Generic Agent (prompt + DB) → dostEvent response + metrics
```

**Reusable across domains** — spin up different agents by changing `DOMAIN_CONFIG` in `.env`:
```bash
# app/.env
DOMAIN_CONFIG=urban_company   # or: myntra, swiggy
AGENT_ENTITY_ID=com.urban.company
AGENT_NAME=UrbanBot
```

**Built-in domains:** `urban_company` (home services), `myntra` (fashion), `swiggy` (food delivery)

**Test it:**
```bash
cd generic
pip install -r requirements.txt
python3 playground.py --config configs/urban_company.yaml -v
```

---

### Way 3: Custom — "I have REST APIs"

**For:** Developers who have their own REST APIs for their service — booking endpoints, search endpoints, CRUD operations — and want an AI agent in front of them.

**How it works:** Define your REST API endpoints as tools in a YAML config file. The agent loads them, understands natural language via a ReAct loop, and calls your APIs with the right parameters. Supports bearer tokens, API keys, OAuth2, and basic auth.

**What the developer provides:**
- REST API endpoints (documented in YAML)
- API credentials

**What we provide:**
- YAML-driven tool registration (no code needed)
- ReAct agent with configurable prompts per domain (ride booking, e-commerce, food delivery, etc.)
- Auth handling (bearer, api_key, basic, oauth2)
- Response mapping from API JSON to dostObjects

```
User (dostEvent) → Custom Agent (YAML tools) → REST APIs → dostEvent response + metrics
```

**Config example:**
```yaml
service:
  name: "themealdb"
  base_url: "https://www.themealdb.com/api/json/v1/1"
agent:
  prompt_name: "food_delivery"
auth:
  type: "none"
tools:
  - name: "search_meals"
    endpoint: "/search.php"
    method: "GET"
    parameters:
      - name: "s"
        type: "string"
        required: true
        in: "query"
```

**Test it:**
```bash
cd custom
pip install -r requirements.txt
python3 mealdb-playground.py    # FREE API, works immediately
```

---

## Comparison

| | MCP | Generic | Custom |
|---|---|---|---|
| **Who is it for** | Devs with MCP servers | Anyone with just data | Devs with REST APIs |
| **What they provide** | MCP server URL | Data + prompt | API endpoints in YAML |
| **Tool discovery** | Automatic from MCP | Pre-built per domain | YAML config |
| **Code required** | None (just YAML config) | None (just prompt + data) | None (just YAML config) |
| **Auth support** | OAuth via mcp-remote | N/A | Bearer, API key, Basic, OAuth2 |
| **LLM** | ReAct agent (OpenAI) | LangGraph ReAct (OpenAI) | ReAct agent (OpenAI) |
| **Config** | YAML + .env | .env (Settings class) | YAML + .env |
| **talk()** | Yes | Yes | Yes |
| **Metrics** | TalkMetrics (DPA format) | TalkMetrics (DPA format) | TalkMetrics (DPA format) |
| **Multi-domain** | Per YAML config | DOMAIN_CONFIG env var | Per YAML config |

---

## How Agents Connect to DOST

All three types produce the same thing: an async `talk()` function.

```python
async def talk(dostEvent) -> (dostEvent, metrics)
```

To make an agent available to clients:

1. **Host it** — We create a WebSocket server around the `talk()` function
2. **Register in DAS** — The agent gets an entity ID (e.g., `agent.mcp.zomato`, `agent.custom.mealdb`) and is registered in the DOST Agent Store so clients can discover it
3. **Clients talk to it** — A client sends a dostEvent over the socket, the agent processes it, and sends back a dostEvent response with structured data (dostObjects) and metrics

```
Client (DOST app)
    │
    ▼ dostEvent over WebSocket
    │
┌───────────────────────────┐
│  Agent Socket Server      │
│  (WebSocket wrapper)      │
│    │                      │
│    ▼                      │
│  talk(dostEvent)          │
│    │                      │
│    ├── MCP Bridge         │  ← Way 1
│    ├── Generic Agent      │  ← Way 2
│    └── Custom REST Agent  │  ← Way 3
│    │                      │
│    ▼                      │
│  (dostEvent, metrics)     │
└───────────────────────────┘
    │
    ▼ dostEvent response
Client receives structured response
```

---

## dostEvent Protocol

Every agent speaks dostEvent (version `00.01.01`):

**Input:**
```json
{
  "version": "00.01.01",
  "sourceEntityId": "hum.user.123",
  "destinationEntityId": "agent.custom.mealdb",
  "sessionId": "...",
  "isAiGenerated": false,
  "eventHint": "user_message",
  "message": { "text": { "data": "Show me Indian dishes" } }
}
```

**Output:**
```json
{
  "version": "00.01.01",
  "sourceEntityId": "agent.custom.mealdb",
  "destinationEntityId": "hum.user.123",
  "sessionId": "...",
  "isAiGenerated": true,
  "eventHint": "search_results",
  "message": { "text": { "data": "Found 15 Indian dishes for you." } },
  "categories": {
    "currency": "INR",
    "categories": [
      {
        "title": "Cuisine Results",
        "objects": [
          { "title": "Butter Chicken", "media": { "images": [...] } },
          { "title": "Dal Makhani", "media": { "images": [...] } }
        ]
      }
    ]
  }
}
```

**Metrics** (DPA billing format — per-model token counts):
```json
{
  "models": {
    "gpt-4o-mini": {
      "input_tokens": 1834,
      "output_tokens": 44
    }
  }
}
```

---

## Quick Start

```bash
# Install shared module first (required by all 3)
pip install -e shared/

# Way 1: MCP (need an MCP server)
cd mcp
pip install -r requirements.txt
python3 playground.py --config configs/airbnb.yaml

# Way 2: Generic (need data + MongoDB)
cd generic
pip install -r requirements.txt
python3 playground.py --config configs/urban_company.yaml

# Way 3: Custom REST API (need API endpoints)
cd custom
pip install -r requirements.txt
python3 mealdb-playground.py          # FREE API, no token needed
```

Or install everything at once from root:
```bash
pip install -r requirements.txt
```

---

## Architecture

All three ways share the same core pattern and the `shared/dost` module:

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Module                            │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌────────────────────────┐ │
│  │ protocol │    │  agent   │    │   tool source          │ │
│  │(shared/  │    │ (ReAct)  │    │                        │ │
│  │  dost)   │    │          │    │  MCP: MCP server       │ │
│  │  IN/OUT  │◄──►│  OpenAI  │◄──►│  Generic: Database     │ │
│  │          │    │  LLM     │    │  Custom: REST APIs     │ │
│  └──────────┘    └──────────┘    └────────────────────────┘ │
│                                                             │
│  ┌──────────┐                                               │
│  │ metrics  │  TalkMetrics (shared/dost)                    │
│  │(DPA fmt) │  Per-model token tracking for billing         │
│  └──────────┘                                               │
│                                                             │
│  talk(dostEvent) → (dostEvent, metrics)                     │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
   Register in DAS              Host on WebSocket
   (agent discovery)            (client communication)
```

---

## Project Structure

```
agent-onboarding/
├── README.md
├── requirements.txt          # Root: installs shared + all 3 templates
│
├── shared/                   # Shared DOST protocol + metrics
│   ├── pyproject.toml
│   └── dost/
│       ├── __init__.py
│       ├── protocol.py       # DOST Event Spec v00.01.01
│       └── metrics.py        # TalkMetrics class
│
├── mcp/                      # Way 1: MCP Server Bridge
│   ├── requirements.txt
│   ├── main.py               # CLI entry point
│   ├── playground.py         # Interactive testing
│   ├── configs/              # YAML configs (airbnb, test-server)
│   └── app/
│       ├── config.py         # Settings (YAML + .env)
│       ├── engine/talk.py    # talk() function
│       ├── llm/              # ReAct agent, response formatter
│       └── client/           # MCP client, transport
│
├── generic/                  # Way 2: Generic Agent
│   ├── requirements.txt
│   ├── config.py             # Settings (.env, lazy-loaded)
│   ├── main.py               # FastAPI server
│   ├── playground.py         # Interactive testing
│   ├── configs/              # Domain YAML configs
│   └── app/
│       ├── .env              # Environment config
│       ├── engine/talk.py    # talk() function
│       ├── core/
│       │   ├── generic_agent.py   # LangGraph ReAct agent
│       │   ├── database.py        # MongoDB
│       │   └── vector_store.py    # ChromaDB
│       ├── api/routes.py     # REST endpoint (POST /uc-agent)
│       ├── domains/          # Domain configs (urban_company, myntra, swiggy)
│       └── tools/            # LangChain tools
│
└── custom/                   # Way 3: Custom REST API Agent
    ├── requirements.txt
    ├── mealdb-playground.py  # Interactive testing (TheMealDB)
    ├── configs/              # YAML API configs (mealdb, template)
    └── app/
        ├── config.py         # Settings (.env, lazy-loaded)
        ├── engine/talk.py    # talk() function
        ├── llm/              # ReAct agent, prompts, response formatter
        └── custom/           # REST client, auth, executor
```
