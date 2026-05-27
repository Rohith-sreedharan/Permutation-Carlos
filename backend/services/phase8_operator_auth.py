"""
Phase 8 — Operator JWT auth (separate from user JWT)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Dict

import jwt as pyjwt
from fastapi import Header, HTTPException, status

from config.agent_config import AGENT_CONFIG


def _secret() -> str:
    secret = os.getenv("OPERATOR_JWT_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPERATOR_JWT_SECRET is not configured",
        )
    return secret


def create_operator_token(operator_id: str, role: str = "operator") -> str:
    cfg = AGENT_CONFIG["phase8"]
    now = datetime.now(timezone.utc)
    payload = {
        "operator_id": operator_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=cfg["operator_jwt_expire_minutes"])).timestamp()),
    }
    return pyjwt.encode(payload, _secret(), algorithm=cfg["operator_jwt_algorithm"])


def require_operator(authorization: str = Header(default="")) -> Dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Operator Authorization header required")

    token = authorization.replace("Bearer ", "").strip()
    cfg = AGENT_CONFIG["phase8"]

    try:
        payload = pyjwt.decode(token, _secret(), algorithms=[cfg["operator_jwt_algorithm"]])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid operator token")

    operator_id = payload.get("operator_id")
    role = payload.get("role")
    if role != "operator" or not operator_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator token missing required claims")

    if operator_id not in cfg["operator_team"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator is not authorized")

    return payload
