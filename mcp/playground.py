#!/usr/bin/env python3
# ============================================================================
# MCP Bridge Playground
# ============================================================================
"""
Test the MCP bridge and see dostEvents clearly.

Usage:
    python3 playground.py --config configs/airbnb.yaml
    python3 playground.py --config configs/test-server.yaml

    # Verbose mode - see ReAct agent tool calls
    python3 playground.py --config configs/airbnb.yaml -v
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from app.config import get_settings, reset_settings
from app.engine.talk import talk
from app.client.mcp_client import initialize_mcp_client, reset_mcp_client

# Will be configured based on --verbose flag
logger = logging.getLogger(__name__)


def print_dost_event(label: str, event: dict):
    """Pretty print a dostEvent."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print('='*60)

    # Key fields
    print(f"  version:       {event.get('version')}")
    print(f"  eventId:       {event.get('eventId', '')[:8]}...")
    print(f"  sessionId:     {event.get('sessionId', '')[:8]}...")
    print(f"  sourceEntityId:      {event.get('sourceEntityId')}")
    print(f"  destinationEntityId: {event.get('destinationEntityId')}")
    print(f"  isAiGenerated: {event.get('isAiGenerated')}")
    print(f"  eventHint:     {event.get('eventHint')}")

    # Message
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
    """Print JSON with optional truncation. max_lines=0 means no truncation."""
    print(f"\n--- {label} ---")
    json_str = json.dumps(data, indent=2)
    lines = json_str.split('\n')
    if max_lines > 0 and len(lines) > max_lines:
        print('\n'.join(lines[:max_lines]))
        print(f"... ({len(lines) - max_lines} more lines)")
    else:
        print(json_str)


async def playground(config_path: str, verbose: bool = False, full_json: bool = False):
    """Interactive playground for testing the MCP bridge."""
    reset_settings()
    reset_mcp_client()

    settings = get_settings(config_path)

    print("\n" + "="*60)
    print("  MCP Bridge Playground")
    print("="*60)
    print(f"  Agent:     {settings.agent.name}")
    print(f"  Entity ID: {settings.agent.entity_id}")
    print(f"  Transport: {settings.mcp.transport}")
    print(f"  LLM:       {'ENABLED' if settings.llm.enabled else 'DISABLED'}")
    if settings.llm.enabled:
        print(f"  Model:     {settings.llm.model}")
    print("="*60)
    print("\nConnecting to MCP server...")

    # Initialize MCP client
    try:
        client = await initialize_mcp_client()
        tools = await client.list_tools()
        print(f"Connected! Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.name}")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    print("\n" + "-"*60)
    print("Type your message to see:")
    print("  1. INPUT dostEvent (what we send)")
    print("  2. OUTPUT dostEvent (what we receive)")
    print("Type 'quit' to exit, 'json' for full JSON output")
    print("-"*60)

    import uuid
    session_id = str(uuid.uuid4())  # Proper UUID per spec
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
            input_event = {
                "version": "00.01.01",
                "sourceEntityId": "hum.playground.user",
                "sessionId": session_id,
                "destinationEntityId": settings.agent.entity_id,
                "isAiGenerated": False,
                "eventHint": "user_message",
                "message": {"text": {"data": user_input}}
            }

            # Show INPUT
            print_dost_event("INPUT dostEvent", input_event)

            if show_full_json:
                print_json("INPUT (full JSON)", input_event)

            print("\nProcessing...")

            # Call talk()
            output_event, metrics = await talk(input_event)

            # Show OUTPUT
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


def main():
    parser = argparse.ArgumentParser(description="MCP Bridge Playground")
    parser.add_argument(
        "--config", "-c",
        default="configs/test-server.yaml",
        help="Path to config file"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show verbose ReAct agent activity (tool calls, args, results)"
    )
    parser.add_argument(
        "--full", "-f",
        action="store_true",
        help="Show full JSON payloads (not truncated)"
    )
    args = parser.parse_args()

    # Configure logging based on verbose flag
    if args.verbose:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        # Enable INFO for our modules
        logging.getLogger('app.llm.agent').setLevel(logging.INFO)
        logging.getLogger('app.llm.response_formatter').setLevel(logging.INFO)
        logging.getLogger('app.client.mcp_client').setLevel(logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Resolve config path
    config_path = args.config
    if not Path(config_path).is_absolute():
        config_path = str(Path(__file__).parent / config_path)

    if not Path(config_path).exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)

    asyncio.run(playground(config_path, args.verbose, args.full))


if __name__ == "__main__":
    main()
