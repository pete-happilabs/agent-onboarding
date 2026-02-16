"""
MongoDB document models for Urban Bot.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class SessionDocument(BaseModel):
    """Session document for conversation persistence."""
    session_id: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    selected_service_id: Optional[str] = None
    booking_details: Dict[str, Any] = Field(default_factory=dict)
    details_shown: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class BookingDocument(BaseModel):
    """Booking document for MongoDB storage."""
    booking_id: str
    session_id: str
    service_id: str
    service_name: str
    customer_name: str
    phone: str
    address: str
    city: str
    preferred_date: str
    preferred_time_slot: str
    status: str = "confirmed"
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class LocationMetadata(BaseModel):
    """Location metadata for service filtering."""
    city: str
    coordinates: Optional[List[float]] = None


class RequestMetadata(BaseModel):
    """Metadata for /talk request to filter services."""
    category: Optional[str] = None
    location: Optional[LocationMetadata] = None


class TalkRequest(BaseModel):
    """Request body for /talk endpoint."""
    message: str
    metadata: Optional[RequestMetadata] = None


class TalkResponse(BaseModel):
    """Response body for /talk endpoint."""
    session_id: str
    response: str
    timestamp: str


class HelpResponse(BaseModel):
    """Response body for /help endpoint."""
    session_id: str
    bookings: List[Dict[str, Any]]
    total: int
