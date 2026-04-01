# Zomato Agent (Custom REST API Template)

Conversational AI agent for food discovery - search dishes, browse cuisines, and get recipes.
Built using the **Custom REST API** template with TheMealDB free API.

## Setup

1. Install dependencies:
```bash
cd Zomato
pip install -r requirements.txt
```

2. Add your OpenAI API key to `.env`:
```
OPENAI_API_KEY=sk-...
```

No food API key needed - TheMealDB is free!

## Run

```bash
python playground.py                          # interactive mode
python playground.py -v                       # verbose (see tool calls)
python playground.py -m "Search for biryani"  # single message
python playground.py -f                       # full JSON output
```

## How it works

- Calls TheMealDB REST API endpoints defined in `config.yaml`
- ReAct agent selects appropriate tools based on user query
- Tools: `search_food`, `browse_by_category`, `browse_by_cuisine`, `get_dish_details`, `surprise_me`, `list_all_categories`
- Returns dostEvent responses with structured food data as dostObjects

## Sample prompts

- "Search for biryani"
- "Show me Indian dishes"
- "What vegetarian options are available?"
- "Surprise me with a random dish"
- "Browse Italian cuisine"
