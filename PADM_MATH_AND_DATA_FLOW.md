# PADM Mathematical Methods and Data Flow Documentation

## Overview
This document explains the mathematical computations, data flow, and updated interface workflow used in PADM: Parkinson’s Analysis Through Digital Motor Metrics. PADM collects motor and cognitive interaction data through participant-facing tests, converts those interactions into structured metrics, stores them in a unified assessment record, and prepares the results for graphing, feature-vector generation, and future dataset comparison.

PADM is not a diagnostic tool. The system is designed to provide comparative, research-aligned insight by examining how a participant’s digital motor and cognitive patterns compare against future reference baselines.

---

## System-Level Data Flow

```text
Participant Setup
    ↓
Motor Tests + Cognitive Tests
    ↓
Raw Input Capture
    ↓
Backend Metric Computation
    ↓
PADMAssessmentManager Session Storage
    ↓
JSON Export + Feature Vector
    ↓
Results Graphs + Future Similarity / Dataset Comparison
```

### Core Files

- `padm_ui_layout.py`
  - Participant-facing interface.
  - Controls navigation, instructions, progress bars, button behavior, graph display, autosave flow, and hidden raw-results access.

- `padm_motor_tests.py`
  - Backend motor test logic.
  - Computes tapping, tremor, and tracing metrics.
  - Includes averaging helpers for repeated trials.

- `padmCognitiveTests.py`
  - Backend cognitive test logic.
  - Computes reaction time, sequence memory, and processing speed results.
  - Stores trial-level details internally while allowing the UI to hide correctness/output from participants.

- `padm_data_integration.py`
  - Unified data layer.
  - Stores participant profile, motor results, cognitive results, JSON export, feature-vector output, autosave support, and future PPMI/AMP-PD alignment placeholders.

---

## Participant Setup Flow

### Input Data

The participant setup screen collects background information used to contextualize test results.

Fields:

- Age
- Sex
- Handedness
- Sleep quality
- Genetic predisposition

### Updated Behavior

- Participant ID is no longer manually entered.
- The program automatically generates a participant ID internally.
- Participant setup remains lightweight and participant-facing.
- The UI includes clearer instructions and non-diagnostic framing.

### Output Data

The setup form creates a `ParticipantProfile` object and passes it into `PADMAssessmentManager`.

Stored fields include:

- `participant_id`
- `age`
- `sex`
- `handedness`
- `sleep_quality`
- `genetic_predisposition`

---

# Motor Tests

## 1. Tapping Speed Battery

### Updated Workflow

The tapping test no longer uses a manual hand-selection dropdown. Instead, the participant completes a structured tapping battery:

1. Left-hand tapping
2. Right-hand tapping
3. Alternating tapping

Each tapping mode is completed 3 times. The repeated trials are averaged into participant-level tapping results.

### Input Data

- Source: Spacebar presses or tap-button events during a fixed test window.
- Captured value: Timestamp of each tap relative to trial start.
- For alternating tapping, the backend can also track left/right tap counts and alternation behavior when passed through the UI.

### Mathematical Computations

```text
Total Taps = count(tap timestamps)

Duration Seconds = fixed trial duration or observed trial duration

Taps Per Second = Total Taps / Duration Seconds

Inter-Tap Intervals = difference between consecutive tap timestamps

Average Interval = mean(Inter-Tap Intervals)

Interval Standard Deviation = population standard deviation of Inter-Tap Intervals
```

For alternating tapping:

```text
Left Tap Count = number of left-side tap inputs

Right Tap Count = number of right-side tap inputs

Alternation Accuracy = proportion of taps that correctly alternate between sides
```

### Output Metrics

The tapping backend can return:

- `tap_mode`
- `hand`
- `total_taps`
- `duration_seconds`
- `taps_per_second`
- `average_interval_seconds`
- `interval_std_seconds`
- `left_tap_count`
- `right_tap_count`
- `alternation_accuracy`

