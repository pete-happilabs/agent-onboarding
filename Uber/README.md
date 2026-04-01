# Uber Agent (Generic Template)

Conversational AI agent for ride booking - search rides, compare prices, and book trips.
Built using the **Generic Agent** template with LangGraph.

## Setup

1. Install dependencies:
```bash
cd Uber
pip install -r requirements.txt
```

2. Add your OpenAI API key to `.env`:
```
OPENAI_API_KEY=sk-...
```

No database needed - uses in-memory mock data for ride types and bookings.

## Run

```bash
python playground.py              # interactive mode
python playground.py -v           # verbose (see tool calls)
python playground.py -f           # full JSON output
```

## How it works

- Uses the Generic template's LangGraph ReAct agent
- Uber domain config provides the system prompt and tools
- Mock tools simulate ride search, pricing, and booking
- Ride types: UberGo, Uber Premier, UberXL, Uber Auto, Uber Moto
- Returns dostEvent responses with ride information

## Sample prompts

- "I need a ride from Connaught Place to the airport"
- "What ride types are available?"
- "Show me UberGo details and pricing"
- "Book an Uber Auto from MG Road to Koramangala"
- "How much does an UberXL cost?"
