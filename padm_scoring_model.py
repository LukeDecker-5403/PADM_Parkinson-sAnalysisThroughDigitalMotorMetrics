"""
padm_scoring_model.py

Similarity-based PADM scoring module.

This module converts PADM motor/cognitive feature outputs into normalized
impairment-style component scores, compares those scores with the local
PPMI Neuro-QoL mobility reference curve, and returns a research-prototype
similarity summary for the UI.

Important: this is not a diagnostic model. It is a structured comparison
model for prototype visualization and later validation work.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import math
import statistics


# Direction indicates whether higher raw metric values are better or worse.
# Anchors are prototype reference bands used only until a validated training set
# replaces them. They are intentionally transparent and easy to revise.
FEATURE_SPECS: Dict[str, Dict[str, Any]] = {
    "motor.tapping_left.taps_per_second": {
        "label": "Left tapping speed",
        "healthy": 5.5,
        "impaired": 2.8,
        "higher_is_worse": False,
        "weight": 1.10,
    },
    "motor.tapping_right.taps_per_second": {
        "label": "Right tapping speed",
        "healthy": 5.5,
        "impaired": 2.8,
        "higher_is_worse": False,
        "weight": 1.10,
    },
    "motor.tapping_alternating.taps_per_second": {
        "label": "Alternating tapping speed",
        "healthy": 4.8,
        "impaired": 2.5,
        "higher_is_worse": False,
        "weight": 1.00,
    },
    "motor.tapping_alternating.alternation_accuracy": {
        "label": "Alternating tapping accuracy",
        "healthy": 0.92,
        "impaired": 0.55,
        "higher_is_worse": False,
        "weight": 0.85,
    },
    "motor.tremor_dominant.estimated_frequency_hz": {
        "label": "Dominant-hand tremor frequency",
        "healthy": 1.0,
        "impaired": 5.0,
        "higher_is_worse": True,
        "weight": 1.35,
    },
    "motor.tremor_non_dominant.estimated_frequency_hz": {
        "label": "Non-dominant-hand tremor frequency",
        "healthy": 1.0,
        "impaired": 5.0,
        "higher_is_worse": True,
        "weight": 1.15,
    },
    "motor.tracing_precision.mean_deviation": {
        "label": "Tracing mean deviation",
        "healthy": 10.0,
        "impaired": 35.0,
        "higher_is_worse": True,
        "weight": 1.20,
    },
    "motor.tracing_precision.path_efficiency": {
        "label": "Tracing path efficiency",
        "healthy": 0.92,
        "impaired": 0.45,
        "higher_is_worse": False,
        "weight": 0.85,
    },
    "cognitive.reaction_time.average_reaction_time_ms": {
        "label": "Average reaction time",
        "healthy": 260.0,
        "impaired": 520.0,
        "higher_is_worse": True,
        "weight": 0.90,
    },
    "cognitive.sequence_memory.accuracy": {
        "label": "Sequence memory accuracy",
        "healthy": 0.88,
        "impaired": 0.48,
        "higher_is_worse": False,
        "weight": 0.75,
    },
    "cognitive.sequence_memory.longest_correct_span": {
        "label": "Longest correct memory span",
        "healthy": 6.0,
        "impaired": 3.0,
        "higher_is_worse": False,
        "weight": 0.65,
    },
    "cognitive.symbol_matching.accuracy": {
        "label": "Symbol matching accuracy",
        "healthy": 0.92,
        "impaired": 0.58,
        "higher_is_worse": False,
        "weight": 0.70,
    },
    "cognitive.symbol_matching.items_per_second": {
        "label": "Symbol matching speed",
        "healthy": 0.85,
        "impaired": 0.35,
        "higher_is_worse": False,
        "weight": 0.70,
    },
}


@dataclass
class ComponentScore:
    feature_key: str
    label: str
    raw_value: float
    impairment_score_0_100: float
    weight: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _as_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    return None


def normalize_feature_value(raw_value: float, spec: Dict[str, Any]) -> float:
    """Convert a raw feature value into a 0-100 impairment-style score."""
    healthy = float(spec["healthy"])
    impaired = float(spec["impaired"])
    if healthy == impaired:
        return 0.0

    if spec["higher_is_worse"]:
        score = ((raw_value - healthy) / (impaired - healthy)) * 100.0
    else:
        score = ((healthy - raw_value) / (healthy - impaired)) * 100.0
    return round(_clamp(score), 2)


def flatten_feature_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Accept either an export payload or an already-flat feature vector."""
    if "feature_vector" in payload and isinstance(payload["feature_vector"], dict):
        return payload["feature_vector"]
    return payload


def build_component_scores(payload: Dict[str, Any]) -> List[ComponentScore]:
    features = flatten_feature_dict(payload)
    components: List[ComponentScore] = []

    for key, spec in FEATURE_SPECS.items():
        raw = _as_number(features.get(key))
        if raw is None:
            continue
        components.append(
            ComponentScore(
                feature_key=key,
                label=str(spec["label"]),
                raw_value=round(raw, 4),
                impairment_score_0_100=normalize_feature_value(raw, spec),
                weight=float(spec["weight"]),
            )
        )
    return components


def weighted_impairment_score(components: List[ComponentScore]) -> Optional[float]:
    if not components:
        return None
    total_weight = sum(c.weight for c in components)
    if total_weight <= 0:
        return None
    weighted = sum(c.impairment_score_0_100 * c.weight for c in components) / total_weight
    return round(weighted, 2)


