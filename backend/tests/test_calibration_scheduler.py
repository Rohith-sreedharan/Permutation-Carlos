import services.calibration_scheduler as scheduler_module
from services.calibration_scheduler import CalibrationScheduler


class FakeJob:
    def __init__(self, func):
        self.func = func


class FakeSchedulerBackend:
    def __init__(self):
        self.jobs = {}
        self.started = False
        self.stopped = False

    def add_job(self, func, trigger, id, name, replace_existing):
        self.jobs[id] = FakeJob(func)

    def start(self):
        self.started = True

    def shutdown(self):
        self.stopped = True

    def get_job(self, job_id):
        return self.jobs.get(job_id)


class FakeCalibrationService:
    def __init__(self):
        self.called = False

    def run_calibration_job(self, training_days, method):
        self.called = True
        return "v_test"


class FakeGradingService:
    def __init__(self):
        self.called = False

    def grade_all_pending(self, lookback_hours):
        self.called = True
        return {"graded": 1, "voided": 0, "pending": 0}


def test_start_registers_weekly_and_daily_jobs():
    sched = CalibrationScheduler()
    fake_backend = FakeSchedulerBackend()
    setattr(sched, "scheduler", fake_backend)

    sched.start()

    assert fake_backend.started is True
    assert "weekly_calibration" in fake_backend.jobs
    assert "daily_grading" in fake_backend.jobs


def test_run_now_returns_false_for_missing_job():
    sched = CalibrationScheduler()
    setattr(sched, "scheduler", FakeSchedulerBackend())

    assert sched.run_now("missing") is False


def test_run_now_executes_existing_job():
    sched = CalibrationScheduler()
    backend = FakeSchedulerBackend()
    ran = {"value": False}

    backend.add_job(
        func=lambda: ran.__setitem__("value", True),
        trigger=None,
        id="job_1",
        name="job",
        replace_existing=True,
    )
    setattr(sched, "scheduler", backend)

    assert sched.run_now("job_1") is True
    assert ran["value"] is True


def test_weekly_and_daily_jobs_call_services(monkeypatch):
    sched = CalibrationScheduler()
    fake_cal = FakeCalibrationService()
    fake_grade = FakeGradingService()

    monkeypatch.setattr(scheduler_module, "calibration_service", fake_cal)
    monkeypatch.setattr(scheduler_module, "grading_service", fake_grade)

    sched.run_weekly_calibration()
    sched.run_daily_grading()

    assert fake_cal.called is True
    assert fake_grade.called is True
