"""
📈 WEEKLY & MONTHLY PERFORMANCE REVIEW
Long-term performance monitoring and drift detection

Weekly reviews track stability and structural health.
Monthly reviews provide deep audit and recalibration guidance.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
import json
import statistics

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.mongo import db
from pymongo.database import Database


class PerformanceReviewer:
    """Weekly and monthly performance review system"""
    
    SPORTS = ["NBA", "NFL", "NCAAF", "NCAAB", "MLB", "NHL"]
    
    def __init__(self, database: Database):
        self.db = database
        self.metrics: Dict[str, Any] = {}
        self.anomalies: List[str] = []
        self.recommendations: List[str] = []
    
    async def run_weekly_review(self, weeks_back: int = 1) -> Dict[str, Any]:
        """
        Run weekly performance review
        
        Args:
            weeks_back: Number of weeks to review (default: last week)
        
        Returns:
            Weekly review report
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=weeks_back)
        
        print("\n📈 WEEKLY PERFORMANCE REVIEW")
        print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print("="*80)
        
        # Collect metrics per sport
        for sport in self.SPORTS:
            print(f"\n🏀 {sport}")
            print("-" * 40)
            
            metrics = await self._collect_weekly_metrics(sport, start_date, end_date)
            self.metrics[sport] = metrics
            
            # Analyze for anomalies
            self._analyze_weekly_anomalies(sport, metrics)
        
        # Print anomalies and recommendations
        self._print_weekly_findings()
        
        # Generate report
        report = self._generate_weekly_report(start_date, end_date)
        await self._save_weekly_report(report)
        
        return report
    
    async def run_monthly_review(self, month_offset: int = 0) -> Dict[str, Any]:
        """
        Run monthly deep audit
        
        Args:
            month_offset: 0 = current month, 1 = last month, etc.
        
        Returns:
            Monthly review report
        """
        # Calculate month boundaries
        now = datetime.now()
        if month_offset == 0:
            start_date = datetime(now.year, now.month, 1)
            end_date = now
        else:
            # Go back month_offset months
            month = now.month - month_offset
            year = now.year
            while month <= 0:
                month += 12
                year -= 1
            
            start_date = datetime(year, month, 1)
            
            # End date is last day of that month
            next_month = month + 1
            next_year = year
            if next_month > 12:
                next_month = 1
                next_year += 1
            end_date = datetime(next_year, next_month, 1) - timedelta(days=1)
        
        print("\n📊 MONTHLY DEEP AUDIT")
        print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print("="*80)
        
        # Comprehensive monthly analysis
        for sport in self.SPORTS:
            print(f"\n🏀 {sport}")
            print("-" * 40)
            
            metrics = await self._collect_monthly_metrics(sport, start_date, end_date)
            self.metrics[sport] = metrics
            
            # Deep analysis
            await self._deep_monthly_analysis(sport, metrics, start_date, end_date)
        
        # Print findings
        self._print_monthly_findings()
        
        # Generate report
        report = self._generate_monthly_report(start_date, end_date)
        await self._save_monthly_report(report)
        
        return report
    
    async def _collect_weekly_metrics(self, sport: str, start: datetime, end: datetime) -> Dict[str, Any]:
        """Collect weekly metrics for a sport"""
        try:
            # Query waves for the period
            waves = list(self.db.db["autonomous_edge_waves"].find({
                "sport": sport,
                "created_at": {"$gte": start, "$lte": end}
            }))
            
            # Count states
            edge_count = sum(1 for w in waves if w.get("state") in ["EDGE_CONFIRMED", "PUBLISHED"])
            lean_count = sum(1 for w in waves if w.get("state") == "LEAN_CONFIRMED")
            no_play_count = sum(1 for w in waves if w.get("state") in ["EDGE_REJECTED", "BLOCKED"])
            
            # Collect probabilities
            probabilities = [w.get("compressed_probability", 0) for w in waves if w.get("compressed_probability")]
            
            # Query graded results for EDGE plays
            graded_edges = list(self.db.db["post_game_grades"].find({
                "sport": sport,
                "original_state": {"$in": ["EDGE_CONFIRMED", "PUBLISHED"]},
                "game_time": {"$gte": start, "$lte": end}
            }))
            
            # Calculate win rate
            wins = sum(1 for g in graded_edges if g.get("result") == "WIN")
            total_graded = len(graded_edges)
            win_rate = (wins / total_graded * 100) if total_graded > 0 else 0
            
            # Calculate CLV (if tracked)
            clv_values = [g.get("clv", 0) for g in graded_edges if g.get("clv") is not None]
            avg_clv = statistics.mean(clv_values) if clv_values else 0
            
            # Count overrides triggered
            override_count = sum(1 for w in waves if w.get("override_applied", False))
            
            metrics = {
                "edge_count": edge_count,
                "lean_count": lean_count,
                "no_play_count": no_play_count,
                "total_evaluations": len(waves),
                "avg_probability": statistics.mean(probabilities) * 100 if probabilities else 0,
                "max_probability": max(probabilities) * 100 if probabilities else 0,
                "graded_count": total_graded,
                "win_rate": win_rate,
                "avg_clv": avg_clv,
                "override_count": override_count
            }
            
            print(f"   EDGE: {edge_count}")
            print(f"   Win Rate: {win_rate:.1f}% ({wins}/{total_graded})")
            print(f"   Avg CLV: {avg_clv:+.2f}")
            print(f"   Overrides: {override_count}")
            
            return metrics
        
        except Exception as e:
            print(f"   ⚠️  Error collecting metrics: {e}")
            return {}
    
    async def _collect_monthly_metrics(self, sport: str, start: datetime, end: datetime) -> Dict[str, Any]:
        """Collect monthly metrics (same as weekly but for longer period)"""
        return await self._collect_weekly_metrics(sport, start, end)
    
    def _analyze_weekly_anomalies(self, sport: str, metrics: Dict[str, Any]):
        """Detect anomalies in weekly metrics"""
        if not metrics:
            return
        
        # Check for drift indicators
        
        # 1. Gradual increase in EDGE count
        edge_count = metrics.get("edge_count", 0)
        total = metrics.get("total_evaluations", 1)
        edge_rate = (edge_count / total * 100) if total > 0 else 0
        
        if edge_rate > 10:  # More than 10% becoming EDGE
            self.anomalies.append(
                f"{sport}: High EDGE rate ({edge_rate:.1f}%) - possible threshold drift"
            )
        
        # 2. Win probabilities creeping upward
        avg_prob = metrics.get("avg_probability", 0)
        if avg_prob > 62:  # Generic threshold
            self.anomalies.append(
                f"{sport}: Avg probability ({avg_prob:.1f}%) very high - check compression"
            )
        
        # 3. Fewer NO_PLAY states
        no_play_count = metrics.get("no_play_count", 0)
        no_play_rate = (no_play_count / total * 100) if total > 0 else 0
        
        if no_play_rate < 40:
            self.anomalies.append(
                f"{sport}: Low NO_PLAY rate ({no_play_rate:.1f}%) - system may be too aggressive"
            )
        
        # 4. Overrides rarely triggering
        override_count = metrics.get("override_count", 0)
        if edge_count > 5 and override_count == 0:
            self.anomalies.append(
                f"{sport}: No overrides triggered despite {edge_count} EDGES - check override logic"
            )
    
    async def _deep_monthly_analysis(self, sport: str, metrics: Dict[str, Any], start: datetime, end: datetime):
        """Perform deep monthly analysis"""
        if not metrics:
            return
        
        # Review a full slate for the month
        # Pick a representative day
        mid_month = start + (end - start) / 2
        
        print(f"   Reviewing sample slate from {mid_month.strftime('%Y-%m-%d')}...")
        
        # Get one day's worth of evaluations
        sample_start = datetime(mid_month.year, mid_month.month, mid_month.day, 0, 0, 0)
        sample_end = sample_start + timedelta(days=1)
        
        try:
            sample_waves = list(self.db.db["autonomous_edge_waves"].find({
                "sport": sport,
                "created_at": {"$gte": sample_start, "$lte": sample_end}
            }))
            
            print(f"   Sample slate size: {len(sample_waves)} games")
            
            # Analyze distribution
            edge_sample = sum(1 for w in sample_waves if w.get("state") in ["EDGE_CONFIRMED", "PUBLISHED"])
            lean_sample = sum(1 for w in sample_waves if w.get("state") == "LEAN_CONFIRMED")
            
            print(f"   Sample EDGE: {edge_sample}, LEAN: {lean_sample}")
            
            # Check if month would look professional if reviewed publicly
            if edge_sample > 5:
                self.recommendations.append(
                    f"{sport}: Sample day had {edge_sample} EDGES - may appear overly aggressive"
                )
        
        except Exception as e:
            print(f"   ⚠️  Error in deep analysis: {e}")
    
    def _print_weekly_findings(self):
        """Print weekly findings"""
        print("\n" + "="*80)
        print("🔍 WEEKLY FINDINGS")
        print("="*80)
        
        if not self.anomalies and not self.recommendations:
            print("\n✅ No anomalies detected - system stable")
            return
        
        if self.anomalies:
            print(f"\n⚠️  ANOMALIES DETECTED ({len(self.anomalies)}):")
            for anomaly in self.anomalies:
                print(f"   • {anomaly}")
            
            print("\n📋 RESPONSE:")
            print("   • Do NOT react to short-term losses")
            print("   • Flag for further monitoring")
            print("   • Consider config adjustments if persistent")
        
        if self.recommendations:
            print(f"\n💡 RECOMMENDATIONS ({len(self.recommendations)}):")
            for rec in self.recommendations:
                print(f"   • {rec}")
    
    def _print_monthly_findings(self):
        """Print monthly findings"""
        print("\n" + "="*80)
        print("🔍 MONTHLY AUDIT FINDINGS")
        print("="*80)
        
        if not self.anomalies and not self.recommendations:
            print("\n✅ Month looks clean - system operating as intended")
            return
        
        if self.anomalies:
            print(f"\n⚠️  STRUCTURAL ISSUES ({len(self.anomalies)}):")
            for anomaly in self.anomalies:
                print(f"   • {anomaly}")
        
        if self.recommendations:
            print(f"\n💡 RECALIBRATION RECOMMENDATIONS ({len(self.recommendations)}):")
            for rec in self.recommendations:
                print(f"   • {rec}")
            
            print("\n📋 NEXT STEPS:")
            print("   • Review config thresholds")
            print("   • Document any changes in version control")
            print("   • Do NOT change pipeline logic mid-season")
    
    def _generate_weekly_report(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Generate weekly report"""
        return {
            "type": "WEEKLY",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics,
            "anomalies": self.anomalies,
            "recommendations": self.recommendations,
            "status": "STABLE" if len(self.anomalies) == 0 else "ATTENTION_NEEDED"
        }
    
    def _generate_monthly_report(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Generate monthly report"""
        return {
            "type": "MONTHLY",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics,
            "anomalies": self.anomalies,
            "recommendations": self.recommendations,
            "status": "HEALTHY" if len(self.anomalies) == 0 else "RECALIBRATION_NEEDED"
        }
    
    async def _save_weekly_report(self, report: Dict[str, Any]):
        """Save weekly report"""
        try:
            self.db.db["performance_reviews"].insert_one(report)
            print(f"\n✅ Weekly report saved to database")
        except Exception as e:
            print(f"\n⚠️  Error saving weekly report: {e}")
    
    async def _save_monthly_report(self, report: Dict[str, Any]):
        """Save monthly report"""
        try:
            self.db.db["performance_reviews"].insert_one(report)
            print(f"\n✅ Monthly report saved to database")
        except Exception as e:
            print(f"\n⚠️  Error saving monthly report: {e}")


async def main():
    """Run performance review"""
    import asyncio
    from db.mongo import db
    
    reviewer = PerformanceReviewer(db)
    
    # Determine if weekly or monthly based on arguments
    review_type = sys.argv[1] if len(sys.argv) > 1 else "weekly"
    
    if review_type.lower() == "weekly":
        report = await reviewer.run_weekly_review()
    elif review_type.lower() == "monthly":
        report = await reviewer.run_monthly_review()
    else:
        print("Usage: python performance_review.py [weekly|monthly]")
        sys.exit(1)
    
    print("\n" + "="*80)
    print(f"{review_type.upper()} REVIEW COMPLETE")
    print(f"Status: {report['status']}")
    print("="*80)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
