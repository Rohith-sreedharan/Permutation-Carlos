"""
Allowed Writers Matrix Enforcement
===================================

Runtime guards + repo-wide tests that block unauthorized database writes.

This is the SINGLE enforcement contract that prevents "helpful shortcuts"
from reintroducing split truth and drift.

Author: System
Date: 2026-02-02
Version: v1.0.0 (Hard-Lock Patch)
"""

import inspect
from typing import List, Dict, Any, Optional
from functools import wraps
from datetime import datetime


# ============================================================================
# ALLOWED WRITERS MATRIX (HARD-LOCKED)
# ============================================================================

ALLOWED_WRITERS_MATRIX = {
    # Collection: grading (canonical outcomes)
    "grading": {
        "allowed_modules": [
            "backend.services.unified_grading_service_v2.UnifiedGradingService"
        ],
        "allowed_operations": ["insert", "update", "upsert"],
        "enforcement": "runtime_guard + repo_grep",
        "exception": "ADMIN_OVERRIDE_WITH_AUDIT",
        "write_type": "canonical grading rows"
    },
    
    # Collection: picks (proposed/published picks)
    "picks": {
        "allowed_modules": [
            "backend.services.pick_creation_service.PickCreationService",
            "backend.core.pick_engine.PickEngine"
        ],
        "allowed_operations": ["insert", "update"],
        "enforcement": "service_layer_allowlist",
        "exception": None,
        "write_type": "proposed/published picks"
    },
    
    # Collection: market_snapshots (immutable)
    "market_snapshots": {
        "allowed_modules": [
            "backend.services.market_ingest_service.MarketIngestService"
        ],
        "allowed_operations": ["insert"],  # INSERT ONLY
        "enforcement": "db_immutability + runtime_guard",
        "exception": None,
        "write_type": "immutable market snapshots"
    },
    
    # Collection: pick_line_tracking
    "pick_line_tracking": {
        "allowed_modules": [
            "backend.services.validity_engine.ValidityEngine",
            "backend.services.line_tracker.LineTracker"
        ],
        "allowed_operations": ["update"],
        "enforcement": "service_layer_allowlist",
        "exception": None,
        "write_type": "line tracking pointers"
    },
    
    # Collection: ops_alerts
    "ops_alerts": {
        "allowed_modules": [
            "backend.services.ops_alert_service.OpsAlertService"
        ],
        "allowed_operations": ["insert"],
        "enforcement": "runtime_guard + repo_grep",
        "exception": None,
        "write_type": "operational alerts"
    },
    
    # Collection: audit_log
    "audit_log": {
        "allowed_modules": [
            "backend.services.audit_log_service.AuditLogService"
        ],
        "allowed_operations": ["insert"],  # APPEND ONLY
        "enforcement": "db_append_only + runtime_guard + repo_grep",
        "exception": None,
        "write_type": "append-only audit trail"
    },
    
    # Collection: feature_flags (admin only)
    "feature_flags": {
        "allowed_modules": [
            "backend.services.admin_config_service.AdminConfigService"
        ],
        "allowed_operations": ["update"],
        "enforcement": "role_gate(ADMIN) + audit_log_required",
        "exception": None,
        "write_type": "feature flag toggles"
    },
    
    # Collection: league_config (admin only)
    "league_config": {
        "allowed_modules": [
            "backend.services.admin_config_service.AdminConfigService"
        ],
        "allowed_operations": ["update"],
        "enforcement": "role_gate(ADMIN) + audit_log + config_versioning",
        "exception": None,
        "write_type": "league configuration"
    }
}


# ============================================================================
# RUNTIME ENFORCEMENT
# ============================================================================

class UnauthorizedWriteError(Exception):
    """Raised when unauthorized module attempts database write"""
    pass


