"""
Generic LangGraph-based ReAct agent.

Production additions over original:
- _invoke_llm()     → sync retry x3 on LangChain LLM calls (tenacity)
- collect_metrics() → DPA-format token usage from LangChain usage_metadata
- Token tracking    → accumulated in _call_model across all ReAct iterations
- % logging         → replaced f-strings for production log safety
"""
import importlib
import logging
from typing import Any, Dict

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.config.domain_config import BaseDomainConfig
from app.models.agent_state import AgentState
from config import LLMConfig

logger = logging.getLogger(__name__)


class GenericReActAgent:
    """
    Generic LangGraph-based ReAct agent.

    Behavior is driven entirely by the provided BaseDomainConfig.
    LangGraph topology is identical across all domains.
    """

    def __init__(self, config: BaseDomainConfig):
        self.config = config
        self.system_prompt: str = config.system_prompt

        self.llm = ChatOpenAI(
            model=LLMConfig.MODEL_NAME,
            temperature=LLMConfig.TEMPERATURE,
            max_tokens=LLMConfig.MAX_TOKENS,
            timeout=LLMConfig.TIMEOUT,
        )

        tools_module = importlib.import_module(config.tools_module)
        self.tools = getattr(tools_module, "TOOLS")

        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.graph = self._build_graph()
        self.conversation_history: Dict[str, list] = {}

        # Token tracking — reset per process_message() call
        self._input_tokens: int = 0
        self._output_tokens: int = 0

        logger.info("GenericReActAgent initialized for domain=%s", self.config.domain_name)

    # -------------------------------------------------------------------------
    # Graph
    # -------------------------------------------------------------------------

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode(self.tools))

        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent", tools_condition, {"tools": "tools", END: END}
        )
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    # -------------------------------------------------------------------------
    # LLM invocation — retry wraps this sync call
    # -------------------------------------------------------------------------

    def _invoke_llm(self, messages_to_send: list) -> Any:
        """
        Invoke the LLM with sync retry on transient failures.

        LangGraph calls _call_model synchronously, so we use tenacity's
        sync retry here (not async). Retries up to 3 times: 1s→2s→4s backoff.
        """
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def _inner():
            return self.llm_with_tools.invoke(messages_to_send)

        return _inner()

    # -------------------------------------------------------------------------
    # Graph node
    # -------------------------------------------------------------------------

    def _call_model(self, state: AgentState) -> Dict[str, Any]:
        """Process state and call the LLM — called synchronously by LangGraph."""
        from datetime import datetime, timedelta

        context_parts = [self.system_prompt]

        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        context_parts.append(f"\nToday: {today.strftime('%d-%m-%Y')}")
        context_parts.append(f"Tomorrow: {tomorrow.strftime('%d-%m-%Y')}")

        if state.get("user_id"):
            context_parts.append(f"\nENTITY_ID: {self.config.entity_id}")
            context_parts.append(f"USER_ID: {state['user_id']}")

        if state.get("selected_service_id"):
            context_parts.append(f"\nCURRENT SERVICE: {state['selected_service_id']}")

        if state.get("customer_profile"):
            profile = state["customer_profile"]
            context_parts.append(
                f"\nCustomer: {profile.get('name')}, {profile.get('phone')}"
            )

        if state.get("metadata"):
            metadata = state["metadata"]
            logger.info("=== AGENT RECEIVED METADATA ===")
            logger.info("  Raw metadata: %s", metadata)
            context_parts.append("\nSERVICE FILTERS:")
            if metadata.get("category"):
                logger.info("  Category filter: %s", metadata["category"])
                context_parts.append(
                    f"  - Category: {metadata['category']} "
                    "(ONLY show services in this category)"
                )
            if metadata.get("location"):
                location = metadata["location"]
                logger.info("  Location filter: city=%s", location.get("city"))
                context_parts.append(
                    f"  - City: {location.get('city')} "
                    "(ONLY show services available in this city)"
                )
                if location.get("coordinates"):
                    context_parts.append(
                        f"  - Coordinates: {location['coordinates']}"
                    )
            context_parts.append(
                "IMPORTANT: When listing or searching services, "
                "ALWAYS pass the city parameter to filter results."
            )
        else:
            logger.info("=== AGENT: NO METADATA IN STATE ===")

        if state.get("details_shown"):
            context_parts.append("\nService details shown. Ready for booking info.")

        system_message = SystemMessage(content="\n".join(context_parts))
        messages_to_send = [system_message] + list(state["messages"])

        # --- LLM call with retry ---
        response = self._invoke_llm(messages_to_send)

        # --- Token tracking ---
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            self._input_tokens += um.get("input_tokens", 0)
            self._output_tokens += um.get("output_tokens", 0)

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

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    def collect_metrics(self) -> Dict[str, Any]:
        """
        Return accumulated LLM token usage in DPA format, then reset.

        Call this once after process_message() returns.
        Returns {"models": {}} if no tokens were tracked (e.g. mock LLM).
        """
        if not (self._input_tokens or self._output_tokens):
            return {"models": {}}

        metrics = {
            "models": {
                LLMConfig.MODEL_NAME: {
                    "input_tokens": self._input_tokens,
                    "output_tokens": self._output_tokens,
                }
            }
        }
        # Reset for next call
        self._input_tokens = 0
        self._output_tokens = 0
        return metrics

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        customer_profile: Dict[str, Any] | None = None,
        previous_state: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Process a user message and return the AI response."""
        try:
            # Reset token counters for this request
            self._input_tokens = 0
            self._output_tokens = 0

            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []

            self.conversation_history[user_id].append(
                HumanMessage(content=user_message)
            )
            messages = self.conversation_history[user_id][-10:]

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

            result = self.graph.invoke(initial_state)

            ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
            if ai_messages:
                final_message = ai_messages[-1]
                self.conversation_history[user_id].append(final_message)
                final_response = final_message.content
            else:
                final_response = "I couldn't process that request."

            return {
                "response": final_response,
                "state": {
                    "selected_service_id": result.get("selected_service_id"),
                    "booking_details": result.get("booking_details", {}),
                    "details_shown": result.get("details_shown", False),
                },
            }

        except Exception as error:
            logger.error("Agent processing failed: %s", error, exc_info=True)
            return {
                "response": "I encountered an error. Please try again.",
                "state": previous_state or {},
            }
