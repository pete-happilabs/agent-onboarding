#!/usr/bin/env python3
# ============================================================================
# Uber Ride Booking Playground (Generic Template)
# ============================================================================
"""
Book rides, check ride types, and get fare estimates.

Usage:
    python playground.py              # interactive mode
    python playground.py -v           # verbose (see tool calls)
"""
import asyncio
import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, Any

# Setup paths
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(AGENT_DIR)
GENERIC_DIR = os.path.join(REPO_ROOT, "generic")
sys.path.insert(0, GENERIC_DIR)

# Load .env from this agent folder
from dotenv import load_dotenv
load_dotenv(os.path.join(AGENT_DIR, ".env"))

# Load generic template .env as fallback
load_dotenv(os.path.join(GENERIC_DIR, "app", ".env"))
load_dotenv(os.path.join(GENERIC_DIR, ".env"))

# Set Uber-specific environment
os.environ["DOMAIN_CONFIG"] = "uber"
os.environ.setdefault("AGENT_ENTITY_ID", "com.uber.rides")
os.environ.setdefault("AGENT_NAME", "UberBot")
os.environ.setdefault("CURRENCY", "INR")

from app.core.generic_agent import GenericReActAgent
from app.domains import get_domain_config
from app.engine.talk import talk, set_agent
from dost.protocol import create_dost_event, create_dost_message

logger = logging.getLogger(__name__)

SAMPLE_PROMPTS = [
    "I need a ride from Connaught Place to the airport",
    "What ride types are available?",
    "Show me UberGo details and pricing",
    "Book an Uber Auto from MG Road to Koramangala",
    "How much does an UberXL cost?",
]


def print_dost_event(label: str, event: dict):
    """Pretty print a dostEvent."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print('='*60)
    print(f"  version:       {event.get('version')}")
    print(f"  eventId:       {event.get('eventId', '')[:8]}...")
    print(f"  sessionId:     {event.get('sessionId', '')[:8]}...")
    print(f"  sourceEntityId:      {event.get('sourceEntityId')}")
    print(f"  destinationEntityId: {event.get('destinationEntityId')}")
    print(f"  isAiGenerated: {event.get('isAiGenerated')}")
    print(f"  eventHint:     {event.get('eventHint')}")

    message = event.get('message', {})
    if message:
        text_data = message.get('text', {}).get('data', '')
        if len(text_data) > 200:
            print(f"  message.text:  {text_data[:200]}...")
            print(f"                 ({len(text_data)} chars total)")
        else:
            print(f"  message.text:  {text_data}")

    print('='*60)


def print_json(label: str, data: dict, max_lines: int = 0):
    """Print JSON with optional truncation."""
    print(f"\n--- {label} ---")
    json_str = json.dumps(data, indent=2)
    lines = json_str.split('\n')
    if max_lines > 0 and len(lines) > max_lines:
        print('\n'.join(lines[:max_lines]))
        print(f"... ({len(lines) - max_lines} more lines)")
    else:
        print(json_str)


async def playground(verbose: bool = False, full_json: bool = False):
    """Interactive playground."""
    # Initialize Uber domain agent
    print("\nInitializing UberBot...")
    try:
        config = get_domain_config("uber")
        agent = GenericReActAgent(config)
        set_agent(agent)
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        return

    print("\n" + "="*60)
    print("  Uber Ride Booking Playground")
    print("="*60)
    print(f"  Agent:     {config.domain_name.replace('_', ' ').title()}")
    print(f"  Entity ID: {config.entity_id}")
    print(f"  Currency:  {config.currency}")
    print(f"  LLM:       ENABLED")
    print(f"  Model:     gpt-4o-mini")
    print("="*60)

    print("\n" + "-"*60)
    print("Type your message to see:")
    print("  1. INPUT dostEvent (what we send)")
    print("  2. OUTPUT dostEvent (what we receive)")
    print("Type 'quit' to exit, 'json' for full JSON output")
    print("\nSample prompts:")
    for i, p in enumerate(SAMPLE_PROMPTS, 1):
        print(f"  {i}. {p}")
    print("-"*60)

    session_id = str(uuid.uuid4())
    show_full_json = full_json

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit']:
                print("Goodbye!")
                break

            if user_input.lower() == 'json':
                show_full_json = not show_full_json
                print(f"Full JSON output: {'ON' if show_full_json else 'OFF'}")
                continue

            # Build INPUT dostEvent
            input_event = create_dost_event(
                source_entity_id="hum.playground.user",
                destination_entity_id=config.entity_id,
                session_id=session_id,
                event_hint="user_message",
                is_ai_generated=False,
                message=create_dost_message(text=user_input)
            )

            print_dost_event("INPUT dostEvent", input_event)

            if show_full_json:
                print_json("INPUT (full JSON)", input_event)

            print("\nProcessing...")

            # Call talk()
            output_event, metrics = await talk(input_event)

            print_dost_event("OUTPUT dostEvent", output_event)

            if show_full_json:
                print_json("OUTPUT (full JSON)", output_event)
                print_json("METRICS", metrics)
            else:
                print(f"\nMetrics: {metrics}")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            if verbose:
                import traceback
                traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Uber Ride Booking Playground")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose mode")
    parser.add_argument("--full", "-f", action="store_true", help="Full JSON output")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        logging.basicConfig(level=logging.WARNING)

    asyncio.run(playground(args.verbose, args.full))


if __name__ == "__main__":
    main()
