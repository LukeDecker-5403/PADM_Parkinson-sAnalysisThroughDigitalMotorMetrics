"""
padm_motor_tests.py

Backend-only motor assessment module for PADM.
No UI is included here. The interface layer can call these classes later.

Tests implemented:
1. Tapping speed test
2. Tremor rate estimation test
3. Tracing precision test

Author: Luke Decker project scaffold
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Dict, Any
import math
import statistics

try:
    import numpy as np
except ImportError:
    np = None


Point = Tuple[float, float]
TimedPoint = Tuple[float, float, float]  # (timestamp, x, y)


@dataclass
class TappingTestResult:
    """Results from tapping speed assessment."""
    hand: str
    total_taps: int
    duration_seconds: float
    taps_per_second: float
    average_interval_seconds: Optional[float]
    interval_std_seconds: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TremorTestResult:
    """Results from tremor rate assessment."""
    hand: str
    duration_seconds: float
    sample_count: int
    estimated_frequency_hz: Optional[float]
    mean_amplitude: Optional[float]
    rms_amplitude: Optional[float]
    method: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TracingTestResult:
    """Results from tracing precision assessment."""
    duration_seconds: float
    sample_count: int
    mean_deviation: Optional[float]
    max_deviation: Optional[float]
    path_efficiency: Optional[float]
    completion_ratio: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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


class TappingSpeedTest:
    """Collects tap timestamps and computes tapping speed metrics."""

    def __init__(self, hand: str):
        self.hand = hand
        self._tap_times: List[float] = []

    def record_tap(self, timestamp: float) -> None:
        self._tap_times.append(timestamp)

    def reset(self) -> None:
        self._tap_times.clear()

    def finalize(self) -> TappingTestResult:
        if len(self._tap_times) < 2:
            duration = 0.0
            return TappingTestResult(
                hand=self.hand,
                total_taps=len(self._tap_times),
                duration_seconds=duration,
                taps_per_second=0.0,
                average_interval_seconds=None,
                interval_std_seconds=None,
            )

        duration = self._tap_times[-1] - self._tap_times[0]
        intervals = [
            self._tap_times[i] - self._tap_times[i - 1]
            for i in range(1, len(self._tap_times))
        ]

        taps_per_second = len(self._tap_times) / duration if duration > 0 else 0.0

        return TappingTestResult(
            hand=self.hand,
            total_taps=len(self._tap_times),
            duration_seconds=duration,
            taps_per_second=taps_per_second,
            average_interval_seconds=statistics.mean(intervals) if intervals else None,
            interval_std_seconds=statistics.pstdev(intervals) if len(intervals) > 1 else 0.0 if intervals else None,
        )


class TremorRateTest:
    """Estimates tremor frequency from cursor/touchpad motion using FFT or zero-crossing."""

    def __init__(self, hand: str):
        self.hand = hand
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
            )

        mean_x = statistics.mean(xs)
        mean_y = statistics.mean(ys)
        radial = [math.sqrt((x - mean_x) ** 2 + (y - mean_y) ** 2) for x, y in zip(xs, ys)]

        mean_amplitude = statistics.mean(radial) if radial else None
        rms_amplitude = math.sqrt(sum(v * v for v in radial) / len(radial)) if radial else None

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
        )

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
        centered = [v - statistics.mean(signal) for v in signal]
        crossings = []

        for i in range(1, len(centered)):
            if centered[i - 1] <= 0 < centered[i] or centered[i - 1] >= 0 > centered[i]:
                crossings.append(times[i])

        if len(crossings) < 3:
            return None

        avg_crossing_interval = statistics.mean(
            crossings[i] - crossings[i - 1] for i in range(1, len(crossings))
        )

        if avg_crossing_interval <= 0:
            return None

        return 1.0 / (2.0 * avg_crossing_interval)


class TracingPrecisionTest:
    """Evaluates tracing accuracy by comparing user path to target path."""

    def __init__(self, target_path: List[Point]):
        if len(target_path) < 2:
            raise ValueError("Target path must have at least 2 points.")
        self.target_path = target_path
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
            )

        times = [s[0] for s in self._trace_samples]
        trace_points = [(s[1], s[2]) for s in self._trace_samples]

        duration = times[-1] - times[0]
        deviations = [point_to_polyline_distance(p, self.target_path) for p in trace_points]

        user_path_len = path_length(trace_points)
        straight_line = euclidean_distance(trace_points[0], trace_points[-1])
        path_efficiency = (straight_line / user_path_len) if user_path_len > 0 else None

        completion_ratio = self._estimate_completion_ratio(trace_points)

        return TracingTestResult(
            duration_seconds=duration,
            sample_count=len(self._trace_samples),
            mean_deviation=statistics.mean(deviations) if deviations else None,
            max_deviation=max(deviations) if deviations else None,
            path_efficiency=path_efficiency,
            completion_ratio=completion_ratio,
        )

    def _estimate_completion_ratio(self, trace_points: List[Point]) -> float:
        if not self.target_path:
            return 0.0

        threshold = 15.0
        covered = 0

        for target_point in self.target_path:
            min_dist = min(euclidean_distance(target_point, tp) for tp in trace_points)
            if min_dist <= threshold:
                covered += 1

        return covered / len(self.target_path)


def _mean_optional(values: List[Optional[float]]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    return statistics.mean(cleaned) if cleaned else None


def average_tapping_results(results: List[TappingTestResult], hand: str) -> Dict[str, Any]:
    if not results:
        raise ValueError("No tapping results supplied.")

    return {
        "hand": hand,
        "trial_count": len(results),
        "trial_results": [r.to_dict() for r in results],
        "total_taps": int(round(statistics.mean(r.total_taps for r in results))),
        "duration_seconds": statistics.mean(r.duration_seconds for r in results),
        "taps_per_second": statistics.mean(r.taps_per_second for r in results),
        "average_interval_seconds": _mean_optional([r.average_interval_seconds for r in results]),
        "interval_std_seconds": _mean_optional([r.interval_std_seconds for r in results]),
    }


def average_tremor_results(results: List[TremorTestResult], hand: str) -> Dict[str, Any]:
    if not results:
        raise ValueError("No tremor results supplied.")

    return {
        "hand": hand,
        "trial_count": len(results),
        "trial_results": [r.to_dict() for r in results],
        "duration_seconds": statistics.mean(r.duration_seconds for r in results),
        "sample_count": int(round(statistics.mean(r.sample_count for r in results))),
        "estimated_frequency_hz": _mean_optional([r.estimated_frequency_hz for r in results]),
        "mean_amplitude": _mean_optional([r.mean_amplitude for r in results]),
        "rms_amplitude": _mean_optional([r.rms_amplitude for r in results]),
        "method": "averaged",
    }


def average_tracing_results(results: List[TracingTestResult]) -> Dict[str, Any]:
    if not results:
        raise ValueError("No tracing results supplied.")

    return {
        "trial_count": len(results),
        "trial_results": [r.to_dict() for r in results],
        "duration_seconds": statistics.mean(r.duration_seconds for r in results),
        "sample_count": int(round(statistics.mean(r.sample_count for r in results))),
        "mean_deviation": _mean_optional([r.mean_deviation for r in results]),
        "max_deviation": _mean_optional([r.max_deviation for r in results]),
        "path_efficiency": _mean_optional([r.path_efficiency for r in results]),
        "completion_ratio": _mean_optional([r.completion_ratio for r in results]),
    }


class MotorAssessmentSession:
    """Collects and exports results from multiple motor assessment tests."""

    def __init__(self):
        self.results = {}

    def save_result(self, test_name: str, result) -> None:
        if hasattr(result, "to_dict"):
            self.results[test_name] = result.to_dict()
        elif isinstance(result, dict):
            self.results[test_name] = result
        else:
            raise TypeError("Result must be a dict or expose a to_dict() method.")

    def export(self) -> Dict[str, Any]:
        return self.results


if __name__ == "__main__":
    tapping = TappingSpeedTest(hand="dominant")
    tap_times = [0.00, 0.19, 0.37, 0.56, 0.75, 0.93, 1.12]
    for t in tap_times:
        tapping.record_tap(t)
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

    target = [(0, 0), (50, 0), (100, 0), (150, 0)]
    tracing = TracingPrecisionTest(target_path=target)

    demo_trace = [
        (0.0, 0, 2),
        (0.1, 25, -1),
        (0.2, 50, 3),
        (0.3, 75, -2),
        (0.4, 100, 1),
        (0.5, 125, -1),
        (0.6, 150, 0),
    ]
    for sample in demo_trace:
        tracing.add_sample(*sample)
    tracing_result = tracing.finalize()
    print("\nTRACING RESULT")
    print(tracing_result.to_dict())

    print("\nAVERAGED TAPPING")
    print(average_tapping_results([tap_result, tap_result, tap_result], hand="dominant"))