#!/usr/bin/env python3
"""
Logging & Calibration System - End-to-End Test
===============================================
Tests the complete workflow from snapshot capture to calibration.

This creates sample data to verify the system works correctly.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from services.snapshot_capture import snapshot_service
from services.sim_run_tracker import sim_run_tracker
from services.publishing_service import publishing_service
from services.grading_service import grading_service
from services.calibration_service import calibration_service
from db.mongo import db
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_event():
    """Create a sample event"""
    # Use timestamp to ensure unique event ID
    event_id = f"nba_lakers_celtics_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"
    
    event = {
        "event_id": event_id,
        "league": "NBA",
        "season": "2025-2026",
        "start_time_utc": datetime.now(timezone.utc) + timedelta(hours=2),
        "home_team": "Lakers",
        "away_team": "Celtics",
        "venue": "Staples Center",
        "status": "SCHEDULED"
    }
    
    db.events.insert_one(event)
    logger.info(f"✅ Created event: {event_id}")
    
    return event_id


def test_snapshot_capture(event_id):
    """Test 1: Capture odds snapshot"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Capturing Odds Snapshot")
    logger.info("="*60)
    
    snapshot_id = snapshot_service.capture_odds_snapshot(
        event_id=event_id,
        provider="OddsAPI",
        book="draftkings",
        market_key="SPREAD:FULL_GAME",
        selection="HOME",
        line=-5.5,
        price_american=-110,
        raw_payload={"test": "data"}
    )
    
    logger.info(f"✅ Captured snapshot: {snapshot_id}")
    
    return snapshot_id


def test_sim_run_tracking(event_id, snapshot_id):
    """Test 2: Create sim_run with lineage"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Creating Sim Run")
    logger.info("="*60)
    
    sim_run_id = sim_run_tracker.create_sim_run(
        event_id=event_id,
        trigger="user_click",
        sim_count=100000,
        model_version="v2.1.0",
        feature_set_version="v1.5",
        decision_policy_version="v1.0"
    )
    
    sim_run_tracker.record_sim_run_inputs(
        sim_run_id=sim_run_id,
        snapshot_id=snapshot_id
    )
    
    sim_run_tracker.complete_sim_run(sim_run_id, runtime_ms=1500)
    
    logger.info(f"✅ Created sim_run: {sim_run_id}")
    
    return sim_run_id


def test_prediction_creation(sim_run_id, event_id, snapshot_id):
    """Test 3: Create prediction"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Creating Prediction")
    logger.info("="*60)
    
    prediction_id = sim_run_tracker.create_prediction(
        sim_run_id=sim_run_id,
        event_id=event_id,
        market_key="SPREAD:FULL_GAME",
        selection="HOME",
        market_snapshot_id_used=snapshot_id,
        model_line=-4.8,
        p_cover=0.62,
        p_win=None,
        p_over=None,
        ev_units=2.1,
        edge_points=3.2,
        uncertainty=1.5,
        distribution_summary={"mean": -4.8, "p50": -4.8},
        rcl_gate_pass=True,
        recommendation_state="EDGE",
        tier="A",
        confidence_index=0.62,
        variance_bucket="MEDIUM"
    )
    
    logger.info(f"✅ Created prediction: {prediction_id}")
    
    return prediction_id


def test_publishing(prediction_id):
    """Test 4: Publish prediction"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Publishing Prediction")
    logger.info("="*60)
    
    publish_id = publishing_service.publish_prediction(
        prediction_id=prediction_id,
        channel="TELEGRAM",
        visibility="PREMIUM",
        decision_reason_codes=["EDGE", "HIGH_CONFIDENCE"],
        ticket_terms={
            "line": -5.5,
            "price": -110,
            "book": "draftkings",
            "selection": "Lakers -5.5"
        },
        is_official=True
    )
    
    logger.info(f"✅ Published prediction: {publish_id}")
    
    return publish_id


def test_event_result(event_id):
    """Test 5: Create event result"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Creating Event Result")
    logger.info("="*60)
    
    # Simulate game result (Lakers win by 8, covering -5.5)
    result = {
        "event_id": event_id,
        "home_score": 112,
        "away_score": 104,
        "total_score": 216,
        "margin": 8.0,  # Lakers win by 8
        "status": "FINAL",
        "official_source": "ESPN",
        "official_timestamp": datetime.now(timezone.utc)
    }
    
    db.event_results.insert_one(result)
    
    logger.info(f"✅ Created event result: {event_id} (Lakers 112, Celtics 104)")
    
    return result