### Averaging

Each tapping mode is tested 3 times. The averaging helper computes participant-level averages across trials.

```text
Average Metric = sum(metric values across valid trials) / number of valid trials
```

The full tapping battery can then summarize left, right, and alternating tapping into graph-ready and model-ready output.

### Where Output Goes

Stored through:

```text
PADMAssessmentManager.save_motor_result(...)
```

Possible stored keys include:

- `tapping_left`
- `tapping_right`
- `tapping_alternating`
- `tapping_battery`

---

## 2. Tremor Rate Test

### Updated Workflow

The tremor screen now uses clearer instructions, a visible Start Trial button, a smaller and more controlled capture region, and no raw output window during testing.

The test is still completed across 3 trials, then averaged into one participant-level tremor result.

### Input Data

- Source: Cursor or touchpad movement during the tremor capture window.
- Captured values:
  - Timestamp
  - X-coordinate
  - Y-coordinate
- Recommended hardware: External touchpad for more accurate tremor capture.

### Mathematical Computations

#### Step 1: Center Motion

```text
mean_x = average(x coordinates)
mean_y = average(y coordinates)

radial_displacement[i] = sqrt((x[i] - mean_x)^2 + (y[i] - mean_y)^2)
```

#### Step 2: Amplitude Metrics

```text
Mean Amplitude = mean(radial_displacement)

RMS Amplitude = sqrt(mean(radial_displacement^2))
```

#### Step 3: Tremor Frequency Estimation

Preferred method if NumPy is available:

```text
1. Convert radial displacement into a time-series signal.
2. Apply FFT.
3. Extract the power spectrum.
4. Search a tremor-relevant frequency range.
5. Select the dominant frequency peak.
```

Fallback method if NumPy is unavailable:

```text
1. Center the displacement signal.
2. Count zero-crossing intervals.
3. Estimate frequency from the average crossing interval.
```

#### Step 4: Movement Area

```text
Movement Area = (max_x - min_x) × (max_y - min_y)
```

This approximates how much screen area the participant’s movement occupied during the trial.

#### Step 5: Signal Quality

The backend can label signal quality as:

- `usable`
- `insufficient_data`
- `low_sample_rate`
- `low_motion`

This helps separate meaningful tremor signals from trials with too little movement or too few samples.

### Output Metrics

The tremor backend can return:

- `hand`
- `duration_seconds`
- `sample_count`
- `estimated_frequency_hz`
- `mean_amplitude`
- `rms_amplitude`
- `method`
- `movement_area`
- `signal_quality`

### Averaging

Across 3 tremor trials, the system averages scalar metrics and can track frequency variability.

```text
Average Frequency = mean(estimated_frequency_hz across valid trials)

Frequency Std Dev = standard deviation of estimated_frequency_hz across valid trials
```

### Where Output Goes

Stored through:

```text
PADMAssessmentManager.save_motor_result(...)
```

Typical stored keys include:

- `tremor_left`
- `tremor_right`
- `tremor_dominant`
- `tremor_non_dominant`

---

## 3. Tracing Precision Test

### Updated Workflow

The tracing test now includes 4 tracing tasks instead of 3. The fourth tracing trial is a circular shape.

The bottom raw results window has been removed from the participant-facing screen. Results are still saved internally after completion.

### Input Data

- Source: Mouse or touchpad drag along guided path.
- Captured values:
  - Timestamp
  - X-coordinate
  - Y-coordinate
- Target path: Predefined shape path.

### Current Shape Set

- Straight/line-based path
- Zig-zag path
- Angular/step path
- Circular path

### Mathematical Computations

#### Step 1: User Path Length

```text
user_path_length = sum(distance between consecutive traced points)
```

#### Step 2: Target Path Length

```text
target_path_length = sum(distance between consecutive target path points)
```

For the circular task, the circle is approximated with sampled points around the circumference.

#### Step 3: Deviation from Target

For each traced point:

