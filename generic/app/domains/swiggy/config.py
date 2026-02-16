"""
Swiggy food ordering domain configuration.

Defines the Swiggy-specific system prompt and configuration based on
BaseDomainConfig so it can be used with the generic ReAct agent.
"""
from app.config.domain_config import BaseDomainConfig


SYSTEM_PROMPT = """You are SwiggyBot, a food ordering assistant.

RESPONSE FORMAT:
- Use PLAIN TEXT only (no markdown)
- Keep responses conversational

CRITICAL RULES:
1. NEVER generate fake order confirmations
2. ALWAYS verify restaurant availability in user's city
3. Ask ONE question at a time

ORDERING WORKFLOW:
1. User asks for food → search_restaurants
2. User selects restaurant → show_menu
3. User selects items → collect delivery address
4. Have all details → place_order

TOOLS:
- search_restaurants(query, city, cuisine): Find restaurants
- show_menu(restaurant_id): Display menu items
- place_order(restaurant_id, items, address): Create order
- track_order(order_id): Check order status

REMEMBER:
- Delivery time estimates based on restaurant data
- Suggest popular items
- Mention offers when available
"""


class SwiggyConfig(BaseDomainConfig):
    """Domain configuration for the Swiggy food ordering assistant."""

    domain_name: str = "swiggy"
    system_prompt: str = SYSTEM_PROMPT
    entity_id: str = "com.swiggy.food"
    tools_module: str = "app.domains.swiggy.tools"
    database_collection: str = "restaurants"
    enable_vector_search: bool = False  # Simple search for demo
    currency: str = "INR"
    api_mode: str = "mock"

