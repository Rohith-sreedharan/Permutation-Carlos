"""
📝 INCIDENT LOGGING SYSTEM
Track and document system incidents and configuration changes

Maintains transparency and change history for all system modifications.
"""

import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.mongo import db
from pymongo.database import Database


class IncidentLogger:
    """Log incidents and configuration changes"""
    
    INCIDENT_TYPES = [
        "BAD_EDGE",
        "LEAN_LEAKAGE",
        "INJURY_MISS",
        "DUPLICATE_POST",
        "STALE_POST",
        "CONFIG_CHANGE",
        "THRESHOLD_ADJUSTMENT",
        "SYSTEM_FREEZE",
        "OTHER"
    ]
    
    SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    
    def __init__(self, database: Database):
        self.db = database
        self.incidents_dir = os.path.join(
            os.path.dirname(__file__),
            "..",
            "logs",
            "incidents"
        )
        os.makedirs(self.incidents_dir, exist_ok=True)
    
    async def log_incident(
        self,
        incident_type: str,
        severity: str,
        description: str,
        sport: Optional[str] = None,
        game_id: Optional[str] = None,
        post_id: Optional[str] = None,
        wave_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a system incident
        
        Args:
            incident_type: Type of incident (from INCIDENT_TYPES)
            severity: Severity level (from SEVERITY_LEVELS)
            description: Detailed description of incident
            sport: Related sport (optional)
            game_id: Related game ID (optional)
            post_id: Related Telegram post ID (optional)
            wave_id: Related wave ID (optional)
            additional_data: Any additional context (optional)
        
        Returns:
            Incident ID
        """
        # Validate inputs
        if incident_type not in self.INCIDENT_TYPES:
            raise ValueError(f"Invalid incident_type. Must be one of: {self.INCIDENT_TYPES}")
        
        if severity not in self.SEVERITY_LEVELS:
            raise ValueError(f"Invalid severity. Must be one of: {self.SEVERITY_LEVELS}")
        
        # Create incident record
        incident = {
            "timestamp": datetime.now(),
            "incident_type": incident_type,
            "severity": severity,
            "description": description,
            "sport": sport,
            "game_id": game_id,
            "post_id": post_id,
            "wave_id": wave_id,
            "additional_data": additional_data or {},
            "resolved": False,
            "resolution": None,
            "resolved_at": None,
            "logged_by": "system"
        }
        
        # Save to database
        try:
            result = self.db["incidents"].insert_one(incident)
            incident_id = str(result.inserted_id)
            
            print(f"✅ Incident logged: {incident_id}")
            print(f"   Type: {incident_type}")
            print(f"   Severity: {severity}")
            print(f"   Description: {description}")
            
            # Also save to file
            self._save_incident_to_file(incident, incident_id)
            
            return incident_id
        
        except Exception as e:
            print(f"❌ Error logging incident: {e}")
            raise
    
    async def log_config_change(
        self,
        sport: str,
        parameter: str,
        old_value: Any,
        new_value: Any,
        reason: str
    ) -> str:
        """
        Log a configuration change
        
        Args:
            sport: Sport being configured
            parameter: Parameter name being changed
            old_value: Previous value
            new_value: New value
            reason: Reason for change
        
        Returns:
            Change log ID
        """
        change_log = {
            "timestamp": datetime.now(),
            "change_type": "CONFIG_CHANGE",
            "sport": sport,
            "parameter": parameter,
            "old_value": str(old_value),
            "new_value": str(new_value),
            "reason": reason,
            "logged_by": "system"
        }
        
        try:
            result = self.db["config_changes"].insert_one(change_log)
            change_id = str(result.inserted_id)
            
            print(f"✅ Configuration change logged: {change_id}")
            print(f"   Sport: {sport}")
            print(f"   Parameter: {parameter}")
            print(f"   Old: {old_value} → New: {new_value}")
            print(f"   Reason: {reason}")
            
            # Save to file
            self._save_config_change_to_file(change_log, change_id)
            
            return change_id
        
        except Exception as e:
            print(f"❌ Error logging config change: {e}")
            raise
    
    async def resolve_incident(self, incident_id: str, resolution: str):
        """Mark an incident as resolved"""
        try:
            self.db["incidents"].update_one(
                {"_id": incident_id},
                {
                    "$set": {
                        "resolved": True,
                        "resolution": resolution,
                        "resolved_at": datetime.now()
                    }
                }
            )
            
            print(f"✅ Incident {incident_id} marked as resolved")
            print(f"   Resolution: {resolution}")
        
        except Exception as e:
            print(f"❌ Error resolving incident: {e}")
            raise
    
    async def get_recent_incidents(
        self,
        days: int = 7,
        severity: Optional[str] = None,
        unresolved_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get recent incidents"""
        cutoff = datetime.now() - timedelta(days=days)
        
        query: Dict[str, Any] = {"timestamp": {"$gte": cutoff}}
        
        if severity:
            query["severity"] = severity
        
        if unresolved_only:
            query["resolved"] = False
        
        try:
            incidents = list(self.db["incidents"].find(query).sort(
                "timestamp", -1
            ).limit(100))
            
            return incidents
        
        except Exception as e:
            print(f"❌ Error fetching incidents: {e}")
            return []
    
    async def get_config_history(
        self,
        sport: Optional[str] = None,
        parameter: Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get configuration change history"""
        cutoff = datetime.now() - timedelta(days=days)
        
        query: Dict[str, Any] = {"timestamp": {"$gte": cutoff}}
        
        if sport:
            query["sport"] = sport
        
        if parameter:
            query["parameter"] = parameter
        
        try:
            changes = list(self.db["config_changes"].find(query).sort(
                "timestamp", -1
            ).limit(100))
            
            return changes
        
        except Exception as e:
            print(f"❌ Error fetching config history: {e}")
            return []
    
    def _save_incident_to_file(self, incident: Dict[str, Any], incident_id: str):
        """Save incident to JSON file"""
        timestamp = incident["timestamp"].strftime("%Y%m%d_%H%M%S")
        filename = f"incident_{timestamp}_{incident_id}.json"
        filepath = os.path.join(self.incidents_dir, filename)
        
        # Convert datetime to string for JSON
        incident_copy = incident.copy()
        incident_copy["timestamp"] = incident_copy["timestamp"].isoformat()
        incident_copy["_id"] = incident_id
        
        try:
            with open(filepath, 'w') as f:
                json.dump(incident_copy, f, indent=2)
        except Exception as e:
            print(f"⚠️  Warning: Could not save incident to file: {e}")
    
    def _save_config_change_to_file(self, change: Dict[str, Any], change_id: str):
        """Save config change to JSON file"""
        # Also append to a running changelog
        changelog_file = os.path.join(self.incidents_dir, "config_changelog.jsonl")
        
        change_copy = change.copy()
        change_copy["timestamp"] = change_copy["timestamp"].isoformat()
        change_copy["_id"] = change_id
        
        try:
            with open(changelog_file, 'a') as f:
                f.write(json.dumps(change_copy) + '\n')
        except Exception as e:
            print(f"⚠️  Warning: Could not save config change to file: {e}")
    
    async def print_incident_summary(self, days: int = 7):
        """Print summary of recent incidents"""
        print(f"\n📝 INCIDENT SUMMARY (Last {days} days)")
        print("="*80)
        
        incidents = await self.get_recent_incidents(days)
        
        if not incidents:
            print("\n✅ No incidents logged")
            return
        
        # Group by severity
        by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
        for incident in incidents:
            severity = incident.get("severity", "LOW")
            by_severity[severity].append(incident)
        
        # Print by severity
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if by_severity[severity]:
                emoji = "🚨" if severity in ["CRITICAL", "HIGH"] else "⚠️" if severity == "MEDIUM" else "ℹ️"
                print(f"\n{emoji} {severity} ({len(by_severity[severity])})")
                
                for incident in by_severity[severity][:5]:  # Show top 5
                    timestamp = incident["timestamp"].strftime("%Y-%m-%d %H:%M")
                    incident_type = incident["incident_type"]
                    description = incident["description"][:60]
                    resolved = "✅" if incident.get("resolved") else "❌"
                    
                    print(f"   {resolved} [{timestamp}] {incident_type}: {description}...")
        
        # Show unresolved count
        unresolved = [i for i in incidents if not i.get("resolved")]
        if unresolved:
            print(f"\n⚠️  {len(unresolved)} unresolved incident(s)")


from datetime import timedelta


async def main():
    """Interactive incident logging"""
    import asyncio
    from db.mongo import db
    
    logger = IncidentLogger(db)
    
    if len(sys.argv) < 2:
        # Show summary
        await logger.print_incident_summary()
        
        print("\n" + "="*80)
        print("USAGE:")
        print("  python incident_logger.py summary [days]")
        print("  python incident_logger.py log")
        print("  python incident_logger.py config_history [sport] [days]")
        print("="*80)
        return
    
    command = sys.argv[1].lower()
    
    if command == "summary":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        await logger.print_incident_summary(days)
    
    elif command == "log":
        # Interactive logging
        print("\n📝 LOG NEW INCIDENT")
        print("="*80)
        
        print("\nIncident Types:")
        for i, itype in enumerate(logger.INCIDENT_TYPES, 1):
            print(f"  {i}. {itype}")
        
        type_idx = int(input("\nSelect type (1-9): ")) - 1
        incident_type = logger.INCIDENT_TYPES[type_idx]
        
        print("\nSeverity Levels:")
        for i, sev in enumerate(logger.SEVERITY_LEVELS, 1):
            print(f"  {i}. {sev}")
        
        sev_idx = int(input("\nSelect severity (1-4): ")) - 1
        severity = logger.SEVERITY_LEVELS[sev_idx]
        
        description = input("\nDescription: ")
        sport = input("Sport (optional, press enter to skip): ") or None
        
        await logger.log_incident(
            incident_type=incident_type,
            severity=severity,
            description=description,
            sport=sport
        )
        
        print("\n✅ Incident logged successfully")
    
    elif command == "config_history":
        sport = sys.argv[2] if len(sys.argv) > 2 else None
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        
        print(f"\n📋 CONFIGURATION CHANGE HISTORY")
        if sport:
            print(f"Sport: {sport}")
        print(f"Last {days} days")
        print("="*80)
        
        changes = await logger.get_config_history(sport=sport, days=days)
        
        if not changes:
            print("\n✅ No configuration changes logged")
        else:
            for change in changes:
                timestamp = change["timestamp"].strftime("%Y-%m-%d %H:%M")
                sport_name = change.get("sport", "N/A")
                param = change["parameter"]
                old = change["old_value"]
                new = change["new_value"]
                reason = change["reason"]
                
                print(f"\n[{timestamp}] {sport_name}")
                print(f"  {param}: {old} → {new}")
                print(f"  Reason: {reason}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
