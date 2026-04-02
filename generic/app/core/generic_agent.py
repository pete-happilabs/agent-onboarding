"""
Generic LangGraph-based ReAct agent.

This agent is configured via a domain-specific BaseDomainConfig instance
so it can be reused across multiple domains (Urban Company, Uber, etc.).
"""
import importlib
import logging
from typing import Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from app.config.domain_config import BaseDomainConfig
from app.models.agent_state import AgentState
from config import get_settings

logger = logging.getLogger(__name__)


class GenericReActAgent:
    """
    Generic LangGraph-based ReAct agent.

    The agent's behavior is driven entirely by the provided
    BaseDomainConfig (system prompt, tools module, persistence
    collection, etc.), while the LangGraph topology remains
    identical to the original UrbanBot implementation.
    """

    def __init__(self, config: BaseDomainConfig):
        """
        Initialize the generic agent with a domain configuration.

        Args:
            config: Domain configuration describing prompt, tools module,
                    and other domain-level settings.
        """
        self.config = config
        self.system_prompt: str = config.system_prompt

        # Token tracking for metrics
        self._current_input_tokens = 0
        self._current_output_tokens = 0
        self._current_model = ""

        # LLM configuration from Settings
        settings = get_settings()
        self.llm = ChatOpenAI(
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            timeout=settings.llm.timeout,
        )

        # Dynamic tool loading: each domain exposes a TOOLS list
        ALLOWED_TOOLS_MODULES = {
            "app.domains.urban_company.tools",
            "app.domains.swiggy.tools",
            "app.domains.myntra.tools",
            "app.domains.uber.tools",
        }
        if config.tools_module not in ALLOWED_TOOLS_MODULES:
            raise ValueError(f"Unauthorized tools module: {config.tools_module}")
        tools_module = importlib.import_module(config.tools_module)
        self.tools = getattr(tools_module, "TOOLS")

        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.graph = self._build_graph()
        self.conversation_history: Dict[str, list] = {}

        logger.info("GenericReActAgent initialized for domain=%s", self.config.domain_name)

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow (unchanged topology)."""
        workflow = StateGraph(AgentState)

        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode(self.tools))

        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    def _call_model(self, state: AgentState) -> Dict[str, Any]:
        """Process state and call the configured LLM."""
        from datetime import datetime, timedelta

        # Build context
        context_parts = [self.system_prompt]

        # Add date info
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        context_parts.append(f"\nToday: {today.strftime('%d-%m-%Y')}")
        context_parts.append(f"Tomorrow: {tomorrow.strftime('%d-%m-%Y')}")

        # Add domain + user identifiers
        if state.get("user_id"):
            # Expose both domain entity_id and user_id to the prompt
            context_parts.append(f"\nENTITY_ID: {self.config.entity_id}")
            context_parts.append(f"USER_ID: {state['user_id']}")

        # Add selected service (domain-specific but still useful metadata)
        if state.get("selected_service_id"):
            context_parts.append(f"\nCURRENT SERVICE: {state['selected_service_id']}")

        # Add customer profile
        if state.get("customer_profile"):
            profile = state["customer_profile"]
            context_parts.append(f"\nCustomer: {profile.get('name')}, {profile.get('phone')}")

        # Add metadata for service filtering
        if state.get("metadata"):
            metadata = state["metadata"]
            logger.info("=== AGENT RECEIVED METADATA ===")
            logger.info("  Raw metadata: %s", metadata)
            context_parts.append("\nSERVICE FILTERS:")
            if metadata.get("category"):
                logger.info("  Category filter: %s", metadata["category"])
                context_parts.append(
                    f"  - Category: {metadata['category']} (ONLY show services in this category)"
                )
            if metadata.get("location"):
                location = metadata["location"]
                logger.info("  Location filter: city=%s", location.get("city"))
                context_parts.append(
                    f"  - City: {location.get('city')} "
                    "(ONLY show services available in this city)"
                )
                if location.get("coordinates"):
                    context_parts.append(f"  - Coordinates: {location['coordinates']}")
            context_parts.append(
                "IMPORTANT: When listing or searching services, "
                "ALWAYS pass the city parameter to filter results."
            )
        else:
            logger.info("=== AGENT: NO METADATA IN STATE ===")

        # Track booking progress
        if state.get("details_shown"):
            context_parts.append("\nService details shown. Ready for booking info.")

        system_message = SystemMessage(content="\n".join(context_parts))
        messages_to_send = [system_message] + list(state["messages"])

        response = self.llm_with_tools.invoke(messages_to_send)

        # Extract token usage from response metadata
        token_usage = response.response_metadata.get("token_usage", {})
        self._current_input_tokens += token_usage.get("prompt_tokens", 0)
        self._current_output_tokens += token_usage.get("completion_tokens", 0)
        self._current_model = response.response_metadata.get("model_name", "")

        # Track state changes
        updated_service_id = state.get("selected_service_id")
        details_shown = state.get("details_shown", False)

        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call["name"] == "get_service_details":
                    updated_service_id = tool_call["args"].get("service_id")
                    details_shown = True
                    logger.info("Selected service: %s", updated_service_id)

        result: Dict[str, Any] = {"messages": [response]}
        if updated_service_id:
            result["selected_service_id"] = updated_service_id
        if details_shown:
            result["details_shown"] = details_shown

        return result

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        customer_profile: Dict[str, Any] | None = None,
        previous_state: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Process a user message and return the AI response.

        This mirrors the original UrbanBotAgent.process_message behavior,
        but uses the injected domain configuration and dynamically loaded tools.
        """
        try:
            # Reset token counters for this request
            self._current_input_tokens = 0
            self._current_output_tokens = 0
            self._current_model = ""

            # Manage conversation history
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []

            self.conversation_history[user_id].append(HumanMessage(content=user_message))
            messages = self.conversation_history[user_id][-10:]  # Keep last 10

            # Build initial state
            initial_state: Dict[str, Any] = {
                "messages": messages,
                "user_id": user_id,
                "customer_profile": customer_profile,
                "selected_service_id": previous_state.get("selected_service_id")
                if previous_state
                else None,
                "booking_details": previous_state.get("booking_details", {})
                if previous_state
                else {},
                "details_shown": previous_state.get("details_shown", False)
                if previous_state
                else False,
                "metadata": metadata,
            }

            # Run graph
            result = self.graph.invoke(initial_state)

            # Extract response
            ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
            if ai_messages:
                final_message = ai_messages[-1]
                self.conversation_history[user_id].append(final_message)
                final_response = final_message.content
            else:
                final_response = "I couldn't process that request."

            # Extract tool results from ToolMessage objects
            tool_results = []
            for msg in result["messages"]:
                if isinstance(msg, ToolMessage):
                    tool_results.append({
                        "name": msg.name or "unknown",
                        "content": msg.content,
                        "is_error": getattr(msg, "status", None) == "error",
                    })

            return {
                "response": final_response,
                "state": {
                    "selected_service_id": result.get("selected_service_id"),
                    "booking_details": result.get("booking_details", {}),
                    "details_shown": result.get("details_shown", False),
                },
                "tool_results": tool_results,
                "input_tokens": self._current_input_tokens,
                "output_tokens": self._current_output_tokens,
                "model": self._current_model,
            }

        except Exception as error:
            logger.error("Agent processing failed: %s", error, exc_info=True)
            return {
                "response": "I encountered an error. Please try again.",
                "state": previous_state or {},
            }

