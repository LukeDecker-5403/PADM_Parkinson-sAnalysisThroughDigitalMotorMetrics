"""
ppmi_mobility_curve.py

PPMI / Neuro-QoL mobility reference-curve helper for PADM.

Purpose:
    Builds a mobility-based Parkinson's reference curve from the uploaded
    Neuro-QoL Lower Extremity Function / Mobility short-form CSV.

Important limitation:
    This does NOT directly validate PADM tapping, tremor, cursor, or tracing
    metrics. It creates a clinically relevant mobility-impairment reference
    curve that can be used as an early PD/NPD-style graph baseline until more
    direct digital motor datasets are integrated.

Expected CSV columns:
    PATNO, EVENT_ID, INFODT,
    NQMOB37, NQMOB30, NQMOB26, NQMOB32,
    NQMOB25, NQMOB33, NQMOB31, NQMOB28

Score logic:
    Raw Mobility Score = sum of the 8 NQMOB item responses
    Minimum possible score = 8
    Maximum possible score = 40

    Mobility Impairment Score = ((40 - Raw Mobility Score) / 32) * 100

Interpretation:
    0   = strongest reported mobility / lowest impairment
    100 = weakest reported mobility / highest impairment
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import csv
import json
import math
import statistics


MOBILITY_ITEM_COLUMNS = [
    "NQMOB37",
    "NQMOB30",
    "NQMOB26",
    "NQMOB32",
    "NQMOB25",
    "NQMOB33",
    "NQMOB31",
    "NQMOB28",
]

MIN_RAW_MOBILITY_SCORE = 8.0
MAX_RAW_MOBILITY_SCORE = 40.0
RAW_SCORE_RANGE = MAX_RAW_MOBILITY_SCORE - MIN_RAW_MOBILITY_SCORE


@dataclass
class MobilityVisitScore:
    """One scored participant visit from the Neuro-QoL mobility CSV."""
    participant_id: str
    event_id: str
    info_date: str
    raw_mobility_score: float
    mobility_impairment_score: float

    def to_dict(self) -> Dict:
        return {
            "participant_id": self.participant_id,
            "event_id": self.event_id,
            "info_date": self.info_date,
            "raw_mobility_score": self.raw_mobility_score,
            "mobility_impairment_score": self.mobility_impairment_score,
        }


def _safe_float(value) -> Optional[float]:
    """Convert a CSV value to float when possible."""
    if value is None:
        return None

    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return None

    try:
        number = float(text)
    except ValueError:
        return None

    if math.isnan(number):
        return None

    return number


def _event_sort_key(event_id: str) -> Tuple[int, str]:
    """
    Convert event labels like V04, V15, V17 into sortable visit numbers.

    Unknown labels are placed after numbered visits but still kept.
    """
    event_text = str(event_id).strip().upper()

    if event_text.startswith("V"):
        number_part = event_text[1:]
        if number_part.isdigit():
            return (int(number_part), event_text)

    if event_text.isdigit():
        return (int(event_text), event_text)

    return (9999, event_text)


def validate_required_columns(csv_path: str | Path) -> None:
    """Raise a clear error if the CSV is missing required PADM/PPMI columns."""
    csv_path = Path(csv_path)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = set(reader.fieldnames or [])

    required = {"PATNO", "EVENT_ID", "INFODT", *MOBILITY_ITEM_COLUMNS}
    missing = sorted(required - columns)

    if missing:
        raise ValueError(
            "The mobility CSV is missing required columns: "
            + ", ".join(missing)
        )


def load_mobility_visit_scores(csv_path: str | Path) -> List[MobilityVisitScore]:
    """
    Load the Neuro-QoL mobility CSV and calculate a mobility-impairment score
    for each valid participant visit.

    Rows with missing item values are skipped because the short-form score
    would otherwise be incomplete.
    """
    csv_path = Path(csv_path)
    validate_required_columns(csv_path)

    visit_scores: List[MobilityVisitScore] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            item_values = [_safe_float(row.get(col)) for col in MOBILITY_ITEM_COLUMNS]

            # Skip incomplete rows.
            if any(value is None for value in item_values):
                continue

            raw_score = float(sum(item_values))

            # Clamp to expected range in case the CSV contains irregular values.
            raw_score = max(MIN_RAW_MOBILITY_SCORE, min(MAX_RAW_MOBILITY_SCORE, raw_score))

            impairment_score = ((MAX_RAW_MOBILITY_SCORE - raw_score) / RAW_SCORE_RANGE) * 100.0

            visit_scores.append(
                MobilityVisitScore(
                    participant_id=str(row.get("PATNO", "")).strip(),
                    event_id=str(row.get("EVENT_ID", "")).strip(),
                    info_date=str(row.get("INFODT", "")).strip(),
                    raw_mobility_score=round(raw_score, 4),
                    mobility_impairment_score=round(impairment_score, 4),
                )
            )

    return visit_scores


def build_event_reference_curve(
    csv_path: str | Path,
    min_records_per_event: int = 5,
) -> List[Dict]:
    """
    Build an aggregated PD mobility reference curve by EVENT_ID.

    Returns a list of dictionaries:
        event_id
        visit_order
        participant_count
        mean_raw_mobility_score
        mean_mobility_impairment_score
        median_mobility_impairment_score
        std_mobility_impairment_score
    """
    visit_scores = load_mobility_visit_scores(csv_path)

    grouped: Dict[str, List[MobilityVisitScore]] = {}
    for score in visit_scores:
        if score.event_id:
            grouped.setdefault(score.event_id, []).append(score)

    curve: List[Dict] = []

    for event_id, records in grouped.items():
        if len(records) < min_records_per_event:
            continue

        raw_scores = [record.raw_mobility_score for record in records]
        impairment_scores = [record.mobility_impairment_score for record in records]

        visit_order = _event_sort_key(event_id)[0]

        curve.append(
            {
                "event_id": event_id,
                "visit_order": visit_order,
                "participant_count": len(records),
                "mean_raw_mobility_score": round(statistics.mean(raw_scores), 4),
                "mean_mobility_impairment_score": round(statistics.mean(impairment_scores), 4),
                "median_mobility_impairment_score": round(statistics.median(impairment_scores), 4),
                "std_mobility_impairment_score": round(
                    statistics.pstdev(impairment_scores), 4
                ) if len(impairment_scores) > 1 else 0.0,
            }
        )

    curve.sort(key=lambda row: _event_sort_key(row["event_id"]))

    return curve


def build_participant_curve(
    csv_path: str | Path,
    participant_id: str,
) -> List[Dict]:
    """
    Build a single participant's mobility-impairment curve across visits.

    This is useful for checking whether one PPMI participant's Neuro-QoL
    mobility score changes over time.
    """
    visit_scores = load_mobility_visit_scores(csv_path)

    participant_records = [
        score for score in visit_scores
        if str(score.participant_id) == str(participant_id)
    ]

    participant_records.sort(key=lambda record: _event_sort_key(record.event_id))

    return [record.to_dict() for record in participant_records]


def calculate_dataset_summary(csv_path: str | Path) -> Dict:
    """Return high-level summary statistics for the mobility CSV."""
    visit_scores = load_mobility_visit_scores(csv_path)

    if not visit_scores:
        return {
            "total_valid_visit_records": 0,
            "unique_participants": 0,
            "events": [],
            "mean_mobility_impairment_score": None,
            "median_mobility_impairment_score": None,
            "min_mobility_impairment_score": None,
            "max_mobility_impairment_score": None,
        }

    impairment_scores = [score.mobility_impairment_score for score in visit_scores]
    participants = {score.participant_id for score in visit_scores if score.participant_id}
    events = sorted({score.event_id for score in visit_scores if score.event_id}, key=_event_sort_key)

    return {
        "total_valid_visit_records": len(visit_scores),
        "unique_participants": len(participants),
        "events": events,
        "mean_mobility_impairment_score": round(statistics.mean(impairment_scores), 4),
        "median_mobility_impairment_score": round(statistics.median(impairment_scores), 4),
        "min_mobility_impairment_score": round(min(impairment_scores), 4),
        "max_mobility_impairment_score": round(max(impairment_scores), 4),
    }


def save_reference_curve_json(
    csv_path: str | Path,
    output_path: str | Path = "ppmi_mobility_reference_curve.json",
) -> str:
    """Build and save the aggregated reference curve as JSON."""
    output_path = Path(output_path)
    curve = build_event_reference_curve(csv_path)

    payload = {
        "source_file": str(csv_path),
        "score_name": "Neuro-QoL mobility impairment score",
        "score_range": {
            "minimum": 0,
            "maximum": 100,
            "lower_means": "less reported mobility impairment",
            "higher_means": "more reported mobility impairment",
        },
        "curve": curve,
    }

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(output_path)


def plot_reference_curve(
    csv_path: str | Path,
    show: bool = True,
    save_path: Optional[str | Path] = None,
) -> List[Dict]:
    """
    Plot the aggregated mobility reference curve.

    Requires matplotlib. If matplotlib is not installed, the curve data is
    still returned and no plot is shown.
    """
    curve = build_event_reference_curve(csv_path)

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is not installed. Returning curve data without plotting.")
        return curve

    if not curve:
        print("No curve data available to plot.")
        return curve

    x_labels = [row["event_id"] for row in curve]
    y_values = [row["mean_mobility_impairment_score"] for row in curve]

    plt.figure(figsize=(10, 5))
    plt.plot(x_labels, y_values, marker="o", linewidth=2)
    plt.title("PPMI Neuro-QoL Mobility-Based PD Reference Curve")
    plt.xlabel("PPMI Visit / Event")
    plt.ylabel("Mean Mobility Impairment Score (0–100)")
    plt.xticks(rotation=45)
    plt.tight_layout()

    if save_path is not None:
        plt.savefig(save_path, dpi=150)

    if show:
        plt.show()

    return curve


def main() -> None:
    """
    Example command-line usage:

        python ppmi_mobility_curve.py

    The CSV should either be in the same folder as this file, or you can edit
    CSV_FILE below to point to the correct location.
    """
    CSV_FILE = "Neuro_QoL__Lower_Extremity_Function__Mobility__-_Short_Form_22Apr2026.csv"

    csv_path = Path(CSV_FILE)

    if not csv_path.exists():
        print("CSV file not found.")
        print(f"Expected file location: {csv_path.resolve()}")
        print("Place the Neuro-QoL mobility CSV in the same project folder, or edit CSV_FILE.")
        return

    summary = calculate_dataset_summary(csv_path)
    print("\nDATASET SUMMARY")
    print(json.dumps(summary, indent=2))

    curve = build_event_reference_curve(csv_path)
    print("\nFIRST 10 CURVE POINTS")
    print(json.dumps(curve[:10], indent=2))

    output_file = save_reference_curve_json(csv_path)
    print(f"\nSaved reference curve JSON to: {output_file}")

    # Set show=True if you want the matplotlib graph window to appear.
    plot_reference_curve(csv_path, show=True, save_path="ppmi_mobility_reference_curve.png")
    print("Saved reference curve plot to: ppmi_mobility_reference_curve.png")


if __name__ == "__main__":
    main()
