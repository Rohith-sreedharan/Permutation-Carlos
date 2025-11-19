from typing import Any, Dict, Optional
from datetime import datetime, timezone

from db.mongo import insert_log_entry


def log_stage(module: str, stage: str, input_payload: Optional[Dict[str, Any]] = None, output_payload: Optional[Dict[str, Any]] = None, level: str = "INFO"):
    entry = {
        "module": module,
        "stage": stage,
        "level": level,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input": input_payload or {},
        "output": output_payload or {},
    }
    insert_log_entry(entry)
