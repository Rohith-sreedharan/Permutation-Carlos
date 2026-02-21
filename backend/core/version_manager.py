"""
Version Manager for Decision Engine
Section 15 - ENGINE LOCK Specification Compliance

Manages semantic versioning for decision_version field.
Ensures deterministic replay: identical inputs → identical outputs + identical version.

SEMVER Format: MAJOR.MINOR.PATCH
- MAJOR: Threshold, formula, or schema breaking changes
- MINOR: Additive rule changes (new features, no breaking changes)
- PATCH: Bug fixes only (no logic changes)

Version increments are OPERATOR-CONTROLLED (manual bumps only).
No automatic version changes on deployment.
"""

import os
import json
from typing import Optional, Tuple
from datetime import datetime, timezone
import hashlib
from pathlib import Path


class DecisionVersionManager:
    """
    Manages semantic versioning for ENGINE LOCK decision system.
    
    Single source of truth for decision_version.
    Ensures deterministic replay and version stability.
    """
    
    def __init__(self):
        """Initialize version manager with current version from file."""
        self.version_file = Path(__file__).parent / "version.json"
        self.current_version = self._load_version()
        self.git_commit_sha = self._get_git_commit_sha()
    
    def _load_version(self) -> str:
        """
        Load current version from version.json file.
        
        Returns:
            str: Current SEMVER version (e.g., "2.0.0")
        """
        if not self.version_file.exists():
            # Initialize with version 2.0.0 (Section 14 milestone)
            initial_version = {
                "major": 2,
                "minor": 0,
                "patch": 0,
                "version": "2.0.0",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": "system",
                "change_description": "Initial ENGINE LOCK version after Section 14 completion"
            }
            self._save_version(initial_version)
            return "2.0.0"
        
        try:
            with open(self.version_file, 'r') as f:
                version_data = json.load(f)
                return version_data.get("version", "2.0.0")
        except Exception as e:
            print(f"[WARNING] Failed to load version.json: {e}")
            return "2.0.0"  # Fallback to current version
    
    def _save_version(self, version_data: dict) -> None:
        """Save version data to version.json file."""
        try:
            with open(self.version_file, 'w') as f:
                json.dump(version_data, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Failed to save version.json: {e}")
    
    def _get_git_commit_sha(self) -> str:
        """
        Get current git commit SHA for traceability.
        
        Returns:
            str: Git commit SHA (short form) or "unknown" if not in git repo
        """
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"
    
    def get_current_version(self) -> str:
        """
        Get current decision_version.
        
        This is the single source of truth for decision_version.
        
        Returns:
            str: Current SEMVER version (e.g., "2.0.0")
        """
        return self.current_version
    
    def get_version_metadata(self) -> dict:
        """
        Get complete version metadata including git SHA.
        
        Returns:
            dict: Version metadata with decision_version, git_commit_sha, etc.
        """
        return {
            "decision_version": self.current_version,
            "git_commit_sha": self.git_commit_sha,
            "engine_version": "2.0.0",  # ENGINE LOCK spec version
            "version_file": str(self.version_file)
        }
    
    def bump_version(
        self,
        bump_type: str,
        updated_by: str,
        change_description: str
    ) -> str:
        """
        Bump version according to SEMVER rules.
        
        OPERATOR-CONTROLLED ONLY. Must be called explicitly.
        Never called automatically on deployment.
        
        Args:
            bump_type: "major", "minor", or "patch"
            updated_by: Operator identifier (e.g., email or username)
            change_description: Description of changes requiring bump
        
        Returns:
            str: New version string
        
        Raises:
            ValueError: If bump_type is invalid
        """
        bump_type = bump_type.lower()
        if bump_type not in ["major", "minor", "patch"]:
            raise ValueError(f"Invalid bump_type: {bump_type}. Must be major, minor, or patch.")
        
        # Parse current version
        try:
            major, minor, patch = map(int, self.current_version.split('.'))
        except ValueError:
            print(f"[ERROR] Invalid current version format: {self.current_version}")
            major, minor, patch = 2, 0, 0
        
        # Increment according to SEMVER rules
        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        elif bump_type == "patch":
            patch += 1
        
        new_version = f"{major}.{minor}.{patch}"
        
        # Save version change
        version_data = {
            "major": major,
            "minor": minor,
            "patch": patch,
            "version": new_version,
            "previous_version": self.current_version,
            "bump_type": bump_type,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": updated_by,
            "change_description": change_description,
            "git_commit_sha": self.git_commit_sha
        }
        
        self._save_version(version_data)
        self.current_version = new_version
        
        print(f"[VERSION] Bumped {bump_type}: {version_data['previous_version']} → {new_version}")
        print(f"[VERSION] By: {updated_by}")
        print(f"[VERSION] Reason: {change_description}")
        
        return new_version
    
    def get_version_history(self) -> list:
        """
        Get version history from version.json file.
        
        Returns:
            list: List of version entries (most recent first)
        """
        if not self.version_file.exists():
            return []
        
        try:
            with open(self.version_file, 'r') as f:
                version_data = json.load(f)
                # Return as single-item list for now
                # In future, could maintain full history in separate file
                return [version_data]
        except Exception as e:
            print(f"[ERROR] Failed to read version history: {e}")
            return []
    
    def validate_version_format(self, version: str) -> bool:
        """
        Validate version string is valid SEMVER.
        
        Args:
            version: Version string to validate
        
        Returns:
            bool: True if valid SEMVER format
        """
        try:
            parts = version.split('.')
            if len(parts) != 3:
                return False
            
            major, minor, patch = map(int, parts)
            return major >= 0 and minor >= 0 and patch >= 0
        except (ValueError, AttributeError):
            return False


# Singleton instance
_version_manager_instance: Optional[DecisionVersionManager] = None


def get_version_manager() -> DecisionVersionManager:
    """
    Get singleton version manager instance.
    
    Returns:
        DecisionVersionManager: Singleton instance
    """
    global _version_manager_instance
    if _version_manager_instance is None:
        _version_manager_instance = DecisionVersionManager()
    return _version_manager_instance


def get_current_decision_version() -> str:
    """
    Convenience function to get current decision_version.
    
    Single source of truth for decision_version field in responses.
    
    Returns:
        str: Current SEMVER version
    """
    return get_version_manager().get_current_version()


def get_version_metadata() -> dict:
    """
    Convenience function to get version metadata.
    
    Returns:
        dict: Version metadata including git SHA
    """
    return get_version_manager().get_version_metadata()
