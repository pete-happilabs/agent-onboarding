"""Custom Agent API routes."""
import logging
from fastapi import APIRouter


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy", "agent": "custom"}