```text
deviation[i] = shortest distance from traced point to target path
```

Then:

```text
Mean Deviation = mean(deviation values)

Max Deviation = max(deviation values)
```

Lower deviation means the participant stayed closer to the target path.

#### Step 4: Path Efficiency

For open shapes:

```text
Path Efficiency = straight-line distance from first traced point to last traced point / user_path_length
```

For circular shapes, path efficiency must be interpreted differently because a circle’s start and end points may be close together even when the trace is accurate. The backend adjusts circular handling so circle tracing is not incorrectly penalized as inefficient solely because it returns near the starting point.

#### Step 5: Completion Ratio

The backend samples the target path and checks whether the participant’s trace came close enough to target segments.

```text
Completion Ratio = covered target samples / total target samples
```

### Output Metrics

The tracing backend can return:

- `shape_name`
- `duration_seconds`
- `sample_count`
- `mean_deviation`
- `max_deviation`
- `path_efficiency`
- `completion_ratio`
- `target_path_length`
- `traced_path_length`

### Averaging

Across 4 tracing tasks:

```text
Average Mean Deviation = mean(mean_deviation values)

Average Max Deviation = mean(max_deviation values)

Average Path Efficiency = mean(path_efficiency values)

Average Completion Ratio = mean(completion_ratio values)
```

The averaged tracing result is saved as participant-level tracing precision output.

### Where Output Goes

Stored through:

```text
PADMAssessmentManager.save_motor_result("tracing_precision", averaged_result)
```

---

# Cognitive Tests

## 1. Reaction Time Test

### Updated Workflow

The reaction time test now uses a longer random wait before the GO signal appears. The wait time is randomly selected between 5 and 15 seconds.

The GO signal is shown more visually and prominently in the UI. Each trial reaction time can be displayed cleanly, but saving the result does not flood the participant screen with raw JSON output.

### Input Data

- Stimulus time
- Response time
- Trial number

### Mathematical Computations

```text
reaction_time_ms = (response_time - stimulus_time) × 1000

Average Reaction Time = mean(reaction_time_ms values)

Minimum Reaction Time = min(reaction_time_ms values)

Maximum Reaction Time = max(reaction_time_ms values)

Reaction Time Standard Deviation = population standard deviation of reaction_time_ms values
```

### Output Metrics

The reaction time backend can return:

- `total_trials`
- `valid_trials`
- `average_reaction_time_ms`
- `min_reaction_time_ms`
- `max_reaction_time_ms`
- `reaction_time_std_ms`
- `trial_reaction_times_ms`

### Autosave Behavior

When the reaction time task is completed, the UI saves the result into the active participant session automatically.

Stored through:

```text
PADMAssessmentManager.save_cognitive_result("reaction_time", result)
```

---

## 2. Sequence Memory Test

### Updated Workflow

The memory test now prevents the participant from typing while the sequence is displayed.

The sequence is shown first, then the participant waits before entering the sequence. This prevents typing during memorization and better separates the viewing period from the recall period.

The UI also hides correctness feedback so the participant does not immediately know whether they were right or wrong.

### Input Data

- Expected digit sequence
- User-entered digit sequence
- Round number
- Span length

### Mathematical Computations

```text
is_correct = expected_sequence == user_sequence

Correct Rounds = count(rounds where is_correct is True)

Accuracy = Correct Rounds / Total Rounds

Longest Correct Span = maximum span length among correct rounds
```

### Output Metrics

The sequence memory backend can return:

- `total_rounds`
- `correct_rounds`
- `longest_correct_span`
- `accuracy`
- `attempted_spans`
- `round_details`

### Participant-Facing Behavior

The participant should see:

- Trial number
- Sequence display period
- Recall entry field after the wait period
- Progress bar

The participant should not see:

- Whether each round was correct
- Raw JSON output
- Internal score calculations during the test

### Autosave Behavior

Stored through:

