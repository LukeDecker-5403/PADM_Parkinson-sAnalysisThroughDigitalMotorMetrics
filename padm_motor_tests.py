"""
padm_motor_tests.py

Backend-only motor assessment module for PADM.
No UI is included here. The interface layer calls these classes to collect,
aggregate, and export participant motor-assessment results.

Tests supported:
1. Tapping speed test
   - left hand
   - right hand
   - alternating tapping
2. Tremor rate estimation test
3. Tracing precision test
   - line / zigzag / maze-style paths
   - circular path support

Author: Luke Decker project scaffold
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import math
import statistics

try:
    import numpy as np
except ImportError:  # Keeps tremor estimation usable even if NumPy is not installed.
    np = None


Point = Tuple[float, float]
TimedPoint = Tuple[float, float, float]  # (timestamp, x, y)


# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------

def normalize_label(value: str | None) -> str:
    """Convert UI labels into stable export keys."""
    if not value:
        return "unspecified"
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def display_label(value: str | None) -> str:
    """Convert internal keys into participant-facing labels."""
    if not value:
        return "Unspecified"
    return value.replace("_", "-").title()


def euclidean_distance(p1: Point, p2: Point) -> float:
    return math.dist(p1, p2)


def path_length(points: List[Point]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(euclidean_distance(points[i - 1], points[i]) for i in range(1, len(points)))


def point_to_segment_distance(p: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    px, py = p

    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay

    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq == 0:
        return euclidean_distance(p, a)

    t = (apx * abx + apy * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))

    closest = (ax + t * abx, ay + t * aby)
    return euclidean_distance(p, closest)


def point_to_polyline_distance(p: Point, polyline: List[Point]) -> float:
    if not polyline:
        raise ValueError("Polyline cannot be empty.")
    if len(polyline) == 1:
        return euclidean_distance(p, polyline[0])

    return min(
        point_to_segment_distance(p, polyline[i - 1], polyline[i])
        for i in range(1, len(polyline))
    )


def make_circle_path(
    center_x: float,
    center_y: float,
    radius: float,
    point_count: int = 96,
) -> List[Point]:
    """Create a circular tracing target path for the fourth tracing trial."""
    if point_count < 8:
        raise ValueError("point_count must be at least 8 for a usable circle path.")
    return [
        (
            center_x + radius * math.cos((2.0 * math.pi * i) / point_count),
            center_y + radius * math.sin((2.0 * math.pi * i) / point_count),
        )
        for i in range(point_count + 1)
    ]


def _mean_optional(values: List[Optional[float]]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    return statistics.mean(cleaned) if cleaned else None


def _std_optional(values: List[Optional[float]]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None
    return statistics.pstdev(cleaned) if len(cleaned) > 1 else 0.0


# -----------------------------------------------------------------------------
# Result data classes
# -----------------------------------------------------------------------------

@dataclass
class TappingTestResult:
    """Results from one tapping-speed trial."""
    hand: str
    total_taps: int
    duration_seconds: float
    taps_per_second: float
    average_interval_seconds: Optional[float]
    interval_std_seconds: Optional[float]
    tap_mode: str = "single_hand"
    left_taps: int = 0
    right_taps: int = 0
    alternation_accuracy: Optional[float] = None
    first_tap_seconds: Optional[float] = None
    last_tap_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TremorTestResult:
    """Results from one tremor-rate trial."""
    hand: str
    duration_seconds: float
    sample_count: int
    estimated_frequency_hz: Optional[float]
    mean_amplitude: Optional[float]
    rms_amplitude: Optional[float]
    method: str
    movement_area: Optional[float] = None
    signal_quality: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TracingTestResult:
    """Results from one tracing-precision trial."""
    duration_seconds: float
    sample_count: int
    mean_deviation: Optional[float]
    max_deviation: Optional[float]
    path_efficiency: Optional[float]
    completion_ratio: Optional[float]
    shape_name: str = "unspecified"
    target_path_length: Optional[float] = None
    traced_path_length: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -----------------------------------------------------------------------------
# Tapping speed test
# -----------------------------------------------------------------------------

class TappingSpeedTest:
    """
    Collects tap timestamps and computes tapping speed metrics.

    `hand` can be "left", "right", "dominant", "non-dominant", or "alternating".
    `target_duration_seconds` lets the UI score a fixed 10-second test window instead
    of using only the time between the first and last tap.
    """

    def __init__(self, hand: str, target_duration_seconds: Optional[float] = None):
        self.hand = normalize_label(hand)
        self.target_duration_seconds = target_duration_seconds
        self._tap_times: List[float] = []
        self._tap_sides: List[Optional[str]] = []

    def record_tap(self, timestamp: float, tap_side: Optional[str] = None) -> None:
        self._tap_times.append(timestamp)
        self._tap_sides.append(normalize_label(tap_side) if tap_side else None)

    def reset(self) -> None:
        self._tap_times.clear()
        self._tap_sides.clear()

    def finalize(self) -> TappingTestResult:
        total_taps = len(self._tap_times)
        first_tap = min(self._tap_times) if self._tap_times else None
        last_tap = max(self._tap_times) if self._tap_times else None

        if self.target_duration_seconds is not None and self.target_duration_seconds > 0:
            duration = float(self.target_duration_seconds)
        elif total_taps >= 2 and first_tap is not None and last_tap is not None:
            duration = max(0.0, last_tap - first_tap)
        else:
            duration = 0.0

        intervals = [
            self._tap_times[i] - self._tap_times[i - 1]
            for i in range(1, total_taps)
            if self._tap_times[i] >= self._tap_times[i - 1]
        ]

        taps_per_second = (total_taps / duration) if duration > 0 else 0.0
        left_taps = sum(1 for side in self._tap_sides if side == "left")
        right_taps = sum(1 for side in self._tap_sides if side == "right")
        alternation_accuracy = self._compute_alternation_accuracy()

        return TappingTestResult(
            hand=self.hand,
            total_taps=total_taps,
            duration_seconds=duration,
            taps_per_second=taps_per_second,
            average_interval_seconds=statistics.mean(intervals) if intervals else None,
            interval_std_seconds=statistics.pstdev(intervals) if len(intervals) > 1 else 0.0 if intervals else None,
            tap_mode="alternating" if self.hand == "alternating" else "single_hand",
            left_taps=left_taps,
            right_taps=right_taps,
            alternation_accuracy=alternation_accuracy,
            first_tap_seconds=first_tap,
            last_tap_seconds=last_tap,
        )

    def _compute_alternation_accuracy(self) -> Optional[float]:
        sides = [side for side in self._tap_sides if side in {"left", "right"}]
        if self.hand != "alternating" or len(sides) < 2:
            return None

        successful_transitions = sum(
            1 for i in range(1, len(sides)) if sides[i] != sides[i - 1]
        )
        return successful_transitions / (len(sides) - 1)


# -----------------------------------------------------------------------------
# Tremor rate test
# -----------------------------------------------------------------------------

class TremorRateTest:
    """Estimates tremor frequency from cursor/touchpad motion using FFT or zero crossing."""

    def __init__(self, hand: str):
        self.hand = normalize_label(hand)
        self._samples: List[TimedPoint] = []

    def add_sample(self, timestamp: float, x: float, y: float) -> None:
        self._samples.append((timestamp, x, y))

    def reset(self) -> None:
        self._samples.clear()

    def finalize(self) -> TremorTestResult:
        if len(self._samples) < 5:
            return TremorTestResult(
                hand=self.hand,
                duration_seconds=0.0,
                sample_count=len(self._samples),
                estimated_frequency_hz=None,
                mean_amplitude=None,
                rms_amplitude=None,
                method="insufficient_data",
                movement_area=None,
                signal_quality="insufficient_data",
            )

        times = [s[0] for s in self._samples]
        xs = [s[1] for s in self._samples]
        ys = [s[2] for s in self._samples]

        duration = times[-1] - times[0]
        if duration <= 0:
            return TremorTestResult(
                hand=self.hand,
                duration_seconds=0.0,
                sample_count=len(self._samples),
                estimated_frequency_hz=None,
                mean_amplitude=None,
                rms_amplitude=None,
                method="invalid_timestamps",
                movement_area=None,
                signal_quality="invalid_timestamps",
            )

        mean_x = statistics.mean(xs)
        mean_y = statistics.mean(ys)
        radial = [math.sqrt((x - mean_x) ** 2 + (y - mean_y) ** 2) for x, y in zip(xs, ys)]

        mean_amplitude = statistics.mean(radial) if radial else None
        rms_amplitude = math.sqrt(sum(v * v for v in radial) / len(radial)) if radial else None
        movement_area = (max(xs) - min(xs)) * (max(ys) - min(ys)) if xs and ys else None
        signal_quality = self._estimate_signal_quality(duration, len(self._samples), rms_amplitude)

        if np is not None:
            estimated_hz = self._estimate_frequency_fft(times, radial)
            method = "fft"
        else:
            estimated_hz = self._estimate_frequency_zero_crossing(times, radial)
            method = "zero_crossing"

        return TremorTestResult(
            hand=self.hand,
            duration_seconds=duration,
            sample_count=len(self._samples),
            estimated_frequency_hz=estimated_hz,
            mean_amplitude=mean_amplitude,
            rms_amplitude=rms_amplitude,
            method=method,
            movement_area=movement_area,
            signal_quality=signal_quality,
        )

    def _estimate_signal_quality(
        self,
        duration: float,
        sample_count: int,
        rms_amplitude: Optional[float],
    ) -> str:
        if duration <= 0 or sample_count < 5:
            return "insufficient_data"
        sample_rate = sample_count / duration
        if sample_rate < 15:
            return "low_sample_rate"
        if rms_amplitude is not None and rms_amplitude < 0.5:
            return "low_motion"
        return "usable"

    def _estimate_frequency_fft(self, times: List[float], signal: List[float]) -> Optional[float]:
        if np is None or len(signal) < 8:
            return None

        dt_list = [times[i] - times[i - 1] for i in range(1, len(times))]
        mean_dt = sum(dt_list) / len(dt_list)
        if mean_dt <= 0:
            return None

        arr = np.array(signal, dtype=float)
        arr = arr - np.mean(arr)

        if np.allclose(arr, 0):
            return 0.0

        fft_vals = np.fft.rfft(arr)
        freqs = np.fft.rfftfreq(len(arr), d=mean_dt)

        band_mask = (freqs >= 1.0) & (freqs <= 20.0)
        if not np.any(band_mask):
            return None

        band_freqs = freqs[band_mask]
        band_power = np.abs(fft_vals[band_mask])

        if len(band_power) == 0:
            return None

        dominant_idx = int(np.argmax(band_power))
        return float(band_freqs[dominant_idx])

    def _estimate_frequency_zero_crossing(self, times: List[float], signal: List[float]) -> Optional[float]:
        if not signal:
            return None
        mean_signal = statistics.mean(signal)
        centered = [v - mean_signal for v in signal]
        crossings = []

        for i in range(1, len(centered)):
            crossed_up = centered[i - 1] <= 0 < centered[i]
            crossed_down = centered[i - 1] >= 0 > centered[i]
            if crossed_up or crossed_down:
                crossings.append(times[i])

        if len(crossings) < 3:
            return None

        avg_crossing_interval = statistics.mean(
            crossings[i] - crossings[i - 1] for i in range(1, len(crossings))
        )

        if avg_crossing_interval <= 0:
            return None

        return 1.0 / (2.0 * avg_crossing_interval)


# -----------------------------------------------------------------------------
# Tracing precision test
# -----------------------------------------------------------------------------

class TracingPrecisionTest:
    """Evaluates tracing accuracy by comparing the user path to a target path."""

    def __init__(self, target_path: List[Point], shape_name: str = "unspecified"):
        if len(target_path) < 2:
            raise ValueError("Target path must have at least 2 points.")
        self.target_path = target_path
        self.shape_name = normalize_label(shape_name)
        self._trace_samples: List[TimedPoint] = []

    def add_sample(self, timestamp: float, x: float, y: float) -> None:
        self._trace_samples.append((timestamp, x, y))

    def reset(self) -> None:
        self._trace_samples.clear()

    def finalize(self) -> TracingTestResult:
        if len(self._trace_samples) < 2:
            return TracingTestResult(
                duration_seconds=0.0,
                sample_count=len(self._trace_samples),
                mean_deviation=None,
                max_deviation=None,
                path_efficiency=None,
                completion_ratio=None,
                shape_name=self.shape_name,
                target_path_length=path_length(self.target_path),
                traced_path_length=0.0,
            )

        times = [s[0] for s in self._trace_samples]
        trace_points = [(s[1], s[2]) for s in self._trace_samples]

        duration = max(0.0, times[-1] - times[0])
        deviations = [point_to_polyline_distance(p, self.target_path) for p in trace_points]

        user_path_len = path_length(trace_points)
        target_len = path_length(self.target_path)
        straight_line = euclidean_distance(trace_points[0], trace_points[-1])

        if self.shape_name == "circle" and target_len > 0:
            path_efficiency = min(user_path_len / target_len, target_len / user_path_len) if user_path_len > 0 else None
        else:
            path_efficiency = (straight_line / user_path_len) if user_path_len > 0 else None

        completion_ratio = self._estimate_completion_ratio(trace_points)

        return TracingTestResult(
            duration_seconds=duration,
            sample_count=len(self._trace_samples),
            mean_deviation=statistics.mean(deviations) if deviations else None,
            max_deviation=max(deviations) if deviations else None,
            path_efficiency=path_efficiency,
            completion_ratio=completion_ratio,
            shape_name=self.shape_name,
            target_path_length=target_len,
            traced_path_length=user_path_len,
        )

    def _estimate_completion_ratio(self, trace_points: List[Point]) -> float:
        """Estimate how much of the target path the participant reached."""
        if not self.target_path or not trace_points:
            return 0.0

        threshold = 18.0
        sampled_target = self._sample_target_path(max_points=50)
        covered = 0

        for target_point in sampled_target:
            min_dist = min(euclidean_distance(target_point, tp) for tp in trace_points)
            if min_dist <= threshold:
                covered += 1

        return covered / len(sampled_target) if sampled_target else 0.0

    def _sample_target_path(self, max_points: int = 50) -> List[Point]:
        if len(self.target_path) <= max_points:
            return self.target_path

        step = (len(self.target_path) - 1) / (max_points - 1)
        sampled = []
        for i in range(max_points):
            idx = int(round(i * step))
            sampled.append(self.target_path[min(idx, len(self.target_path) - 1)])
        return sampled


# -----------------------------------------------------------------------------
# Averaging helpers
# -----------------------------------------------------------------------------

def average_tapping_results(results: List[TappingTestResult], hand: str) -> Dict[str, Any]:
    if not results:
        raise ValueError("No tapping results supplied.")

    return {
        "hand": normalize_label(hand),
        "display_hand": display_label(hand),
        "tap_mode": "alternating" if normalize_label(hand) == "alternating" else "single_hand",
        "trial_count": len(results),
        "trial_results": [r.to_dict() for r in results],
        "total_taps": int(round(statistics.mean(r.total_taps for r in results))),
        "duration_seconds": statistics.mean(r.duration_seconds for r in results),
        "taps_per_second": statistics.mean(r.taps_per_second for r in results),
        "average_interval_seconds": _mean_optional([r.average_interval_seconds for r in results]),
        "interval_std_seconds": _mean_optional([r.interval_std_seconds for r in results]),
        "left_taps": int(round(statistics.mean(r.left_taps for r in results))),
        "right_taps": int(round(statistics.mean(r.right_taps for r in results))),
        "alternation_accuracy": _mean_optional([r.alternation_accuracy for r in results]),
    }


def average_tapping_battery(results_by_mode: Dict[str, List[TappingTestResult]]) -> Dict[str, Any]:
    """Average the full left/right/alternating tapping battery for one participant."""
    averaged_modes = {}
    for mode, mode_results in results_by_mode.items():
        if mode_results:
            averaged_modes[normalize_label(mode)] = average_tapping_results(mode_results, hand=mode)

    tps_values = [v["taps_per_second"] for v in averaged_modes.values() if v.get("taps_per_second") is not None]
    interval_values = [v["average_interval_seconds"] for v in averaged_modes.values() if v.get("average_interval_seconds") is not None]

    return {
        "test_name": "tapping_battery",
        "mode_count": len(averaged_modes),
        "modes": averaged_modes,
        "average_taps_per_second": statistics.mean(tps_values) if tps_values else 0.0,
        "average_interval_seconds": statistics.mean(interval_values) if interval_values else None,
        "left_taps_per_second": averaged_modes.get("left", {}).get("taps_per_second"),
        "right_taps_per_second": averaged_modes.get("right", {}).get("taps_per_second"),
        "alternating_taps_per_second": averaged_modes.get("alternating", {}).get("taps_per_second"),
        "alternation_accuracy": averaged_modes.get("alternating", {}).get("alternation_accuracy"),
    }


def average_tremor_results(results: List[TremorTestResult], hand: str) -> Dict[str, Any]:
    if not results:
        raise ValueError("No tremor results supplied.")

    return {
        "hand": normalize_label(hand),
        "display_hand": display_label(hand),
        "trial_count": len(results),
        "trial_results": [r.to_dict() for r in results],
        "duration_seconds": statistics.mean(r.duration_seconds for r in results),
        "sample_count": int(round(statistics.mean(r.sample_count for r in results))),
        "estimated_frequency_hz": _mean_optional([r.estimated_frequency_hz for r in results]),
        "estimated_frequency_std_hz": _std_optional([r.estimated_frequency_hz for r in results]),
        "mean_amplitude": _mean_optional([r.mean_amplitude for r in results]),
        "rms_amplitude": _mean_optional([r.rms_amplitude for r in results]),
        "movement_area": _mean_optional([r.movement_area for r in results]),
        "method": "averaged",
        "signal_quality": "usable" if any(r.signal_quality == "usable" for r in results) else "review_needed",
    }


def average_tracing_results(results: List[TracingTestResult]) -> Dict[str, Any]:
    if not results:
        raise ValueError("No tracing results supplied.")

    return {
        "trial_count": len(results),
        "trial_results": [r.to_dict() for r in results],
        "shape_names": [r.shape_name for r in results],
        "duration_seconds": statistics.mean(r.duration_seconds for r in results),
        "sample_count": int(round(statistics.mean(r.sample_count for r in results))),
        "mean_deviation": _mean_optional([r.mean_deviation for r in results]),
        "max_deviation": _mean_optional([r.max_deviation for r in results]),
        "path_efficiency": _mean_optional([r.path_efficiency for r in results]),
        "completion_ratio": _mean_optional([r.completion_ratio for r in results]),
        "target_path_length": _mean_optional([r.target_path_length for r in results]),
        "traced_path_length": _mean_optional([r.traced_path_length for r in results]),
    }


class MotorAssessmentSession:
    """Collects and exports results from multiple motor assessment tests."""

    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}

    def save_result(self, test_name: str, result) -> None:
        key = normalize_label(test_name)
        if hasattr(result, "to_dict"):
            self.results[key] = result.to_dict()
        elif isinstance(result, dict):
            self.results[key] = result
        else:
            raise TypeError("Result must be a dict or expose a to_dict() method.")

    def export(self) -> Dict[str, Any]:
        return self.results


if __name__ == "__main__":
    tapping = TappingSpeedTest(hand="left", target_duration_seconds=10.0)
    tap_times = [0.00, 0.19, 0.37, 0.56, 0.75, 0.93, 1.12]
    for t in tap_times:
        tapping.record_tap(t, tap_side="left")
    tap_result = tapping.finalize()
    print("TAPPING RESULT")
    print(tap_result.to_dict())

    tremor = TremorRateTest(hand="dominant")
    for i in range(200):
        t = i * 0.01
        x = 100 + 3 * math.sin(2 * math.pi * 5 * t)
        y = 100 + 2 * math.cos(2 * math.pi * 5 * t)
        tremor.add_sample(t, x, y)
    tremor_result = tremor.finalize()
    print("\nTREMOR RESULT")
    print(tremor_result.to_dict())

    circle_target = make_circle_path(150, 150, 75)
    tracing = TracingPrecisionTest(target_path=circle_target, shape_name="circle")
    for i, (x, y) in enumerate(circle_target[:40]):
        tracing.add_sample(i * 0.05, x + 2, y - 2)
    tracing_result = tracing.finalize()
    print("\nTRACING RESULT")
    print(tracing_result.to_dict())

    print("\nAVERAGED TAPPING")
    print(average_tapping_results([tap_result, tap_result, tap_result], hand="left"))
