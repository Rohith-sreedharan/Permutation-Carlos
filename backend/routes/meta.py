"""
Meta Endpoint - Build/Version Information
==========================================
Acceptance Gate #1: Build/version stamp for validation
"""

from fastapi import APIRouter
from datetime import datetime, timezone
from core.sim_integrity import CURRENT_SIM_VERSION, ENGINE_BUILD_ID
import os

router = APIRouter()


@router.get("/meta")
async def get_meta():
    """
    Build and version metadata endpoint.
    Used for validation and debugging.
    
    Returns:
        {
            "engine_build_id": "v2.0.0-integrity-layer",
            "sim_version": 2,
            "deployed_at": "2026-01-24T12:34:56.789Z",
            "environment": "production",
            "python_version": "3.12",
            "status": "operational"
        }
    """
    import sys
    
    # Get deployment timestamp from environment or use current time
    deployed_at = os.getenv("DEPLOYED_AT", datetime.now(timezone.utc).isoformat())
    environment = os.getenv("ENVIRONMENT", "development")
    
    return {
        "engine_build_id": ENGINE_BUILD_ID,
        "sim_version": CURRENT_SIM_VERSION,
        "deployed_at": deployed_at,
        "environment": environment,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "status": "operational"
    }
