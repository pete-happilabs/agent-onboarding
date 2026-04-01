#!/usr/bin/env python3
# ============================================================================
# Zomato Food Discovery Playground (Custom REST API Template)
# ============================================================================
"""
Search for food, browse cuisines, and discover dishes.

Usage:
    python playground.py                          # interactive
    python playground.py -v                       # verbose
    python playground.py -m "Search for biryani"  # single message
    python playground.py -f                       # full JSON output
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path

# Setup paths
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(AGENT_DIR)
CUSTOM_DIR = os.path.join(REPO_ROOT, "custom")
sys.path.insert(0, CUSTOM_DIR)

# Load .env from this agent folder
from dotenv import load_dotenv
load_dotenv(os.path.join(AGENT_DIR, ".env"))

# Load custom template .env as fallback
load_dotenv(os.path.join(CUSTOM_DIR, "app", ".env"))

# Service-specific overrides
os.environ["CUSTOM_CONFIG_PATH"] = os.path.join(AGENT_DIR, "config.yaml")
os.environ.setdefault("AGENT_ENTITY_ID", "agent.custom.zomato")
os.environ.setdefault("AGENT_NAME", "Zomato Food Assistant")

from app.config import get_settings, reset_settings
from app.engine.talk import talk
from app.custom.client import CustomClient

logger = logging.getLogger(__name__)

SAMPLE_PROMPTS = [
    "Search for biryani",
    "Show me Indian dishes",
    "What vegetarian options are available?",
    "Surprise me with a random dish",
    "Browse Italian cuisine",
    "List all food categories",
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

    categories = event.get('categories')
    if categories and categories.get('categories'):
        cats = categories['categories']
        total_objects = sum(len(c.get('objects', [])) for c in cats)
        print(f"  categories:    {len(cats)} category(ies), {total_objects} dostObject(s)")

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
    reset_settings()
    settings = get_settings()

    print("\n" + "="*60)
    print("  Zomato Food Discovery Playground")
    print("="*60)
    print(f"  Agent:     {settings.agent.name}")
    print(f"  Entity ID: {settings.agent.entity_id}")
    print(f"  Config:    {settings.custom.config_path}")
    print(f"  Model:     {settings.llm.model}")
    print(f"  Auth:      None (FREE API)")
    print("="*60)

    print("\nLoading tools...")
    try:
        client = CustomClient(settings.custom.config_path)
        tools = await client.list_tools()
        print(f"Ready! Found {len(tools)} tools:")
        for tool_item in tools:
            print(f"  - {tool_item.name}: {tool_item.description}")
    except Exception as e:
        print(f"Failed to load tools: {e}")
        return

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

            input_event = {
                "version": "00.01.01",
                "sourceEntityId": "hum.playground.user",
                "sessionId": session_id,
                "destinationEntityId": settings.agent.entity_id,
                "isAiGenerated": False,
                "eventHint": "user_message",
                "message": {"text": {"data": user_input}}
            }

            print_dost_event("INPUT dostEvent", input_event)

            if show_full_json:
                print_json("INPUT (full JSON)", input_event)

            print("\nProcessing...")

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


async def single_message(message: str):
    """Send a single message and print result."""
    reset_settings()
    settings = get_settings()

    input_event = {
        "version": "00.01.01",
        "sourceEntityId": "hum.playground.user",
        "sessionId": str(uuid.uuid4()),
        "destinationEntityId": settings.agent.entity_id,
        "isAiGenerated": False,
        "eventHint": "user_message",
        "message": {"text": {"data": message}}
    }

    print_dost_event("INPUT dostEvent", input_event)
    print("\nProcessing...")

    output_event, metrics = await talk(input_event)

    print_dost_event("OUTPUT dostEvent", output_event)
    print_json("OUTPUT (full JSON)", output_event)
    print_json("METRICS", metrics)


def main():
    parser = argparse.ArgumentParser(description="Zomato Food Discovery Playground")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose mode")
    parser.add_argument("--full", "-f", action="store_true", help="Full JSON output")
    parser.add_argument("--message", "-m", default=None, help="Single message mode")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        logging.getLogger('app.llm.agent').setLevel(logging.INFO)
        logging.getLogger('app.llm.response_formatter').setLevel(logging.INFO)
        logging.getLogger('app.custom.executor').setLevel(logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    if args.message:
        asyncio.run(single_message(args.message))
    else:
        asyncio.run(playground(args.verbose, args.full))


if __name__ == "__main__":
    main()
