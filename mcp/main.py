#!/usr/bin/env python3
# ============================================================================
# MCP Bridge - Main Entry Point
# ============================================================================
"""
MCP-to-dostEvent Bridge

Run with:
    python main.py --config configs/zomato.yaml
    python main.py --config configs/test-server.yaml

Or for interactive testing:
    python main.py --config configs/zomato.yaml --interactive
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings, reset_settings
from app.engine.talk import talk
from app.client.mcp_client import initialize_mcp_client, reset_mcp_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def interactive_mode(config_path: str):
    """
    Interactive mode - chat with the MCP server via terminal.
    """
    reset_settings()
    reset_mcp_client()

    settings = get_settings(config_path)
    logger.info(f"Starting interactive mode with: {settings.agent.name}")
    logger.info(f"Transport: {settings.mcp.transport}")

    if settings.mcp.transport == "remote":
        logger.info(f"URL: {settings.mcp.url}")
        logger.info("NOTE: First run may open browser for OAuth login")
    elif settings.mcp.transport == "stdio":
        logger.info(f"Command: {settings.mcp.command}")

    print("\n" + "=" * 60)
    print(f"  MCP Bridge - {settings.agent.name}")
    print("=" * 60)
    print("Type your message and press Enter.")
    print("Type 'quit' or 'exit' to stop.")
    print("Type 'tools' to list available MCP tools.")
    print("=" * 60 + "\n")

    # Initialize the MCP client (will trigger OAuth if needed)
    try:
        client = await initialize_mcp_client()
        tools = await client.list_tools()
        print(f"Connected! Found {len(tools)} tools.\n")
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return

    session_id = "interactive-session"

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit"]:
                print("Goodbye!")
                break

            if user_input.lower() == "tools":
                print("\nAvailable tools:")
                for tool in tools:
                    print(f"  - {tool.name}: {tool.description}")
                print()
                continue

            # Build dostEvent
            event = {
                "version": "00.01.01",
                "sourceEntityId": "hum.interactive.user",
                "sessionId": session_id,
                "message": {"text": {"data": user_input}}
            }

            # Call talk()
            response_event, metrics = await talk(event)

            # Extract response text
            response_text = response_event.get("message", {}).get("text", {}).get("data", "")
            print(f"\n{settings.agent.name}: {response_text}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"Error: {e}")


async def test_talk(config_path: str, message: str):
    """
    Single test - send one message and print response.
    """
    reset_settings()
    reset_mcp_client()

    settings = get_settings(config_path)
    logger.info(f"Testing with: {settings.agent.name}")

    # Build dostEvent
    event = {
        "version": "00.01.01",
        "sourceEntityId": "hum.test.user",
        "sessionId": "test-session",
        "message": {"text": {"data": message}}
    }

    print(f"\nSending: {message}")
    print("-" * 40)

    # Call talk()
    response_event, metrics = await talk(event)

    # Print response
    print("\nResponse Event:")
    print(json.dumps(response_event, indent=2))
    print("\nMetrics:")
    print(json.dumps(metrics, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="MCP-to-dostEvent Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive chat with Zomato
  python main.py --config configs/zomato.yaml --interactive

  # Test with a single message
  python main.py --config configs/zomato.yaml --message "Find restaurants near Koramangala"

  # Use test server
  python main.py --config configs/test-server.yaml --interactive
        """
    )
    parser.add_argument(
        "--config", "-c",
        default="mcp.yaml",
        help="Path to config file (default: mcp.yaml)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--message", "-m",
        help="Send a single message and exit"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Resolve config path relative to this file
    config_path = args.config
    if not Path(config_path).is_absolute():
        config_path = str(Path(__file__).parent / config_path)

    if not Path(config_path).exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    if args.interactive:
        asyncio.run(interactive_mode(config_path))
    elif args.message:
        asyncio.run(test_talk(config_path, args.message))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