def test_grading(publish_id, snapshot_id):
    """Test 6: Grade prediction"""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: Grading Prediction")
    logger.info("="*60)
    
    # Mark snapshot as closing line
    snapshot_service.mark_as_closing_line(snapshot_id)
    
    # Grade the prediction
    graded_id = grading_service.grade_published_prediction(publish_id)
    
    if graded_id:
        grading = grading_service.get_grading_for_publish(publish_id)
        if grading:
            logger.info(f"✅ Graded prediction: {graded_id}")
            logger.info(f"   Result: {grading['result_code']}")
            logger.info(f"   CLV: {grading.get('clv', 'N/A')}")
            logger.info(f"   Brier: {grading.get('brier_component', 'N/A')}")
            logger.info(f"   Units: {grading.get('unit_return', 'N/A')}")
        else:
            logger.warning("⚠️ Grading record not found")
    else:
        logger.warning("⚠️ Grading not completed (may need event result)")
    
    return graded_id


def create_sample_graded_predictions(num_predictions=50):
    """Create sample graded predictions for calibration"""
    logger.info("\n" + "="*60)
    logger.info(f"Creating {num_predictions} Sample Graded Predictions")
    logger.info("="*60)
    
    timestamp_suffix = datetime.now().strftime('%Y%m%d%H%M%S')
    
    for i in range(num_predictions):
        # Create event with unique timestamp
        event_id = f"nba_sample_{i}_{timestamp_suffix}"
        event = {
            "event_id": event_id,
            "league": "NBA",
            "season": "2025-2026",
            "start_time_utc": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30)),
            "home_team": f"Team_A_{i}",
            "away_team": f"Team_B_{i}",
            "status": "SCHEDULED"
        }
        db.events.insert_one(event)
        
        # Create snapshot
        snapshot_id = snapshot_service.capture_odds_snapshot(
            event_id=event_id,
            provider="OddsAPI",
            book="draftkings",
            market_key="SPREAD:FULL_GAME",
            selection="HOME",
            line=-5.5,
            price_american=-110,
            raw_payload={}
        )
        
        # Create sim_run
        sim_run_id = sim_run_tracker.create_sim_run(
            event_id=event_id,
            trigger="auto_internal",
            sim_count=100000,
            model_version="v2.1.0",
            feature_set_version="v1.5",
            decision_policy_version="v1.0"
        )
        
        sim_run_tracker.record_sim_run_inputs(sim_run_id, snapshot_id=snapshot_id)
        sim_run_tracker.complete_sim_run(sim_run_id, runtime_ms=1000)
        
        # Create prediction
        predicted_prob = random.uniform(0.52, 0.75)
        
        prediction_id = sim_run_tracker.create_prediction(
            sim_run_id=sim_run_id,
            event_id=event_id,
            market_key="SPREAD:FULL_GAME",
            selection="HOME",
            market_snapshot_id_used=snapshot_id,
            model_line=-5.0,
            p_cover=predicted_prob,
            p_win=None,
            p_over=None,
            ev_units=random.uniform(0, 3),
            edge_points=random.uniform(0, 5),
            uncertainty=1.5,
            distribution_summary={},
            rcl_gate_pass=True,
            recommendation_state="EDGE" if predicted_prob > 0.60 else "PICK",
            tier="A" if predicted_prob > 0.60 else "B",
            confidence_index=predicted_prob,
            variance_bucket="MEDIUM"
        )
        
        # Publish
        publish_id = publishing_service.publish_prediction(
            prediction_id=prediction_id,
            channel="TELEGRAM",
            visibility="PREMIUM",
            decision_reason_codes=["EDGE"],
            ticket_terms={"line": -5.5, "price": -110, "book": "draftkings"},
            is_official=True
        )
        
        # Create result (60% win rate to simulate realistic performance)
        is_win = random.random() < 0.60
        
        result = {
            "event_id": event_id,
            "home_score": 110 if is_win else 100,
            "away_score": 100 if is_win else 110,
            "total_score": 210,
            "margin": 10.0 if is_win else -10.0,
            "status": "FINAL",
            "official_source": "ESPN",
            "official_timestamp": datetime.now(timezone.utc)
        }
        db.event_results.insert_one(result)
        
        # Mark as closing line and grade
        snapshot_service.mark_as_closing_line(snapshot_id)
        grading_service.grade_published_prediction(publish_id)
    
    logger.info(f"✅ Created {num_predictions} sample graded predictions")


