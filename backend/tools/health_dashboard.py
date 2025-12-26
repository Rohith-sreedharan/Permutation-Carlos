"""
📊 SYSTEM HEALTH DASHBOARD
Real-time health monitoring and reporting

Generates a comprehensive health score and dashboard data.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import statistics

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.mongo import db
from pymongo.database import Database


class HealthDashboard:
    """System health dashboard and scoring"""
    
    SPORTS = ["NBA", "NFL", "NCAAF", "NCAAB", "MLB", "NHL"]
    
    def __init__(self, database: Database):
        self.db = database
        self.health_scores: Dict[str, float] = {}
        self.issues: List[str] = []
    
    async def generate_dashboard(self) -> Dict[str, Any]:
        """
        Generate comprehensive health dashboard
        
        Returns:
            Dashboard data with health scores and metrics
        """
        print("\n📊 SYSTEM HEALTH DASHBOARD")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Collect metrics
        dashboard_data = {
            "timestamp": datetime.now().isoformat(),
            "sports": {},
            "overall_health": 0,
            "status": "UNKNOWN"
        }
        
        # Analyze each sport
        total_health = 0
        sports_analyzed = 0
        
        for sport in self.SPORTS:
            print(f"\n🏀 {sport}")
            print("-" * 40)
            
            sport_health = await self._calculate_sport_health(sport)
            
            if sport_health is not None:
                self.health_scores[sport] = sport_health
                dashboard_data["sports"][sport] = sport_health
                total_health += sport_health
                sports_analyzed += 1
                
                print(f"   Health Score: {sport_health:.1f}/100")
        
        # Calculate overall health
        if sports_analyzed > 0:
            overall_health = total_health / sports_analyzed
            dashboard_data["overall_health"] = overall_health
            
            # Determine status
            if overall_health >= 90:
                status = "EXCELLENT"
            elif overall_health >= 75:
                status = "GOOD"
            elif overall_health >= 60:
                status = "FAIR"
            else:
                status = "POOR"
            
            dashboard_data["status"] = status
        
        # Add issue summary
        dashboard_data["issues"] = self.issues
        
        # Print summary
        self._print_dashboard_summary(dashboard_data)
        
        # Save to database
        await self._save_dashboard(dashboard_data)
        
        return dashboard_data
    
    async def _calculate_sport_health(self, sport: str) -> Optional[float]:
        """
        Calculate health score for a sport (0-100)
        
        Health score based on:
        - EDGE/day within expected range (25 points)
        - Avg probability reasonable (25 points)
        - NO_PLAY % adequate (20 points)
        - CLV positive or neutral (15 points)
        - Win rate reasonable (15 points)
        """
        try:
            # Last 7 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            # Collect data
            waves = list(self.db.db["autonomous_edge_waves"].find({
                "sport": sport,
                "created_at": {"$gte": start_date, "$lte": end_date}
            }))
            
            if not waves:
                print(f"   ⚠️  No data available")
                return None
            
            total = len(waves)
            edge_count = sum(1 for w in waves if w.get("state") in ["EDGE_CONFIRMED", "PUBLISHED"])
            no_play_count = sum(1 for w in waves if w.get("state") in ["EDGE_REJECTED", "BLOCKED"])
            
            probabilities = [w.get("compressed_probability", 0) for w in waves if w.get("compressed_probability")]
            avg_probability = (statistics.mean(probabilities) * 100) if probabilities else 0
            
            edge_per_day = edge_count / 7
            no_play_pct = (no_play_count / total * 100) if total > 0 else 0
            
            # Get graded results
            graded = list(self.db.db["post_game_grades"].find({
                "sport": sport,
                "game_time": {"$gte": start_date, "$lte": end_date}
            }))
            
            if graded:
                wins = sum(1 for g in graded if g.get("result") == "WIN")
                win_rate = (wins / len(graded) * 100) if graded else 0
                
                clv_values = [g.get("clv", 0) for g in graded if g.get("clv") is not None]
                avg_clv = statistics.mean(clv_values) if clv_values else 0
            else:
                win_rate = 0
                avg_clv = 0
            
            # Calculate health score
            health_score = 0
            
            # 1. EDGE/day within expected range (25 points)
            expected_edge_ranges = {
                "NBA": (1, 3),
                "NFL": (0, 2),
                "NCAAF": (1, 3),
                "NCAAB": (2, 5),
                "MLB": (0, 2),
                "NHL": (0, 2)
            }
            min_edge, max_edge = expected_edge_ranges.get(sport, (0, 5))
            
            if min_edge <= edge_per_day <= max_edge:
                health_score += 25
            elif edge_per_day < min_edge:
                health_score += 15  # Too conservative but not bad
            else:
                health_score += 5  # Too aggressive - bad
                self.issues.append(f"{sport}: EDGE/day ({edge_per_day:.1f}) exceeds expected range")
            
            # 2. Avg probability reasonable (25 points)
            expected_prob_ranges = {
                "NBA": (55, 61),
                "NFL": (54, 59),
                "NCAAF": (54, 60),
                "NCAAB": (53, 58),
                "MLB": (53, 57),
                "NHL": (52, 56)
            }
            min_prob, max_prob = expected_prob_ranges.get(sport, (50, 65))
            
            if min_prob <= avg_probability <= max_prob:
                health_score += 25
            elif avg_probability > max_prob:
                health_score += 5  # Probabilities too high
                self.issues.append(f"{sport}: Avg probability ({avg_probability:.1f}%) too high")
            else:
                health_score += 15  # Probabilities low but ok
            
            # 3. NO_PLAY % adequate (20 points)
            min_no_play = {"NBA": 50, "NFL": 60, "NCAAF": 50, "NCAAB": 40, "MLB": 60, "NHL": 60}.get(sport, 50)
            
            if no_play_pct >= min_no_play:
                health_score += 20
            else:
                deficit = min_no_play - no_play_pct
                health_score += max(0, 20 - deficit)  # Lose points proportional to deficit
                self.issues.append(f"{sport}: NO_PLAY% ({no_play_pct:.1f}%) below minimum")
            
            # 4. CLV positive or neutral (15 points)
            if graded:
                if avg_clv >= 0:
                    health_score += 15
                elif avg_clv >= -2:
                    health_score += 10  # Slightly negative ok
                else:
                    health_score += 0  # Negative CLV bad
                    self.issues.append(f"{sport}: CLV ({avg_clv:.2f}) negative")
            else:
                health_score += 10  # No data yet, neutral
            
            # 5. Win rate reasonable (15 points)
            if graded:
                if win_rate >= 52:
                    health_score += 15
                elif win_rate >= 48:
                    health_score += 10
                else:
                    health_score += 5
                    self.issues.append(f"{sport}: Win rate ({win_rate:.1f}%) below expected")
            else:
                health_score += 10  # No data yet, neutral
            
            return health_score
        
        except Exception as e:
            print(f"   ⚠️  Error calculating health: {e}")
            return None
    
    def _print_dashboard_summary(self, dashboard: Dict[str, Any]):
        """Print dashboard summary"""
        print("\n" + "="*80)
        print("📊 HEALTH DASHBOARD SUMMARY")
        print("="*80)
        
        overall = dashboard.get("overall_health", 0)
        status = dashboard.get("status", "UNKNOWN")
        
        # Status emoji
        if status == "EXCELLENT":
            emoji = "🟢"
        elif status == "GOOD":
            emoji = "🟡"
        elif status == "FAIR":
            emoji = "🟠"
        else:
            emoji = "🔴"
        
        print(f"\n{emoji} Overall Health: {overall:.1f}/100 - {status}")
        
        print("\nSport Scores:")
        for sport, score in dashboard.get("sports", {}).items():
            bar_length = int(score / 5)
            bar = "█" * bar_length + "░" * (20 - bar_length)
            print(f"   {sport:8s} {bar} {score:.1f}/100")
        
        if self.issues:
            print(f"\n⚠️  Issues Detected ({len(self.issues)}):")
            for issue in self.issues[:5]:  # Show top 5
                print(f"   • {issue}")
        else:
            print("\n✅ No issues detected")
    
    async def _save_dashboard(self, dashboard: Dict[str, Any]):
        """Save dashboard to database"""
        try:
            self.db.db["health_dashboards"].insert_one(dashboard)
            print(f"\n✅ Dashboard saved to database")
        except Exception as e:
            print(f"\n⚠️  Error saving dashboard: {e}")


async def main():
    """Generate health dashboard"""
    import asyncio
    from db.mongo import db
    
    dashboard_gen = HealthDashboard(db)
    dashboard = await dashboard_gen.generate_dashboard()
    
    print("\n" + "="*80)
    print("DASHBOARD GENERATION COMPLETE")
    print("="*80)
    
    # Return exit code based on health
    if dashboard["overall_health"] >= 75:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
