"""
EyeconBumps Web App - Public API Router
Endpoints for public access (no authentication required)
"""
from fastapi import APIRouter, HTTPException
from database import db

router = APIRouter(tags=["Public"])

@router.get("/track/{order_id}")
async def track_order(order_id: str):
    """Public track order by ID."""
    order = db.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order": order}
