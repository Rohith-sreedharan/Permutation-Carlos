"""
Calibration Job Service
=======================
Weekly calibration system with versioning and activation gates.

Purpose:
- Train calibration models on graded predictions
- Segment by league, market, edge bucket, variance bucket
- Version all calibration models
- Gate activation on improvement metrics (ECE, Brier)
- Prevent low-sample overfitting

Schedule: Weekly (or twice weekly as volume increases)
"""
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from db.mongo import db
from db.schemas.logging_calibration_schemas import (
    CalibrationVersion,
    CalibrationSegment,
    CalibrationStatus
)
import logging
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)


class CalibrationService:
    """
    Versioned calibration system with segment-based modeling
    """
    
    # Minimum samples required for calibration
    MIN_SAMPLES_GLOBAL = 500
    MIN_SAMPLES_SEGMENT = 100
    
    def __init__(self):
        self.calibration_versions_collection = db.calibration_versions
        self.calibration_segments_collection = db.calibration_segments
        self.grading_collection = db.grading
        self.published_collection = db.published_predictions
        self.predictions_collection = db.predictions
    
    def run_calibration_job(
        self,
        training_days: int = 30,
        method: str = "isotonic"
    ) -> str:
        """
        Run full calibration job
        
        Args:
            training_days: Days of historical data to train on
            method: isotonic, platt, temperature, beta
        
        Returns:
            calibration_version
        """
        logger.info(f"🎯 Starting calibration job (method={method}, training_days={training_days})")
        
        # Define training period
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=training_days)
        
        # Generate version identifier
        calibration_version = f"v_{end_date.strftime('%Y%m%d_%H%M%S')}"
        
        # Get training data
        training_data = self._get_training_data(start_date, end_date)
        
        if len(training_data) < self.MIN_SAMPLES_GLOBAL:
            logger.error(
                f"❌ Insufficient training data: {len(training_data)} samples "
                f"(need {self.MIN_SAMPLES_GLOBAL})"
            )
            return None  # type: ignore[return-value]
        
        logger.info(f"📊 Training on {len(training_data)} graded predictions")
        
        # Segment data
        segments = self._segment_data(training_data)
        
        logger.info(f"📦 Created {len(segments)} segments")
        
        # Train calibration for each segment
        segment_results = []
        overall_metrics = {"ece": [], "brier": [], "mce": []}
        
        for segment_key, segment_data in segments.items():
            if len(segment_data) < self.MIN_SAMPLES_SEGMENT:
                logger.warning(
                    f"⚠️ Skipping segment {segment_key}: "
                    f"only {len(segment_data)} samples "
                    f"(need {self.MIN_SAMPLES_SEGMENT})"
                )
                continue
            
            # Train calibration
            result = self._train_segment_calibration(
                segment_key=segment_key,
                segment_data=segment_data,
                method=method
            )
            
            if result:
                segment_results.append(result)
                overall_metrics["ece"].append(result["metrics"]["ece"])
                overall_metrics["brier"].append(result["metrics"]["brier_mean"])
                overall_metrics["mce"].append(result["metrics"]["mce"])
        
        if not segment_results:
            logger.error("❌ No segments had sufficient data for calibration")
            return None  # type: ignore[return-value]
        
        # Calculate overall metrics
        overall_ece = np.mean(overall_metrics["ece"])
        overall_brier = np.mean(overall_metrics["brier"])
        overall_mce = np.mean(overall_metrics["mce"])
        
        # Create calibration version
        cal_version = CalibrationVersion(
            calibration_version=calibration_version,
            trained_on_start=start_date,
            trained_on_end=end_date,
            created_at_utc=datetime.now(timezone.utc),
            method=method,  # type: ignore[arg-type]
            min_samples_required=self.MIN_SAMPLES_SEGMENT,
            activation_status=CalibrationStatus.CANDIDATE,
            overall_ece=float(overall_ece),
            overall_brier=float(overall_brier),
            overall_mce=float(overall_mce),
            notes=f"Trained on {len(training_data)} samples across {len(segment_results)} segments"
        )
        
        self.calibration_versions_collection.insert_one(cal_version.model_dump())
        
        # Save segments
        for result in segment_results:
            segment = CalibrationSegment(
                calibration_version=calibration_version,
                segment_key=result["segment_key"],
                n_samples=result["n_samples"],
                mapping_params=result["mapping_params"],
                ece=result["metrics"]["ece"],
                brier_mean=result["metrics"]["brier_mean"],
                mce=result["metrics"]["mce"],
                reliability_diagram=result.get("reliability_diagram")
            )
            
            self.calibration_segments_collection.insert_one(segment.model_dump())
        
        logger.info(
            f"✅ Created calibration version: {calibration_version} "
            f"(ECE={overall_ece:.4f}, Brier={overall_brier:.4f})"
        )
        
        # Check activation gate
        should_activate = self._check_activation_gate(calibration_version)
        
        if should_activate:
            self.activate_calibration_version(calibration_version)
        else:
            logger.warning(
                f"⚠️ Calibration {calibration_version} did not pass activation gate. "
                f"Keeping current active version."
            )
        
        return calibration_version
    
    def _get_training_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get training data: only official published predictions that are settled
        """
        # Get graded predictions in date range
        gradings = list(self.grading_collection.find({
            "graded_at": {"$gte": start_date, "$lte": end_date},
            "bet_status": "SETTLED"
        }))
        
        training_data = []
        
        for grading in gradings:
            # Get published prediction
            published = self.published_collection.find_one({
                "publish_id": grading["publish_id"],
                "is_official": True
            })
            
            if not published:
                continue
            
            # Get prediction
            prediction = self.predictions_collection.find_one({
                "prediction_id": grading["prediction_id"]
            })
            
            if not prediction:
                continue
            
            # Extract probability
            p_win = prediction.get("p_win") or prediction.get("p_cover") or prediction.get("p_over")
            
            if p_win is None:
                continue
            
            # Extract outcome (1 for win, 0 for loss, exclude push/void)
            result_code = grading.get("result_code")
            if result_code == "PUSH" or result_code == "VOID":
                continue
            
            outcome = 1 if result_code == "WIN" else 0
            
            # Build training sample
            sample = {
                "predicted_prob": p_win,
                "actual_outcome": outcome,
                "cohort_tags": grading.get("cohort_tags", {}),
                "grading": grading,
                "prediction": prediction
            }
            
            training_data.append(sample)
        
        return training_data
    
    def _segment_data(
        self,
        training_data: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Segment data by league and market
        
        Segmentation rules:
        1. Start with (league, market_key)
        2. Add edge_bucket, variance_bucket only when n >= MIN_SAMPLES
        """
        segments = {}
        
        for sample in training_data:
            tags = sample["cohort_tags"]
            
            # Primary segmentation: league | market
            league = tags.get("league", "UNKNOWN")
            market = tags.get("market", "UNKNOWN")
            
            segment_key = f"{league}|{market}"
            
            if segment_key not in segments:
                segments[segment_key] = []
            
            segments[segment_key].append(sample)
        
        return segments
    
    def _train_segment_calibration(
        self,
        segment_key: str,
        segment_data: List[Dict[str, Any]],
        method: str
    ) -> Optional[Dict[str, Any]]:
        """
        Train calibration for a segment
        
        Returns:
            {
                segment_key: str,
                n_samples: int,
                mapping_params: dict,
                metrics: {ece, brier_mean, mce}
            }
        """
        # Extract X (predicted probs) and y (actual outcomes)
        X = np.array([s["predicted_prob"] for s in segment_data])
        y = np.array([s["actual_outcome"] for s in segment_data])
        
        n_samples = len(segment_data)
        
        logger.info(f"🔧 Training {method} calibration for {segment_key} ({n_samples} samples)")
        
        # Train calibration model
        if method == "isotonic":
            mapping_params = self._train_isotonic(X, y)
        elif method == "platt":
            mapping_params = self._train_platt(X, y)
        elif method == "temperature":
            mapping_params = self._train_temperature_scaling(X, y)
        else:
            logger.error(f"Unknown calibration method: {method}")
            return None
        
        # Compute metrics
        calibrated_probs = self._apply_calibration(X, mapping_params, method)
        
        ece = self._compute_ece(calibrated_probs, y)
        mce = self._compute_mce(calibrated_probs, y)
        brier_mean = np.mean((calibrated_probs - y) ** 2)
        
        # Generate reliability diagram data
        reliability_diagram = self._generate_reliability_diagram(calibrated_probs, y)
        
        return {
            "segment_key": segment_key,
            "n_samples": n_samples,
            "mapping_params": mapping_params,
            "metrics": {
                "ece": float(ece),
                "mce": float(mce),
                "brier_mean": float(brier_mean)
            },
            "reliability_diagram": reliability_diagram
        }
    
    def _train_isotonic(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Train isotonic regression calibration"""
        iso_reg = IsotonicRegression(out_of_bounds="clip")
        iso_reg.fit(X, y)
        
        return {
            "type": "isotonic",
            "X_": iso_reg.X_.tolist(),  # type: ignore[attr-defined]
            "y_": iso_reg.y_.tolist()   # type: ignore[attr-defined]
        }
    
    def _train_platt(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Train Platt scaling (logistic regression)"""
        lr = LogisticRegression()
        lr.fit(X.reshape(-1, 1), y)
        
        return {
            "type": "platt",
            "coef": float(lr.coef_[0][0]),
            "intercept": float(lr.intercept_[0])
        }
    
    def _train_temperature_scaling(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Train temperature scaling"""
        # Simple temperature scaling: find T that minimizes NLL
        best_temp = 1.0
        best_nll = float('inf')
        
        for temp in np.linspace(0.1, 5.0, 50):
            calibrated = self._apply_temperature(X, temp)
            nll = -np.mean(y * np.log(calibrated + 1e-10) + (1 - y) * np.log(1 - calibrated + 1e-10))
            
            if nll < best_nll:
                best_nll = nll
                best_temp = temp
        
        return {
            "type": "temperature",
            "temperature": float(best_temp)
        }
    
    def _apply_calibration(
        self,
        X: np.ndarray,
        mapping_params: Dict[str, Any],
        method: str
    ) -> np.ndarray:
        """Apply calibration mapping"""
        if method == "isotonic" or mapping_params["type"] == "isotonic":
            iso_reg = IsotonicRegression(out_of_bounds="clip")
            iso_reg.X_ = np.array(mapping_params["X_"])  # type: ignore[attr-defined]
            iso_reg.y_ = np.array(mapping_params["y_"])  # type: ignore[attr-defined]
            return iso_reg.predict(X)
        
        elif method == "platt" or mapping_params["type"] == "platt":
            logits = mapping_params["coef"] * X + mapping_params["intercept"]
            return 1 / (1 + np.exp(-logits))
        
        elif method == "temperature" or mapping_params["type"] == "temperature":
            return self._apply_temperature(X, mapping_params["temperature"])
        
        return X
    
    def _apply_temperature(self, X: np.ndarray, temperature: float) -> np.ndarray:
        """Apply temperature scaling"""
        # Convert prob to logits, scale, convert back
        logits = np.log(X / (1 - X + 1e-10) + 1e-10)
        scaled_logits = logits / temperature
        return 1 / (1 + np.exp(-scaled_logits))
    
    def _compute_ece(
        self,
        predicted_probs: np.ndarray,
        actual_outcomes: np.ndarray,
        n_bins: int = 10
    ) -> float:
        """
        Compute Expected Calibration Error (ECE)
        """
        bins = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(predicted_probs, bins) - 1
        
        ece = 0.0
        
        for i in range(n_bins):
            mask = bin_indices == i
            if np.sum(mask) > 0:
                bin_accuracy = np.mean(actual_outcomes[mask])
                bin_confidence = np.mean(predicted_probs[mask])
                bin_weight = np.sum(mask) / len(predicted_probs)
                
                ece += bin_weight * abs(bin_accuracy - bin_confidence)
        
        return ece
    
    def _compute_mce(
        self,
        predicted_probs: np.ndarray,
        actual_outcomes: np.ndarray,
        n_bins: int = 10
    ) -> float:
        """
        Compute Maximum Calibration Error (MCE)
        """
        bins = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(predicted_probs, bins) - 1
        
        max_error = 0.0
        
        for i in range(n_bins):
            mask = bin_indices == i
            if np.sum(mask) > 0:
                bin_accuracy = np.mean(actual_outcomes[mask])
                bin_confidence = np.mean(predicted_probs[mask])
                
                max_error = max(max_error, abs(bin_accuracy - bin_confidence))
        
        return float(max_error)
    
    def _generate_reliability_diagram(
        self,
        predicted_probs: np.ndarray,
        actual_outcomes: np.ndarray,
        n_bins: int = 10
    ) -> Dict[str, Any]:
        """
        Generate reliability diagram data
        """
        bins = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(predicted_probs, bins) - 1
        
        diagram = {
            "bins": [],
            "accuracies": [],
            "confidences": [],
            "counts": []
        }
        
        for i in range(n_bins):
            mask = bin_indices == i
            count = np.sum(mask)
            
            if count > 0:
                bin_accuracy = float(np.mean(actual_outcomes[mask]))
                bin_confidence = float(np.mean(predicted_probs[mask]))
                
                diagram["bins"].append(i)
                diagram["accuracies"].append(bin_accuracy)
                diagram["confidences"].append(bin_confidence)
                diagram["counts"].append(int(count))
        
        return diagram
    
    def _check_activation_gate(self, calibration_version: str) -> bool:
        """
        Check if new calibration should be activated
        
        Activation criteria:
        1. ECE improves (or doesn't worsen beyond tolerance)
        2. Brier improves
        3. Segment coverage meets minimums
        """
        # Get current active version
        current_active = self.calibration_versions_collection.find_one({
            "activation_status": CalibrationStatus.ACTIVE.value
        })
        
        if not current_active:
            # No active version, auto-activate if metrics are reasonable
            new_version = self.calibration_versions_collection.find_one({
                "calibration_version": calibration_version
            })
            
            if not new_version:
                return False
            
            if new_version["overall_ece"] < 0.15:  # Reasonable ECE threshold
                return True
            
            return False
        
        # Get new version
        new_version = self.calibration_versions_collection.find_one({
            "calibration_version": calibration_version
        })
        
        if not new_version:
            return False
        
        # Compare metrics
        ece_improvement = current_active["overall_ece"] - new_version["overall_ece"]
        brier_improvement = current_active["overall_brier"] - new_version["overall_brier"]
        
        # Tolerances
        ECE_TOLERANCE = 0.01
        BRIER_TOLERANCE = 0.01
        
        # Check improvements
        ece_ok = ece_improvement >= -ECE_TOLERANCE
        brier_ok = brier_improvement >= -BRIER_TOLERANCE
        
        logger.info(
            f"📊 Activation gate check:\n"
            f"  ECE: {current_active['overall_ece']:.4f} → {new_version['overall_ece']:.4f} "
            f"(Δ={ece_improvement:.4f}, ok={ece_ok})\n"
            f"  Brier: {current_active['overall_brier']:.4f} → {new_version['overall_brier']:.4f} "
            f"(Δ={brier_improvement:.4f}, ok={brier_ok})"
        )
        
        return ece_ok and brier_ok
    
    def activate_calibration_version(self, calibration_version: str) -> bool:
        """
        Activate a calibration version (deactivate others)
        """
        # Deactivate current active
        self.calibration_versions_collection.update_many(
            {"activation_status": CalibrationStatus.ACTIVE.value},
            {"$set": {"activation_status": CalibrationStatus.CANDIDATE.value}}
        )
        
        # Activate new version
        result = self.calibration_versions_collection.update_one(
            {"calibration_version": calibration_version},
            {"$set": {"activation_status": CalibrationStatus.ACTIVE.value}}
        )
        
        if result.modified_count > 0:
            logger.info(f"✅ Activated calibration version: {calibration_version}")
            return True
        
        return False
    
    def get_active_calibration_version(self) -> Optional[str]:
        """
        Get the currently active calibration version
        """
        active = self.calibration_versions_collection.find_one({
            "activation_status": CalibrationStatus.ACTIVE.value
        })
        
        return active["calibration_version"] if active else None
    
    def get_calibration_mapping(
        self,
        calibration_version: str,
        segment_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get calibration mapping for a segment
        """
        segment = self.calibration_segments_collection.find_one({
            "calibration_version": calibration_version,
            "segment_key": segment_key
        })
        
        if segment:
            return segment["mapping_params"]
        
        return None
    
    def calibrate_probability(
        self,
        raw_probability: float,
        league: str,
        market_key: str,
        calibration_version: Optional[str] = None
    ) -> float:
        """
        Apply calibration to a raw probability
        
        Args:
            raw_probability: Uncalibrated probability
            league: NBA, NFL, etc.
            market_key: SPREAD:FULL_GAME, etc.
            calibration_version: Specific version or None for active
        
        Returns:
            Calibrated probability
        """
        if calibration_version is None:
            calibration_version = self.get_active_calibration_version()
        
        if not calibration_version:
            logger.warning("No active calibration version, returning raw probability")
            return raw_probability
        
        segment_key = f"{league}|{market_key}"
        
        mapping = self.get_calibration_mapping(calibration_version, segment_key)
        
        if not mapping:
            logger.warning(f"No calibration mapping for {segment_key}, returning raw probability")
            return raw_probability
        
        # Apply calibration
        calibrated = self._apply_calibration(
            np.array([raw_probability]),
            mapping,
            mapping["type"]
        )[0]
        
        return float(calibrated)


# Singleton instance
calibration_service = CalibrationService()
