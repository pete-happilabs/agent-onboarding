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
├── mcp/        # Way 1: MCP Server Bridge
├── generic/    # Way 2: Generic Agent (just data + prompt)
└── custom/     # Way 3: Custom REST API Agent + prompt
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
python3 playground.py --config configs/airbnb.yaml -v
```

---

### Way 2: Generic — "I just have data"

**For:** Someone with no technical resources — no APIs, no MCP server. They just have data (a database, documents, spreadsheets, a catalog) and want an AI agent that can answer questions about it.

**How it works:** Change the system prompt and point to a database. The agent becomes whatever you describe in the prompt — a restaurant guide, a real estate assistant, a product catalog. No code changes needed, just configuration.

**What the developer provides:**
- Data (database, CSV, documents)
- A description of what the agent should do (the prompt)

**What we provide:**
- A ready-made agent with pre-defined tools (search, lookup, filter)
- Configurable system prompt that defines the agent's personality and behavior
- Database connectors

```
User (dostEvent) → Generic Agent (prompt + DB) → dostEvent response
```

**Example use cases:**
- Restaurant owner with a menu database → "Food ordering assistant"
- Real estate agent with property listings → "Property search assistant"
- College with course catalog → "Admissions assistant"

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
User (dostEvent) → Custom Agent (YAML tools) → REST APIs → dostEvent response
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
python3 mealdb-playground.py    # FREE API, works immediately
```

---

## Comparison

| | MCP | Generic | Custom |
|---|---|---|---|
| **Who is it for** | Devs with MCP servers | Anyone with just data | Devs with REST APIs |
| **What they provide** | MCP server URL | Data + prompt | API endpoints in YAML |
| **Tool discovery** | Automatic from MCP | Pre-built | YAML config |
| **Code required** | None (just YAML config) | None (just prompt + data) | None (just YAML config) |
| **Auth support** | OAuth via mcp-remote | N/A | Bearer, API key, Basic, OAuth2 |
| **LLM** | ReAct agent (OpenAI) | ReAct agent (OpenAI) | ReAct agent (OpenAI) |
| **Input/Output** | dostEvent | dostEvent | dostEvent |
| **Metrics** | DPA format | DPA format | DPA format |

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

**For MCP and Custom agents:** We wrap the `talk()` function in a WebSocket server, host it, and register the agent's entity ID in DAS. Once registered, any DOST client can discover the agent and talk to it directly.

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
          { "title": "Butter Chicken", "media": { "images": ["..."] } },
          { "title": "Dal Makhani",    "media": { "images": ["..."] } }
        ]
      }
    ]
  }
}
```

**Metrics** (DPA format):
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
# Way 1: MCP (need an MCP server)
cd mcp
pip install -r requirements.txt
python3 playground.py --config configs/airbnb.yaml

# Way 2: Generic (need data + prompt)
cd generic

# Way 3: Custom REST API (need API endpoints + prompt)
cd custom
pip install -r requirements.txt
python3 mealdb-playground.py          # FREE API, no token needed
python3 uber-playground.py            # Needs UBER_API_TOKEN
python3 flipkart-playground.py        # Needs FLIPKART_AFFILIATE_ID
```

---

## Architecture

All three ways share the same core pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Module                            │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌────────────────────────┐ │
│  │ protocol │    │  agent   │    │   tool source          │ │
│  │(dostEvent)│   │ (ReAct)  │    │                        │ │
│  │          │    │          │    │  MCP: MCP server       │ │
│  │  IN/OUT  │◄──►│  OpenAI  │◄──►│  Generic: Database     │ │
│  │          │    │  LLM     │    │  Custom: REST APIs     │ │
│  └──────────┘    └──────────┘    └────────────────────────┘ │
│                                                             │
│  talk(dostEvent) → (dostEvent, metrics)                     │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
   Register in DAS              Host on WebSocket
   (agent discovery)            (client communication)
```

---
---

## 🛡️ Resilience

All three agents are production-hardened with the same resilience layer:

dostEvent
│
▼
validate_dost_event() ← Rejects malformed input before any processing
│
▼
with_timeout(agent.run()) ← Hard cap prevents hung WebSocket connections
│
├── LLM calls ← Retry ×3 with exponential backoff
│
└── External calls ← AsyncCircuitBreaker
CLOSED → calls pass through
OPEN → CircuitBreakerOpen → "Service unavailable" (user-facing)
HALF_OPEN → probe after recovery_timeout


### Input Validation

Every `talk()` validates the incoming dostEvent before touching any LLM or tool:

```python
validate_dost_event(event)   # raises ValueError if sourceEntityId or sessionId missing

Invalid events get a structured error dostEvent back immediately — no LLM call is made.

Hard Timeouts
| Agent   | Timeout | Reason                                      |
| ------- | ------- | ------------------------------------------- |
| Custom  | 28s     | Less than typical WebSocket gateway timeout |
| MCP     | 28s     | MCP server calls can hang indefinitely      |
| Generic | 55s     | LangGraph ReAct loops can be multi-step     |

