"""Direct test of Myntra search function."""
import json
from pathlib import Path

# Load data
DATA_FILE = Path('app/domains/myntra/data.json')

def _load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def search_products(query: str, category: str = "", brand: str = "", gender: str = ""):
    """Search function (copy from tools.py)"""
    data = _load_data()
    products = data.get("products", [])
    
    results = []
    
    # Split query into keywords
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
        
        # Keyword matching
        if query_keywords:
            searchable_text = " ".join([
                p["name"].lower(),
                p.get("description", "").lower(),
                p["category"].lower(),
                p.get("subcategory", "").lower(),
                p["brand"].lower(),
                p.get("gender", "").lower()
            ])
            
            keyword_match = any(keyword in searchable_text for keyword in query_keywords)
            
            if not keyword_match:
                continue
        
        results.append(p)
    
    return results


# Test cases
print('='*70)
print('DIRECT FUNCTION TESTS')
print('='*70)

print('\nTest 1: query="Nike t-shirts for men"')
results = search_products('Nike t-shirts for men')
print(f'Found {len(results)} products')
for r in results[:3]:
    print(f'  - {r["name"]} ({r["brand"]}, {r.get("gender")})')

print('\n' + '-'*70)

print('\nTest 2: query="nike"')
results = search_products('nike')
print(f'Found {len(results)} products')
for r in results[:5]:
    print(f'  - {r["name"]} ({r["brand"]}, {r.get("gender")})')

print('\n' + '-'*70)

print('\nTest 3: query="t-shirt", brand="Nike", gender="Men"')
results = search_products('t-shirt', brand='Nike', gender='Men')
print(f'Found {len(results)} products')
for r in results:
    print(f'  - {r["name"]} ({r["brand"]}, {r.get("gender")})')

print('\n' + '-'*70)

print('\nTest 4: query="shirt", gender="Men"')
results = search_products('shirt', gender='Men')
print(f'Found {len(results)} products')
for r in results[:5]:
    print(f'  - {r["name"]} ({r["brand"]}, {r.get("gender")})')

print('\n' + '='*70)
