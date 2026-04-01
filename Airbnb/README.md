# Airbnb Agent (MCP Template)

Conversational AI agent for searching Airbnb listings and getting property details.
Built using the **MCP Bridge** template.

## Setup

1. Install dependencies:
```bash
cd Airbnb
pip install -r requirements.txt
```

2. Add your OpenAI API key to `.env`:
```
OPENAI_API_KEY=sk-...
```

3. Ensure Node.js/npm is installed (needed for the MCP server).

## Run

```bash
python playground.py              # interactive mode
python playground.py -v           # verbose (see tool calls)
python playground.py -f           # full JSON output
```

## How it works

- Uses `@openbnb/mcp-server-airbnb` MCP server via stdio transport
- ReAct agent discovers tools automatically from the MCP server
- Supports: `airbnb_search`, `airbnb_listing_details`
- Returns dostEvent responses with structured property data

## Sample prompts

- "Find apartments in Paris for 2 guests"
- "Search for beachfront stays in Goa"
- "Show me places to stay in Tokyo under $100"
