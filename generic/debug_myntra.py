"""Debug script for Myntra products."""
import json
from pathlib import Path

# Load data
data_file = Path('app/domains/myntra/data.json')
with open(data_file) as f:
    data = json.load(f)

print('='*70)
print('MYNTRA DATA DEBUG')
print('='*70)

print(f'\nTotal products: {len(data["products"])}')

print('\n--- Nike Products ---')
nike_products = [p for p in data['products'] if 'Nike' in p['brand']]
print(f'Found {len(nike_products)} Nike products:')
for p in nike_products:
    print(f"  - {p['product_id']}: {p['name']}")
    print(f"    Brand: {p['brand']}, Gender: {p.get('gender', 'N/A')}")
    print(f"    Category: {p['category']}")

print('\n--- Men\'s Products ---')
mens_products = [p for p in data['products'] if p.get('gender') == 'Men']
print(f'Found {len(mens_products)} Men\'s products:')
for p in mens_products[:5]:  # Show first 5
    print(f"  - {p['product_id']}: {p['name']} ({p['brand']})")

print('\n--- All Products Summary ---')
for p in data['products']:
    print(f"{p['product_id']}: {p['name']} | {p['brand']} | {p.get('gender', 'N/A')}")

print('\n' + '='*70)

# Now test the tool directly
print('\nTESTING TOOL FUNCTION...\n')
print('='*70)

# Import the actual tool function (before @tool decorator)
import sys
sys.path.insert(0, 'app/domains/myntra')

# Read the tools file and extract the function
exec(open('app/domains/myntra/tools.py').read().replace('@tool', '# @tool'))

# Test search
print('\nTest 1: Searching for "Nike t-shirt Men"')
result = search_products('Nike t-shirt Men')
print(result)

print('\n' + '='*70)
print('\nTest 2: Searching for "nike"')
result = search_products('nike')
print(result)

print('\n' + '='*70)
print('\nTest 3: Searching for "t-shirt" with brand="Nike"')
result = search_products('t-shirt', brand='Nike')
print(result)