def confidence_from_components(components: List[ComponentScore]) -> Dict[str, Any]:
    present = {c.feature_key for c in components}
    motor_count = sum(1 for key in present if key.startswith("motor."))
    cognitive_count = sum(1 for key in present if key.startswith("cognitive."))
    expected = len(FEATURE_SPECS)
    coverage = len(present) / expected if expected else 0.0

    if len(present) >= 9 and motor_count >= 5 and cognitive_count >= 3:
        level = "strong prototype coverage"
    elif len(present) >= 5 and motor_count >= 3:
        level = "moderate prototype coverage"
    elif len(present) > 0:
        level = "limited prototype coverage"
    else:
        level = "no scorable data"

    return {
        "completed_scorable_features": len(present),
        "expected_scorable_features": expected,
        "motor_feature_count": motor_count,
        "cognitive_feature_count": cognitive_count,
        "coverage_ratio": round(coverage, 3),
        "level": level,
    }


def load_ppmi_reference_curve(curve_path: str | Path = "ppmi_mobility_reference_curve.json") -> Dict[str, Any]:
    path = Path(curve_path)
    if not path.exists():
        # Also support running from a different working directory while this file
        # sits beside the JSON reference file.
        local = Path(__file__).resolve().parent / str(curve_path)
        path = local if local.exists() else path
    if not path.exists():
        return {"available": False, "reason": f"Reference file not found: {curve_path}", "curve": []}

    data = json.loads(path.read_text(encoding="utf-8"))
    data["available"] = True
    return data


def nearest_ppmi_visit(score: Optional[float], curve_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if score is None or not curve_data.get("curve"):
        return None
    candidates = []
    for row in curve_data["curve"]:
        mean_score = _as_number(row.get("mean_mobility_impairment_score"))
        if mean_score is None:
            continue
        enriched = dict(row)
        enriched["absolute_difference"] = round(abs(score - mean_score), 3)
        candidates.append(enriched)
    return min(candidates, key=lambda r: r["absolute_difference"]) if candidates else None


def interpret_score(score: Optional[float]) -> str:
    if score is None:
        return "No similarity score available yet. Complete more tests first."
    if score < 25:
        return "Low prototype impairment similarity"
    if score < 50:
        return "Mild prototype impairment similarity"
    if score < 75:
        return "Moderate prototype impairment similarity"
    return "High prototype impairment similarity"


def calculate_padm_similarity(
    payload: Dict[str, Any],
    curve_path: str | Path = "ppmi_mobility_reference_curve.json",
) -> Dict[str, Any]:
    """Return the full PADM similarity summary used by the Results page."""
    components = build_component_scores(payload)
    score = weighted_impairment_score(components)
    curve_data = load_ppmi_reference_curve(curve_path)
    nearest = nearest_ppmi_visit(score, curve_data)

    values = [c.impairment_score_0_100 for c in components]
    spread = round(statistics.pstdev(values), 2) if len(values) > 1 else 0.0 if values else None

    return {
        "model_name": "PADM weighted similarity prototype v1",
        "diagnostic_status": "research_prototype_not_diagnostic",
        "overall_similarity_score_0_100": score,
        "interpretation": interpret_score(score),
        "component_spread_std": spread,
        "confidence": confidence_from_components(components),
        "component_scores": [c.to_dict() for c in components],
        "ppmi_reference": {
            "available": bool(curve_data.get("available")),
            "score_name": curve_data.get("score_name"),
            "score_range": curve_data.get("score_range"),
            "nearest_visit": nearest,
            "curve": curve_data.get("curve", []),
        },
    }


def validate_required_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Debug helper for the UI: identify missing major sections/tests."""
    motor = payload.get("motor_results", {}) if isinstance(payload.get("motor_results"), dict) else {}
    cognitive = payload.get("cognitive_results", {}) if isinstance(payload.get("cognitive_results"), dict) else {}

    required_motor = ["tapping_left", "tapping_right", "tapping_alternating", "tracing_precision"]
    required_cognitive = ["reaction_time", "sequence_memory", "symbol_matching"]

    missing_motor = [name for name in required_motor if name not in motor]
    # The tremor workflow allows either dominant or non-dominant hand. Do not mark
    # the whole results page incomplete when one valid tremor hand has been saved.
    if "tremor_dominant" not in motor and "tremor_non_dominant" not in motor:
        missing_motor.append("tremor_test")
    missing_cognitive = [name for name in required_cognitive if name not in cognitive]

    return {
        "complete": not missing_motor and not missing_cognitive,
        "missing_motor_tests": missing_motor,
        "missing_cognitive_tests": missing_cognitive,
        "saved_motor_tests": sorted(motor.keys()),
        "saved_cognitive_tests": sorted(cognitive.keys()),
    }


if __name__ == "__main__":
    demo_payload = {
        "feature_vector": {
            "motor.tapping_left.taps_per_second": 4.2,
            "motor.tapping_right.taps_per_second": 4.0,
            "motor.tremor_dominant.estimated_frequency_hz": 4.8,
            "motor.tracing_precision.mean_deviation": 22.0,
            "cognitive.reaction_time.average_reaction_time_ms": 360.0,
        }
    }
    print(json.dumps(calculate_padm_similarity(demo_payload), indent=2))
