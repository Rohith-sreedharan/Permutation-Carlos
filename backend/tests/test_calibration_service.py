import math

from services.calibration_service import CalibrationService


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("calibration_version", "ok")})

    def update_many(self, query, update):
        modified = 0
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update.get("$set", {}))
                modified += 1
        return type("UpdateResult", (), {"modified_count": modified})

    def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update.get("$set", {}))
                return type("UpdateResult", (), {"modified_count": 1})
        return type("UpdateResult", (), {"modified_count": 0})

    def find(self, query):
        return []


def make_service() -> CalibrationService:
    svc = CalibrationService()
    svc.calibration_versions_collection = FakeCollection()
    svc.calibration_segments_collection = FakeCollection()
    svc.grading_collection = FakeCollection()
    svc.published_collection = FakeCollection()
    svc.predictions_collection = FakeCollection()
    return svc


def test_run_calibration_job_returns_none_when_insufficient_training_data():
    svc = make_service()
    svc._get_training_data = lambda *_args, **_kwargs: []

    result = svc.run_calibration_job(training_days=30, method="isotonic")

    assert result is None


def test_check_activation_gate_without_active_version_uses_reasonable_ece_threshold():
    svc = make_service()
    svc.calibration_versions_collection.docs = [
        {
            "calibration_version": "v_good",
            "activation_status": "CANDIDATE",
            "overall_ece": 0.10,
            "overall_brier": 0.20,
        },
        {
            "calibration_version": "v_bad",
            "activation_status": "CANDIDATE",
            "overall_ece": 0.20,
            "overall_brier": 0.20,
        },
    ]

    assert svc._check_activation_gate("v_good") is True
    assert svc._check_activation_gate("v_bad") is False


def test_calibrate_probability_returns_raw_when_no_active_version():
    svc = make_service()
    svc.get_active_calibration_version = lambda: None

    raw = 0.62
    calibrated = svc.calibrate_probability(raw_probability=raw, league="NBA", market_key="SPREAD:FULL_GAME")

    assert calibrated == raw


def test_calibrate_probability_applies_platt_mapping_for_segment():
    svc = make_service()
    svc.get_active_calibration_version = lambda: "v1"
    svc.get_calibration_mapping = lambda _version, _segment: {
        "type": "platt",
        "coef": 2.0,
        "intercept": 0.0,
    }

    calibrated = svc.calibrate_probability(raw_probability=0.5, league="NBA", market_key="SPREAD:FULL_GAME")

    expected = 1.0 / (1.0 + math.exp(-1.0))
    assert abs(calibrated - expected) < 1e-6
