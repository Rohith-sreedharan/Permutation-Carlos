"""
SANITY CHECK MONITORING SERVICE — POST-LAUNCH SOP
==================================================
Automated monitoring, alerting, and health tracking for edge outputs.

This is NOT a decision gate - it's a MONITORING & ALERTING CHECK ONLY.

What it does:
- Tracks EDGE/LEAN/NO_PLAY distribution per sport
- Monitors probability clustering
- Detects calibration drift
- Generates health reports
- Triggers alerts on anomalies

What it does NOT do:
- Block valid edges
- Cap probabilities
- Override classification logic
- Make decisions

Expected behavior when healthy:
- Most games → NO_PLAY
- Several LEANS on full slates
- 1-3 EDGES max per sport per day
- Win probabilities in expected ranges
- No clustering above expected maximums
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

from core.sport_sanity_config import (
    SportSanityConfig,
    SPORT_SANITY_CONFIGS,
    get_sport_sanity_config,
    EdgeState,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ALERT TYPES
# ============================================================================

class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertType(str, Enum):
    """Alert types for monitoring"""
    EDGE_COUNT_HIGH = "EDGE_COUNT_HIGH"
    EDGE_COUNT_LOW = "EDGE_COUNT_LOW"
    PROB_CLUSTERING_HIGH = "PROB_CLUSTERING_HIGH"
    NO_PLAY_RATE_LOW = "NO_PLAY_RATE_LOW"
    COMPRESSION_DRIFT = "COMPRESSION_DRIFT"
    OVERRIDE_RATE_HIGH = "OVERRIDE_RATE_HIGH"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
    CALIBRATION_DRIFT = "CALIBRATION_DRIFT"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class DailyMetrics:
    """Daily metrics for a sport"""
    sport: str
    date: str
    
    # Counts
    total_games: int = 0
    edge_count: int = 0
    lean_count: int = 0
    no_play_count: int = 0
    
    # Probabilities
    probabilities: List[float] = field(default_factory=list)
    avg_probability: float = 0.5
    max_probability: float = 0.5
    probs_above_60: int = 0
    probs_above_65: int = 0
    
    # Reason code distribution
    reason_codes: Dict[str, int] = field(default_factory=dict)
    
    # Override tracking
    override_count: int = 0
    volatility_downgrade_count: int = 0
    
    def calculate_metrics(self):
        """Calculate derived metrics"""
        if self.probabilities:
            self.avg_probability = sum(self.probabilities) / len(self.probabilities)
            self.max_probability = max(self.probabilities)
            self.probs_above_60 = sum(1 for p in self.probabilities if p > 0.60)
            self.probs_above_65 = sum(1 for p in self.probabilities if p > 0.65)
    
    @property
    def no_play_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.no_play_count / self.total_games
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sport": self.sport,
            "date": self.date,
            "total_games": self.total_games,
            "edge_count": self.edge_count,
            "lean_count": self.lean_count,
            "no_play_count": self.no_play_count,
            "no_play_rate": self.no_play_rate,
            "avg_probability": self.avg_probability,
            "max_probability": self.max_probability,
            "probs_above_60": self.probs_above_60,
            "probs_above_65": self.probs_above_65,
            "override_count": self.override_count,
            "volatility_downgrade_count": self.volatility_downgrade_count,
            "reason_codes": self.reason_codes,
        }


@dataclass
class SanityAlert:
    """Sanity check alert"""
    alert_id: str
    sport: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    metric_value: float
    expected_range: Tuple[float, float]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "sport": self.sport,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "metric_value": self.metric_value,
            "expected_range": self.expected_range,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class HealthReport:
    """System health report"""
    report_id: str
    generated_at: datetime
    
    # Overall health
    overall_health: str  # "HEALTHY", "WARNING", "CRITICAL"
    
    # Per-sport metrics
    sport_metrics: Dict[str, DailyMetrics] = field(default_factory=dict)
    
    # Alerts
    alerts: List[SanityAlert] = field(default_factory=list)
    
    # Summary
    total_edges: int = 0
    total_leans: int = 0
    total_no_plays: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "overall_health": self.overall_health,
            "sport_metrics": {k: v.to_dict() for k, v in self.sport_metrics.items()},
            "alerts": [a.to_dict() for a in self.alerts],
            "total_edges": self.total_edges,
            "total_leans": self.total_leans,
            "total_no_plays": self.total_no_plays,
        }


# ============================================================================
# SANITY CHECK SERVICE
# ============================================================================

class SanityCheckService:
    """
    Post-launch monitoring service for edge outputs
    
    Does NOT make decisions - only monitors and alerts
    """
    
    def __init__(self, db=None):
        self.db = db
        self._daily_metrics: Dict[str, Dict[str, DailyMetrics]] = defaultdict(dict)
        self._alerts: List[SanityAlert] = []
    
    # ========================================================================
    # METRICS COLLECTION
    # ========================================================================
    
    def record_evaluation(
        self,
        sport: str,
        date: str,
        state: EdgeState,
        compressed_prob: float,
        reason_codes: List[str],
        was_override: bool = False,
        was_volatility_downgrade: bool = False
    ):
        """Record an evaluation for monitoring"""
        if sport not in self._daily_metrics:
            self._daily_metrics[sport] = {}
        
        if date not in self._daily_metrics[sport]:
            self._daily_metrics[sport][date] = DailyMetrics(sport=sport, date=date)
        
        metrics = self._daily_metrics[sport][date]
        metrics.total_games += 1
        metrics.probabilities.append(compressed_prob)
        
        if state == EdgeState.EDGE:
            metrics.edge_count += 1
        elif state == EdgeState.LEAN:
            metrics.lean_count += 1
        else:
            metrics.no_play_count += 1
        
        if was_override:
            metrics.override_count += 1
        if was_volatility_downgrade:
            metrics.volatility_downgrade_count += 1
        
        for code in reason_codes:
            metrics.reason_codes[code] = metrics.reason_codes.get(code, 0) + 1
        
        metrics.calculate_metrics()
    
    # ========================================================================
    # SANITY CHECKS
    # ========================================================================
    
    def run_sanity_checks(self, sport: str, date: str) -> List[SanityAlert]:
        """Run all sanity checks for a sport on a given date"""
        alerts = []
        
        config = get_sport_sanity_config(sport)
        if not config:
            return alerts
        
        metrics = self._daily_metrics.get(sport, {}).get(date)
        if not metrics or metrics.total_games == 0:
            return alerts
        
        # Check 1: EDGE count
        alerts.extend(self._check_edge_count(config, metrics))
        
        # Check 2: Probability clustering
        alerts.extend(self._check_probability_clustering(config, metrics))
        
        # Check 3: NO_PLAY rate
        alerts.extend(self._check_no_play_rate(config, metrics))
        
        # Check 4: Override rate
        alerts.extend(self._check_override_rate(config, metrics))
        
        self._alerts.extend(alerts)
        return alerts
    
    def _check_edge_count(
        self,
        config: SportSanityConfig,
        metrics: DailyMetrics
    ) -> List[SanityAlert]:
        """Check if EDGE count is within expected range"""
        alerts = []
        expected_min, expected_max = config.expected_edge_count_per_day
        
        if metrics.edge_count > expected_max:
            alert = SanityAlert(
                alert_id=f"{metrics.sport}_{metrics.date}_edge_high",
                sport=metrics.sport,
                alert_type=AlertType.EDGE_COUNT_HIGH,
                severity=AlertSeverity.WARNING,
                message=f"EDGE count ({metrics.edge_count}) exceeds expected max ({expected_max}). "
                        f"Thresholds may be too loose.",
                metric_value=metrics.edge_count,
                expected_range=(expected_min, expected_max),
            )
            alerts.append(alert)
            logger.warning(f"SANITY CHECK: {alert.message}")
        
        return alerts
    
    def _check_probability_clustering(
        self,
        config: SportSanityConfig,
        metrics: DailyMetrics
    ) -> List[SanityAlert]:
        """Check for suspicious probability clustering"""
        alerts = []
        expected_min, expected_max = config.expected_prob_range
        
        # Check if many probabilities are above expected max
        above_60_rate = metrics.probs_above_60 / max(1, metrics.total_games)
        
        if above_60_rate > 0.30:  # More than 30% above 60%
            alert = SanityAlert(
                alert_id=f"{metrics.sport}_{metrics.date}_prob_cluster",
                sport=metrics.sport,
                alert_type=AlertType.PROB_CLUSTERING_HIGH,
                severity=AlertSeverity.WARNING,
                message=f"{metrics.probs_above_60} games ({above_60_rate:.1%}) have >60% probability. "
                        f"Expected range: {expected_min:.0%}-{expected_max:.0%}. "
                        f"Compression may be broken.",
                metric_value=above_60_rate,
                expected_range=(0.0, 0.30),
            )
            alerts.append(alert)
            logger.warning(f"SANITY CHECK: {alert.message}")
        
        # NHL/MLB specific - tighter clustering expected
        if config.sport_key in ("icehockey_nhl", "baseball_mlb"):
            if metrics.max_probability > 0.58:
                alert = SanityAlert(
                    alert_id=f"{metrics.sport}_{metrics.date}_prob_max",
                    sport=metrics.sport,
                    alert_type=AlertType.PROB_CLUSTERING_HIGH,
                    severity=AlertSeverity.WARNING,
                    message=f"Max probability ({metrics.max_probability:.1%}) exceeds {config.sport_name} "
                            f"expected ceiling (58%). Market efficiency suggests tighter range.",
                    metric_value=metrics.max_probability,
                    expected_range=(0.52, 0.58),
                )
                alerts.append(alert)
                logger.warning(f"SANITY CHECK: {alert.message}")
        
        return alerts
    
    def _check_no_play_rate(
        self,
        config: SportSanityConfig,
        metrics: DailyMetrics
    ) -> List[SanityAlert]:
        """Check if NO_PLAY rate is healthy"""
        alerts = []
        
        if metrics.no_play_rate < config.expected_no_play_rate:
            alert = SanityAlert(
                alert_id=f"{metrics.sport}_{metrics.date}_no_play_low",
                sport=metrics.sport,
                alert_type=AlertType.NO_PLAY_RATE_LOW,
                severity=AlertSeverity.WARNING,
                message=f"NO_PLAY rate ({metrics.no_play_rate:.1%}) is below expected "
                        f"({config.expected_no_play_rate:.1%}). Everything looking playable = thresholds too loose.",
                metric_value=metrics.no_play_rate,
                expected_range=(config.expected_no_play_rate, 1.0),
            )
            alerts.append(alert)
            logger.warning(f"SANITY CHECK: {alert.message}")
        
        return alerts
    
    def _check_override_rate(
        self,
        config: SportSanityConfig,
        metrics: DailyMetrics
    ) -> List[SanityAlert]:
        """Check if override rate is unusually high"""
        alerts = []
        
        override_rate = metrics.override_count / max(1, metrics.total_games)
        
        if override_rate > 0.40:  # More than 40% overridden
            alert = SanityAlert(
                alert_id=f"{metrics.sport}_{metrics.date}_override_high",
                sport=metrics.sport,
                alert_type=AlertType.OVERRIDE_RATE_HIGH,
                severity=AlertSeverity.INFO,
                message=f"Override rate ({override_rate:.1%}) is high. "
                        f"This may indicate data quality issues or unusual slate.",
                metric_value=override_rate,
                expected_range=(0.0, 0.40),
            )
            alerts.append(alert)
            logger.info(f"SANITY CHECK: {alert.message}")
        
        return alerts
    
    # ========================================================================
    # HEALTH REPORTS
    # ========================================================================
    
    def generate_daily_health_report(self, date: str) -> HealthReport:
        """Generate a health report for all sports on a date"""
        import uuid
        
        report = HealthReport(
            report_id=str(uuid.uuid4()),
            generated_at=datetime.now(timezone.utc),
            overall_health="HEALTHY",
        )
        
        all_alerts = []
        
        for sport_key in SPORT_SANITY_CONFIGS.keys():
            metrics = self._daily_metrics.get(sport_key, {}).get(date)
            if metrics:
                report.sport_metrics[sport_key] = metrics
                report.total_edges += metrics.edge_count
                report.total_leans += metrics.lean_count
                report.total_no_plays += metrics.no_play_count
                
                # Run sanity checks
                alerts = self.run_sanity_checks(sport_key, date)
                all_alerts.extend(alerts)
        
        report.alerts = all_alerts
        
        # Determine overall health
        critical_count = sum(1 for a in all_alerts if a.severity == AlertSeverity.CRITICAL)
        warning_count = sum(1 for a in all_alerts if a.severity == AlertSeverity.WARNING)
        
        if critical_count > 0:
            report.overall_health = "CRITICAL"
        elif warning_count >= 3:
            report.overall_health = "WARNING"
        else:
            report.overall_health = "HEALTHY"
        
        return report
    
    def get_metrics_for_sport(
        self,
        sport: str,
        date: Optional[str] = None
    ) -> Optional[DailyMetrics]:
        """Get metrics for a sport on a specific date"""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        return self._daily_metrics.get(sport, {}).get(date)
    
    def get_recent_alerts(
        self,
        sport: Optional[str] = None,
        hours: int = 24
    ) -> List[SanityAlert]:
        """Get recent alerts, optionally filtered by sport"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        alerts = [a for a in self._alerts if a.created_at >= cutoff]
        
        if sport:
            alerts = [a for a in alerts if a.sport == sport]
        
        return alerts


