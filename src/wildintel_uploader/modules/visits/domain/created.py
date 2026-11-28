"""What a file of visits creates when it names a camera or an SD card the research project doesn't have yet — plain Python: its record as the
catalog keeps one that has just been made, ready to be used, with what the row says of it."""
from __future__ import annotations

_KEPT = {"in_service": None, "research_project": None, "status": "ready", "archive_reason": None, "status_date": None, "status_note": None,
         "id": None, "created_at": None, "updated_at": None, "deleted_at": None}


def new_camera(label: str, serial: str | None, make: str | None, model: str | None) -> dict:
    return {"label": label, "camera_id": serial, "camera_make": make, "camera_model": model, "connectivity": None, "power_source": None,
            "battery_removable": None, **_KEPT}


def new_card(label: str, brand: str | None, capacity: str | None) -> dict:
    return {"label": label, "brand": brand, "capacity": capacity, **_KEPT}
