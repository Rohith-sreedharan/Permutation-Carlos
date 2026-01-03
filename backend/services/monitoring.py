"""
Post-Launch Monitoring SOP

System health monitoring, calibration drift detection, and automated alerts.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import asyncio

from ..db.database import Database
from ..core.sport_configs import Sport
from ..services.slack_notifier import SlackNotifier


@dataclass
class HealthCheckResult:
    """Health check result"""
    check_name: str
    status: str  # OK, WARNING, CRITICAL
    message: str
    details: Optional[Dict] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class SystemMonitor:
    """Monitors system health and performance"""
    
    def __init__(self, db: Database, slack_notifier: SlackNotifier):
        self.db = db
        self.slack = slack_notifier
        
        # Thresholds
        self.thresholds = {
            "edge_calibration_error_max": 1.5,  # 1.5% max error
            "win_rate_min": 0.52,  # 52% minimum
            "simulation_latency_max": 5000,  # 5 seconds max
            "api_error_rate_max": 0.05,  # 5% max error rate
            "telegram_delivery_rate_min": 0.98,  # 98% min delivery
        }
    
    
    async def run_full_health_check(self) -> List[HealthCheckResult]:
        """
        Run full system health check
        
        Returns: List of health check results
        """
        results = []
        
        # 1. Calibration drift check
        results.append(await self.check_calibration_drift())
        
        # 2. Win rate check
        results.append(await self.check_win_rate())
        
        # 3. Simulation latency check
        results.append(await self.check_simulation_latency())
        
        # 4. API error rate check
        results.append(await self.check_api_error_rate())
        
        # 5. Telegram delivery check
        results.append(await self.check_telegram_delivery())
        
        # 6. Database connection check
        results.append(await self.check_database())
        
        # 7. Sharp Pass verification queue check
        results.append(await self.check_sharp_pass_queue())
        
        # 8. SimSports API usage check
        results.append(await self.check_simsports_usage())
        
        # Send alerts for CRITICAL/WARNING
        await self.send_alerts(results)
        
        return results
    
    
    async def check_calibration_drift(self) -> HealthCheckResult:
        """
        Check for calibration drift
        
        Alert if predicted edge differs from actual by >1.5%
        """
        try:
            # Get last 7 days of calibration data
            start_date = datetime.now() - timedelta(days=7)
            calibration_data = list(
                self.db.signals.find({
                    "created_at": {"$gte": start_date},
                    "status": "GRADED"
                }).sort("created_at", -1)
            )
            
            critical_sports = []
            warning_sports = []
            
            for cal in calibration_data:
                error = abs(cal['edge_calibration_error'])
                
                if error > self.thresholds["edge_calibration_error_max"]:
                    if error > 2.5:
                        critical_sports.append(f"{cal['sport']} ({error:.2f}%)")
                    else:
                        warning_sports.append(f"{cal['sport']} ({error:.2f}%)")
            
            if critical_sports:
                return HealthCheckResult(
                    check_name="Calibration Drift",
                    status="CRITICAL",
                    message=f"Severe calibration drift detected: {', '.join(critical_sports)}",
                    details={"critical_sports": critical_sports}
                )
            elif warning_sports:
                return HealthCheckResult(
                    check_name="Calibration Drift",
                    status="WARNING",
                    message=f"Calibration drift detected: {', '.join(warning_sports)}",
                    details={"warning_sports": warning_sports}
                )
            else:
                return HealthCheckResult(
                    check_name="Calibration Drift",
                    status="OK",
                    message="All sports within calibration tolerance"
                )
        
        except Exception as e:
            return HealthCheckResult(
                check_name="Calibration Drift",
                status="CRITICAL",
                message=f"Error checking calibration: {str(e)}"
            )
    
    
    async def check_win_rate(self) -> HealthCheckResult:
        """
        Check overall win rate
        
        Alert if win rate drops below 52%
        """
        try:
            # Get last 30 days of graded signals
            signals = await self.db.get_graded_signals(
                start_date=datetime.now() - timedelta(days=30),
                edge_state="EDGE"  # Only check EDGE signals
            )
            
            if not signals:
                return HealthCheckResult(
                    check_name="Win Rate",
                    status="WARNING",
                    message="No graded signals in last 30 days"
                )
            
            wins = sum(1 for s in signals if s['result'] == 'WIN')
            total = len(signals)
            win_rate = wins / total if total > 0 else 0
            
            if win_rate < 0.50:
                return HealthCheckResult(
                    check_name="Win Rate",
                    status="CRITICAL",
                    message=f"Win rate critically low: {win_rate:.1%} ({wins}/{total})",
                    details={"win_rate": win_rate, "wins": wins, "total": total}
                )
            elif win_rate < self.thresholds["win_rate_min"]:
                return HealthCheckResult(
                    check_name="Win Rate",
                    status="WARNING",
                    message=f"Win rate below target: {win_rate:.1%} ({wins}/{total})",
                    details={"win_rate": win_rate, "wins": wins, "total": total}
                )
            else:
                return HealthCheckResult(
                    check_name="Win Rate",
                    status="OK",
                    message=f"Win rate healthy: {win_rate:.1%} ({wins}/{total})"
                )
        
        except Exception as e:
            return HealthCheckResult(
                check_name="Win Rate",
                status="CRITICAL",
                message=f"Error checking win rate: {str(e)}"
            )
    
    
    async def check_simulation_latency(self) -> HealthCheckResult:
        """
        Check simulation execution latency
        
        Alert if average latency >5 seconds
        """
        try:
            # Get last 100 simulations
            simulations = await self.db.get_recent_simulations(limit=100)
            
            if not simulations:
                return HealthCheckResult(
                    check_name="Simulation Latency",
                    status="WARNING",
                    message="No recent simulations"
                )
            
            latencies = [s['execution_duration_ms'] for s in simulations]
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            
            if avg_latency > self.thresholds["simulation_latency_max"]:
                return HealthCheckResult(
                    check_name="Simulation Latency",
                    status="CRITICAL",
                    message=f"Avg simulation latency high: {avg_latency:.0f}ms (max: {max_latency:.0f}ms)",
                    details={"avg_ms": avg_latency, "max_ms": max_latency}
                )
            elif avg_latency > 3000:
                return HealthCheckResult(
                    check_name="Simulation Latency",
                    status="WARNING",
                    message=f"Avg simulation latency elevated: {avg_latency:.0f}ms",
                    details={"avg_ms": avg_latency}
                )
            else:
                return HealthCheckResult(
                    check_name="Simulation Latency",
                    status="OK",
                    message=f"Simulation latency normal: {avg_latency:.0f}ms"
                )
        
        except Exception as e:
            return HealthCheckResult(
                check_name="Simulation Latency",
                status="CRITICAL",
                message=f"Error checking latency: {str(e)}"
            )
    
    
    async def check_api_error_rate(self) -> HealthCheckResult:
        """Check API error rate"""
        try:
            # Get last hour of API requests
            requests = await self.db.get_api_requests(
                minutes=60
            )
            
            if not requests:
                return HealthCheckResult(
                    check_name="API Error Rate",
                    status="OK",
                    message="No recent API requests"
                )
            
            total = len(requests)
            errors = sum(1 for r in requests if r['status_code'] >= 500)
            error_rate = errors / total if total > 0 else 0
            
            if error_rate > self.thresholds["api_error_rate_max"]:
                return HealthCheckResult(
                    check_name="API Error Rate",
                    status="CRITICAL",
                    message=f"API error rate high: {error_rate:.1%} ({errors}/{total})",
                    details={"error_rate": error_rate, "errors": errors, "total": total}
                )
            elif error_rate > 0.02:
                return HealthCheckResult(
                    check_name="API Error Rate",
                    status="WARNING",
                    message=f"API error rate elevated: {error_rate:.1%}",
                    details={"error_rate": error_rate}
                )
            else:
                return HealthCheckResult(
                    check_name="API Error Rate",
                    status="OK",
                    message=f"API error rate normal: {error_rate:.1%}"
                )
        
        except Exception as e:
            return HealthCheckResult(
                check_name="API Error Rate",
                status="CRITICAL",
                message=f"Error checking API: {str(e)}"
            )
    
    
    async def check_telegram_delivery(self) -> HealthCheckResult:
        """Check Telegram delivery success rate"""
        try:
            # Get last 24 hours of Telegram posts
            posts = await self.db.get_telegram_posts(
                hours=24
            )
            
            if not posts:
                return HealthCheckResult(
                    check_name="Telegram Delivery",
                    status="WARNING",
                    message="No Telegram posts in last 24 hours"
                )
            
            total = len(posts)
            successful = sum(1 for p in posts if p['telegram_message_id'] is not None)
            delivery_rate = successful / total if total > 0 else 0
            
            if delivery_rate < self.thresholds["telegram_delivery_rate_min"]:
                return HealthCheckResult(
                    check_name="Telegram Delivery",
                    status="CRITICAL",
                    message=f"Telegram delivery rate low: {delivery_rate:.1%} ({successful}/{total})",
                    details={"delivery_rate": delivery_rate, "successful": successful, "total": total}
                )
            else:
                return HealthCheckResult(
                    check_name="Telegram Delivery",
                    status="OK",
                    message=f"Telegram delivery healthy: {delivery_rate:.1%}"
                )
        
        except Exception as e:
            return HealthCheckResult(
                check_name="Telegram Delivery",
                status="CRITICAL",
                message=f"Error checking Telegram: {str(e)}"
            )
    
    
    async def check_database(self) -> HealthCheckResult:
        """Check database connection"""
        try:
            await self.db.ping()
            return HealthCheckResult(
                check_name="Database",
                status="OK",
                message="Database connection healthy"
            )
        except Exception as e:
            return HealthCheckResult(
                check_name="Database",
                status="CRITICAL",
                message=f"Database connection failed: {str(e)}"
            )
    
    
    async def check_sharp_pass_queue(self) -> HealthCheckResult:
        """Check Sharp Pass verification queue"""
        try:
            pending = await self.db.count_sharp_pass_applications(status="PENDING")
            
            if pending > 20:
                return HealthCheckResult(
                    check_name="Sharp Pass Queue",
                    status="WARNING",
                    message=f"Large Sharp Pass queue: {pending} pending applications",
                    details={"pending": pending}
                )
            else:
                return HealthCheckResult(
                    check_name="Sharp Pass Queue",
                    status="OK",
                    message=f"Sharp Pass queue normal: {pending} pending"
                )
        
        except Exception as e:
            return HealthCheckResult(
                check_name="Sharp Pass Queue",
                status="WARNING",
                message=f"Error checking queue: {str(e)}"
            )
    
    
    async def check_simsports_usage(self) -> HealthCheckResult:
        """Check SimSports API usage"""
        try:
            # Get last 24 hours of SimSports API requests
            requests = await self.db.get_simsports_api_requests(
                minutes=60
            )
            
            total_simulations = sum(r['simulations_consumed'] for r in requests)
            
            return HealthCheckResult(
                check_name="SimSports Usage",
                status="OK",
                message=f"SimSports usage: {total_simulations:,} simulations (24h)",
                details={"simulations": total_simulations, "requests": len(requests)}
            )
        
        except Exception as e:
            return HealthCheckResult(
                check_name="SimSports Usage",
                status="WARNING",
                message=f"Error checking SimSports: {str(e)}"
            )
    
    
    async def send_alerts(self, results: List[HealthCheckResult]):
        """Send alerts for CRITICAL/WARNING results"""
        critical = [r for r in results if r.status == "CRITICAL"]
        warnings = [r for r in results if r.status == "WARNING"]
        
        if critical:
            await self.slack.send_alert(
                severity="CRITICAL",
                title="🚨 CRITICAL SYSTEM ALERTS",
                message="\n".join([f"{r.check_name}: {r.message}" for r in critical]),
                details={r.check_name: r.message for r in critical}
            )
        
        if warnings:
            await self.slack.send_alert(
                severity="WARNING",
                title="⚠️ System Warnings",
                message="\n".join([f"{r.check_name}: {r.message}" for r in warnings]),
                details={r.check_name: r.message for r in warnings}
            )


# Scheduled monitoring job
async def run_monitoring_loop():
    """Run continuous monitoring (call from background task)"""
    db = Database()
    slack = SlackNotifier()
    monitor = SystemMonitor(db, slack)
    
    while True:
        try:
            results = await monitor.run_full_health_check()
            
            # Log results
            print(f"[{datetime.now()}] Health check complete:")
            for result in results:
                print(f"  {result.check_name}: {result.status} - {result.message}")
        
        except Exception as e:
            print(f"Monitoring error: {e}")
        
        # Run every 5 minutes
        await asyncio.sleep(300)
