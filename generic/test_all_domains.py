"""
Test script for all 3 domains: Urban Company, Swiggy, Myntra.
"""
import asyncio
import sys
from app.core.generic_agent import GenericReActAgent
from app.domains import get_domain_config

async def test_domain(domain_name: str, test_query: str):
    """Test a single domain with a sample query."""
    print(f"\n{'='*70}")
    print(f"🧪 Testing Domain: {domain_name.upper().replace('_', ' ')}")
    print(f"{'='*70}")
    print(f"Query: {test_query}\n")
    
    try:
        # Load config and create agent
        config = get_domain_config(domain_name)
        agent = GenericReActAgent(config)
        
        # Process message
        result = await agent.process_message(
            user_message=test_query,
            user_id=f"test_{domain_name}_user"
        )
        
        print(f"✅ Response:\n{result['response']}\n")
        print(f"State: {result.get('state', {})}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run tests for all domains."""
    print("\n" + "="*70)
    print("🚀 GENERIC AGENT TEMPLATE - MULTI-DOMAIN TEST")
    print("="*70)
    
    # Test 1: Urban Company
    await test_domain(
        "urban_company",
        "Show me plumbing services in Bangalore"
    )
    
    # Test 2: Swiggy
    await test_domain(
        "swiggy",
        "Find North Indian restaurants in Bangalore"
    )
    
    # Test 3: Myntra
    await test_domain(
        "myntra",
        "Show me Nike t-shirts for men"
    )
    
    print("\n" + "="*70)
    print("✅ ALL DOMAIN TESTS COMPLETED!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
