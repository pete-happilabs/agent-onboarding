"""
Swiggy domain tools for restaurant search and ordering.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain.tools import tool

logger = logging.getLogger(__name__)

# Load restaurant data
DATA_FILE = Path(__file__).parent / "data.json"

def _load_data() -> Dict[str, List[Dict]]:
    """Load restaurant data from JSON file."""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load Swiggy data: {e}")
        return {"restaurants": []}

def _normalize_city(city: str) -> str:
    """Normalize city names for matching."""
    return city.lower().strip()


@tool
def search_restaurants(query: str, city: str = "", cuisine: str = "") -> str:
    """
    Search for restaurants by name, city, or cuisine type.
    
    Args:
        query: Restaurant name or search term
        city: Filter by city (Bangalore, Delhi, Mumbai)
        cuisine: Filter by cuisine type (North Indian, South Indian, Chinese, etc.)
    
    Returns:
        Formatted list of matching restaurants with details
    
    Use this when user asks: "Find restaurants", "Show me North Indian food", etc.
    """
    try:
        data = _load_data()
        restaurants = data.get("restaurants", [])
        
        # Apply filters
        results = []
        city_norm = _normalize_city(city) if city else ""
        cuisine_lower = cuisine.lower() if cuisine else ""
        query_lower = query.lower()
        
        for r in restaurants:
            # City filter
            if city_norm and _normalize_city(r["location"]["city"]) != city_norm:
                continue
            
            # Cuisine filter
            if cuisine_lower:
                cuisines_lower = [c.lower() for c in r["cuisine"]]
                if not any(cuisine_lower in c for c in cuisines_lower):
                    continue
            
            # Query match (name or description)
            if query_lower:
                if query_lower not in r["name"].lower() and query_lower not in r["description"].lower():
                    # Check cuisine as well
                    if not any(query_lower in c.lower() for c in r["cuisine"]):
                        continue
            
            results.append(r)
        
        if not results:
            filter_info = []
            if city: filter_info.append(f"in {city}")
            if cuisine: filter_info.append(f"for {cuisine} cuisine")
            filters = " ".join(filter_info)
            return f"Sorry, no restaurants found for '{query}' {filters}. Try a different search or city."
        
        # Format response
        response_parts = [f"Found {len(results)} restaurant(s):\n"]
        
        for i, r in enumerate(results[:10], 1):  # Limit to 10
            cuisines = ", ".join(r["cuisine"])
            offers = " | ".join(r["offers"]) if r.get("offers") else "No offers"
            
            response_parts.append(
                f"{i}. {r['name']} ({r['location']['area']})\n"
                f"   Cuisine: {cuisines}\n"
                f"   Rating: {r['rating']}★ ({r['reviews_count']} reviews)\n"
                f"   Cost for 2: ₹{r['cost_for_two']} | Delivery: {r['delivery_time_mins']} mins\n"
                f"   Offers: {offers}\n"
            )
        
        if len(results) > 10:
            response_parts.append(f"\n... and {len(results) - 10} more restaurants.")
        
        return "\n".join(response_parts)
    
    except Exception as e:
        logger.exception("Error in search_restaurants")
        return f"Sorry, I encountered an error searching for restaurants: {str(e)}"


@tool
def show_menu(restaurant_id: str) -> str:
    """
    Display the menu for a specific restaurant.
    
    Args:
        restaurant_id: ID of the restaurant (e.g., 'rest_001')
    
    Returns:
        Formatted menu with items, prices, and categories
    
    Use this when user says: "Show menu", "What do they have?", "Menu for [restaurant]"
    """
    try:
        data = _load_data()
        restaurants = data.get("restaurants", [])
        
        restaurant = None
        for r in restaurants:
            if r["restaurant_id"] == restaurant_id:
                restaurant = r
                break
        
        if not restaurant:
            return f"Restaurant '{restaurant_id}' not found. Please search again."
        
        # Format menu by category
        menu_items = restaurant.get("menu", [])
        if not menu_items:
            return f"{restaurant['name']} doesn't have a menu available."
        
        # Group by category
        categories: Dict[str, List[Dict]] = {}
        for item in menu_items:
            cat = item.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        
        # Build response
        response_parts = [
            f"📋 Menu for {restaurant['name']}\n",
            f"Cuisine: {', '.join(restaurant['cuisine'])}\n",
            f"Cost for 2: ₹{restaurant['cost_for_two']}\n"
        ]
        
        for category, items in categories.items():
            response_parts.append(f"\n--- {category} ---")
            for item in items:
                veg_icon = "🟢" if item.get("veg") else "🔴"
                desc = f" - {item['description']}" if item.get("description") else ""
                response_parts.append(
                    f"{veg_icon} {item['name']}: ₹{item['price']}{desc}"
                )
        
        return "\n".join(response_parts)
    
    except Exception as e:
        logger.exception("Error in show_menu")
        return f"Sorry, couldn't load menu: {str(e)}"


@tool
def place_order(restaurant_id: str, items: str, delivery_address: str) -> str:
    """
    Place a food order (mock - simulates order placement).
    
    Args:
        restaurant_id: ID of restaurant
        items: Comma-separated list of item names and quantities (e.g., "Paneer Tikka x2, Naan x3")
        delivery_address: Full delivery address
    
    Returns:
        Order confirmation with estimated delivery time
    
    Use this ONLY after user has confirmed all details.
    """
    try:
        data = _load_data()
        restaurants = data.get("restaurants", [])
        
        restaurant = None
        for r in restaurants:
            if r["restaurant_id"] == restaurant_id:
                restaurant = r
                break
        
        if not restaurant:
            return "Restaurant not found. Please start over."
        
        # Generate mock order ID
        import random
        order_id = f"SWG{random.randint(100000, 999999)}"
        
        # Calculate estimated time
        delivery_time = restaurant.get("delivery_time_mins", 40)
        
        return (
            f"✅ Order Placed Successfully!\n\n"
            f"Order ID: {order_id}\n"
            f"Restaurant: {restaurant['name']}\n"
            f"Items: {items}\n"
            f"Delivery Address: {delivery_address}\n"
            f"Estimated Delivery: {delivery_time} minutes\n\n"
            f"You can track your order anytime!"
        )
    
    except Exception as e:
        logger.exception("Error in place_order")
        return f"Order failed: {str(e)}"


# Export tools for domain registry
TOOLS = [
    search_restaurants,
    show_menu,
    place_order
]
