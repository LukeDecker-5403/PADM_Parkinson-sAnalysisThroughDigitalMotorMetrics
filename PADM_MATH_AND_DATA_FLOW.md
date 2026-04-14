# PADM Mathematical Methods and Data Flow Documentation

## Overview
This document explains the mathematical computations used in each motor and cognitive test, where raw input data originates, and where computed output values are stored and used.

---

## MOTOR TESTS

### 1. Tapping Speed Test

#### **Input Data**
- **Source**: User spacebar presses or button clicks during 10-second window
- **Data Captured**: Timestamp (in seconds, relative to test start) for each tap event
- **Storage Location**: `TappingSpeedTest._tap_times` (List[float])

#### **Mathematical Computations**

```
Total Taps = count of elements in _tap_times

Duration = _tap_times[-1] - _tap_times[0]
(last timestamp minus first timestamp)

Taps Per Second = Total Taps / Duration

Inter-tap Intervals = [_tap_times[i] - _tap_times[i-1] for i in 1..n]
(time gap between consecutive taps)

Average Interval = mean(Inter-tap Intervals)
(arithmetic mean of all gaps)

Interval Std Dev = population_stdev(Inter-tap Intervals)
(measure of variability in tap timing; indicates tremor/dysrhythmia)
```

#### **Output Data**
- **Result Object**: `TappingTestResult`
- **Fields**:
  - `hand`: "dominant" or "non_dominant"
  - `total_taps`: integer count
  - `duration_seconds`: float (test length)
  - `taps_per_second`: float (primary motor speed metric)
  - `average_interval_seconds`: float (expected ~1/taps_per_second)
  - `interval_std_seconds`: float (lower = more regular, higher = tremor present)

#### **Where Output Goes**
1. Stored in `PADMAssessmentManager.motor_results["tapping_{hand}"]`
2. Exported to JSON via `manager.export_json()`
3. Included in flattened feature vector: `feature_vector()` creates entries like:
   - `motor.tapping_dominant.taps_per_second`
   - `motor.tapping_dominant.interval_std_seconds`

---

### 2. Tremor Rate Test

#### **Input Data**
- **Source**: Mouse/cursor position sampled during 8-second window
- **Data Captured**: Timestamp (seconds), x-coordinate (pixels), y-coordinate (pixels)
- **Storage Location**: `TremorRateTest._samples` (List[TimedPoint])
- **Sample Rate**: Typically 30–100 Hz depending on system responsiveness

#### **Mathematical Computations**

##### **Step 1: Center the Motion**
```
mean_x = average of all x coordinates
mean_y = average of all y coordinates

radial_displacement[i] = sqrt((x[i] - mean_x)² + (y[i] - mean_y)²)
(distance from center of motion for each sample)
```

##### **Step 2: Compute Amplitude Metrics**
```
Mean Amplitude = mean(radial_displacement)
(average deviation from resting position)

RMS Amplitude = sqrt(sum(radial_displacement[i]²) / count)
(root mean square; emphasizes larger deviations)
```

##### **Step 3: Estimate Tremor Frequency**

**Option A: FFT Method (if NumPy available)**
```
1. Apply Fast Fourier Transform (FFT) to radial_displacement signal
2. Extract power spectrum
3. Filter to 1–20 Hz range (human tremor band)
4. Find dominant frequency (peak power)

Estimated Frequency = frequency value at peak power in Hz
```

**Option B: Zero-Crossing Method (fallback without NumPy)**
```
1. Center signal: centered[i] = radial_displacement[i] - mean(radial_displacement)
2. Count zero-crossings: transitions from negative to positive or vice versa
3. Average crossing interval = sum of gaps between crossings / count
4. Frequency ≈ 1 / (2 × average_crossing_interval)
(one complete oscillation = two zero-crossings)
```

#### **Output Data**
- **Result Object**: `TremorTestResult`
- **Fields**:
  - `hand`: "dominant" or "non_dominant"
  - `duration_seconds`: float (8 seconds nominal)
  - `sample_count`: integer (number of position samples)
  - `estimated_frequency_hz`: float (tremor frequency; typically 4–12 Hz in PD)
  - `mean_amplitude`: float (pixels; measure of tremor magnitude)
  - `rms_amplitude`: float (pixels; alternative amplitude measure)
  - `method`: "fft" or "zero_crossing"

#### **Where Output Goes**
1. Stored in `PADMAssessmentManager.motor_results["tremor_{hand}"]`
2. Exported to JSON
3. Feature vector includes:
   - `motor.tremor_dominant.estimated_frequency_hz`
   - `motor.tremor_dominant.rms_amplitude`