class WriterMatrixGuard:
    """
    Runtime guard that enforces allowed writers matrix.
    
    Usage:
        guard = WriterMatrixGuard()
        guard.validate_write_permission(
            collection="grading",
            operation="update",
            caller_module="backend.services.unified_grading_service_v2"
        )
    """
    
    def __init__(self, audit_db=None):
        self.audit_db = audit_db
        self.matrix = ALLOWED_WRITERS_MATRIX
    
    def validate_write_permission(
        self,
        collection: str,
        operation: str,
        caller_module: Optional[str] = None,
        admin_override: bool = False,
        audit_note: Optional[str] = None
    ):
        """
        Validate write permission against allowed writers matrix.
        
        Raises:
            UnauthorizedWriteError if write not allowed
        """
        # Determine caller if not provided
        if not caller_module:
            caller_module = self._get_caller_module()
        
        # Check if collection has write restrictions
        if collection not in self.matrix:
            # No restrictions defined - allow (but log)
            self._log_untracked_write(collection, operation, caller_module)
            return
        
        rules = self.matrix[collection]
        
        # Check admin override exception
        if admin_override and rules.get("exception") == "ADMIN_OVERRIDE_WITH_AUDIT":
            if not audit_note:
                raise UnauthorizedWriteError(
                    f"Admin override for {collection} requires audit_note"
                )
            self._log_admin_override(collection, operation, caller_module, audit_note)
            return
        
        # Check allowed operations
        if operation not in rules["allowed_operations"]:
            raise UnauthorizedWriteError(
                f"Operation '{operation}' not allowed on collection '{collection}'. "
                f"Allowed: {rules['allowed_operations']}"
            )
        
        # Check allowed modules
        allowed = rules["allowed_modules"]
        
        # Match caller against allowed list
        is_allowed = any(
            caller_module.startswith(allowed_module.rsplit(".", 1)[0])
            for allowed_module in allowed
        )
        
        if not is_allowed:
            raise UnauthorizedWriteError(
                f"Module '{caller_module}' not allowed to write to '{collection}'. "
                f"Allowed modules: {allowed}"
            )
        
        # Write permission granted
        self._log_authorized_write(collection, operation, caller_module)
    
    def _get_caller_module(self) -> str:
        """Inspect call stack to determine caller module"""
        frame = inspect.currentframe()
        
        try:
            # Walk up stack to find first non-guard frame
            for _ in range(10):  # Max 10 frames
                if frame is None:
                    break
                frame = frame.f_back
                if not frame:
                    break
                
                module = inspect.getmodule(frame)
                if module and not module.__name__.startswith(__name__):
                    return module.__name__
        finally:
            del frame  # Avoid reference cycles
        
        return "UNKNOWN_CALLER"
    
    def _log_authorized_write(self, collection: str, operation: str, caller: str):
        """Log successful write authorization"""
        if not self.audit_db:
            return
        
        try:
            self.audit_db["write_authorization_log"].insert_one({
                "collection": collection,
                "operation": operation,
                "caller_module": caller,
                "authorized": True,
                "timestamp": datetime.utcnow()
            })
        except Exception:
            pass  # Don't fail writes due to logging errors
    
    def _log_admin_override(
        self,
        collection: str,
        operation: str,
        caller: str,
        audit_note: str
    ):
        """Log admin override write"""
        if not self.audit_db:
            return
        
        try:
            self.audit_db["audit_log"].insert_one({
                "event_type": "ADMIN_OVERRIDE_WRITE",
                "collection": collection,
                "operation": operation,
                "caller_module": caller,
                "audit_note": audit_note,
                "timestamp": datetime.utcnow(),
                "severity": "WARNING"
            })
        except Exception:
            pass
    
    def _log_untracked_write(self, collection: str, operation: str, caller: str):
        """Log write to untracked collection"""
        if not self.audit_db:
            return
        
        try:
            self.audit_db["ops_alerts"].insert_one({
                "alert_type": "UNTRACKED_COLLECTION_WRITE",
                "collection": collection,
                "operation": operation,
                "caller_module": caller,
                "severity": "INFO",
                "message": f"Write to untracked collection '{collection}' - consider adding to matrix",
                "created_at": datetime.utcnow(),
                "resolved": False
            })
        except Exception:
            pass


# ============================================================================
# DECORATOR FOR PROTECTED WRITES
# ============================================================================