Retry Logic
LLM API calls (OpenAI / LangChain) are retried up to 3 times with exponential backoff on any transient failure (rate limits, 500s, network blips):
Attempt 1 → fail → wait 1s
Attempt 2 → fail → wait 2s
Attempt 3 → fail → wait 4s (capped at 8s)
Attempt 4 → reraise

Circuit Breaker
External service calls (REST APIs in Custom, MCP connect/call in MCP) are protected by AsyncCircuitBreaker:
| Parameter         | Custom REST | MCP Connect | MCP Call |
| ----------------- | ----------- | ----------- | -------- |
| failure_threshold | 5           | 3           | 5        |
| recovery_timeout  | 30s         | 60s         | 30s      |

MCP connect has a lower threshold (3) and longer recovery (60s) because an MCP server going down is a harder failure than a single tool call failing.

When a circuit is OPEN, the user receives:
"Service temporarily unavailable. Please try again shortly."
— never a raw Python exception.

Resilience Files
custom/app/core/resilience.py    ← AsyncCircuitBreaker, with_timeout, llm_retry
mcp/app/core/resilience.py       ← identical
generic/app/core/resilience.py   ← identical

***

## Also Update Test Structure Block

Replace the existing test structure tree with:

```markdown
agent-onboarding/
├── mcp/test-suites/
│ ├── conftest.py
│ ├── pytest.ini
│ ├── requirements-test.txt
│ ├── contract/
│ │ └── test_dostevent_schema.py # 2 contract tests
│ ├── integration/
│ │ └── test_talk_function.py # 4 integration tests
│ └── unit/
│ ├── test_dostevent_parser.py
│ ├── test_metrics_and_resilience.py
│ ├── test_protocol_and_errors.py
│ └── test_resilience.py # 28 resilience tests ← NEW
│
├── custom/test-suites/ # Same structure as MCP
│ └── unit/
│ └── test_resilience.py # 36 resilience tests ← NEW
│
└── generic/test-suites/
└── unit/
└── test_resilience.py # 28 resilience tests ← NEW
undefined

## 🧪 Test Suites

Production-grade test suites are provided for all three agents.

### Test Coverage

| Agent | Total Tests | Unit | Integration | Contract |
|-------|-------------|------|-------------|----------|
| **MCP** | 71 | 65 | 4 | 2 |
| **Custom** | 78 | 72 | 3 | 2 |
| **Generic** | 71 | 65 | 4 | 2 |
| **TOTAL** | **220** | **202** | **11** | **6** |


### Run All Tests

```powershell
# Activate venv first
.\venv\Scripts\Activate.ps1

# MCP Agent
cd mcp\test-suites
pytest -v

# Custom Agent
cd ..\..\custom\test-suites
pytest -v

# Generic Agent
cd ..\..\generic\test-suites
pytest -v
```

### Run by Test Type

```powershell
pytest -m unit        # Unit tests only
pytest -m integration # Integration tests only
pytest -m contract    # Contract tests only
```

### Test Categories

**Unit Tests (111 tests)**
- dostEvent protocol validation per DOST spec v00.01.01
- Error handling and edge cases (missing fields, invalid types)
- DPA metrics format (token tracking per model)
- dostEvent parsing and extraction

**Integration Tests (11 tests)**
- Real `talk()` function — MCP and Custom agents
- Real `process_message()` — Generic agent
- End-to-end workflows with mocked LLM and tool dependencies

**Contract Tests (6 tests)**
- DOST spec v00.01.01 compliance
- Schema validation (required fields, types, version format)

### Test Structure

```
agent-onboarding/
├── mcp/test-suites/
│   ├── conftest.py                          # Shared fixtures
│   ├── pytest.ini                           # Pytest config + markers
│   ├── requirements-test.txt                # Test dependencies
│   ├── contract/
│   │   └── test_dostevent_schema.py         # 2 contract tests
│   ├── integration/
│   │   └── test_talk_function.py            # 4 integration tests
│   └── unit/
│       ├── test_dostevent_parser.py         # Parser unit tests
│       ├── test_metrics_and_resilience.py   # Metrics unit tests
│       └── test_protocol_and_errors.py      # Protocol error tests
│
├── custom/test-suites/                      # Same structure as MCP
│   └── ...
│
└── generic/test-suites/                     # Same structure, adapted
    └── integration/
        └── test_generic_agent.py            # Tests process_message()
```

### Test Conventions

- **Markers:** `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.contract`
- **Fixtures:** Shared in `conftest.py` per agent
- **Naming:** `test_*.py` for all test files
- **Mocking:** Real code imports + mocked external dependencies (LLM, MCP server, REST APIs)
- **Async:** `@pytest.mark.asyncio` for all async tests

### Environment Setup

```bash
# Create and activate venv
python -m venv venv
.\venv\Scripts\Activate.ps1      # Windows
source venv/bin/activate          # macOS/Linux

# Install test dependencies per agent
pip install -r mcp/requirements.txt
pip install -r mcp/test-suites/requirements-test.txt

pip install -r custom/requirements.txt
pip install -r custom/test-suites/requirements-test.txt

pip install -r generic/requirements.txt
pip install -r generic/test-suites/requirements-test.txt
```

> **Note:** Never commit `.env` files. Copy `.env.example` to `.env` and fill in your keys locally.
