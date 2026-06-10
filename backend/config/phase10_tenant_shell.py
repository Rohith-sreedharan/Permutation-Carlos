"""
Phase 10 tenant shell constants.

Defines enum values required for beta shell confirmation.
"""

TENANT_TYPE_ENUM = ["CONSUMER", "B2B_API", "WHITE_LABEL"]
ENTITLEMENT_TYPE_ENUM = ["B2C_PLATFORM", "B2C_SYNDICATE", "B2B_CONTRACT", "WHITE_LABEL"]
TENANT_STATUS_ENUM = ["ACTIVE", "SUSPENDED", "PENDING"]

REQUIRED_TENANT_FIELDS = [
    "tenant_id",
    "tenant_type",
    "entitlement_type",
    "status",
    "rate_limit_tier",
    "api_key_hash",
    "created_at_utc",
    "updated_at_utc",
    "custom_thresholds",
    "trace_id",
]

PHASE10_AUDIT_COLLECTIONS = [
    "decision_records",
    "decision_settlement_metrics",
    "parlay_execution_log",
    "sentinel_event_log",
    "response_action_log",
    "outbound_communication_log",
    "billing_state_change_log",
    "phase4_scheduler_log",
    "calibration_records",
    "clv_records",
]
