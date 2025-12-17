#!/usr/bin/env python3
"""
Weekly Trust Loop Report Generator
===================================

Generates comprehensive weekly trust metrics report including:
- Overall performance
- Confidence calibration analysis
- Regime effectiveness evaluation
- Safety engine suppression accuracy

Usage:
    python backend/scripts/run_weekly_report.py [days]
    
Examples:
    python backend/scripts/run_weekly_report.py        # Last 7 days
    python backend/scripts/run_weekly_report.py 14     # Last 14 days
    python backend/scripts/run_weekly_report.py 30     # Last 30 days
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.services.trust_metrics import trust_metrics_service
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Generate and display weekly trust loop report"""
    # Parse days from command line
    days = 7
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid days argument: {sys.argv[1]}")
            sys.exit(1)
    
    logger.info(f"Generating trust loop report for last {days} days...")
    
    # Generate report
    report = await trust_metrics_service.generate_weekly_report(days)
    
    # Display executive summary
    print("\n" + "="*80)
    print(report.get("executive_summary", "No summary available"))
    print("="*80)
    
    # Display by-sport breakdown
    print("\n📊 Performance by Sport:")
    print("-" * 80)
    for sport, stats in report.get("by_sport", {}).items():
        print(f"\n{sport.upper()}:")
        print(f"  Predictions: {stats['total_predictions']}")
        print(f"  Win Rate: {stats['win_rate']:.1%}")
        print(f"  Avg Model Error: {stats['avg_model_error']:.1f} points")
    
    # Display environment breakdown
    print("\n🏆 Performance by Environment:")
    print("-" * 80)
    for env, stats in report.get("by_environment", {}).items():
        print(f"\n{env.upper().replace('_', ' ')}:")
        print(f"  Predictions: {stats['total_predictions']}")
        print(f"  Win Rate: {stats['win_rate']:.1%}")
        print(f"  Avg Model Error: {stats['avg_model_error']:.1f} points")
    
    # Display calibration issues
    calibration = report.get("calibration_analysis", {})
    if calibration.get("calibration_issues"):
        print("\n⚠️  Calibration Issues:")
        print("-" * 80)
        for issue in calibration["calibration_issues"]:
            print(f"\n{issue['bucket']}:")
            print(f"  Expected: {issue['expected_win_rate']:.1%}")
            print(f"  Actual: {issue['actual_win_rate']:.1%}")
            print(f"  Diagnosis: {issue['diagnosis']}")
            print(f"  Recommendation: {issue['recommendation']}")
    else:
        print("\n✅ Confidence calibration is accurate!")
    
    # Display regime effectiveness
    regime_analysis = report.get("regime_effectiveness", {}).get("regime_analysis", [])
    if regime_analysis:
        print("\n🔧 Regime Adjustment Effectiveness:")
        print("-" * 80)
        for analysis in regime_analysis:
            print(f"\nRegime: {analysis['regime']}")
            print(f"  Adjustments: {', '.join(analysis['adjustments_applied'])}")
            print(f"  Predictions: {analysis['total_predictions']}")
            print(f"  Win Rate: {analysis['win_rate']:.1%}")
            print(f"  Assessment: {analysis['assessment']}")
            print(f"  Note: {analysis['note']}")
            if analysis.get('recommendation'):
                print(f"  ⚠️  {analysis['recommendation']}")
    
    print("\n" + "="*80)
    print("Report saved to database: trust_metrics_weekly collection")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
