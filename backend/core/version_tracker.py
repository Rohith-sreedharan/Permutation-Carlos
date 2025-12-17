"""
Version Control and Change Traceability
Every pick logs model version, config version, and triggered dampening factors

NO SILENT CHANGES - ALL modifications are tracked and auditable

Logs:
- model_version_hash: Git commit hash of model code
- config_version_hash: Hash of calibration configs
- dampening_triggers_fired: List of active dampening reasons
- feature_flags: Active experimental features
"""

import hashlib
import json
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class VersionTracker:
    """
    Tracks model versions and configuration changes
    Ensures full traceability of all predictions
    """
    
    def __init__(self):
        self._model_version_cache = None
        self._config_version_cache = None
        self._git_commit_cache = None
    
    def get_git_commit_hash(self) -> str:
        """Get current git commit hash"""
        if self._git_commit_cache:
            return self._git_commit_cache
        
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True
            )
            commit_hash = result.stdout.strip()
            self._git_commit_cache = commit_hash
            return commit_hash
        except Exception as e:
            logger.warning(f"Failed to get git commit hash: {e}")
            return "UNKNOWN"
    
    def get_model_version_hash(self) -> str:
        """
        Generate hash of critical model files
        Detects changes to simulation logic
        """
        if self._model_version_cache:
            return self._model_version_cache
        
        try:
            # Critical model files to hash
            model_files = [
                "core/monte_carlo_engine.py",
                "core/sport_strategies.py",
                "core/calibration_engine.py",
                "core/calibration_logger.py",
                "core/sport_calibration_config.py"
            ]
            
            backend_path = Path(__file__).parent.parent
            hasher = hashlib.sha256()
            
            for file_path in model_files:
                full_path = backend_path / file_path
                if full_path.exists():
                    with open(full_path, 'rb') as f:
                        hasher.update(f.read())
            
            version_hash = hasher.hexdigest()[:12]  # First 12 chars
            self._model_version_cache = version_hash
            return version_hash
        except Exception as e:
            logger.error(f"Failed to generate model version hash: {e}")
            return "ERROR"
    
    def get_config_version_hash(self) -> str:
        """
        Generate hash of calibration configs
        Detects threshold/parameter changes
        """
        if self._config_version_cache:
            return self._config_version_cache
        
        try:
            from core.sport_calibration_config import SPORT_CONFIGS
            
            # Serialize configs to JSON and hash
            config_json = json.dumps(
                {k: v.__dict__ for k, v in SPORT_CONFIGS.items()},
                sort_keys=True
            )
            
            hasher = hashlib.sha256(config_json.encode())
            version_hash = hasher.hexdigest()[:12]
            self._config_version_cache = version_hash
            return version_hash
        except Exception as e:
            logger.error(f"Failed to generate config version hash: {e}")
            return "ERROR"
    
    def get_version_metadata(
        self,
        dampening_triggers: Optional[List[str]] = None,
        feature_flags: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Get complete version metadata for a pick
        
        Args:
            dampening_triggers: List of active dampening reasons
            feature_flags: Active experimental features
        
        Returns:
            Version metadata dict
        """
        return {
            "git_commit": self.get_git_commit_hash(),
            "model_version": self.get_model_version_hash(),
            "config_version": self.get_config_version_hash(),
            "dampening_triggers": dampening_triggers or [],
            "feature_flags": feature_flags or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "python_version": self._get_python_version()
        }
    
    def _get_python_version(self) -> str:
        """Get Python version"""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def detect_config_changes(
        self,
        previous_config_hash: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect if config has changed since previous run
        
        Returns:
            (has_changed, change_description)
        """
        if not previous_config_hash:
            return False, None
        
        current_hash = self.get_config_version_hash()
        
        if current_hash != previous_config_hash:
            return True, f"Config changed: {previous_config_hash[:6]} → {current_hash[:6]}"
        
        return False, None
    
    def generate_audit_trail(
        self,
        pick_data: Dict[str, Any],
        dampening_active: bool = False,
        dampening_reasons: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate complete audit trail for a pick
        
        Args:
            pick_data: Pick metadata (game_id, sport, probabilities, etc.)
            dampening_active: Whether dampening is active
            dampening_reasons: Reasons for dampening
        
        Returns:
            Audit trail dict
        """
        version_metadata = self.get_version_metadata(
            dampening_triggers=dampening_reasons if dampening_active else []
        )
        
        audit_trail = {
            "pick_id": f"{pick_data.get('game_id')}_{pick_data.get('market_type', 'total')}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            
            # Version tracking
            "version": version_metadata,
            
            # Pick metadata
            "game_id": pick_data.get("game_id"),
            "sport": pick_data.get("sport"),
            "market_type": pick_data.get("market_type", "total"),
            
            # Model outputs
            "model_total": pick_data.get("model_total"),
            "vegas_total": pick_data.get("vegas_total"),
            "probability": pick_data.get("probability"),
            "edge": pick_data.get("edge"),
            "confidence_score": pick_data.get("confidence_score"),
            
            # Calibration metadata
            "calibration_publish": pick_data.get("calibration_publish", True),
            "calibration_block_reasons": pick_data.get("calibration_block_reasons", []),
            
            # Dampening status
            "dampening_active": dampening_active,
            "dampening_reasons": dampening_reasons or [],
            "damp_factor": pick_data.get("damp_factor", 1.0),
            
            # Pick state
            "pick_state": pick_data.get("pick_state", "UNKNOWN"),
            "can_publish": pick_data.get("can_publish", False),
            "can_parlay": pick_data.get("can_parlay", False)
        }
        
        return audit_trail
    
    def log_configuration_change(
        self,
        change_type: str,
        old_value: Any,
        new_value: Any,
        changed_by: str = "SYSTEM"
    ) -> None:
        """
        Log configuration changes to audit trail
        
        Args:
            change_type: Type of change (threshold, dampening, feature_flag)
            old_value: Previous value
            new_value: New value
            changed_by: Who made the change
        """
        from db.mongo import db
        
        change_log = {
            "timestamp": datetime.now(timezone.utc),
            "change_type": change_type,
            "old_value": old_value,
            "new_value": new_value,
            "changed_by": changed_by,
            "git_commit": self.get_git_commit_hash(),
            "model_version": self.get_model_version_hash(),
            "config_version": self.get_config_version_hash()
        }
        
        try:
            db["config_change_log"].insert_one(change_log)
            logger.info(f"📝 Configuration change logged: {change_type}")
        except Exception as e:
            logger.error(f"Failed to log configuration change: {e}")


# Global version tracker instance
_version_tracker = None

def get_version_tracker() -> VersionTracker:
    """Get global version tracker instance"""
    global _version_tracker
    if _version_tracker is None:
        _version_tracker = VersionTracker()
    return _version_tracker
