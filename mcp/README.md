# MCP-to-dostEvent Bridge

A universal bridge for connecting **any MCP server** (like Zomato, Linear, Sentry) to the DOST ecosystem.

## Quick Start with Zomato

```bash
cd /Users/joydahiya/Documents/Projects/DOST/agent-onboarding/mcp

# Install dependencies
pip install -r requirements.txt

# Run interactive chat with Zomato
python main.py --config configs/zomato.yaml --interactive
```

**First run:** A browser window will open for Zomato OAuth login. Log in with your Zomato account.

**Then chat:**
```
You: Find restaurants near Koramangala
Zomato: Here are some restaurants near Koramangala...

You: Show me the menu for Truffles
Zomato: Here's the menu for Truffles...

You: Add 1 Classic Burger to my cart
Zomato: Added 1 Classic Burger to your cart...
```

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    dostEvent    │ ──► │   talk()        │ ──► │   mcp-remote    │
│  (your message) │     │  (this bridge)  │     │  (OAuth + HTTP) │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │  Zomato/Linear/ │
                                                │  Any MCP Server │
                                                └─────────────────┘
```

**Key:** We use [`mcp-remote`](https://github.com/geelen/mcp-remote) to handle OAuth authentication automatically.

## Supported MCP Servers

| Server | Config | OAuth Required |
|--------|--------|----------------|
| [Zomato](https://github.com/Zomato/mcp-server-manifest) | `configs/zomato.yaml` | Yes |
| [Linear](https://linear.app/docs/mcp) | Coming soon | Yes |
| [Sentry](https://docs.sentry.io/product/sentry-mcp/) | Coming soon | Yes |
| Test Server | `configs/test-server.yaml` | No |

## Configuration

### Transport Types

1. **`remote`** - For remote MCP servers with OAuth (Zomato, Linear, etc.)
   ```yaml
   mcp:
     transport: remote
     url: "https://mcp-server.zomato.com/mcp"
   ```

2. **`stdio`** - For local MCP servers (no OAuth)
   ```yaml
   mcp:
     transport: stdio
     command: "npx @modelcontextprotocol/server-everything"
   ```

3. **`sse`** - Direct HTTP/SSE (no OAuth, for self-hosted)
   ```yaml
   mcp:
     transport: sse
     url: "http://localhost:3000/sse"
   ```

### Full Config Options

```yaml
# mcp.yaml
mcp:
  transport: remote              # remote | stdio | sse
  url: "https://..."            # For remote/sse
  command: "npx ..."            # For stdio
  timeout: 60                   # Request timeout (seconds)

  # Remote-specific (OAuth)
  oauth_port: 3334              # OAuth callback port
  auth_timeout: 120             # OAuth login timeout
  transport_mode: http-first    # http-first | sse-first

agent:
  entity_id: "agent.mcp.zomato"
  name: "Zomato"
```

## Usage

### Interactive Mode

```bash
# Chat with Zomato
python main.py --config configs/zomato.yaml --interactive

# Test with mock server
python main.py --config configs/test-server.yaml --interactive
```

### Single Message Test

```bash
python main.py --config configs/zomato.yaml \
  --message "Find restaurants near Indiranagar"
```

### Programmatic Usage

```python
import asyncio
from app.config import get_settings
from app.engine.talk import talk

async def main():
    # Load Zomato config
    get_settings("configs/zomato.yaml")

    # Create dostEvent
    event = {
        "version": "00.01.01",
        "sourceEntityId": "hum.test.user",
        "sessionId": "order-session",
        "message": {"text": {"data": "Find pizza places near Koramangala"}}
    }

    # Call talk() - returns dostEvent
    response_event, metrics = await talk(event)
    print(response_event["message"]["text"]["data"])

asyncio.run(main())
```

### WebSocket Server (Optional)

Wrap `talk()` in a WebSocket for your backend:

```python
from fastapi import FastAPI, WebSocket
import json
from app.engine.talk import talk

app = FastAPI()

@app.websocket("/talk/{session_id}")
async def talk_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()

    while True:
        data = await websocket.receive_text()
        event = json.loads(data)
        event["sessionId"] = session_id

        response_event, metrics = await talk(event)

        await websocket.send_json({
            "event": response_event,
            "metrics": metrics
        })
```

## Adding New MCP Servers

1. Create a config file in `configs/`:
   ```yaml
   # configs/linear.yaml
   mcp:
     transport: remote
     url: "https://mcp.linear.app/mcp"
     auth_timeout: 120

   agent:
     entity_id: "agent.mcp.linear"
     name: "Linear"
   ```

2. Test it:
   ```bash
   python main.py --config configs/linear.yaml --interactive
   ```

3. Share the config!

## Project Structure

```
mcp/
├── main.py                      # CLI entry point
├── requirements.txt
├── README.md
│
├── configs/                     # Ready-to-use configs
│   ├── zomato.yaml             # Zomato food ordering
│   └── test-server.yaml        # MCP test server
│
└── app/                         # Application code
    ├── __init__.py
    ├── config.py               # Configuration loader
    │
    ├── core/                   # DOST Protocol
    │   └── protocol.py         # dostEvent spec
    │
    ├── engine/                 # Talk Engine
    │   └── talk.py             # talk(dostEvent) → dostEvent
    │
    └── client/                 # MCP Client
        ├── mcp_client.py       # MCP JSON-RPC client
        └── transport.py        # stdio/SSE transports
```

## Troubleshooting

### OAuth Issues

```bash
# Clear OAuth tokens and retry
rm -rf ~/.mcp-auth
python main.py --config configs/zomato.yaml --interactive
```

### Connection Timeout

Increase timeouts in config:
```yaml
mcp:
  timeout: 120
  auth_timeout: 180
```

### Debug Mode

```bash
python main.py --config configs/zomato.yaml --interactive --verbose
```

## Requirements

- Python 3.9+
- Node.js 16+ (for `npx mcp-remote`)
- Dependencies: `pip install -r requirements.txt`

## Sources

- [mcp-remote](https://github.com/geelen/mcp-remote) - OAuth bridge for remote MCP servers
- [Zomato MCP Server](https://github.com/Zomato/mcp-server-manifest)
- [Model Context Protocol](https://modelcontextprotocol.io/)
