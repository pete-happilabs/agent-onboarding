"""
Myntra domain tools for fashion product search and shopping.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from langchain.tools import tool


logger = logging.getLogger(__name__)


DATA_FILE = Path(__file__).parent / "data.json"


def _load_data() -> Dict[str, List[Dict]]:
    """Load product data from JSON."""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load Myntra data: {e}")
        return {"products": []}


@tool
def search_products(query: str, category: str = "", brand: str = "", gender: str = "") -> str:
    """
    Search for fashion products by name, category, brand, or gender.
    
    Args:
        query: Product name or search term (e.g., "t-shirt", "jeans", "nike shoes")
        category: Filter by category (Sports Wear, Casual Wear, Footwear, etc.)
        brand: Filter by brand (Nike, Adidas, Levi's, etc.)
        gender: Filter by gender (Men, Women, Unisex)
    
    Returns:
        List of matching products with details
    
    Use when user asks: "Show me Nike shoes", "Women's dresses", etc.
    """
    try:
        data = _load_data()
        products = data.get("products", [])
        
        results = []
        
        # Split query into keywords for better matching
        query_keywords = query.lower().split() if query else []
        
        for p in products:
            # Category filter
            if category and category.lower() not in p["category"].lower():
                continue
            
            # Brand filter
            if brand and brand.lower() != p["brand"].lower():
                continue
            
            # Gender filter
            if gender and p.get("gender", "").lower() != gender.lower():
                continue
            
            # Keyword matching - product matches if ANY keyword is found
            if query_keywords:
                # Build searchable text from product fields
                searchable_text = " ".join([
                    p["name"].lower(),
                    p.get("description", "").lower(),
                    p["category"].lower(),
                    p.get("subcategory", "").lower(),
                    p["brand"].lower(),
                    p.get("gender", "").lower()
                ])
                
                # Check if ANY keyword appears in searchable text
                keyword_match = any(keyword in searchable_text for keyword in query_keywords)
                
                if not keyword_match:
                    continue
            
            results.append(p)
        
        if not results:
            filters = []
            if category: filters.append(f"category '{category}'")
            if brand: filters.append(f"brand '{brand}'")
            if gender: filters.append(f"for {gender}")
            filter_str = ", ".join(filters)
            search_term = f"'{query}'" if query else "products"
            return f"No products found for {search_term} {filter_str}. Try different search terms or filters."
        
        # Format response
        response_parts = [f"Found {len(results)} product(s):\n"]
        
        for i, p in enumerate(results[:10], 1):
            discount_text = f"{p['discount_percentage']}% OFF" if p.get('discount_percentage') else ""
            sizes = ", ".join(p.get("sizes", []))
            colors = ", ".join(p.get("colors", []))
            tags_str = ", ".join(p.get("tags", []))
            
            response_parts.append(
                f"{i}. {p['name']}\n"
                f"   Brand: {p['brand']} | {p['category']}\n"
                f"   Price: ₹{p['price']} (MRP: ₹{p['mrp']}) {discount_text}\n"
                f"   Rating: {p['rating']}★ ({p['reviews_count']} reviews)\n"
                f"   Sizes: {sizes}\n"
                f"   Colors: {colors}\n"
                f"   {tags_str}\n"
            )
        
        if len(results) > 10:
            response_parts.append(f"\n... and {len(results) - 10} more products.")
        
        return "\n".join(response_parts)
    
    except Exception as e:
        logger.exception("Error in search_products")
        return f"Search error: {str(e)}"


@tool
def get_product_details(product_id: str) -> str:
    """
    Get detailed information about a specific product.
    
    Args:
        product_id: Product ID (e.g., 'MYN001')
    
    Returns:
        Complete product details
    
    Use when user asks: "Tell me more about this", "Show details", etc.
    """
    try:
        data = _load_data()
        products = data.get("products", [])
        
        product = None
        for p in products:
            if p["product_id"] == product_id:
                product = p
                break
        
        if not product:
            return f"Product '{product_id}' not found."
        
        discount = f"{product['discount_percentage']}% OFF" if product.get('discount_percentage') else "No discount"
        stock_status = "✅ In Stock" if product.get("in_stock") else "❌ Out of Stock"
        
        response = (
            f"📦 {product['name']}\n\n"
            f"Brand: {product['brand']}\n"
            f"Category: {product['category']} > {product.get('subcategory', 'N/A')}\n"
            f"Gender: {product.get('gender', 'Unisex')}\n\n"
            f"💰 Pricing:\n"
            f"Price: ₹{product['price']} (MRP: ₹{product['mrp']})\n"
            f"Discount: {discount}\n\n"
            f"📏 Available Sizes: {', '.join(product.get('sizes', []))}\n"
            f"🎨 Available Colors: {', '.join(product.get('colors', []))}\n\n"
            f"⭐ Rating: {product['rating']} ({product['reviews_count']} reviews)\n"
            f"Stock: {stock_status}\n\n"
            f"Description: {product.get('description', 'No description')}\n"
        )
        
        return response
    
    except Exception as e:
        logger.exception("Error in get_product_details")
        return f"Error loading product: {str(e)}"


@tool
def add_to_bag(product_id: str, size: str, color: str) -> str:
    """
    Add a product to shopping bag (mock simulation).
    
    Args:
        product_id: Product ID
        size: Selected size
        color: Selected color
    
    Returns:
        Confirmation message
    
    Use ONLY after user confirms size and color.
    """
    try:
        data = _load_data()
        products = data.get("products", [])
        
        product = None
        for p in products:
            if p["product_id"] == product_id:
                product = p
                break
        
        if not product:
            return "Product not found."
        
        # Validate size and color
        if size not in product.get("sizes", []):
            return f"Size '{size}' not available. Available sizes: {', '.join(product['sizes'])}"
        
        if color not in product.get("colors", []):
            return f"Color '{color}' not available. Available colors: {', '.join(product['colors'])}"
        
        return (
            f"✅ Added to Bag!\n\n"
            f"Product: {product['name']}\n"
            f"Brand: {product['brand']}\n"
            f"Size: {size} | Color: {color}\n"
            f"Price: ₹{product['price']}\n\n"
            f"You can continue shopping or proceed to checkout!"
        )
    
    except Exception as e:
        logger.exception("Error in add_to_bag")
        return f"Failed to add to bag: {str(e)}"


# Export tools
TOOLS = [
    search_products,
    get_product_details,
    add_to_bag
]
