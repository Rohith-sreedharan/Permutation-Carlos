#!/usr/bin/env python3
"""
ROOT CAUSE DIAGNOSTIC REPORTER
Gathers all 5 required diagnostic items for "Failed to Load Decision" state
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

class DiagnosticReporter:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("DATABASE_NAME", "beatvegas")
        self.odds_api_key = os.getenv("ODDS_API_KEY")
        self.odds_base_url = os.getenv("ODDS_BASE_URL", "https://api.the-odds-api.com/v4")
        
        # Connect to MongoDB
        try:
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            print("✅ MongoDB connected")
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            self.db = None
    
    def diagnostic_1_api_response(self, league: str = "nba", game_id: Optional[str] = None) -> Dict[str, Any]:
        """
        1. API Response (Required)
        Get full raw JSON response for one affected game
        """
        print("\n" + "="*80)
        print("DIAGNOSTIC 1: API Response for Single Affected Game")
        print("="*80)
        
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "description": "Full raw JSON response from GET /api/games/{league}/{game_id}/decisions",
            "league": league,
            "game_id": game_id,
            "api_response": None,
            "error": None,
            "notes": []
        }
        
        # If no game_id provided, find one from database
        if not game_id:
            if self.db:
                events = list(self.db["events"].find(
                    {"sport_key": {"$regex": f"^{league}"}},
                    limit=1
                ))
                if events:
                    event = events[0]
                    game_id = event.get("id") or event.get("event_id")
                    result["notes"].append(f"Found game_id: {game_id} from database")
                else:
                    result["error"] = f"No events found for league: {league}"
                    result["notes"].append("Database search failed - using example format")
                    print(f"❌ No events found for {league}")
                    return result
        
        # Make request to decisions endpoint
        try:
            url = f"http://localhost:8000/api/games/{league}/{game_id}/decisions"
            response = requests.get(url, timeout=10)
            
            result["api_response"] = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.json() if response.text else None,
                "raw_text": response.text[:500] if response.text else None
            }
            
            if response.status_code == 200:
                print(f"✅ API Response retrieved for {league}/{game_id}")
                print(f"   Status: {response.status_code}")
                print(f"   Body size: {len(response.text)} bytes")
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text[:200]}"
                print(f"❌ API Error: {response.status_code}")
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Request failed: {e}")
        
        return result
    
    def diagnostic_2_odds_pipeline_status(self) -> Dict[str, Any]:
        """
        2. Odds Ingestion Pipeline Status
        Check if odds pipeline is running, get last successful run timestamp
        """
        print("\n" + "="*80)
        print("DIAGNOSTIC 2: Odds Ingestion Pipeline Status")
        print("="*80)
        
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "description": "Status of odds polling job and last successful run",
            "pipeline_running": False,
            "last_successful_run": None,
            "api_status": None,
            "recent_events": [],
            "error": None,
            "notes": []
        }
        
        if not self.db:
            result["error"] = "MongoDB not connected"
            return result
        
        # Check recent events in database (proxy for pipeline activity)
        try:
            # Find most recent event
            recent = list(self.db["events"].find({}).sort("updated_at", -1).limit(1))
            if recent:
                event = recent[0]
                last_update = event.get("updated_at") or event.get("created_at")
                result["last_successful_run"] = last_update
                
                # Check if odds are fresh (within 1 hour)
                if isinstance(last_update, str):
                    last_update = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                
                age_minutes = (datetime.utcnow() - last_update).total_seconds() / 60
                result["notes"].append(f"Most recent odds update: {age_minutes:.1f} minutes ago")
                
                if age_minutes < 60:
                    result["pipeline_running"] = True
                    print(f"✅ Pipeline appears active (odds updated {age_minutes:.1f}m ago)")
                else:
                    result["notes"].append(f"⚠️  Odds are stale ({age_minutes:.1f}m old)")
                    print(f"⚠️  Odds are stale ({age_minutes:.1f}m old)")
            
            # Sample recent events
            events = list(self.db["events"].find({}).sort("updated_at", -1).limit(10))
            result["recent_events"] = [
                {
                    "event_id": e.get("id") or e.get("event_id"),
                    "sport": e.get("sport_key"),
                    "updated_at": str(e.get("updated_at") or e.get("created_at")),
                    "bookmaker_count": len(e.get("bookmakers", []))
                }
                for e in events
            ]
            print(f"✅ Found {len(events)} recent events in database")
            
        except Exception as e:
            result["error"] = f"Database query failed: {e}"
            print(f"❌ Database error: {e}")
        
        # Check Odds API health
        try:
            url = f"{self.odds_base_url}/sports"
            response = requests.get(url, params={"apiKey": self.odds_api_key}, timeout=5)
            result["api_status"] = {
                "status_code": response.status_code,
                "available_sports": len(response.json()) if response.status_code == 200 else 0
            }
            if response.status_code == 200:
                print("✅ Odds API is accessible")
            else:
                print(f"⚠️  Odds API returned {response.status_code}")
        except Exception as e:
            result["api_status"] = {"error": str(e)}
            print(f"⚠️  Odds API unreachable: {e}")
        
        return result
    
    def diagnostic_3_market_snapshots(self) -> Dict[str, Any]:
        """
        3. Market Snapshot Verification
        Run the exact query provided and return results
        """
        print("\n" + "="*80)
        print("DIAGNOSTIC 3: Market Snapshots (Last 24 Hours)")
        print("="*80)
        
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "description": "SELECT game_id, created_at, status FROM market_snapshots WHERE created_at > NOW() - INTERVAL '24 hours' ORDER BY created_at DESC LIMIT 20",
            "query": "db.market_snapshots.find({'created_at': {'$gt': ISODate('" + (datetime.utcnow() - timedelta(hours=24)).isoformat() + "')}}).sort({'created_at': -1}).limit(20)",
            "results": [],
            "total_count": 0,
            "error": None
        }
        
        if not self.db:
            result["error"] = "MongoDB not connected"
            return result
        
        try:
            # Check if collection exists
            if "market_snapshots" not in self.db.list_collection_names():
                result["notes"] = ["⚠️  Collection 'market_snapshots' does not exist"]
                print("⚠️  Collection not found - checking alternative naming...")
                
                # Check for similar collections
                collections = self.db.list_collection_names()
                snapshot_collections = [c for c in collections if "snapshot" in c.lower()]
                result["similar_collections"] = snapshot_collections
                print(f"   Similar collections: {snapshot_collections}")
            
            # Query market_snapshots
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            snapshots = list(
                self.db["market_snapshots"].find(
                    {"created_at": {"$gt": cutoff_time}}
                ).sort("created_at", -1).limit(20)
            )
            
            result["total_count"] = len(snapshots)
            result["results"] = [
                {
                    "game_id": s.get("game_id"),
                    "created_at": s.get("created_at"),
                    "status": s.get("status"),
                    "_id": str(s.get("_id"))
                }
                for s in snapshots
            ]
            
            print(f"✅ Found {len(snapshots)} market snapshots in last 24 hours")
            for snap in snapshots[:5]:
                print(f"   - {snap.get('game_id')}: {snap.get('created_at')} (status: {snap.get('status')})")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Query failed: {e}")
        
        return result
    
    def diagnostic_4_decision_records(self, game_id: Optional[str] = None) -> Dict[str, Any]:
        """
        4. Decision Record Existence
        Check if DecisionRecord exists in database for affected game
        """
        print("\n" + "="*80)
        print("DIAGNOSTIC 4: Decision Records for Affected Game")
        print("="*80)
        
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "description": "Check existence and retrieve DecisionRecord for affected game",
            "game_id": game_id,
            "record_exists": False,
            "record_data": None,
            "all_records_count": 0,
            "error": None
        }
        
        if not self.db:
            result["error"] = "MongoDB not connected"
            return result
        
        # If no game_id, find one that failed
        if not game_id:
            try:
                records = list(self.db["decision_records"].find({}).limit(1))
                if records:
                    game_id = records[0].get("game_id")
                    result["game_id"] = game_id
                    result["notes"] = ["Using first available record from database"]
            except:
                pass
        
        try:
            # Count total decision records
            total = self.db["decision_records"].count_documents({})
            result["all_records_count"] = total
            print(f"✅ Total decision records in database: {total}")
            
            if game_id:
                # Check for this specific game
                record = self.db["decision_records"].find_one({"game_id": game_id})
                
                if record:
                    result["record_exists"] = True
                    result["record_data"] = {
                        "_id": str(record.get("_id")),
                        "game_id": record.get("game_id"),
                        "identity_key": record.get("identity_key"),
                        "record_id": record.get("record_id"),
                        "created_at": str(record.get("created_at")),
                        "classification": record.get("classification"),
                        "release_status": record.get("release_status"),
                        "spread": record.get("spread"),
                        "total": record.get("total"),
                        "moneyline": record.get("moneyline")
                    }
                    print(f"✅ DecisionRecord EXISTS for game {game_id}")
                    print(f"   Status: {record.get('release_status')}")
                else:
                    result["record_exists"] = False
                    print(f"❌ NO DecisionRecord found for game {game_id}")
                    
                    # Check if game exists in events table
                    event = self.db["events"].find_one({"$or": [{"id": game_id}, {"event_id": game_id}]})
                    if event:
                        result["notes"] = ["Game exists in events table but no decision record"]
            
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Query failed: {e}")
        
        return result
    
    def diagnostic_5_data_providers(self) -> Dict[str, Any]:
        """
        5. Data Provider Confirmation
        Identify data providers for MLB and NHL odds, confirm status
        """
        print("\n" + "="*80)
        print("DIAGNOSTIC 5: Data Provider Status (MLB & NHL)")
        print("="*80)
        
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "description": "Data provider identification and status for MLB and NHL odds",
            "primary_provider": "The Odds API",
            "provider_url": "https://api.the-odds-api.com/v4",
            "api_key_status": "configured" if self.odds_api_key else "not configured",
            "sports_status": {},
            "error": None
        }
        
        if not self.odds_api_key:
            result["error"] = "ODDS_API_KEY not configured in environment"
            print("❌ API key not configured")
            return result
        
        # Check status for each sport
        sports_to_check = [
            ("baseball_mlb", "MLB"),
            ("icehockey_nhl", "NHL")
        ]
        
        for sport_key, sport_name in sports_to_check:
            print(f"\nChecking {sport_name}...")
            try:
                url = f"{self.odds_base_url}/sports/{sport_key}/odds"
                response = requests.get(
                    url,
                    params={"apiKey": self.odds_api_key, "markets": "h2h,spreads,totals"},
                    timeout=10
                )
                
                status = "UNKNOWN"
                data_available = False
                details = {}
                
                if response.status_code == 200:
                    data = response.json()
                    data_available = len(data) > 0
                    status = "LIVE" if data_available else "NO_ACTIVE_GAMES"
                    details = {
                        "active_games": len(data),
                        "sample_bookmakers": []
                    }
                    if data:
                        sample = data[0]
                        bookmakers = sample.get("bookmakers", [])
                        details["sample_bookmakers"] = [b.get("title") for b in bookmakers[:3]]
                        details["sample_event"] = {
                            "home_team": sample.get("home_team"),
                            "away_team": sample.get("away_team"),
                            "commence_time": sample.get("commence_time")
                        }
                    print(f"✅ {sport_name}: {status} ({len(data)} games)")
                
                elif response.status_code == 401:
                    status = "AUTH_FAILED"
                    details["error"] = "Invalid API key"
                    print(f"❌ {sport_name}: Authentication failed")
                
                elif response.status_code == 429:
                    status = "RATE_LIMITED"
                    details["error"] = "API rate limit exceeded"
                    print(f"⚠️  {sport_name}: Rate limited")
                
                elif response.status_code == 404:
                    status = "DELAYED"
                    details["error"] = "Sport not available or out of season"
                    print(f"ℹ️  {sport_name}: Out of season or not available")
                
                else:
                    status = f"ERROR_{response.status_code}"
                    details["error"] = response.text[:200]
                    print(f"❌ {sport_name}: HTTP {response.status_code}")
                
                result["sports_status"][sport_name] = {
                    "status": status,
                    "data_available": data_available,
                    "details": details
                }
                
            except Exception as e:
                result["sports_status"][sport_name] = {
                    "status": "UNREACHABLE",
                    "error": str(e)
                }
                print(f"❌ {sport_name}: Unreachable - {e}")
        
        return result
    
    def generate_full_report(self, league: str = "nba", game_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate complete diagnostic report with all 5 items
        """
        print("\n" + "🔍 "*40)
        print("ROOT CAUSE DIAGNOSTIC REPORTER")
        print("Gathering all 5 diagnostic items...")
        print("🔍 "*40)
        
        report = {
            "report_timestamp": datetime.utcnow().isoformat(),
            "environment": {
                "mongo_uri_configured": bool(self.mongo_uri),
                "odds_api_configured": bool(self.odds_api_key),
                "backend_url": "http://localhost:8000"
            },
            "diagnostics": {
                "1_api_response": self.diagnostic_1_api_response(league, game_id),
                "2_odds_pipeline": self.diagnostic_2_odds_pipeline_status(),
                "3_market_snapshots": self.diagnostic_3_market_snapshots(),
                "4_decision_records": self.diagnostic_4_decision_records(game_id),
                "5_data_providers": self.diagnostic_5_data_providers()
            }
        }
        
        return report
    
    def print_report_summary(self, report: Dict[str, Any]):
        """Print a formatted summary of the diagnostic report"""
        print("\n" + "="*80)
        print("DIAGNOSTIC SUMMARY")
        print("="*80)
        
        d = report["diagnostics"]
        
        print("\n1. API Response:")
        if d["1_api_response"]["error"]:
            print(f"   ❌ {d['1_api_response']['error']}")
        else:
            print(f"   ✅ Retrieved for {d['1_api_response']['league']}/{d['1_api_response']['game_id']}")
        
        print("\n2. Odds Pipeline:")
        print(f"   Pipeline Running: {d['2_odds_pipeline']['pipeline_running']}")
        print(f"   Last Update: {d['2_odds_pipeline']['last_successful_run']}")
        
        print("\n3. Market Snapshots:")
        print(f"   Total in 24h: {d['3_market_snapshots']['total_count']}")
        
        print("\n4. Decision Records:")
        print(f"   Total in DB: {d['4_decision_records']['all_records_count']}")
        print(f"   For game: {'EXISTS ✅' if d['4_decision_records']['record_exists'] else 'NOT FOUND ❌'}")
        
        print("\n5. Data Providers:")
        for sport, status in d["5_data_providers"]["sports_status"].items():
            print(f"   {sport}: {status['status']}")
        
        print("\n" + "="*80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Root cause diagnostic reporter")
    parser.add_argument("--league", default="nba", help="League code (nba, mlb, nhl, etc)")
    parser.add_argument("--game-id", help="Specific game ID to diagnose")
    parser.add_argument("--output", default="diagnostic_report.json", help="JSON output file")
    args = parser.parse_args()
    
    reporter = DiagnosticReporter()
    report = reporter.generate_full_report(args.league, args.game_id)
    reporter.print_report_summary(report)
    
    # Save full report to JSON
    with open(args.output, 'w') as f:
        # Handle datetime serialization
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n✅ Full report saved to {args.output}")