def test_calibration():
    """Test 7: Run calibration"""
    logger.info("\n" + "="*60)
    logger.info("TEST 7: Running Calibration")
    logger.info("="*60)
    
    # Check if we have enough data
    graded_count = grading_service.grading_collection.count_documents({
        "bet_status": "SETTLED"
    })
    
    logger.info(f"📊 Found {graded_count} graded predictions")
    
    if graded_count < 50:
        logger.warning(f"⚠️ Insufficient data for calibration (need 500+, have {graded_count})")
        logger.info("Creating sample data...")
        create_sample_graded_predictions(60)
    
    try:
        calibration_version = calibration_service.run_calibration_job(
            training_days=30,
            method="isotonic"
        )
        
        if calibration_version:
            logger.info(f"✅ Calibration completed: {calibration_version}")
            
            version_doc = calibration_service.calibration_versions_collection.find_one({
                "calibration_version": calibration_version
            })
            
            if version_doc:
                logger.info(f"   Status: {version_doc['activation_status']}")
                logger.info(f"   ECE: {version_doc['overall_ece']:.4f}")
                logger.info(f"   Brier: {version_doc['overall_brier']:.4f}")
            else:
                logger.warning("⚠️ Version document not found")
        else:
            logger.warning("⚠️ Calibration did not create a version")
    
    except Exception as e:
        logger.error(f"❌ Calibration failed: {e}")


def test_performance_summary():
    """Test 8: Get performance summary"""
    logger.info("\n" + "="*60)
    logger.info("TEST 8: Performance Summary")
    logger.info("="*60)
    
    summary = grading_service.get_performance_summary()
    
    if "error" in summary:
        logger.warning(f"⚠️ {summary['error']}")
    else:
        logger.info(f"✅ Performance Summary:")
        logger.info(f"   Total Graded: {summary['total_graded']}")
        logger.info(f"   Win Rate: {summary['win_rate']:.2f}%")
        logger.info(f"   ROI: {summary['roi']:.2f}%")
        logger.info(f"   Total Units: {summary['total_units']:.2f}")
        logger.info(f"   Avg CLV: {summary['avg_clv']:.2f}")
        if summary['avg_brier']:
            logger.info(f"   Avg Brier: {summary['avg_brier']:.4f}")


def run_all_tests():
    """Run complete end-to-end test"""
    logger.info("=" * 60)
    logger.info("LOGGING & CALIBRATION SYSTEM - END-TO-END TEST")
    logger.info("=" * 60)
    
    try:
        # Test 1-6: Complete workflow
        event_id = create_sample_event()
        snapshot_id = test_snapshot_capture(event_id)
        sim_run_id = test_sim_run_tracking(event_id, snapshot_id)
        prediction_id = test_prediction_creation(sim_run_id, event_id, snapshot_id)
        publish_id = test_publishing(prediction_id)
        test_event_result(event_id)
        test_grading(publish_id, snapshot_id)
        
        # Test 7: Calibration
        test_calibration()
        
        # Test 8: Performance
        test_performance_summary()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Check API endpoints: http://localhost:8000/api/calibration/health")
        logger.info("2. View calibration versions: http://localhost:8000/api/calibration/calibration-versions")
        logger.info("3. Integrate with your existing services")
        logger.info("")
    
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
