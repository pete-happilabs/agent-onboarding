"""
OmniAgent Playground - Interactive Multi-Domain Agent CLI

Universal Conversational AI for Every Domain

Usage:
    python playground.py --config configs/swiggy.yaml -v
    python playground.py --config configs/myntra.yaml
    python playground.py --config configs/urban_company.yaml
"""
import asyncio
import argparse
import uuid
import sys
from datetime import datetime
from typing import Dict, Any
import yaml
import json

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    # Fallback if colorama not installed
    class Fore:
        GREEN = YELLOW = RED = CYAN = BLUE = MAGENTA = WHITE = ""
    class Style:
        BRIGHT = RESET_ALL = ""

from app.core.generic_agent import GenericReActAgent
from app.domains import get_domain_config
from dost.protocol import create_dost_event, create_dost_message


class OmniAgentPlayground:
    """Interactive playground for testing OmniAgent domains."""
    
    def __init__(self, domain_name: str, verbose: bool = False):
        self.domain_name = domain_name
        self.verbose = verbose
        self.session_id = str(uuid.uuid4())
        self.json_mode = False
        
        # Load domain config
        try:
            self.config = get_domain_config(domain_name)
            self.agent = GenericReActAgent(self.config)
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to load domain '{domain_name}': {e}")
            sys.exit(1)
    
    def print_banner(self):
        """Print startup banner."""
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}  {Style.BRIGHT}OmniAgent Playground")
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.WHITE}  Agent:     {Fore.GREEN}{self.config.domain_name.replace('_', ' ').title()}")
        print(f"{Fore.WHITE}  Entity ID: {Fore.YELLOW}{self.config.entity_id}")
        print(f"{Fore.WHITE}  Currency:  {Fore.GREEN}{self.config.currency}")
        print(f"{Fore.WHITE}  LLM:       {Fore.GREEN}ENABLED")
        print(f"{Fore.WHITE}  Model:     {Fore.CYAN}gpt-4o-mini")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print()
    
    def print_instructions(self):
        """Print usage instructions."""
        print(f"{Fore.YELLOW}{'-'*60}")
        print(f"{Fore.WHITE}Type your message to see:")
        print(f"{Fore.WHITE}  1. INPUT dostEvent (what we send)")
        print(f"{Fore.WHITE}  2. OUTPUT dostEvent (what we receive)")
        print(f"{Fore.YELLOW}Type 'quit' or 'exit' to leave, 'json' for full JSON output")
        print(f"{Fore.YELLOW}{'-'*60}{Style.RESET_ALL}")
        print()
    
    def create_input_event(self, user_message: str) -> Dict[str, Any]:
        """Create input dostEvent."""
        return create_dost_event(
            source_entity_id="hum.playground.user",
            destination_entity_id=self.config.entity_id,
            session_id=self.session_id,
            event_hint="user_message",
            is_ai_generated=False,
            message=create_dost_message(text=user_message)
        )
    
    def display_input_event(self, event: Dict[str, Any]):
        """Display formatted input dostEvent."""
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}  INPUT dostEvent")
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.WHITE}  version:       {Fore.GREEN}{event['version']}")
        print(f"{Fore.WHITE}  eventId:       {Fore.YELLOW}{event['eventId'][:8]}...")
        print(f"{Fore.WHITE}  sessionId:     {Fore.YELLOW}{event['sessionId'][:8]}...")
        print(f"{Fore.WHITE}  sourceEntityId:      {Fore.CYAN}{event['sourceEntityId']}")
        print(f"{Fore.WHITE}  destinationEntityId: {Fore.CYAN}{event['destinationEntityId']}")
        print(f"{Fore.WHITE}  isAiGenerated: {Fore.RED}{event['isAiGenerated']}")
        print(f"{Fore.WHITE}  eventHint:     {Fore.MAGENTA}{event.get('eventHint', 'N/A')}")
        
        if event.get('message', {}).get('text'):
            text = event['message']['text']['data']
            print(f"{Fore.WHITE}  message.text:  {Fore.WHITE}{text}")
        
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print()
        
        if self.json_mode:
            print(f"{Fore.BLUE}--- INPUT (full JSON) ---")
            print(json.dumps(event, indent=2))
            print()
    
    def display_output_event(self, event: Dict[str, Any], response_text: str):
        """Display formatted output dostEvent."""
        print(f"{Fore.GREEN}{'='*60}")
        print(f"{Fore.GREEN}  OUTPUT dostEvent")
        print(f"{Fore.GREEN}{'='*60}")
        print(f"{Fore.WHITE}  version:       {Fore.GREEN}{event['version']}")
        print(f"{Fore.WHITE}  eventId:       {Fore.YELLOW}{event['eventId'][:8]}...")
        print(f"{Fore.WHITE}  sessionId:     {Fore.YELLOW}{event['sessionId'][:8]}...")
        print(f"{Fore.WHITE}  sourceEntityId:      {Fore.CYAN}{event['sourceEntityId']}")
        print(f"{Fore.WHITE}  destinationEntityId: {Fore.CYAN}{event['destinationEntityId']}")
        print(f"{Fore.WHITE}  isAiGenerated: {Fore.GREEN}{event['isAiGenerated']}")
        print(f"{Fore.WHITE}  eventHint:     {Fore.MAGENTA}{event.get('eventHint', 'response')}")
        
        # Truncate message if too long for header
        display_text = response_text[:80] + "..." if len(response_text) > 80 else response_text
        print(f"{Fore.WHITE}  message.text:  {Fore.WHITE}{display_text}")
        
        print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
        print()
        
        if self.json_mode:
            print(f"{Fore.BLUE}--- OUTPUT (full JSON) ---")
            print(json.dumps(event, indent=2))
            print()
    
    async def process_message(self, user_message: str):
        """Process user message and return dostEvents."""
        # Create input dostEvent
        input_event = self.create_input_event(user_message)
        self.display_input_event(input_event)
        
        print(f"{Fore.YELLOW}Processing...{Style.RESET_ALL}")
        
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"{Fore.BLUE}{timestamp} | omniagent.playground | Processing: '{user_message[:50]}...'{Style.RESET_ALL}")
        
        try:
            # Call agent
            result = await self.agent.process_message(
                user_message=user_message,
                user_id="playground_user"
            )
            
            # Create output dostEvent
            output_event = create_dost_event(
                source_entity_id=self.config.entity_id,
                destination_entity_id="hum.playground.user",
                session_id=self.session_id,
                event_hint="response",
                is_ai_generated=True,
                message=create_dost_message(text=result['response'])
            )
            
            self.display_output_event(output_event, result['response'])
            
            if self.verbose:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"{Fore.BLUE}{timestamp} | omniagent.playground | Response delivered{Style.RESET_ALL}\n")
        
        except Exception as e:
            print(f"{Fore.RED}❌ Error processing message: {e}{Style.RESET_ALL}")
            if self.verbose:
                import traceback
                traceback.print_exc()
    
    async def run(self):
        """Run interactive playground loop."""
        self.print_banner()
        self.print_instructions()
        
        try:
            while True:
                try:
                    user_input = input(f"{Fore.CYAN}You: {Style.RESET_ALL}").strip()
                    
                    if not user_input:
                        continue
                    
                    if user_input.lower() in ['quit', 'exit']:
                        print(f"\n{Fore.GREEN}👋 Goodbye!{Style.RESET_ALL}")
                        return  # Clean exit
                    
                    if user_input.lower() == 'json':
                        self.json_mode = not self.json_mode
                        status = "ON" if self.json_mode else "OFF"
                        print(f"{Fore.YELLOW}Full JSON output: {status}{Style.RESET_ALL}\n")
                        continue
                    
                    await self.process_message(user_input)
                    
                except EOFError:
                    # Handle Ctrl+D
                    print(f"\n\n{Fore.GREEN}👋 Goodbye!{Style.RESET_ALL}")
                    return
                except Exception as e:
                    print(f"{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
                    if self.verbose:
                        import traceback
                        traceback.print_exc()
        except KeyboardInterrupt:
            # Handle Ctrl+C
            print(f"\n\n{Fore.GREEN}👋 Goodbye!{Style.RESET_ALL}")
            return


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OmniAgent Playground - Universal Conversational AI for Every Domain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python playground.py --config configs/swiggy.yaml -v
  python playground.py --config configs/myntra.yaml
  python playground.py --config configs/urban_company.yaml
        """
    )
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to domain config YAML file'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Load config to get domain name
    try:
        with open(args.config, 'r') as f:
            config_data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"{Fore.RED}❌ Config file not found: {args.config}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Available configs:{Style.RESET_ALL}")
        print("  - configs/swiggy.yaml")
        print("  - configs/myntra.yaml")
        print("  - configs/urban_company.yaml")
        sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}❌ Failed to load config: {e}{Style.RESET_ALL}")
        sys.exit(1)
    
    domain_name = config_data.get('domain_name')
    if not domain_name:
        print(f"{Fore.RED}❌ Config missing 'domain_name' field{Style.RESET_ALL}")
        sys.exit(1)
    
    # Run playground
    playground = OmniAgentPlayground(domain_name, args.verbose)
    asyncio.run(playground.run())


if __name__ == "__main__":
    main()
