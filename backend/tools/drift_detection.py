"""
🔬 DRIFT DETECTION SYSTEM
Automated detection of logic drift and threshold creep

Monitors for subtle degradation in system discipline over time.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import statistics

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.mongo import db
from pymongo.database import Database


class DriftDetector:
    """Detect logic drift and configuration creep"""
    
    # Baseline expected values (set after initial calibration)
    BASELINES = {
        "NBA": {
            "edge_rate": 2.5,  # % of games becoming EDGE
            "avg_probability": 58.0,  # %
            "no_play_rate": 70.0,  # %
            "override_rate": 15.0  # % of EDGEs with overrides
        },
        "NFL": {
            "edge_rate": 1.5,
            "avg_probability": 56.5,
            "no_play_rate": 75.0,
            "override_rate": 20.0
        },
        "NCAAF": {
            "edge_rate": 2.0,
            "avg_probability": 57.0,
            "no_play_rate": 65.0,
            "override_rate": 18.0
        },
        "NCAAB": {
            "edge_rate": 3.5,
            "avg_probability": 55.5,
            "no_play_rate": 55.0,
            "override_rate": 12.0
        },
        "MLB": {
            "edge_rate": 1.5,
            "avg_probability": 55.0,
            "no_play_rate": 75.0,
            "override_rate": 25.0
        },
        "NHL": {
            "edge_rate": 1.5,
            "avg_probability": 54.0,
            "no_play_rate": 75.0,
            "override_rate": 20.0
        }
    }
    
    # Drift thresholds (% change from baseline that triggers warning)
    DRIFT_THRESHOLDS = {
        "edge_rate": 30.0,  # 30% increase in EDGE rate
        "avg_probability": 3.0,  # 3 percentage point increase
        "no_play_rate": -20.0,  # 20% decrease in NO_PLAY rate
        "override_rate": -30.0  # 30% decrease in override rate
    }
    
    def __init__(self, database: Database):
        self.db = database
        self.drift_alerts: List[Dict[str, Any]] = []
    
    async def detect_drift(self, weeks_to_analyze: int = 4) -> Dict[str, Any]:
        """
        Detect drift by comparing recent performance to baselines
        
        Args:
            weeks_to_analyze: Number of weeks to analyze for trends
        
        Returns:
            Drift detection report
        """
        print("\n🔬 DRIFT DETECTION ANALYSIS")
        print(f"Analyzing last {weeks_to_analyze} weeks")
        print("="*80)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=weeks_to_analyze)
        
        # Analyze each sport
        for sport, baseline in self.BASELINES.items():
            print(f"\n🏀 {sport}")
            print("-" * 40)
            
            # Collect current metrics
            current_metrics = await self._collect_current_metrics(sport, start_date, end_date)
            
            # Compare to baseline
            self._compare_to_baseline(sport, current_metrics, baseline)
        
        # Detect trending drift (week-over-week changes)
        await self._detect_trending_drift(weeks_to_analyze)
        
        # Print drift alerts
        self._print_drift_alerts()
        
        # Generate report
        report = self._generate_drift_report()
        await self._save_drift_report(report)
        
        return report
    
    async def _collect_current_metrics(self, sport: str, start: datetime, end: datetime) -> Dict[str, float]:
        """Collect current metrics for drift comparison"""
        try:
            waves = list(self.db["autonomous_edge_waves"].find({
                "sport": sport,
                "created_at": {"$gte": start, "$lte": end}
            }).limit(10000))
            
            if not waves:
                return {}
            
            total = len(waves)
            edge_count = sum(1 for w in waves if w.get("state") in ["EDGE_CONFIRMED", "PUBLISHED"])
            no_play_count = sum(1 for w in waves if w.get("state") in ["EDGE_REJECTED", "BLOCKED"])
            override_count = sum(1 for w in waves if w.get("override_applied", False))
            
            probabilities = [w.get("compressed_probability", 0) for w in waves if w.get("compressed_probability")]
            
            metrics = {
                "edge_rate": (edge_count / total * 100) if total > 0 else 0,
                "avg_probability": (statistics.mean(probabilities) * 100) if probabilities else 0,
                "no_play_rate": (no_play_count / total * 100) if total > 0 else 0,
                "override_rate": (override_count / edge_count * 100) if edge_count > 0 else 0
            }
            
            return metrics
        
        except Exception as e:
            print(f"   ⚠️  Error collecting metrics: {e}")
            return {}
    
    def _compare_to_baseline(self, sport: str, current: Dict[str, float], baseline: Dict[str, float]):
        """Compare current metrics to baseline and detect drift"""
        if not current:
            print("   ⚠️  No data available")
            return
        
        print(f"   Baseline vs Current:")
        
        for metric, baseline_value in baseline.items():
            current_value = current.get(metric, 0)
            
            # Calculate change
            if metric in ["avg_probability"]:
                # Absolute change for probability
                change = current_value - baseline_value
            else:
                # Percentage change for rates
                change = ((current_value - baseline_value) / baseline_value * 100) if baseline_value > 0 else 0
            
            # Check if exceeds drift threshold
            threshold = self.DRIFT_THRESHOLDS.get(metric, 999)
            
            if metric in ["avg_probability"]:
                # For probability, check absolute change
                is_drift = abs(change) >= threshold
                change_str = f"{change:+.1f}pp"
            else:
                # For rates, check percentage change
                is_drift = (change >= threshold) or (threshold < 0 and change <= threshold)
                change_str = f"{change:+.1f}%"
            
            status = "🚨 DRIFT" if is_drift else "✅"
            
            print(f"   {status} {metric}: {baseline_value:.1f} → {current_value:.1f} ({change_str})")
            
            if is_drift:
                self.drift_alerts.append({
                    "sport": sport,
                    "metric": metric,
                    "baseline": baseline_value,
                    "current": current_value,
                    "change": change,
                    "severity": "HIGH"
                })
    
    async def _detect_trending_drift(self, weeks: int):
        """Detect trending drift by comparing week-over-week changes"""
        print("\n📈 TRENDING ANALYSIS")
        print("-" * 40)
        
        # Collect metrics for each week
        end_date = datetime.now()
        
        for sport in self.BASELINES.keys():
            weekly_edge_rates = []
            
            for week in range(weeks):
                week_end = end_date - timedelta(weeks=week)
                week_start = week_end - timedelta(weeks=1)
                
                try:
                    waves = list(self.db["autonomous_edge_waves"].find({
                        "sport": sport,
                        "created_at": {"$gte": week_start, "$lte": week_end}
                    }).limit(10000))
                    
                    if waves:
                        total = len(waves)
                        edge_count = sum(1 for w in waves if w.get("state") in ["EDGE_CONFIRMED", "PUBLISHED"])
                        edge_rate = (edge_count / total * 100) if total > 0 else 0
                        weekly_edge_rates.append(edge_rate)
                
                except Exception as e:
                    continue
            
            # Check for consistent upward trend
            if len(weekly_edge_rates) >= 3:
                # Reverse so oldest is first
                weekly_edge_rates.reverse()
                
                # Simple trend detection: each week higher than previous
                is_upward_trend = all(
                    weekly_edge_rates[i] < weekly_edge_rates[i+1]
                    for i in range(len(weekly_edge_rates) - 1)
                )
                
                if is_upward_trend:
                    increase = weekly_edge_rates[-1] - weekly_edge_rates[0]
                    print(f"   🚨 {sport}: Consistent upward trend in EDGE rate (+{increase:.1f}pp over {weeks} weeks)")
                    
                    self.drift_alerts.append({
                        "sport": sport,
                        "metric": "edge_rate_trend",
                        "trend": "UPWARD",
                        "change": increase,
                        "severity": "MEDIUM"
                    })
    
    def _print_drift_alerts(self):
        """Print drift alerts"""
        print("\n" + "="*80)
        print("🔬 DRIFT DETECTION RESULTS")
        print("="*80)
        
        if not self.drift_alerts:
            print("\n✅ NO DRIFT DETECTED - System stable")
            return
        
        # Group by severity
        high = [a for a in self.drift_alerts if a["severity"] == "HIGH"]
        medium = [a for a in self.drift_alerts if a["severity"] == "MEDIUM"]
        
        if high:
            print(f"\n🚨 HIGH SEVERITY DRIFT ({len(high)}):")
            for alert in high:
                print(f"   • {alert['sport']}: {alert['metric']}")
                if "baseline" in alert:
                    print(f"      {alert['baseline']:.1f} → {alert['current']:.1f} ({alert['change']:+.1f})")
        
        if medium:
            print(f"\n⚠️  MEDIUM SEVERITY DRIFT ({len(medium)}):")
            for alert in medium:
                print(f"   • {alert['sport']}: {alert['metric']} ({alert.get('trend', 'N/A')})")
        
        print("\n📋 RECOMMENDED ACTIONS:")
        print("   1. Review configuration changes in version control")
        print("   2. Identify which thresholds may need adjustment")
        print("   3. Do NOT loosen multiple knobs at once")
        print("   4. Document any recalibration decisions")
        print("   5. Never change pipeline logic mid-season")
    
    def _generate_drift_report(self) -> Dict[str, Any]:
        """Generate drift report"""
        high_severity = [a for a in self.drift_alerts if a["severity"] == "HIGH"]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "alerts": self.drift_alerts,
            "summary": {
                "total_alerts": len(self.drift_alerts),
                "high_severity": len(high_severity),
                "drift_detected": len(self.drift_alerts) > 0
            },
            "status": "STABLE" if len(self.drift_alerts) == 0 else "DRIFT_DETECTED"
        }
    
    async def _save_drift_report(self, report: Dict[str, Any]):
        """Save drift report"""
        try:
            self.db["drift_detection_reports"].insert_one(report)
            print(f"\n✅ Drift report saved to database")
        except Exception as e:
            print(f"\n⚠️  Error saving drift report: {e}")


async def main():
    """Run drift detection"""
    import asyncio
    from db.mongo import db
    
    detector = DriftDetector(db)
    
    # Allow specifying weeks via command line
    weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    
    report = await detector.detect_drift(weeks)
    
    print("\n" + "="*80)
    print("DRIFT DETECTION COMPLETE")
    print(f"Status: {report['status']}")
    print("="*80)
    
    if report['summary']['drift_detected']:
        print("\n⚠️  Drift detected - review recommended")
        sys.exit(1)
    else:
        print("\n✅ System stable - no action required")
        sys.exit(0)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