---

### 3. Tracing Precision Test

#### **Input Data**
- **Source**: User mouse drag along guided blue path
- **Data Captured**: Timestamp (seconds), x-coordinate (pixels), y-coordinate (pixels)
- **Target Path**: Pre-defined polyline (e.g., 5 waypoints)
- **Storage Location**: `TracingPrecisionTest._trace_samples` (List[TimedPoint])

#### **Mathematical Computations**

##### **Step 1: Compute Path Length**
```
user_path_length = sum of distances between consecutive trace points
= d(p[0],p[1]) + d(p[1],p[2]) + ... + d(p[n-1],p[n])

target_path_length = sum of distances along target polyline
```

##### **Step 2: Compute Deviations from Target**
```
For each traced point p:
  deviation[i] = shortest distance from p to target polyline
  (computed using point_to_polyline_distance)

Mean Deviation = mean(deviation)
(average error from target; lower is better)

Max Deviation = max(deviation)
(worst-case single sample error)
```

##### **Step 3: Compute Path Efficiency**
```
straight_line = distance from first trace point to last
(Euclidean distance)

Path Efficiency = straight_line / user_path_length
Range: 0 to 1 (1.0 = perfectly straight line, <1.0 = wandering/shakiness)
```

##### **Step 4: Compute Completion Ratio**
```
For each target waypoint:
  min_distance_to_trace = minimum distance from waypoint to any trace point
  covered = 1 if min_distance ≤ 15 pixels (threshold), else 0

Completion Ratio = (number of covered waypoints) / (total target waypoints)
Range: 0 to 1 (1.0 = hit all waypoints)
```

#### **Output Data**
- **Result Object**: `TracingTestResult`
- **Fields**:
  - `duration_seconds`: float (time from first to last trace sample)
  - `sample_count`: integer (number of traced points)
  - `mean_deviation`: float (pixels; primary precision metric)
  - `max_deviation`: float (pixels; worst-case error)
  - `path_efficiency`: float (0–1; straightness of path)
  - `completion_ratio`: float (0–1; coverage of target waypoints)

#### **Where Output Goes**
1. Stored in `PADMAssessmentManager.motor_results["tracing_precision"]`
2. Exported to JSON
3. Feature vector includes:
   - `motor.tracing_precision.mean_deviation`
   - `motor.tracing_precision.path_efficiency`

---

## COGNITIVE TESTS

### 1. Reaction Time Test

#### **Input Data**
- **Source**: Stimulus presentation time and measured response time (in seconds)
- **Data Captured**: stimulus_time, response_time for each trial
- **Storage Location**: `ReactionTimeTest._reaction_times_ms` (List[float], converted to milliseconds)

#### **Mathematical Computations**

```
reaction_time_ms[i] = (response_time[i] - stimulus_time[i]) × 1000
(time delta converted to milliseconds)

Average Reaction Time = mean(reaction_times_ms)

Min Reaction Time = min(reaction_times_ms)
Max Reaction Time = max(reaction_times_ms)

Reaction Time Std Dev = population_stdev(reaction_times_ms)
(variability measure; higher indicates inconsistency)
```

#### **Output Data**
- **Result Object**: `ReactionTimeTestResult`
- **Fields**:
  - `total_trials`: integer count
  - `valid_trials`: integer (same as total if no filtering)
  - `average_reaction_time_ms`: float (primary cognitive speed metric)
  - `min_reaction_time_ms`: float
  - `max_reaction_time_ms`: float
  - `reaction_time_std_ms`: float (variability)

#### **Where Output Goes**
1. Stored in `CognitiveAssessmentSession.results["reaction_time"]`
2. Exported from session
3. Sent to `PADMAssessmentManager` if integrated with motor results

---

### 2. Sequence Memory Test

#### **Input Data**
- **Source**: Expected sequence [e₀, e₁, ..., eₙ] vs. user-entered sequence [u₀, u₁, ..., uₘ]
- **Data Captured**: Two lists of integers per round
- **Storage Location**: `SequenceMemoryTest._rounds` (List of dicts with "span" and "correct" keys)

#### **Mathematical Computations**

```
For each round:
  is_correct = (expected_sequence == user_sequence)
  span = length of expected_sequence
  
  Store: {"span": span, "correct": is_correct}

Total Rounds = count of recorded rounds

Correct Rounds = sum of (1 if round["correct"] else 0)

Accuracy = correct_rounds / total_rounds
Range: 0 to 1 (1.0 = perfect memory)

Longest Correct Span = max(span for rounds where correct == True)
(deepest sequence level successfully recalled)
```

