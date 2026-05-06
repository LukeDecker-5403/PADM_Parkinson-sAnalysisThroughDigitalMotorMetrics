"""
padm_data_integration.py

Data integration and session management module for PADM.
Combines motor and cognitive test outputs into a unified structure for analysis,
comparison, autosave, graphing, and future machine learning / PPMI alignment.

Core responsibilities:
1. Store participant metadata.
2. Store motor and cognitive assessment outputs in one session record.
3. Normalize dataclass, dictionary, and primitive result values.
4. Export clean JSON for hidden/raw review.
5. Generate a flattened numeric feature vector for modeling and dataset correlation.
6. Provide autosave support so progress is not lost during testing.

Important project note:
PADM is not a diagnostic tool. This module only prepares structured comparison
features that can later be aligned with external reference datasets.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import json
import math

try:
    from padm_scoring_model import calculate_padm_similarity, validate_required_workflow
except Exception:
    calculate_padm_similarity = None
    validate_required_workflow = None


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
        """Convert participant metadata to a plain dictionary."""
        return asdict(self)


@dataclass
class PADMAssessmentRecord:
    """Unified export structure that combines participant, motor, and cognitive outputs."""

    participant: ParticipantProfile
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    motor_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cognitive_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    session_notes: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update the record timestamp whenever new data is saved."""
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def to_dict(self, include_feature_vector: bool = True) -> Dict[str, Any]:
        """Build a dictionary representation of the complete assessment record."""
        payload: Dict[str, Any] = {
            "participant": self.participant.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "motor_results": self.motor_results,
            "cognitive_results": self.cognitive_results,
            "session_notes": self.session_notes,
        }

        if include_feature_vector:
            payload["feature_vector"] = self.feature_vector()

        return payload

    def feature_vector(self) -> Dict[str, Any]:
        """
        Flatten results into an analysis-friendly dictionary.

        The feature vector intentionally keeps only model-friendly scalar values.
        Large raw fields such as trial_results, item_details, and round_details are
        preserved in full JSON exports but skipped here so later similarity models
        and PPMI correlation code receive a clean feature set.
        """
        flat: Dict[str, Any] = {}

        for section_name, section in (
            ("motor", self.motor_results),
            ("cognitive", self.cognitive_results),
        ):
            for test_name, metrics in section.items():
                self._flatten_metrics(
                    output=flat,
                    prefix=f"{section_name}.{test_name}",
                    value=metrics,
                    keep_scalars_only=True,
                )

        participant = self.participant.to_dict()
        for key, value in participant.items():
            converted = self._coerce_feature_value(value)
            if converted is not None:
                flat[f"participant.{key}"] = converted

        return flat

    @classmethod
    def _flatten_metrics(
        cls,
        output: Dict[str, Any],
        prefix: str,
        value: Any,
        keep_scalars_only: bool,
    ) -> None:
        """Recursively flatten dictionaries while avoiding raw list-heavy fields."""
        skip_keys = {
            "trial_results",
            "item_details",
            "round_details",
            "reaction_times_ms",
            "attempted_spans",
        }

        if isinstance(value, dict):
            for key, nested_value in value.items():
                if key in skip_keys:
                    continue
                cls._flatten_metrics(
                    output=output,
                    prefix=f"{prefix}.{key}",
                    value=nested_value,
                    keep_scalars_only=keep_scalars_only,
                )
            return

        if isinstance(value, list):
            if not keep_scalars_only:
                output[prefix] = value
            return

        converted = cls._coerce_feature_value(value)
        if converted is not None:
            output[prefix] = converted

    @staticmethod
    def _coerce_feature_value(value: Any) -> Optional[Any]:
        """Convert common values into feature-vector-safe scalar values."""
        if value is None:
            return None

        if isinstance(value, bool):
            return int(value)

        if isinstance(value, (int, float)):
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                return None
            return value

        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned == "":
                return None
            return cleaned

        return None