def enforce_writer_matrix(collection: str, operation: str):
    """
    Decorator that enforces writer matrix on database write methods.
    
    Usage:
        @enforce_writer_matrix(collection="grading", operation="update")
        def grade_pick(self, pick_id: str):
            self.db["grading"].update_one(...)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract db from args (assumes self.db or db parameter)
            audit_db = None
            if args and hasattr(args[0], 'db'):
                audit_db = args[0].db
            elif 'db' in kwargs:
                audit_db = kwargs['db']
            
            # Validate permission
            guard = WriterMatrixGuard(audit_db=audit_db)
            
            admin_override = kwargs.get('admin_override', False)
            audit_note = kwargs.get('admin_note')
            
            guard.validate_write_permission(
                collection=collection,
                operation=operation,
                admin_override=admin_override,
                audit_note=audit_note
            )
            
            # Permission granted - execute write
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# LEGACY FUNCTION BLOCKERS
# ============================================================================

class LegacyGraderBlocker:
    """
    Blocks legacy grading functions unless admin override.
    
    Install in legacy modules to prevent accidental use.
    """
    
    @staticmethod
    def block_legacy_grader(
        function_name: str,
        admin_override: bool = False,
        audit_note: Optional[str] = None
    ):
        """
        Block legacy grader function.
        
        Usage:
            def update_pick_outcome(pick_id, outcome):
                LegacyGraderBlocker.block_legacy_grader(
                    "update_pick_outcome",
                    admin_override=admin_override,
                    audit_note=audit_note
                )
                # ... rest of function
        """
        if not admin_override:
            raise UnauthorizedWriteError(
                f"Legacy function '{function_name}' is DISABLED. "
                f"Use UnifiedGradingService instead. "
                f"Admin override requires admin_override=True + audit_note."
            )
        
        if not audit_note:
            raise UnauthorizedWriteError(
                f"Admin override for '{function_name}' requires audit_note"
            )
        
        # Log admin override
        print(f"⚠️  ADMIN OVERRIDE: {function_name} - {audit_note}")


# ============================================================================
# REPO-WIDE TEST HELPERS
# ============================================================================

def generate_grep_commands() -> List[str]:
    """
    Generate grep commands to verify writer matrix enforcement.
    
    Returns list of commands to run in CI/pre-commit.
    """
    commands = []
    
    # Check grading writes
    commands.append(
        'grep -rn "db\\[\\"grading\\"\\].\\(insert\\|update\\)" backend/ '
        '| grep -v "unified_grading_service_v2.py" '
        '| grep -v "test_" '
        '&& echo "❌ Unauthorized grading write found" || echo "✅ Grading writes OK"'
    )
    
    # Check outcomes writes (legacy field)
    commands.append(
        'grep -rn "db\\[\\"outcomes\\"\\].\\(insert\\|update\\)" backend/ '
        '| grep -v "test_" '
        '&& echo "❌ Legacy outcomes write found" || echo "✅ No legacy outcomes writes"'
    )
    
    # Check ops_alerts writes
    commands.append(
        'grep -rn "db\\[\\"ops_alerts\\"\\].insert" backend/ '
        '| grep -v "ops_alert_service.py" '
        '| grep -v "test_" '
        '&& echo "❌ Unauthorized ops_alert write found" || echo "✅ Ops alerts writes OK"'
    )
    
    # Check audit_log writes
    commands.append(
        'grep -rn "db\\[\\"audit_log\\"\\].insert" backend/ '
        '| grep -v "audit_log_service.py" '
        '| grep -v "test_" '
        '&& echo "❌ Unauthorized audit_log write found" || echo "✅ Audit log writes OK"'
    )
    
    return commands


def validate_matrix_compliance(repo_path: str) -> Dict[str, Any]:
    """
    Validate repo compliance with writer matrix.
    
    Runs grep searches and returns compliance report.
    """
    import subprocess
    
    commands = generate_grep_commands()
    results = {}
    
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            results[cmd] = {
                "passed": result.returncode == 0,
                "output": result.stdout + result.stderr
            }
        except Exception as e:
            results[cmd] = {
                "passed": False,
                "output": str(e)
            }
    
    return results
