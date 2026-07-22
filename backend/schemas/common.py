"""
Pydantic Schemas — Common.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


class ErrorResponse(BaseModel):
    """Generic error response."""
    detail: str
