"""Test Myntra with verbose logging."""
import asyncio
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

from app.core.generic_agent import GenericReActAgent
from app.domains import get_domain_config

async def test():
    config = get_domain_config('myntra')
    agent = GenericReActAgent(config)
    
    print('\n' + '='*70)
    print('VERBOSE MYNTRA TEST')
    print('='*70 + '\n')
    
    result = await agent.process_message(
        'Show me Nike t-shirts for men',
        'test_user'
    )
    
    print('\n' + '='*70)
    print('FINAL RESPONSE:')
    print('='*70)
    print(result['response'])

asyncio.run(test())
