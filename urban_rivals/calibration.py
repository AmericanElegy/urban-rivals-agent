"""Normalized (0.0-1.0) viewport calibration storage for Urban Rivals WebGL."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path

REQUIRED_POINTS = (
    "hand_0",
    "hand_1",
    "hand_2",
    "hand_3",
    "opp_0",
    "opp_1",
    "opp_2",
    "opp_3",
    "pillz_plus",
    "pillz_minus",
    "fury_btn",
    "confirm_btn",
)


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def __post_init__(self):
        if not (0.0 <= self.x <= 1.0 and 0.0 <= self.y <= 1.0):
            raise ValueError(f"Normalized point out of range [0, 1]: ({self.x}, {self.y})")


def default_points() -> dict[str, dict[str, float]]:
    """Default 16:9 WebGL click centers matching standard Urban Rivals layout."""
    centers = (0.20, 0.40, 0.60, 0.80)
    pts: dict[str, dict[str, float]] = {}
    for i, cx in enumerate(centers):
        pts[f"hand_{i}"] = {"x": cx, "y": 0.72}
        pts[f"opp_{i}"] = {"x": cx, "y": 0.24}
    pts["pillz_plus"] = {"x": 0.56, "y": 0.60}
    pts["pillz_minus"] = {"x": 0.44, "y": 0.60}
    pts["fury_btn"] = {"x": 0.50, "y": 0.54}
    pts["confirm_btn"] = {"x": 0.50, "y": 0.66}
    return pts


def validate_calibration(payload: dict) -> dict[str, dict[str, float]]:
    if not isinstance(payload, dict):
        raise ValueError("Calibration payload must be a JSON object")
    points = payload.get("points", payload)
    if not isinstance(points, dict):
        raise ValueError("Calibration points must be a JSON object")
    validated: dict[str, dict[str, float]] = {}
    for key in REQUIRED_POINTS:
        if key not in points:
            raise ValueError(f"Missing calibration point: {key}")
        raw = points[key]
        if not isinstance(raw, dict) or "x" not in raw or "y" not in raw:
            raise ValueError(f"Invalid calibration point for {key}")
        pt = Point(float(raw["x"]), float(raw["y"]))
        validated[key] = asdict(pt)
    return validated


def save_calibration(path: str | Path, payload: dict) -> dict[str, dict[str, float]]:
    validated = validate_calibration(payload)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"points": validated}, indent=2), encoding="utf-8")
    return validated


def load_calibration(path: str | Path) -> dict[str, dict[str, float]]:
    target = Path(path)
    if not target.exists():
        return default_points()
    return validate_calibration(json.loads(target.read_text(encoding="utf-8")))