#### **Output Data**
- **Result Object**: `SequenceMemoryTestResult`
- **Fields**:
  - `total_rounds`: integer count
  - `correct_rounds`: integer
  - `longest_correct_span`: integer (primary working memory metric)
  - `accuracy`: float (0–1 range)

#### **Where Output Goes**
1. Stored in `CognitiveAssessmentSession.results["sequence_memory"]`
2. Feature vector: `cognitive.sequence_memory.longest_correct_span`

---

### 3. Symbol Matching / Processing Speed Test

#### **Input Data**
- **Source**: Correctness of each item match (True/False) + start/stop timestamps
- **Data Captured**: Boolean value for each response, test duration
- **Storage Location**: `SymbolMatchingTest._correct` (count), `._incorrect` (count), `._start_time`, `._end_time`

#### **Mathematical Computations**

```
correct_count = sum of True responses
incorrect_count = sum of False responses

total_items = correct_count + incorrect_count

duration_seconds = end_time - start_time

Accuracy = correct_count / total_items
Range: 0 to 1

Items Per Second = total_items / duration_seconds
(primary processing speed metric; higher = faster cognition)
```

#### **Output Data**
- **Result Object**: `SymbolMatchingTestResult`
- **Fields**:
  - `total_items`: integer
  - `correct_items`: integer
  - `incorrect_items`: integer
  - `duration_seconds`: float
  - `accuracy`: float (0–1)
  - `items_per_second`: float (speed metric)

#### **Where Output Goes**
1. Stored in `CognitiveAssessmentSession.results["symbol_matching"]`
2. Feature vector: `cognitive.symbol_matching.items_per_second`

---

## DATA INTEGRATION & EXPORT FLOW

### Step 1: Participant Setup
- User enters: age, sex, handedness, sleep quality, genetic predisposition
- Creates: `ParticipantProfile` object
- Initializes: `PADMAssessmentManager(profile)`

### Step 2: Motor Tests Execution
1. User runs tapping, tremor, and/or tracing tests via UI
2. Each test accumulates raw sample data
3. `finalize()` computes metrics
4. Manager stores result via `save_motor_result(test_name, result_object)`

### Step 3: Cognitive Tests Execution
1. Similar flow to motor tests
2. Results stored in `CognitiveAssessmentSession` or directly to manager
3. Manager stores via `save_cognitive_result(test_name, result_object)`

### Step 4: Flattened Feature Vector
```
manager.export_dict() calls record.to_dict()
  → record.to_dict() includes:
    - participant metadata
    - all motor results
    - all cognitive results
    - flattened feature_vector()

feature_vector() creates dotted keys:
  motor.tapping_dominant.taps_per_second
  motor.tremor_dominant.estimated_frequency_hz
  motor.tracing_precision.mean_deviation
  cognitive.reaction_time.average_reaction_time_ms
  cognitive.sequence_memory.longest_correct_span
  cognitive.symbol_matching.items_per_second
  participant.age
  participant.sex
  ... (etc.)
```

### Step 5: JSON Export
```
manager.export_json(filepath=None)
  → Serializes the full dict to JSON string
  → Optionally writes to file
  → Returns JSON for display or transmission
```

---

## Summary of Key Metrics for Parkinson's Analysis

| Test | Primary Metric | Clinical Interpretation |
|------|---|---|
| **Tapping** | taps_per_second | Motor speed; decreased in bradykinesia |
| | interval_std_seconds | Rhythmicity; increased variability suggests tremor |
| **Tremor** | estimated_frequency_hz | Tremor type (4–6 Hz rest, 8–12 Hz action in PD) |
| | rms_amplitude | Tremor severity |
| **Tracing** | mean_deviation | Motor control precision |
| | path_efficiency | Smoothness; <1.0 indicates intention tremor |
| **Reaction Time** | average_reaction_time_ms | Cognitive speed; slowed in PD |
| | reaction_time_std_ms | Consistency; high variability = cognitive slowing |
| **Sequence Memory** | longest_correct_span | Working memory capacity |
| **Symbol Matching** | items_per_second | Processing speed; slowed in PD dementia |

---

## Notes
- All timestamps are in seconds unless otherwise noted
- All spatial measurements (deviation, amplitude) are in pixels
- Frequency measurements are in Hz
- Accuracy metrics are 0–1 or percentages
- Statistical functions (mean, stdev) use Python's `statistics` module for CPU efficiency