"""
LangGraph agent state definition.
"""
import operator
from typing import TypedDict, Annotated, List, Dict, Optional

from langchain_core.messages import AnyMessage


class AgentState(TypedDict):
    """State passed through LangGraph workflow."""
    messages: Annotated[List[AnyMessage], operator.add]
    user_id: str
    customer_profile: Optional[Dict]
    selected_service_id: Optional[str]
    booking_details: Dict
    details_shown: bool
    metadata: Optional[Dict]

