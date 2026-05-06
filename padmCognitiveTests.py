"""
padmCognitiveTests.py

Backend-only cognitive assessment module for PADM.
The UI layer calls these classes to collect structured cognitive testing data.

Tests implemented:
1. Reaction time test
2. Sequence memory test
3. Symbol / shape matching processing-speed test

Current workflow support:
- Stores participant-safe aggregate metrics for graphing
- Stores detailed trial/item data for hidden raw-results review
- Supports autosaving from the UI as each cognitive test is completed
- Keeps method names compatible with the existing PADM UI

Author: Luke Decker
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import statistics


# -----------------------------------------------------------------------------
# RESULT DATA CLASSES
# -----------------------------------------------------------------------------

@dataclass
class ReactionTimeTestResult:
    """Aggregated result from the reaction-time assessment."""
    total_trials: int
    valid_trials: int
    average_reaction_time_ms: Optional[float]
    min_reaction_time_ms: Optional[float]
    max_reaction_time_ms: Optional[float]
    reaction_time_std_ms: Optional[float]
    trial_reaction_times_ms: List[float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to a plain dictionary for JSON export."""
        return asdict(self)


@dataclass
class SequenceMemoryTestResult:
    """Aggregated result from the sequence-memory assessment."""
    total_rounds: int
    correct_rounds: int
    longest_correct_span: int
    accuracy: float
    attempted_spans: List[int]
    round_details: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to a plain dictionary for JSON export."""
        return asdict(self)


@dataclass
class SymbolMatchingTestResult:
    """Aggregated result from symbol / shape matching processing-speed assessment."""
    total_items: int
    correct_items: int
    incorrect_items: int
    duration_seconds: float
    accuracy: float
    items_per_second: float
    symbol_items: int
    shape_items: int
    item_details: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to a plain dictionary for JSON export."""
        return asdict(self)


# -----------------------------------------------------------------------------
# REACTION TIME TEST
# -----------------------------------------------------------------------------

class ReactionTimeTest:
    """
    Collects reaction times for multiple trials.

    The UI is responsible for creating the visual GO signal and randomized wait
    period. This backend stores only the measured stimulus/response timing.
    """

    def __init__(self) -> None:
        self._reaction_times_ms: List[float] = []

    def record_trial(self, stimulus_time: float, response_time: float) -> None:
        """Record one valid trial using stimulus and response timestamps in seconds."""
        delta_ms = (response_time - stimulus_time) * 1000.0
        if delta_ms >= 0:
            self._reaction_times_ms.append(delta_ms)

    def reset(self) -> None:
        """Clear all recorded reaction-time trials."""
        self._reaction_times_ms.clear()

    def finalize(self) -> ReactionTimeTestResult:
        """Compute aggregate reaction-time metrics."""
        if not self._reaction_times_ms:
            return ReactionTimeTestResult(
                total_trials=0,
                valid_trials=0,
                average_reaction_time_ms=None,
                min_reaction_time_ms=None,
                max_reaction_time_ms=None,
                reaction_time_std_ms=None,
                trial_reaction_times_ms=[],
            )

        return ReactionTimeTestResult(
            total_trials=len(self._reaction_times_ms),
            valid_trials=len(self._reaction_times_ms),
            average_reaction_time_ms=statistics.mean(self._reaction_times_ms),
            min_reaction_time_ms=min(self._reaction_times_ms),
            max_reaction_time_ms=max(self._reaction_times_ms),
            reaction_time_std_ms=(
                statistics.pstdev(self._reaction_times_ms)
                if len(self._reaction_times_ms) > 1
                else 0.0
            ),
            trial_reaction_times_ms=list(self._reaction_times_ms),
        )


# -----------------------------------------------------------------------------
# SEQUENCE MEMORY TEST
# -----------------------------------------------------------------------------

class SequenceMemoryTest:
    """
    Tracks correctness across memory-sequence rounds.

    The UI can hide correctness from the participant while this backend still
    stores correctness internally for analysis and export.
    """

    def __init__(self) -> None:
        self._rounds: List[Dict[str, Any]] = []

    def record_round(self, expected_sequence: List[int], user_sequence: List[int]) -> None:
        """Record one memory round."""
        is_correct = expected_sequence == user_sequence
        self._rounds.append(
            {
                "round_number": len(self._rounds) + 1,
                "span": len(expected_sequence),
                "expected_sequence": list(expected_sequence),
                "user_sequence": list(user_sequence),
                "correct": is_correct,
            }
        )

    def reset(self) -> None:
        """Clear all recorded memory rounds."""
        self._rounds.clear()

    def finalize(self) -> SequenceMemoryTestResult:
        """Compute sequence-memory metrics."""
        if not self._rounds:
            return SequenceMemoryTestResult(
                total_rounds=0,
                correct_rounds=0,
                longest_correct_span=0,
                accuracy=0.0,
                attempted_spans=[],
                round_details=[],
            )

        correct_rounds = sum(1 for round_data in self._rounds if round_data["correct"])
        longest_correct_span = max(
            (round_data["span"] for round_data in self._rounds if round_data["correct"]),
            default=0,
        )

        return SequenceMemoryTestResult(
            total_rounds=len(self._rounds),
            correct_rounds=correct_rounds,
            longest_correct_span=longest_correct_span,
            accuracy=correct_rounds / len(self._rounds),
            attempted_spans=[round_data["span"] for round_data in self._rounds],
            round_details=[dict(round_data) for round_data in self._rounds],
        )


