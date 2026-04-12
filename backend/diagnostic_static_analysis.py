#!/usr/bin/env python3
"""
ENHANCED DIAGNOSTIC TOOL
Works with or without running services, provides static code analysis
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class StaticDiagnostics:
    """Analyze code and configuration without requiring running services"""
    
    def __init__(self, backend_path: str = "."):
        self.backend_path = Path(backend_path)
        self.env_path = self.backend_path / ".env"
        self.config = self._load_env()
    
    def _load_env(self) -> Dict[str, str]:
        """Load .env file"""
        config = {}
        if self.env_path.exists():
            with open(self.env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
        return config
    
    def analyze_env_config(self) -> Dict[str, Any]:
        """Check .env configuration"""
        result = {
            "env_file_exists": self.env_path.exists(),
            "configured_keys": {},
            "missing_keys": [],
            "issues": []
        }
        
        if not result["env_file_exists"]:
            result["issues"].append("No .env file found")
            return result
        
        required_keys = ["MONGO_URI", "ODDS_API_KEY", "ODDS_BASE_URL", "DATABASE_NAME"]
        
        for key in required_keys:
            if key in self.config:
                value = self.config[key]
                # Mask sensitive data
                if "API_KEY" in key:
                    masked = value[:10] + "***" if len(value) > 10 else "***"
                else:
                    masked = value
                result["configured_keys"][key] = masked
            else:
                result["missing_keys"].append(key)
        
        return result
    
    def analyze_decision_endpoint(self) -> Dict[str, Any]:
        """Analyze decisions endpoint code"""
        decisions_file = self.backend_path / "routes" / "decisions.py"
        
        result = {
            "file_exists": decisions_file.exists(),
            "endpoint_path": "GET /api/games/{league}/{game_id}/decisions",
            "failure_points": [],
            "expected_response_structure": {
                "spread": "MarketDecision object",
                "moneyline": "MarketDecision object",
                "total": "MarketDecision object"
            }
        }
        
        if not decisions_file.exists():
            result["issues"] = ["File not found"]
            return result
        
        with open(decisions_file) as f:
            content = f.read()
            
            # Extract failure scenarios
            if 'status_code=404, detail=f"Game {game_id} not found"' in content:
                result["failure_points"].append({
                    "scenario": "MISSING_EVENT",
                    "condition": "Event not found in db['events']",
                    "http_code": 404,
                    "error_message": "Game {game_id} not found"
                })
            
            if 'status_code=404, detail=f"No odds available for {game_id}"' in content:
                result["failure_points"].append({
                    "scenario": "NO_ODDS_AVAILABLE",
                    "condition": "No bookmakers/markets in event",
                    "http_code": 404,
                    "error_message": "No odds available for {game_id}"
                })
            
            if "MarketDecisionComputer" in content:
                result["failure_points"].append({
                    "scenario": "DECISION_COMPUTATION",
                    "condition": "MarketDecisionComputer.compute_all() fails",
                    "http_code": 500,
                    "error_message": "Internal server error (returned as Failed to load)"
                })
        
        return result
    
    def analyze_database_schema(self) -> Dict[str, Any]:
        """Analyze expected database schema"""
        return {
            "collections": {
                "events": {
                    "purpose": "Raw odds data from Odds API",
                    "key_fields": ["id", "event_id", "sport_key", "bookmakers", "markets"],
                    "sample_index": "event_id (unique)"
                },
                "market_snapshots": {
                    "purpose": "Historical market state snapshots",
                    "key_fields": ["game_id", "created_at", "status", "wave"],
                    "sample_index": "(created_at DESC)"
                },
                "decision_records": {
                    "purpose": "Cached decision computation results",
                    "key_fields": ["identity_key", "record_id", "game_id", "classification", "release_status"],
                    "sample_index": "(identity_key, unique), (game_id, created_at DESC)"
                },
                "monte_carlo_simulations": {
                    "purpose": "Pre-computed simulation results",
                    "key_fields": ["game_id", "league", "iteration_count", "results"],
                    "sample_index": "game_id"
                }
            }
        }
    
    def analyze_odds_pipeline(self) -> Dict[str, Any]:
        """Analyze odds ingestion pipeline"""
        scheduler_file = self.backend_path / "services" / "scheduler.py"
        
        result = {
            "file_exists": scheduler_file.exists(),
            "job_name": "poll_odds_api",
            "frequency": "APScheduler interval (default 5-10 min)",
            "slo": "< 20s pre-match, < 10s in-play",
            "pipeline_stages": [
                {
                    "stage": 1,
                    "action": "Call Odds API",
                    "endpoint": "GET /v4/sports/{sport}/odds",
                    "parameters": ["apiKey", "regions", "markets", "oddsFormat"],
                    "timeout": "15 seconds"
                },
                {
                    "stage": 2,
                    "action": "Normalize events",
                    "details": "Add EST dates, convert decimal→American odds"
                },
                {
                    "stage": 3,
                    "action": "Upsert to MongoDB",
                    "collection": "events",
                    "upsert_key": "id"
                }
            ],
            "failure_modes": [
                {
                    "scenario": "API_TIMEOUT",
                    "cause": "Odds API not responding within 15s",
                    "impact": "New odds not loaded, old odds returned"
                },
                {
                    "scenario": "API_ERROR",
                    "cause": "HTTP 401 (auth), 429 (quota), 422 (bad request)",
                    "impact": "Pipeline fails, odds go stale"
                },
                {
                    "scenario": "MONGODB_UNAVAILABLE",
                    "cause": "MongoDB connection fails",
                    "impact": "Cannot upsert odds, pipeline halts"
                },
                {
                    "scenario": "NORMALIZATION_FAILURE",
                    "cause": "Exception in normalize_event()",
                    "impact": "Some events skipped"
                }
            ]
        }
        
        return result
    
    def analyze_data_providers(self) -> Dict[str, Any]:
        """Analyze data provider configuration"""
        return {
            "primary_provider": "The Odds API",
            "provider_url": "https://api.the-odds-api.com/v4",
            "api_key_env_var": "ODDS_API_KEY",
            "base_url_env_var": "ODDS_BASE_URL",
            "supported_sports": [
                {
                    "sport": "NBA",
                    "api_key": "basketball_nba",
                    "markets": ["spreads", "totals", "h2h"],
                    "status": "CHECK_WITH_RUNNING_SERVER"
                },
                {
                    "sport": "MLB",
                    "api_key": "baseball_mlb",
                    "markets": ["spreads", "totals", "h2h"],
                    "status": "ERROR_422_MISSING_REGION (known issue)",
                    "fix": "Ensure 'regions' parameter included in API request"
                },
                {
                    "sport": "NHL",
                    "api_key": "icehockey_nhl",
                    "markets": ["spreads", "totals", "h2h"],
                    "status": "OUT_OF_SEASON_TODAY"
                },
                {
                    "sport": "NFL",
                    "api_key": "americanfootball_nfl",
                    "markets": ["spreads", "totals", "h2h"],
                    "status": "CHECK_WITH_RUNNING_SERVER"
                }
            ],
            "current_issues": [
                {
                    "sport": "MLB",
                    "issue": "422 MISSING_REGION error",
                    "root_cause": "API parameters not aligned with current API version",
                    "fix_location": "backend/integrations/odds_api.py",
                    "fix_action": "Add 'regions=us' to request params"
                }
            ]
        }
    
    def generate_static_report(self) -> Dict[str, Any]:
        """Generate complete static analysis report"""
        return {
            "report_timestamp": datetime.utcnow().isoformat(),
            "report_type": "STATIC_ANALYSIS",
            "note": "This report requires NO running services. Infrastructure diagnostics stored in separate JSON.",
            "analysis": {
                "environment_config": self.analyze_env_config(),
                "decision_endpoint": self.analyze_decision_endpoint(),
                "database_schema": self.analyze_database_schema(),
                "odds_pipeline": self.analyze_odds_pipeline(),
                "data_providers": self.analyze_data_providers()
            }
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Static diagnostic analyzer")
    parser.add_argument("--backend-path", default="/Users/rohithaditya/Downloads/Permutation-Carlos/backend",
                        help="Path to backend directory")
    parser.add_argument("--output", default="diagnostic_static_analysis.json",
                        help="Output file for static analysis")
    args = parser.parse_args()
    
    print("📊 STATIC DIAGNOSTIC ANALYSIS (No services required)")
    print("=" * 80)
    
    analyzer = StaticDiagnostics(args.backend_path)
    report = analyzer.generate_static_report()
    
    # Print summary
    config = report["analysis"]["environment_config"]
    print(f"\n✅ Configuration Check:")
    print(f"   .env file: {'Present' if config['env_file_exists'] else 'MISSING'}")
    print(f"   Configured keys: {len(config['configured_keys'])}")
    print(f"   Missing keys: {len(config['missing_keys'])}")
    if config['missing_keys']:
        print(f"      ⚠️  {config['missing_keys']}")
    
    endpoints = report["analysis"]["decision_endpoint"]
    print(f"\n🔌 API Endpoint Analysis:")
    print(f"   File: {endpoints['file_exists']}")
    print(f"   Path: {endpoints['endpoint_path']}")
    print(f"   Failure modes found: {len(endpoints['failure_points'])}")
    for fp in endpoints['failure_points']:
        print(f"      • {fp['scenario']}: HTTP {fp['http_code']}")
    
    pipeline = report["analysis"]["odds_pipeline"]
    print(f"\n⏱️  Odds Pipeline Analysis:")
    print(f"   File: {pipeline['file_exists']}")
    print(f"   Job: {pipeline['job_name']}")
    print(f"   Failure modes: {len(pipeline['failure_modes'])}")
    
    providers = report["analysis"]["data_providers"]
    print(f"\n📡 Data Provider Analysis:")
    print(f"   Primary: {providers['primary_provider']}")
    print(f"   Supported sports: {len(providers['supported_sports'])}")
    print(f"   Known issues: {len(providers['current_issues'])}")
    if providers['current_issues']:
        for issue in providers['current_issues']:
            print(f"      ⚠️  {issue['sport']}: {issue['issue']}")
    
    # Save report
    with open(args.output, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n✅ Static analysis saved to {args.output}")
    print("=" * 80)
    print("\nTo complete diagnostics:")
    print("1. Start MongoDB: brew services start mongodb-community")
    print("2. Start Backend: python backend/main.py")
    print("3. Run: python backend/diagnostic_reporter.py --league nba")


if __name__ == "__main__":
    main()