class PADMAssessmentManager:
    """Central manager for collecting, autosaving, and exporting PADM results."""

    def __init__(self, participant: ParticipantProfile, autosave_path: Optional[str] = None):
        self.record = PADMAssessmentRecord(participant=participant)
        self.autosave_path = Path(autosave_path) if autosave_path else None

    def set_autosave_path(self, filepath: str) -> None:
        """Set or update the JSON autosave path."""
        self.autosave_path = Path(filepath)
        self.autosave()

    def save_motor_result(self, test_name: str, result: Any) -> None:
        """Save motor test results into the assessment record and autosave."""
        clean_name = self._clean_test_name(test_name)
        self.record.motor_results[clean_name] = self._normalize_result(result)
        self.record.touch()
        self.autosave()

    def save_cognitive_result(self, test_name: str, result: Any) -> None:
        """Save cognitive test results into the assessment record and autosave."""
        clean_name = self._clean_test_name(test_name)
        self.record.cognitive_results[clean_name] = self._normalize_result(result)
        self.record.touch()
        self.autosave()

    def add_session_note(self, key: str, value: Any) -> None:
        """Attach non-test metadata such as UI version, research note, or dataset note."""
        self.record.session_notes[key] = value
        self.record.touch()
        self.autosave()

    def export_dict(self, include_feature_vector: bool = True) -> Dict[str, Any]:
        """Return the full assessment payload as a dictionary."""
        return self.record.to_dict(include_feature_vector=include_feature_vector)

    def export_json(
        self,
        filepath: Optional[str] = None,
        indent: int = 2,
        include_feature_vector: bool = True,
    ) -> str:
        """
        Serialize the full assessment payload to JSON.

        If filepath is supplied, the JSON payload is also written to disk.
        """
        payload = json.dumps(
            self.export_dict(include_feature_vector=include_feature_vector),
            indent=indent,
            default=str,
        )

        if filepath:
            output_path = Path(filepath)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")

        return payload

    def autosave(self) -> None:
        """Write the current session to the configured autosave path, if one exists."""
        if self.autosave_path is None:
            return

        self.autosave_path.parent.mkdir(parents=True, exist_ok=True)
        self.autosave_path.write_text(self.export_json(), encoding="utf-8")

    def summary(self) -> Dict[str, Any]:
        """Return a compact summary of completed motor and cognitive tests."""
        motor_count = len(self.record.motor_results)
        cognitive_count = len(self.record.cognitive_results)
        return {
            "participant_id": self.record.participant.participant_id,
            "motor_tests_completed": motor_count,
            "cognitive_tests_completed": cognitive_count,
            "total_tests_completed": motor_count + cognitive_count,
            "motor_test_names": list(self.record.motor_results.keys()),
            "cognitive_test_names": list(self.record.cognitive_results.keys()),
            "created_at": self.record.created_at,
            "updated_at": self.record.updated_at,
        }

    def model_ready_features(self) -> Dict[str, Any]:
        """Return only the flattened feature vector used for scoring/modeling."""
        return self.record.feature_vector()

    def scoring_summary(self) -> Dict[str, Any]:
        """Return the current PADM similarity score summary, if the scoring module is available."""
        if calculate_padm_similarity is None or validate_required_workflow is None:
            return {
                "available": False,
                "reason": "padm_scoring_model.py could not be imported.",
            }

        payload = self.export_dict(include_feature_vector=True)
        summary = calculate_padm_similarity(payload)
        summary["workflow_check"] = validate_required_workflow(payload)
        summary["available"] = True
        return summary

    def ppmi_alignment_template(self) -> Dict[str, Any]:
        """
        Return a placeholder mapping structure for future PPMI/AMP-PD alignment.

        This does not claim that PADM and PPMI variables are already correlated.
        It simply names PADM-derived features that are likely candidates for later
        comparison once the approved PPMI dataset file is added to the project.
        """
        return {
            "status": "template_only_pending_dataset_integration",
            "candidate_motor_features": [
                "motor.tapping_left.taps_per_second",
                "motor.tapping_right.taps_per_second",
                "motor.tapping_alternating.taps_per_second",
                "motor.tremor_dominant.estimated_frequency_hz",
                "motor.tracing_precision.mean_deviation",
                "motor.tracing_precision.path_efficiency",
            ],
            "candidate_cognitive_features": [
                "cognitive.reaction_time.average_reaction_time_ms",
                "cognitive.sequence_memory.accuracy",
                "cognitive.sequence_memory.longest_correct_span",
                "cognitive.symbol_matching.accuracy",
                "cognitive.symbol_matching.items_per_second",
            ],
            "next_step": "Upload/import approved PPMI CSV and define exact column-level mappings.",
        }

    @staticmethod
    def _normalize_result(result: Any) -> Dict[str, Any]:
        """Convert a result object into a dictionary for storage."""
        if hasattr(result, "to_dict"):
            return result.to_dict()
        if isinstance(result, dict):
            return result
        raise TypeError("Result must be a dict or expose a to_dict() method.")

    @staticmethod
    def _clean_test_name(test_name: str) -> str:
        """Standardize result keys while preserving existing naming style."""
        return test_name.strip().lower().replace(" ", "_").replace("-", "_")


if __name__ == "__main__":
    participant = ParticipantProfile(
        participant_id="demo_001",
        age=67,
        sex="Male",
        handedness="right",
        sleep_quality=7,
        genetic_predisposition=False,
    )

    manager = PADMAssessmentManager(participant)

    manager.save_motor_result(
        "tapping_left",
        {
            "mode": "left",
            "trial_count": 3,
            "total_taps": 52,
            "duration_seconds": 10.0,
            "taps_per_second": 5.2,
            "trial_results": [],
        },
    )

    manager.save_cognitive_result(
        "sequence_memory",
        {
            "total_rounds": 3,
            "correct_rounds": 2,
            "longest_correct_span": 4,
            "accuracy": 0.67,
            "round_details": [],
        },
    )

    print(manager.summary())
    print(manager.export_json())
    print(manager.ppmi_alignment_template())