# -----------------------------------------------------------------------------
# SYMBOL / SHAPE MATCHING TEST
# -----------------------------------------------------------------------------

class SymbolMatchingTest:
    """
    Tracks correct and incorrect responses during a processing-speed task.

    Backward compatible method:
    - record_response(is_correct)

    Expanded method for the updated UI:
    - record_item(...), which stores whether the item was a symbol or shape trial.
    """

    def __init__(self) -> None:
        self._correct = 0
        self._incorrect = 0
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._items: List[Dict[str, Any]] = []

    def start(self, timestamp: float) -> None:
        """Start the processing-speed timer and reset prior data."""
        self._start_time = timestamp
        self._end_time = None
        self._correct = 0
        self._incorrect = 0
        self._items.clear()

    def record_response(self, is_correct: bool) -> None:
        """
        Record whether one item was answered correctly.

        This method is kept for compatibility with older UI calls.
        """
        self.record_item(
            item_type="symbol",
            left_item=None,
            right_item=None,
            expected_same=None,
            user_said_same=None,
            is_correct=is_correct,
        )

    def record_item(
        self,
        item_type: str,
        left_item: Any,
        right_item: Any,
        expected_same: Optional[bool],
        user_said_same: Optional[bool],
        is_correct: bool,
    ) -> None:
        """
        Record one symbol or shape matching item with analysis-friendly details.

        item_type should usually be "symbol" or "shape".
        """
        normalized_type = item_type.strip().lower() if item_type else "symbol"
        if normalized_type not in {"symbol", "shape"}:
            normalized_type = "symbol"

        if is_correct:
            self._correct += 1
        else:
            self._incorrect += 1

        self._items.append(
            {
                "item_number": len(self._items) + 1,
                "item_type": normalized_type,
                "left_item": left_item,
                "right_item": right_item,
                "expected_same": expected_same,
                "user_said_same": user_said_same,
                "correct": is_correct,
            }
        )

    def stop(self, timestamp: float) -> None:
        """Stop the processing-speed timer."""
        self._end_time = timestamp

    def reset(self) -> None:
        """Clear all recorded processing-speed data."""
        self._correct = 0
        self._incorrect = 0
        self._start_time = None
        self._end_time = None
        self._items.clear()

    def finalize(self) -> SymbolMatchingTestResult:
        """Compute processing-speed metrics."""
        total_items = self._correct + self._incorrect
        duration = 0.0

        if self._start_time is not None and self._end_time is not None:
            duration = max(0.0, self._end_time - self._start_time)

        accuracy = (self._correct / total_items) if total_items > 0 else 0.0
        items_per_second = (total_items / duration) if duration > 0 else 0.0
        symbol_items = sum(1 for item in self._items if item["item_type"] == "symbol")
        shape_items = sum(1 for item in self._items if item["item_type"] == "shape")

        return SymbolMatchingTestResult(
            total_items=total_items,
            correct_items=self._correct,
            incorrect_items=self._incorrect,
            duration_seconds=duration,
            accuracy=accuracy,
            items_per_second=items_per_second,
            symbol_items=symbol_items,
            shape_items=shape_items,
            item_details=[dict(item) for item in self._items],
        )


# -----------------------------------------------------------------------------
# OPTIONAL SESSION WRAPPER
# -----------------------------------------------------------------------------

class CognitiveAssessmentSession:
    """Collects and exports results from multiple cognitive assessment tests."""

    def __init__(self) -> None:
        self.results: Dict[str, Dict[str, Any]] = {}

    def save_result(self, test_name: str, result: Any) -> None:
        """Store a cognitive test result by name."""
        if hasattr(result, "to_dict"):
            self.results[test_name] = result.to_dict()
        elif isinstance(result, dict):
            self.results[test_name] = result
        else:
            raise TypeError("Cognitive result must be a dict or expose a to_dict() method.")

    def export(self) -> Dict[str, Dict[str, Any]]:
        """Return all stored cognitive results as a dictionary."""
        return self.results

    def completed_tests(self) -> int:
        """Return the number of saved cognitive test sections."""
        return len(self.results)


# -----------------------------------------------------------------------------
# DEMO / QUICK SELF-CHECK
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    reaction = ReactionTimeTest()
    reaction.record_trial(0.00, 0.31)
    reaction.record_trial(1.00, 1.28)
    reaction.record_trial(2.00, 2.34)
    reaction_result = reaction.finalize()
    print("REACTION TIME RESULT")
    print(reaction_result.to_dict())

    memory = SequenceMemoryTest()
    memory.record_round([1, 3, 2], [1, 3, 2])
    memory.record_round([2, 4, 1, 3], [2, 4, 1, 0])
    memory.record_round([3, 1, 4, 2, 5], [3, 1, 4, 2, 5])
    memory_result = memory.finalize()
    print("\nSEQUENCE MEMORY RESULT")
    print(memory_result.to_dict())

    symbols = SymbolMatchingTest()
    symbols.start(0.0)
    symbols.record_item("symbol", "@", "@", True, True, True)
    symbols.record_item("shape", "circle", "square", False, False, True)
    symbols.record_item("shape", "triangle", "triangle", True, False, False)
    symbols.stop(12.0)
    symbols_result = symbols.finalize()
    print("\nSYMBOL / SHAPE MATCHING RESULT")
    print(symbols_result.to_dict())

    session = CognitiveAssessmentSession()
    session.save_result("reaction_time", reaction_result)
    session.save_result("sequence_memory", memory_result)
    session.save_result("symbol_matching", symbols_result)
    print("\nSESSION EXPORT")
    print(session.export())
