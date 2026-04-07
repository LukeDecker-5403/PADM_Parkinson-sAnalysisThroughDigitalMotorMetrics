"""
padm_cognitive_tests.py

Backend-only cognitive assessment module for PADM.
No UI is included here. The interface layer can call these classes later.

Tests implemented:
1. Reaction time test
2. Sequence memory test
3. Symbol matching / processing speed test

Author: Luke Decker 
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import statistics


# RESULT DATA CLASSES
# =========================================

@dataclass
class ReactionTimeTestResult:
    """Results from reaction time assessment."""
    total_trials: int
    valid_trials: int
    average_reaction_time_ms: Optional[float]
    min_reaction_time_ms: Optional[float]
    max_reaction_time_ms: Optional[float]
    reaction_time_std_ms: Optional[float]

    def to_dict(self) -> Dict:
        """Convert result to dictionary."""
        return asdict(self)


@dataclass
class SequenceMemoryTestResult:
    """Results from sequence memory assessment."""
    total_rounds: int
    correct_rounds: int
    longest_correct_span: int
    accuracy: float

    def to_dict(self) -> Dict:
        """Convert result to dictionary."""
        return asdict(self)


@dataclass
class SymbolMatchingTestResult:
    """Results from symbol matching / processing speed assessment."""
    total_items: int
    correct_items: int
    incorrect_items: int
    duration_seconds: float
    accuracy: float
    items_per_second: float

    def to_dict(self) -> Dict:
        """Convert result to dictionary."""
        return asdict(self)


# REACTION TIME TEST
# =========================================

class ReactionTimeTest:
    """Collects reaction times for multiple trials."""

    def __init__(self):
        """Initialize empty reaction time trial list."""
        self._reaction_times_ms: List[float] = []

    def record_trial(self, stimulus_time: float, response_time: float) -> None:
        """Record one trial using stimulus and response timestamps in seconds."""
        delta_ms = (response_time - stimulus_time) * 1000.0
        if delta_ms >= 0:
            self._reaction_times_ms.append(delta_ms)

    def reset(self) -> None:
        """Clear all recorded trials."""
        self._reaction_times_ms.clear()

    def finalize(self) -> ReactionTimeTestResult:
        """Compute and return reaction time results."""
        if not self._reaction_times_ms:
            return ReactionTimeTestResult(
                total_trials=0,
                valid_trials=0,
                average_reaction_time_ms=None,
                min_reaction_time_ms=None,
                max_reaction_time_ms=None,
                reaction_time_std_ms=None,
            )

        return ReactionTimeTestResult(
            total_trials=len(self._reaction_times_ms),
            valid_trials=len(self._reaction_times_ms),
            average_reaction_time_ms=statistics.mean(self._reaction_times_ms),
            min_reaction_time_ms=min(self._reaction_times_ms),
            max_reaction_time_ms=max(self._reaction_times_ms),
            reaction_time_std_ms=statistics.pstdev(self._reaction_times_ms)
            if len(self._reaction_times_ms) > 1 else 0.0,
        )


# SEQUENCE MEMORY TEST
# =========================================

class SequenceMemoryTest:
    """Tracks correctness across memory-sequence rounds."""

    def __init__(self):
        """Initialize memory test results storage."""
        self._rounds: List[Dict[str, int | bool]] = []

    def record_round(self, expected_sequence: List[int], user_sequence: List[int]) -> None:
        """Record one memory round."""
        is_correct = expected_sequence == user_sequence
        self._rounds.append({
            "span": len(expected_sequence),
            "correct": is_correct
        })

    def reset(self) -> None:
        """Clear all recorded rounds."""
        self._rounds.clear()

    def finalize(self) -> SequenceMemoryTestResult:
        """Compute and return sequence memory results."""
        if not self._rounds:
            return SequenceMemoryTestResult(
                total_rounds=0,
                correct_rounds=0,
                longest_correct_span=0,
                accuracy=0.0,
            )

        correct_rounds = sum(1 for r in self._rounds if r["correct"])
        longest_correct_span = max(
            (r["span"] for r in self._rounds if r["correct"]),
            default=0
        )

        return SequenceMemoryTestResult(
            total_rounds=len(self._rounds),
            correct_rounds=correct_rounds,
            longest_correct_span=longest_correct_span,
            accuracy=correct_rounds / len(self._rounds),
        )


# SYMBOL MATCHING / PROCESSING SPEED TEST
# =========================================

class SymbolMatchingTest:
    """Tracks correct and incorrect responses during a processing-speed task."""

    def __init__(self):
        """Initialize empty symbol matching state."""
        self._correct = 0
        self._incorrect = 0
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    def start(self, timestamp: float) -> None:
        """Start the test timer."""
        self._start_time = timestamp
        self._end_time = None
        self._correct = 0
        self._incorrect = 0

    def record_response(self, is_correct: bool) -> None:
        """Record whether one symbol/item was matched correctly."""
        if is_correct:
            self._correct += 1
        else:
            self._incorrect += 1

    def stop(self, timestamp: float) -> None:
        """Stop the test timer."""
        self._end_time = timestamp

    def reset(self) -> None:
        """Clear all recorded data."""
        self._correct = 0
        self._incorrect = 0
        self._start_time = None
        self._end_time = None

    def finalize(self) -> SymbolMatchingTestResult:
        """Compute and return symbol matching results."""
        total_items = self._correct + self._incorrect
        duration = 0.0

        if self._start_time is not None and self._end_time is not None:
            duration = max(0.0, self._end_time - self._start_time)

        accuracy = (self._correct / total_items) if total_items > 0 else 0.0
        items_per_second = (total_items / duration) if duration > 0 else 0.0

        return SymbolMatchingTestResult(
            total_items=total_items,
            correct_items=self._correct,
            incorrect_items=self._incorrect,
            duration_seconds=duration,
            accuracy=accuracy,
            items_per_second=items_per_second,
        )


# OPTIONAL SESSION WRAPPER
# =========================================

class CognitiveAssessmentSession:
    """Collects and exports results from multiple cognitive assessment tests."""

    def __init__(self):
        """Initialize empty results container."""
        self.results = {}

    def save_result(self, test_name: str, result) -> None:
        """Store test result by name."""
        self.results[test_name] = result.to_dict()

    def export(self) -> Dict:
        """Return all stored results as dictionary."""
        return self.results


# EXAMPLE USAGE
# =========================================

if __name__ == "__main__":
    # Reaction time demo
    reaction = ReactionTimeTest()
    reaction.record_trial(0.00, 0.31)
    reaction.record_trial(1.00, 1.28)
    reaction.record_trial(2.00, 2.34)
    reaction_result = reaction.finalize()
    print("REACTION TIME RESULT")
    print(reaction_result.to_dict())

    # Sequence memory demo
    memory = SequenceMemoryTest()
    memory.record_round([1, 3, 2], [1, 3, 2])
    memory.record_round([2, 4, 1, 3], [2, 4, 1, 0])
    memory.record_round([3, 1, 4, 2, 5], [3, 1, 4, 2, 5])
    memory_result = memory.finalize()
    print("\nSEQUENCE MEMORY RESULT")
    print(memory_result.to_dict())

    # Symbol matching demo
    symbols = SymbolMatchingTest()
    symbols.start(0.0)
    for value in [True, True, False, True, True, False, True]:
        symbols.record_response(value)
    symbols.stop(12.0)
    symbols_result = symbols.finalize()
    print("\nSYMBOL MATCHING RESULT")
    print(symbols_result.to_dict())

    # Session export demo
    session = CognitiveAssessmentSession()
    session.save_result("reaction_time", reaction_result)
    session.save_result("sequence_memory", memory_result)
    session.save_result("symbol_matching", symbols_result)

    print("\nSESSION EXPORT")
    print(session.export())