```text
PADMAssessmentManager.save_cognitive_result("sequence_memory", result)
```

---

## 3. Processing Speed / Symbol Matching Test

### Updated Workflow

The processing speed test now uses larger visual prompts and clearer trial tracking.

Some items remain symbol-based, while some items can use shape-based prompts. This supports the requested change where two of the trials shift from symbols to shapes.

### Input Data

For each item:

- Left prompt
- Right prompt
- Whether the pair truly matches
- User response
- Whether the user was correct
- Item type: symbol or shape

### Mathematical Computations

```text
Total Items = correct_items + incorrect_items

Accuracy = correct_items / total_items

Duration Seconds = end_time - start_time

Items Per Second = total_items / duration_seconds
```

The backend can also track:

```text
Symbol Item Count = number of symbol-based prompts

Shape Item Count = number of shape-based prompts
```

### Output Metrics

The processing speed backend can return:

- `total_items`
- `correct_items`
- `incorrect_items`
- `duration_seconds`
- `accuracy`
- `items_per_second`
- `symbol_items`
- `shape_items`
- `item_details`

### Autosave Behavior

Stored through:

```text
PADMAssessmentManager.save_cognitive_result("symbol_matching", result)
```

---

# Results and Graphing Flow

## Updated Results UI

The results screen now separates participant-facing results from hidden raw output.

Visible tabs:

- `Motorskill Results`
- `Cognitive Test Results`

The raw JSON tab has been removed from normal participant view.

## Hidden Raw Results Access

Raw JSON/session results are still available through a hidden shortcut on the Results page.

Shortcut:

```text
Ctrl + Shift + R
```

This opens a separate raw-results window for developer/research review.

## Graph Data Sources

Motor graphs can use:

- Tapping speed
- Tapping interval consistency
- Alternation accuracy
- Tremor frequency
- Tremor amplitude
- Tracing deviation
- Tracing completion ratio
- Tracing path efficiency

Cognitive graphs can use:

- Average reaction time
- Reaction time variability
- Sequence memory accuracy
- Longest correct span
- Processing speed accuracy
- Items per second

## Current PD/NPD Curve Status

Current graph curves are structural placeholders unless connected to a real reference dataset. They should be treated as UI testing curves only.

Future graphing should use dataset-driven baselines from approved Parkinson’s datasets.

---

# Unified Data Integration

## Assessment Record

The unified session stores:

- Participant profile
- Motor results
- Cognitive results
- Created timestamp
- Updated timestamp

## Saving Results

Motor results are saved through:

```text
save_motor_result(test_name, result)
```

Cognitive results are saved through:

```text
save_cognitive_result(test_name, result)
```

The manager normalizes result objects into dictionaries before storing them.

## Autosave Support

The data integration layer supports optional autosave behavior. This allows the program to save results as tests are completed instead of waiting until the entire session is finished.

This is important for cognitive testing because the updated workflow saves results as the user progresses.

## JSON Export

The full assessment session can be exported through:

```text
export_json()
```

This is used for:

- Hidden raw-results review
- Session backup
- Future dataset alignment
- Future model development

## Feature Vector Output

The feature-vector system flattens nested motor and cognitive results into model-friendly scalar values.

Example feature keys:

```text
motor.tapping_left.taps_per_second
motor.tapping_right.interval_std_seconds
motor.tapping_alternating.alternation_accuracy
motor.tremor_left.estimated_frequency_hz
motor.tracing_precision.mean_deviation
cognitive.reaction_time.average_reaction_time_ms
cognitive.sequence_memory.accuracy
cognitive.symbol_matching.items_per_second
```

Raw-heavy fields are excluded from model-ready features when appropriate.

Examples of excluded raw-heavy fields:

- Trial result lists
- Individual reaction-time lists
- Memory round details
- Processing-speed item details

---

# Future PPMI / Dataset Alignment

## Current Status

PPMI access has been approved, but true correlation cannot be implemented until the actual PPMI CSV/data file is placed into the project and its columns are reviewed.

