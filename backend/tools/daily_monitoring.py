"""
📊 DAILY MONITORING AUTOMATION
Post-Launch Daily Quality Control System

Runs automated daily checks and generates human-readable reports.
Should be scheduled via cron for daily execution.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.mongo import db
from pymongo.database import Database


class DailyMonitor:
    """Daily automated monitoring and quality control"""
    
    # Expected ranges (sanity bands)
    EXPECTED_RANGES = {
        "NBA": {
            "edge_per_day": (1, 3),
            "avg_win_pct": (55, 61),
            "min_no_play_pct": 50
        },
        "NFL": {
            "edge_per_day": (0, 2),
            "avg_win_pct": (54, 59),
            "min_no_play_pct": 60
        },
        "NCAAF": {
            "edge_per_day": (1, 3),
            "avg_win_pct": (54, 60),
            "min_no_play_pct": 50
        },
        "NCAAB": {
            "edge_per_day": (2, 5),
            "avg_win_pct": (53, 58),
            "min_no_play_pct": 40
        },
        "MLB": {
            "edge_per_day": (0, 2),
            "avg_win_pct": (53, 57),
            "min_no_play_pct": 60
        },
        "NHL": {
            "edge_per_day": (0, 2),
            "avg_win_pct": (52, 56),
            "min_no_play_pct": 60
        }
    }
    
    def __init__(self, database: Database):
        self.db = database
        self.alerts: List[str] = []
        self.metrics: Dict[str, Any] = {}
    
    async def run_daily_checks(self, target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Run all daily automated checks
        
        Args:
            target_date: Date to check (defaults to yesterday)
        
        Returns:
            Dictionary of metrics and alerts
        """
        if target_date is None:
            target_date = datetime.utcnow() - timedelta(days=1)
        
        print(f"\n📊 DAILY MONITORING REPORT")
        print(f"Date: {target_date.strftime('%Y-%m-%d')}")
        print("="*80)
        
        # Collect metrics per sport
        for sport in self.EXPECTED_RANGES.keys():
            print(f"\n🏀 {sport}")
            print("-" * 40)
            
            metrics = await self._check_sport_metrics(sport, target_date)
            self.metrics[sport] = metrics
            
            # Check against expected ranges
            self._validate_sport_metrics(sport, metrics)
        
        # Print alerts
        self._print_alerts()
        
        # 2-minute human check prompt
        self._prompt_human_check()
        
        # Save report
        report = self._generate_report(target_date)
        await self._save_report(report, target_date)
        
        return report
    
    async def _check_sport_metrics(self, sport: str, date: datetime) -> Dict[str, Any]:
        """Collect metrics for a single sport"""
        # Query edge candidates/publications from database
        start_of_day = datetime(date.year, date.month, date.day, 0, 0, 0)
        end_of_day = datetime(date.year, date.month, date.day, 23, 59, 59)
        
        # Count EDGE, LEAN, NO_PLAY states
        # This assumes you have a collection tracking evaluations
        edge_count = 0
        lean_count = 0
        no_play_count = 0
        total_games = 0
        probabilities = []
        
        # Example query structure - adjust based on your schema
        try:
            # Query autonomous_edge_waves or similar collection
            waves = list(self.db["autonomous_edge_waves"].find({
                "sport": sport,
                "created_at": {"$gte": start_of_day, "$lte": end_of_day}
            }).limit(1000))
            
            for wave in waves:
                total_games += 1
                state = wave.get("state", "")
                
                if state in ["EDGE_CONFIRMED", "PUBLISHED"]:
                    edge_count += 1
                elif state == "LEAN_CONFIRMED":
                    lean_count += 1
                elif state in ["EDGE_REJECTED", "BLOCKED"]:
                    no_play_count += 1
                
                # Collect probability if available
                if "compressed_probability" in wave:
                    probabilities.append(wave["compressed_probability"])
        
        except Exception as e:
            print(f"   ⚠️  Error querying {sport} data: {e}")
        
        # Calculate metrics
        avg_probability = sum(probabilities) / len(probabilities) * 100 if probabilities else 0
        max_probability = max(probabilities) * 100 if probabilities else 0
        no_play_pct = (no_play_count / total_games * 100) if total_games > 0 else 0
        
        metrics = {
            "edge_count": edge_count,
            "lean_count": lean_count,
            "no_play_count": no_play_count,
            "total_games": total_games,
            "avg_probability": avg_probability,
            "max_probability": max_probability,
            "no_play_pct": no_play_pct
        }
        
        # Print metrics
        print(f"   EDGE: {edge_count}")
        print(f"   LEAN: {lean_count}")
        print(f"   NO_PLAY: {no_play_count}")
        print(f"   Total Games: {total_games}")
        print(f"   Avg Win%: {avg_probability:.1f}%")
        print(f"   Max Win%: {max_probability:.1f}%")
        print(f"   NO_PLAY%: {no_play_pct:.1f}%")
        
        return metrics
    
    def _validate_sport_metrics(self, sport: str, metrics: Dict[str, Any]):
        """Validate metrics against expected ranges and create alerts
        
        ⚠️  CRITICAL: These checks are OBSERVATIONAL ONLY.
        They do NOT block edges, downgrade decisions, or cap probabilities.
        High individual probabilities (65-70%) are VALID in rare justified cases.
        
        Alerts trigger when PATTERNS indicate drift, not individual high values.
        """
        expected = self.EXPECTED_RANGES.get(sport, {})
        
        # Check EDGE count
        edge_min, edge_max = expected.get("edge_per_day", (0, 10))
        edge_count = metrics["edge_count"]
        
        if edge_count > edge_max:
            self.alerts.append(
                f"🚨 {sport}: EDGE count ({edge_count}) exceeds expected max ({edge_max}) - possible threshold drift"
            )
        
        # Check average probability (MONITORING ONLY - not a blocker)
        prob_min, prob_max = expected.get("avg_win_pct", (50, 70))
        avg_prob = metrics["avg_probability"]
        
        if avg_prob > prob_max:
            self.alerts.append(
                f"🚨 {sport}: Avg win% ({avg_prob:.1f}%) exceeds typical ({prob_max}%) - check for compression drift (NOTE: individual high values are OK)"
            )
        
        # Check for clustering above expected ranges (not individual games)
        # NOTE: A single game at 65-70% is VALID. Many games clustering high indicates drift.
        max_prob = metrics["max_probability"]
        if max_prob > 70:  # Only alert if VERY high (not 65%)
            self.alerts.append(
                f"⚠️  {sport}: Max probability ({max_prob:.1f}%) very high - verify if justified by matchup (talent mismatch, injury, etc.)"
            )
        
        # Check NO_PLAY percentage
        min_no_play = expected.get("min_no_play_pct", 50)
        no_play_pct = metrics["no_play_pct"]
        
        if no_play_pct < min_no_play and metrics["total_games"] > 0:
            self.alerts.append(
                f"⚠️  {sport}: NO_PLAY% ({no_play_pct:.1f}%) below expected minimum ({min_no_play}%) - system may be too aggressive"
            )
    
    def _print_alerts(self):
        """Print all alerts"""
        print("\n" + "="*80)
        print("🚨 ALERTS")
        print("="*80)
        
        if not self.alerts:
            print("✅ No alerts - all metrics within expected ranges")
        else:
            for alert in self.alerts:
                print(alert)
    
    def _prompt_human_check(self):
        """Prompt for 2-minute human sanity check"""
        print("\n" + "="*80)
        print("👤 2-MINUTE HUMAN CHECK (REQUIRED)")
        print("="*80)
        print("\nReview today's EDGES and answer ONE question:")
        print("  'Do today's EDGES feel disciplined?'")
        print("\nIf NO:")
        print("  → Do NOT override logic")
        print("  → Flag for weekly review")
        print("  → Continue monitoring")
        print("="*80)
    
    def _generate_report(self, date: datetime) -> Dict[str, Any]:
        """Generate complete daily report"""
        return {
            "date": date.isoformat(),
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics,
            "alerts": self.alerts,
            "summary": {
                "total_alerts": len(self.alerts),
                "sports_checked": len(self.metrics),
                "status": "HEALTHY" if len(self.alerts) == 0 else "ATTENTION_NEEDED"
            }
        }
    
    async def _save_report(self, report: Dict[str, Any], date: datetime):
        """Save report to database and file"""
        # Save to database
        try:
            self.db["daily_monitoring_reports"].insert_one(report)
            print(f"\n✅ Report saved to database")
        except Exception as e:
            print(f"\n⚠️  Error saving report to database: {e}")
        
        # Save to file for backup
        reports_dir = os.path.join(os.path.dirname(__file__), "..", "logs", "daily_reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        report_file = os.path.join(
            reports_dir,
            f"daily_report_{date.strftime('%Y%m%d')}.json"
        )
        
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✅ Report saved to {report_file}")
        except Exception as e:
            print(f"⚠️  Error saving report to file: {e}")


async def main():
    """Run daily monitoring"""
    import asyncio
    from dateutil import parser
    
    monitor = DailyMonitor(db)
    
    # Allow specifying date via command line
    if len(sys.argv) > 1:
        target_date = parser.parse(sys.argv[1])
    else:
        target_date = None
    
    report = await monitor.run_daily_checks(target_date)
    
    print("\n" + "="*80)
    print(f"DAILY MONITORING COMPLETE")
    print(f"Status: {report['summary']['status']}")
    print("="*80)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