# ============================================================================
# EXPECTED PROBABILITY DISTRIBUTIONS (OBSERVATIONAL ONLY)
# ============================================================================

EXPECTED_PROBABILITY_RANGES = {
    "basketball_nba": {"common": (0.54, 0.59), "rare": (0.60, 0.62)},
    "americanfootball_nfl": {"common": (0.54, 0.57), "rare": (0.58, 0.60)},
    "americanfootball_ncaaf": {"common": (0.55, 0.60), "rare": (0.61, 0.65)},
    "basketball_ncaab": {"common": (0.53, 0.58), "rare": (0.59, 0.62)},
    "baseball_mlb": {"common": (0.53, 0.56), "rare": (0.57, 0.59)},
    "icehockey_nhl": {"common": (0.52, 0.55), "rare": (0.56, 0.58)},
}

"""
🚨 IMPORTANT CLARIFICATION — PROBABILITY SANITY TEST (DO NOT MISINTERPRET)

This is NOT:
- A hard cap on probabilities
- A rule that blocks EDGE classification
- A downgrade mechanism
- A replacement for edge thresholds

This IS:
- A MONITORING & ALERTING CHECK ONLY
- Exists to detect calibration drift, compression failure, logic regressions
- Does not change decisions

HIGH PROBABILITIES ARE ALLOWED in rare, justified cases:
- True talent mismatches (college blowouts)
- Late injury confirmations
- Backup QB situations
- Pitcher vs bullpen mismatches
- Extreme pace/scheme mismatches

These should remain visible, actionable, and eligible for EDGE.

WARNING CONDITION = clustering, not individual values.
"""
