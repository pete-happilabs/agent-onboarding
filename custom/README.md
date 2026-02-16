# Custom REST API Agent

Create AI agents by hooking your REST APIs as tools. Same `talk()` interface, dostEvent input AND output as MCP/DPA.

## Overview

This module allows developers to create AI agents that:
- Understand natural language
- Call their REST APIs as tools
- Accept dostEvent as INPUT (from DOST)
- Return dostEvent as OUTPUT (to DOST)
- Track metrics in DPA format

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and customize config
cp configs/template-custom.yaml configs/my-service.yaml
# Edit: Define your REST endpoints as tools

# 3. Set environment variables
export OPENAI_API_KEY="sk-..."
export MY_API_TOKEN="your-api-token"
export CUSTOM_CONFIG_PATH="configs/my-service.yaml"

# 4. Test
python playground.py --interactive
```

## Architecture

```
custom/
├── app/
│   ├── .env                      # Environment variables
│   ├── config.py                 # Settings (LLM, Agent, Custom)
│   ├── core/
│   │   ├── protocol.py           # DOST Event spec
│   │   └── metrics.py            # Token tracking
│   ├── llm/
│   │   ├── agent.py              # ReAct agent with metrics
│   │   ├── prompts.py            # Configurable system prompts
│   │   ├── tool_converter.py     # REST tools → OpenAI format
│   │   └── response_formatter.py # API response → dostObjects
│   ├── custom/
│   │   ├── registry.py           # Load tools from YAML
│   │   ├── executor.py           # Execute REST API calls
│   │   ├── auth.py               # Auth handlers
│   │   └── client.py             # Unified interface
│   └── engine/
│       └── talk.py               # Main entry point
├── configs/
│   ├── template-custom.yaml      # Template for developers
│   └── uber-example.yaml         # Example: ride booking
├── playground.py                 # Test REPL
└── requirements.txt
```

## YAML Configuration

Define your REST APIs as tools:

```yaml
service:
  name: "my-service"
  base_url: "https://api.myservice.com/v1"

agent:
  prompt_name: "default"  # or: ride_booking, food_delivery, etc.

auth:
  type: "bearer"
  token_env: "MY_API_TOKEN"

tools:
  - name: "search_items"
    description: "Search for items"
    endpoint: "/items/search"
    method: "GET"
    parameters:
      - name: "query"
        type: "string"
        required: true
        in: "query"
    response_mapping:
      items_path: "data.items"
      title_field: "name"
      price_field: "price"
```

## Auth Types

```yaml
# Bearer Token
auth:
  type: "bearer"
  token_env: "MY_TOKEN"

# API Key
auth:
  type: "api_key"
  header: "X-API-Key"
  key_env: "MY_API_KEY"

# Basic Auth
auth:
  type: "basic"
  username_env: "MY_USERNAME"
  password_env: "MY_PASSWORD"

# OAuth2 (Client Credentials)
auth:
  type: "oauth2"
  token_url: "https://auth.example.com/token"
  client_id_env: "CLIENT_ID"
  client_secret_env: "CLIENT_SECRET"
```

## System Prompts

Change agent behavior by editing prompts in `app/llm/prompts.py` or using built-in prompts:

| Prompt Name | Use Case |
|-------------|----------|
| `default` | Generic assistant |
| `ride_booking` | Uber/Ola style |
| `food_delivery` | Zomato/Swiggy style |
| `hotel_booking` | OYO/Booking.com style |
| `ecommerce` | Amazon/Flipkart style |

Set in YAML:
```yaml
agent:
  prompt_name: "ride_booking"
```

## Usage

### Programmatic

```python
from app import talk
from app.core.protocol import create_dost_event, create_dost_message

# Create input dostEvent
event = create_dost_event(
    source_entity_id="user.123",
    message=create_dost_message(text="Book me a ride to the airport")
)

# Call talk
response_event, metrics = await talk(event)

# response_event: dostEvent with message and categories
# metrics: {"models": {"gpt-4o-mini": {"input_tokens": 150, "output_tokens": 50}}}
```

### Interactive

```bash
python playground.py --interactive
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `CUSTOM_CONFIG_PATH` | No | Path to YAML config (default: configs/custom.yaml) |
| `LLM_MODEL` | No | Model name (default: gpt-4o-mini) |
| `LLM_TEMPERATURE` | No | Temperature (default: 0.7) |
| `AGENT_ENTITY_ID` | No | Agent's entity ID |
| `CUSTOM_CURRENCY` | No | Currency code (default: INR) |

## Response Mapping

Map API response fields to dostObjects:

```yaml
response_mapping:
  items_path: "data.rides"        # Path to items array
  title_field: "vehicle_type"     # → dostObject.title
  description_field: "driver"     # → dostObject.description
  price_field: "fare"             # → dostObject.pricing
  image_field: "image_url"        # → dostObject.media.images
  reputation_field: "rating"      # → dostObject.reputation
  location_fields:
    latitude: "pickup.lat"
    longitude: "pickup.lng"
    address: "pickup.address"
```

## Flow

```
DOST sends dostEvent:
{
  "sourceEntityId": "user.123",
  "message": { "text": { "data": "Book me a ride" } }
}
    │
    ▼
┌───────────────────────────────────────────┐
│  talk(dostEvent)                          │
│    │                                      │
│    ├─ CustomClient.list_tools()           │
│    ├─ ReActAgent.run()                    │
│    │    ├─ OpenAI (track tokens)          │
│    │    └─ call_tool() → REST API         │
│    ├─ build_dost_categories()             │
│    └─ Return (dostEvent, metrics)         │
└───────────────────────────────────────────┘
    │
    ▼
DOST receives:
{
  "sourceEntityId": "agent.custom.uber",
  "isAiGenerated": true,
  "message": { "text": { "data": "Your ride is booked!" } },
  "categories": { "currency": "INR", "categories": [...] }
}
metrics: {"models": {"gpt-4o-mini": {...}}}
```
