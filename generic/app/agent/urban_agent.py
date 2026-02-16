"""
UrbanBot AI Agent - A smart booking assistant for home services.

Uses LangGraph for AI workflow, ChromaDB for semantic search,
and MongoDB for session/booking persistence.
"""
import logging

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from app.models.agent_state import AgentState
from app.tools.service_tools import URBAN_BOT_TOOLS
from config import LLMConfig

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are UrbanBot, a smart booking assistant for home services.

RESPONSE FORMAT:
- Use PLAIN TEXT only. No markdown (no **, no ###, no -)
- NO bullet points or numbered lists in responses
- Write in flowing conversational sentences
- Keep responses short and friendly, like a WhatsApp message
- When asking for information, ask ONE question at a time

CRITICAL RULES:
1. NEVER generate fake booking confirmations - MUST call save_booking tool
2. NEVER say "booking confirmed" unless save_booking tool returned success
3. ALWAYS verify city availability BEFORE collecting user details
4. If service isn't in user's city: STOP and tell them immediately

DATE HANDLING:
- Today's date is provided in context. Use it for "tomorrow" calculations
- Date format must be DD-MM-YYYY

BOOKING WORKFLOW:
1. User requests service -> search_services or list_all_services
2. User selects -> get_service_details to show full info
3. User confirms -> Ask for details ONE BY ONE:
   a. City FIRST (must match service availability)
   b. If city unavailable: STOP, suggest alternatives
   c. If city OK: name, phone, address, date, time
4. Have all details -> MUST call save_booking tool
5. Tool returns success -> THEN say confirmed

TOOLS:
- search_services(query, city="", category=""): Find services by query, optionally filter by city and category
- list_all_services(city="", category=""): List all services, optionally filter by city and category
- get_service_details(service_id): Full service info
- save_booking(...): Confirm booking
- get_user_bookings(user_id): View booking history

REMEMBER:
- Always use user_id from state for save_booking/get_user_bookings
- Service availability is city-specific
"""


class UrbanBotAgent:
    """LangGraph-based AI agent for home services booking."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=LLMConfig.MODEL_NAME,
            temperature=LLMConfig.TEMPERATURE,
            max_tokens=LLMConfig.MAX_TOKENS,
            timeout=LLMConfig.TIMEOUT
        )
        self.llm_with_tools = self.llm.bind_tools(URBAN_BOT_TOOLS)
        self.graph = self._build_graph()
        self.conversation_history = {}
        logger.info("UrbanBot agent initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)
        
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode(URBAN_BOT_TOOLS))
        
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
        workflow.add_edge("tools", "agent")
        
        return workflow.compile()

    def _call_model(self, state: AgentState) -> dict:
        """Process state and call LLM."""
        from datetime import datetime, timedelta
        
        # Build context
        context_parts = [SYSTEM_PROMPT]
        
        # Add date info
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        context_parts.append(f"\nToday: {today.strftime('%d-%m-%Y')}")
        context_parts.append(f"Tomorrow: {tomorrow.strftime('%d-%m-%Y')}")
        
        # Add user_id
        if state.get("user_id"):
            context_parts.append(f"\nUSER_ID: {state['user_id']}")
        
        # Add selected service
        if state.get("selected_service_id"):
            context_parts.append(f"\nCURRENT SERVICE: {state['selected_service_id']}")
        
        # Add customer profile
        if state.get("customer_profile"):
            profile = state["customer_profile"]
            context_parts.append(f"\nCustomer: {profile.get('name')}, {profile.get('phone')}")
        
        # Add metadata for service filtering
        if state.get("metadata"):
            metadata = state["metadata"]
            logger.info(f"=== AGENT RECEIVED METADATA ===")
            logger.info(f"  Raw metadata: {metadata}")
            context_parts.append("\nSERVICE FILTERS:")
            if metadata.get("category"):
                logger.info(f"  Category filter: {metadata['category']}")
                context_parts.append(f"  - Category: {metadata['category']} (ONLY show services in this category)")
            if metadata.get("location"):
                location = metadata["location"]
                logger.info(f"  Location filter: city={location.get('city')}")
                context_parts.append(f"  - City: {location.get('city')} (ONLY show services available in this city)")
                if location.get("coordinates"):
                    context_parts.append(f"  - Coordinates: {location['coordinates']}")
            context_parts.append("IMPORTANT: When listing or searching services, ALWAYS pass the city parameter to filter results.")
        else:
            logger.info("=== AGENT: NO METADATA IN STATE ===")
        
        # Track booking progress
        if state.get("details_shown"):
            context_parts.append("\nService details shown. Ready for booking info.")
        
        system_message = SystemMessage(content="\n".join(context_parts))
        messages_to_send = [system_message] + list(state["messages"])
        
        response = self.llm_with_tools.invoke(messages_to_send)
        
        # Track state changes
        updated_service_id = state.get("selected_service_id")
        details_shown = state.get("details_shown", False)
        
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call["name"] == "get_service_details":
                    updated_service_id = tool_call["args"].get("service_id")
                    details_shown = True
                    logger.info(f"Selected service: {updated_service_id}")
        
        result = {"messages": [response]}
        if updated_service_id:
            result["selected_service_id"] = updated_service_id
        if details_shown:
            result["details_shown"] = details_shown
        
        return result

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        customer_profile: dict = None,
        previous_state: dict = None,
        metadata: dict = None
    ) -> dict:
        """Process a user message and return AI response."""
        try:
            # Manage conversation history
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            
            self.conversation_history[user_id].append(HumanMessage(content=user_message))
            messages = self.conversation_history[user_id][-10:]  # Keep last 10
            
            # Build initial state
            initial_state = {
                "messages": messages,
                "user_id": user_id,
                "customer_profile": customer_profile,
                "selected_service_id": previous_state.get("selected_service_id") if previous_state else None,
                "booking_details": previous_state.get("booking_details", {}) if previous_state else {},
                "details_shown": previous_state.get("details_shown", False) if previous_state else False,
                "metadata": metadata
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
            
            return {
                "response": final_response,
                "state": {
                    "selected_service_id": result.get("selected_service_id"),
                    "booking_details": result.get("booking_details", {}),
                    "details_shown": result.get("details_shown", False)
                }
            }
            
        except Exception as error:
            logger.error(f"Agent processing failed: {error}", exc_info=True)
            return {"response": "I encountered an error. Please try again.", "state": previous_state or {}}
