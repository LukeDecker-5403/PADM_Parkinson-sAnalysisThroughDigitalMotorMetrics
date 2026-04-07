"""
padm_data_integration.py

Data integration and session management module for PADM.
Combines motor and cognitive test outputs into a unified structure
for analysis, comparison, and future machine learning use.

Features implemented:
1. Participant metadata storage (age, sex, handedness, etc.)
2. Unified storage for motor and cognitive test results
3. JSON export of full assessment session
4. Flattened feature vector generation for analysis/model input
5. Session summary and result tracking

Note:
This module serves as the bridge between data collection and analysis.
It prepares structured outputs for dataset comparison and similarity scoring.

Author: Luke Decker project scaffold
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any, Dict, Optional
import json


@dataclass
class ParticipantProfile:
    """Basic participant metadata for a PADM assessment session."""
    participant_id: str
    age: Optional[int] = None
    sex: Optional[str] = None
    handedness: Optional[str] = None
    sleep_quality: Optional[int] = None
    genetic_predisposition: Optional[bool] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PADMAssessmentRecord:
    """Unified export structure that combines motor and cognitive outputs."""
    participant: ParticipantProfile
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    motor_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cognitive_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "participant": self.participant.to_dict(),
            "created_at": self.created_at,
            "motor_results": self.motor_results,
            "cognitive_results": self.cognitive_results,
            "feature_vector": self.feature_vector(),
        }

    def feature_vector(self) -> Dict[str, Any]:
        """Flatten nested outputs into one analysis-friendly dictionary."""
        flat: Dict[str, Any] = {}

        for section_name, section in (
            ("motor", self.motor_results),
            ("cognitive", self.cognitive_results),
        ):
            for test_name, metrics in section.items():
                for metric_name, value in metrics.items():
                    flat[f"{section_name}.{test_name}.{metric_name}"] = value

        participant = self.participant.to_dict()
        for key, value in participant.items():
            flat[f"participant.{key}"] = value

        return flat


class PADMAssessmentManager:
    """Central manager for collecting and exporting PADM results."""

    def __init__(self, participant: ParticipantProfile):
        self.record = PADMAssessmentRecord(participant=participant)

    def save_motor_result(self, test_name: str, result: Any) -> None:
        self.record.motor_results[test_name] = self._normalize_result(result)

    def save_cognitive_result(self, test_name: str, result: Any) -> None:
        self.record.cognitive_results[test_name] = self._normalize_result(result)

    def export_dict(self) -> Dict[str, Any]:
        return self.record.to_dict()

    def export_json(self, filepath: Optional[str] = None, indent: int = 2) -> str:
        payload = json.dumps(self.export_dict(), indent=indent)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(payload)
        return payload

    def summary(self) -> Dict[str, Any]:
        motor_count = len(self.record.motor_results)
        cognitive_count = len(self.record.cognitive_results)
        return {
            "participant_id": self.record.participant.participant_id,
            "motor_tests_completed": motor_count,
            "cognitive_tests_completed": cognitive_count,
            "total_tests_completed": motor_count + cognitive_count,
            "created_at": self.record.created_at,
        }

    @staticmethod
    def _normalize_result(result: Any) -> Dict[str, Any]:
        if hasattr(result, "to_dict"):
            return result.to_dict()
        if isinstance(result, dict):
            return result
        raise TypeError("Result must be a dict or expose a to_dict() method.")


if __name__ == "__main__":
    participant = ParticipantProfile(
        participant_id="demo_001",
        age=67,
        sex="M",
        handedness="right",
        sleep_quality=7,
        genetic_predisposition=False,
    )

    manager = PADMAssessmentManager(participant)
    manager.save_motor_result(
        "tapping_dominant",
        {
            "hand": "dominant",
            "total_taps": 52,
            "duration_seconds": 10.0,
            "taps_per_second": 5.2,
        },
    )
    manager.save_cognitive_result(
        "sequence_memory",
        {
            "total_rounds": 5,
            "correct_rounds": 4,
            "longest_correct_span": 6,
            "accuracy": 0.8,
        },
    )

    print(manager.summary())
    print(manager.export_json())