## Planned Dataset Comparison Workflow

```text
PADM Feature Vector
    ↓
Feature Cleaning / Normalization
    ↓
PPMI or AMP-PD Variable Mapping
    ↓
Baseline Distribution Creation
    ↓
Similarity or Distance-Based Comparison
    ↓
Dataset-Driven PD/NPD Curve Visualization
```

## Candidate PADM Features for Dataset Comparison

Motor features:

- Tapping rate
- Tapping variability
- Alternating tapping accuracy
- Tremor frequency
- Tremor amplitude
- Movement area
- Tracing deviation
- Tracing path efficiency
- Tracing completion ratio

Cognitive features:

- Average reaction time
- Reaction time variability
- Memory accuracy
- Longest correct memory span
- Processing speed accuracy
- Processing speed rate

## Candidate Model Methods

Initial comparison methods may include:

- Z-score comparison against reference distributions
- Euclidean distance
- Cosine similarity
- k-nearest neighbors
- Weighted similarity scoring

## Non-Diagnostic Output Language

The final output should avoid diagnostic wording.

Preferred language:

- “Similarity score”
- “Comparison to reference pattern”
- “Research-aligned digital biomarker pattern”
- “Participant curve compared with dataset baseline”

Avoid language such as:

- “Diagnosis”
- “You have Parkinson’s”
- “Disease confirmation”
- “Medical determination”

---

# Implementation Change Log

## Files Updated

### `padm_ui_layout.py`

- Updated menu/home screen styling.
- Added clearer project purpose language.
- Added non-diagnostic framing.
- Improved participant setup instructions.
- Updated tapping workflow to test left, right, and alternating tapping.
- Added 3 trials per tapping mode.
- Removed visible raw output windows during testing.
- Fixed/clarified tremor Start Trial workflow.
- Reduced tremor capture area dominance.
- Added clearer tremor instructions and external touchpad note.
- Added fourth circular tracing task.
- Added cognitive progress tracking.
- Updated reaction time wait range to 5–15 seconds.
- Enlarged visual GO signal.
- Prevented memory typing while sequence is shown.
- Added memory wait period before entry.
- Hid memory correctness feedback.
- Updated processing speed visuals with larger symbols/shapes.
- Removed visible raw results tab.
- Added hidden raw-results shortcut.
- Renamed graph sections to `Motorskill Results` and `Cognitive Test Results`.

### `padmCognitiveTests.py`

- Added more detailed reaction time result storage.
- Added trial-level reaction time list.
- Added memory round details and attempted spans.
- Added more detailed processing speed item tracking.
- Added support for symbol and shape item types.
- Improved cognitive session wrapper for autosave-style workflows.

### `padm_data_integration.py`

- Added updated timestamp tracking.
- Added autosave-ready structure.
- Improved result normalization.
- Improved JSON export support.
- Improved feature-vector generation.
- Added model-ready feature output.
- Added placeholder structure for future PPMI alignment.

### `padm_motor_tests.py`

- Added support for left, right, and alternating tapping.
- Added alternating tapping metrics.
- Added tapping battery averaging.
- Improved tremor signal quality handling.
- Added tremor movement area.
- Added tremor frequency variability in averaged output.
- Added tracing shape-name tracking.
- Added circular path helper.
- Improved tracing completion-ratio handling.
- Improved tracing averaging output.

---

# Next Development Steps

1. Run the updated program from the project folder.
2. Complete one full test session using test participant data.
3. Confirm all motor and cognitive results autosave correctly.
4. Confirm hidden raw-results shortcut works.
5. Upload or place the approved PPMI CSV/data file into the project.
6. Review PPMI columns and identify usable mappings.
7. Replace placeholder PD/NPD graph curves with dataset-driven baselines.
8. Implement similarity scoring using normalized PADM features.
9. Document the first dataset comparison results in the progress sheet.
