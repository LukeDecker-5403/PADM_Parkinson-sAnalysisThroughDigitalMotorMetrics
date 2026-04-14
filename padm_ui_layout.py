"""
padm_ui_layout.py

Frontend interface module for PADM.
Provides a structured user interface for participant setup, motor test execution,
and result visualization. Connects directly to backend motor assessment logic.

Features implemented:
1. Participant profile setup (age, sex, handedness, sleep, genetics)
2. Tapping speed test interface with real-time input capture
3. Tremor rate test using cursor motion tracking
4. Tracing precision test using guided path interaction
5. Results display and session export

Note:
This UI acts as a control layer only. It does not compute metrics directly.
All analysis is handled by backend modules.

Author: Luke Decker project scaffold
"""

from __future__ import annotations

import json
import time
import tkinter as tk
from tkinter import ttk, messagebox

from padm_motor_tests import (
    TappingSpeedTest,
    TremorRateTest,
    TracingPrecisionTest,
    average_tapping_results,
    average_tremor_results,
    average_tracing_results,
)
from padm_data_integration import ParticipantProfile, PADMAssessmentManager

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


TAPPING_DURATION_SECONDS = 10
TREMOR_DURATION_SECONDS = 8
TRIALS_PER_TEST = 3


class PADMApp(tk.Tk):
    """Minimal PADM interface scaffold connected to motor-test data collection."""

    def __init__(self):
        super().__init__()
        self.title("PADM - Parkinson's Analysis Through Digital Motor Metrics")
        self.geometry("1180x760")

        self.manager: PADMAssessmentManager | None = None
        self.current_frame: ttk.Frame | None = None

        self._build_shell()
        self.show_home()

    def _build_shell(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.sidebar = ttk.Frame(self, padding=12)
        self.sidebar.grid(row=0, column=0, sticky="ns")

        ttk.Label(
            self.sidebar,
            text="PADM",
            font=("Arial", 16, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        buttons = [
            ("Home", self.show_home),
            ("Participant Setup", self.show_participant_setup),
            ("Tapping Test", self.show_tapping_test),
            ("Tremor Test", self.show_tremor_test),
            ("Tracing Test", self.show_tracing_test),
            ("Results", self.show_results),
        ]

        for text, command in buttons:
            ttk.Button(self.sidebar, text=text, command=command).pack(fill="x", pady=4)

        self.content = ttk.Frame(self, padding=16)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

    def _set_content(self, frame: ttk.Frame) -> None:
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame
        self.current_frame.grid(row=0, column=0, sticky="nsew")

    def _require_manager(self) -> bool:
        if self.manager is None:
            messagebox.showwarning("Participant Required", "Please complete Participant Setup first.")
            self.show_participant_setup()
            return False
        return True

    def _generate_participant_id(self) -> str:
        return f"participant_{int(time.time())}"

    def _participant_curve(self, value: float | None) -> list[float]:
        base = value if value is not None and value > 0 else 1.0
        return [base * (0.92 + 0.02 * i) for i in range(5)]

    def _pd_curve(self, value: float | None) -> list[float]:
        base = value if value is not None and value > 0 else 1.0
        return [base * (0.70 + 0.03 * i) for i in range(5)]

    def _render_metric_plot(
        self,
        master: ttk.Frame,
        title: str,
        y_label: str,
        participant_value: float | None,
    ) -> None:
        if participant_value is None:
            ttk.Label(master, text=f"{title}: no data available yet.").pack(anchor="w", pady=8)
            return

        fig, ax = plt.subplots(figsize=(5.6, 3.2))
        x_values = list(range(1, 6))
        npd_curve = self._participant_curve(participant_value)
        pd_curve = self._pd_curve(participant_value)

        ax.plot(x_values, npd_curve, marker="o", label="Participant curve (NPD)")
        ax.plot(x_values, pd_curve, marker="o", label="Parkinson's projected curve (PD)")
        ax.set_title(title)
        ax.set_xlabel("Comparison window")
        ax.set_ylabel(y_label)
        ax.legend()

        canvas = FigureCanvasTkAgg(fig, master=master)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="x", expand=False, pady=6)

    def show_home(self) -> None:
        frame = ttk.Frame(self.content)

        ttk.Label(frame, text="PADM Interface Layout", font=("Arial", 20, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(
            frame,
            text=(
                "This build includes clearer participant instructions, repeated motor trials, "
                "trial averaging, progress indicators, and graph-based results.\n\n"
                "Current connected flows:\n"
                "• Participant profile setup\n"
                "• Tapping speed data capture over 3 trials\n"
                "• Tremor motion capture over 3 trials\n"
                "• Tracing precision capture with multiple shapes over 3 trials\n"
                "• Unified session export / graph preview"
            ),
            justify="left",
        ).pack(anchor="w")

        self._set_content(frame)

    def show_participant_setup(self) -> None:
        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Participant Setup", font=("Arial", 18, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        ttk.Label(
            frame,
            text="Enter the participant background fields below. A participant ID will be generated automatically.",
            wraplength=700,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        age_var = tk.StringVar()
        sex_var = tk.StringVar(value="Prefer not to say")
        hand_var = tk.StringVar(value="right")
        sleep_var = tk.StringVar()
        genetic_var = tk.StringVar(value="no")

        row = 2

        ttk.Label(frame, text="Age").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frame, textvariable=age_var, width=32).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frame, text="Sex").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Combobox(
            frame,
            textvariable=sex_var,
            values=["Male", "Female", "Other", "Prefer not to say"],
            state="readonly",
            width=29,
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frame, text="Handedness").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Combobox(
            frame,
            textvariable=hand_var,
            values=["right", "left", "ambidextrous"],
            state="readonly",
            width=29,
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frame, text="Sleep Quality (1-10)").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frame, textvariable=sleep_var, width=32).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frame, text="Genetic Predisposition").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Combobox(
            frame,
            textvariable=genetic_var,
            values=["yes", "no"],
            state="readonly",
            width=29,
        ).grid(row=row, column=1, sticky="w", pady=4)

        def save_participant() -> None:
            try:
                age = int(age_var.get().strip()) if age_var.get().strip() else None
                sleep_quality = int(sleep_var.get().strip()) if sleep_var.get().strip() else None
            except ValueError:
                messagebox.showerror("Invalid Input", "Age and Sleep Quality must be numeric when entered.")
                return

            participant_id = self._generate_participant_id()
            profile = ParticipantProfile(
                participant_id=participant_id,
                age=age,
                sex=sex_var.get().strip() or None,
                handedness=hand_var.get().strip() or None,
                sleep_quality=sleep_quality,
                genetic_predisposition=genetic_var.get().strip().lower() == "yes",
            )
            self.manager = PADMAssessmentManager(profile)
            messagebox.showinfo("Saved", f"Participant setup saved.\nGenerated ID: {participant_id}")

        ttk.Button(frame, text="Save Participant", command=save_participant).grid(
            row=row + 1, column=0, columnspan=2, sticky="w", pady=12
        )

        self._set_content(frame)

    def show_tapping_test(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Tapping Speed Test", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            frame,
            text=(
                "Instructions:\n"
                "1. Select the hand being tested.\n"
                "2. Press Start Trial.\n"
                "3. Tap the SPACEBAR or click Tap as quickly and consistently as possible for 10 seconds.\n"
                "4. Complete all 3 trials. Your averaged result will be saved automatically."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        hand_var = tk.StringVar(value="dominant")
        ttk.Label(frame, text="Hand").pack(anchor="w")
        ttk.Combobox(
            frame,
            textvariable=hand_var,
            values=["dominant", "non-dominant"],
            state="readonly",
            width=24,
        ).pack(anchor="w", pady=(0, 8))

        timer_label = ttk.Label(frame, text=f"Time Remaining: {TAPPING_DURATION_SECONDS:.1f}s")
        timer_label.pack(anchor="w")

        trial_label = ttk.Label(frame, text=f"Trial: 1 / {TRIALS_PER_TEST}")
        trial_label.pack(anchor="w", pady=(4, 0))

        progress = ttk.Progressbar(frame, maximum=TRIALS_PER_TEST, length=300)
        progress.pack(anchor="w", pady=(4, 10))

        button_row = ttk.Frame(frame)
        button_row.pack(anchor="w", pady=(0, 8))

        result_text = tk.Text(frame, height=16, width=92)
        result_text.pack(fill="both", expand=True, pady=10)

        state = {
            "test": None,
            "start_time": None,
            "running": False,
            "trial": 0,
            "trial_results": [],
        }

        def record_tap(_event=None):
            if state["running"] and state["test"] is not None and state["start_time"] is not None:
                timestamp = time.perf_counter() - state["start_time"]
                state["test"].record_tap(timestamp)

        def update_timer():
            if not state["running"] or state["start_time"] is None:
                return
            elapsed = time.perf_counter() - state["start_time"]
            remaining = max(0.0, TAPPING_DURATION_SECONDS - elapsed)
            timer_label.config(text=f"Time Remaining: {remaining:.1f}s")
            if remaining > 0:
                self.after(100, update_timer)

        def finish_test():
            if not state["running"] or state["test"] is None:
                return

            state["running"] = False
            timer_label.config(text="Time Remaining: 0.0s")

            result = state["test"].finalize()
            state["trial_results"].append(result)
            state["trial"] += 1
            progress["value"] = state["trial"]

            result_text.insert(
                tk.END,
                f"\nTrial {state['trial']} result:\n{json.dumps(result.to_dict(), indent=2)}\n",
            )
            result_text.see(tk.END)

            if state["trial"] >= TRIALS_PER_TEST:
                averaged = average_tapping_results(state["trial_results"], hand=hand_var.get())
                self.manager.save_motor_result(f"tapping_{hand_var.get().replace('-', '_')}", averaged)
                trial_label.config(text=f"Trial: {TRIALS_PER_TEST} / {TRIALS_PER_TEST}")
                result_text.insert(
                    tk.END,
                    f"\nAveraged participant tapping result:\n{json.dumps(averaged, indent=2)}\n",
                )
                result_text.see(tk.END)
                messagebox.showinfo("Tapping Complete", "All 3 tapping trials are complete.")
            else:
                trial_label.config(text=f"Trial: {state['trial'] + 1} / {TRIALS_PER_TEST}")
                result_text.insert(tk.END, "\nPress Start Trial to begin the next tapping trial.\n")
                result_text.see(tk.END)

        def start_test():
            if state["running"]:
                return

            if state["trial"] >= TRIALS_PER_TEST:
                state["trial"] = 0
                state["trial_results"] = []
                progress["value"] = 0
                result_text.delete("1.0", tk.END)
                trial_label.config(text=f"Trial: 1 / {TRIALS_PER_TEST}")

            state["test"] = TappingSpeedTest(hand=hand_var.get())
            state["start_time"] = time.perf_counter()
            state["running"] = True
            result_text.insert(tk.END, f"\nTapping trial {state['trial'] + 1} started...\n")
            result_text.see(tk.END)
            update_timer()
            self.after(TAPPING_DURATION_SECONDS * 1000, finish_test)

        ttk.Button(button_row, text="Start Trial", command=start_test).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Tap", command=record_tap).pack(side="left")
        self.bind("<space>", record_tap)

        self._set_content(frame)

    def show_tremor_test(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Tremor Rate Test", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            frame,
            text=(
                "Instructions:\n"
                "1. Use an external touchpad for best accuracy.\n"
                "2. Select the hand being tested.\n"
                "3. Press Start Trial.\n"
                "4. Move naturally inside the white capture area for 8 seconds.\n"
                "5. Complete all 3 trials. Your averaged result will be saved automatically."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        hand_var = tk.StringVar(value="dominant")
        ttk.Label(frame, text="Handedness / Test Hand").pack(anchor="w")
        ttk.Combobox(
            frame,
            textvariable=hand_var,
            values=["dominant", "non-dominant"],
            state="readonly",
            width=24,
        ).pack(anchor="w", pady=(4, 8))

        timer_label = ttk.Label(frame, text=f"Time Remaining: {TREMOR_DURATION_SECONDS:.1f}s")
        timer_label.pack(anchor="w")

        trial_label = ttk.Label(frame, text=f"Trial: 1 / {TRIALS_PER_TEST}")
        trial_label.pack(anchor="w", pady=(4, 0))

        progress = ttk.Progressbar(frame, maximum=TRIALS_PER_TEST, length=300)
        progress.pack(anchor="w", pady=(4, 10))

        canvas = tk.Canvas(frame, width=650, height=300, bg="white", highlightthickness=1, highlightbackground="#999")
        canvas.pack(pady=8)

        result_text = tk.Text(frame, height=14, width=92)
        result_text.pack(fill="both", expand=True)

        state = {
            "test": None,
            "start_time": None,
            "running": False,
            "trial": 0,
            "trial_results": [],
        }

        def on_motion(event):
            if state["running"] and state["test"] is not None and state["start_time"] is not None:
                timestamp = time.perf_counter() - state["start_time"]
                state["test"].add_sample(timestamp, event.x, event.y)
                r = 2
                canvas.create_oval(event.x - r, event.y - r, event.x + r, event.y + r, fill="black", outline="")

        def update_timer():
            if not state["running"] or state["start_time"] is None:
                return
            elapsed = time.perf_counter() - state["start_time"]
            remaining = max(0.0, TREMOR_DURATION_SECONDS - elapsed)
            timer_label.config(text=f"Time Remaining: {remaining:.1f}s")
            if remaining > 0:
                self.after(100, update_timer)

        def finish_test():
            if not state["running"] or state["test"] is None:
                return

            state["running"] = False
            timer_label.config(text="Time Remaining: 0.0s")

            result = state["test"].finalize()
            state["trial_results"].append(result)
            state["trial"] += 1
            progress["value"] = state["trial"]

            result_text.insert(
                tk.END,
                f"\nTrial {state['trial']} result:\n{json.dumps(result.to_dict(), indent=2)}\n",
            )
            result_text.see(tk.END)

            if state["trial"] >= TRIALS_PER_TEST:
                averaged = average_tremor_results(state["trial_results"], hand=hand_var.get())
                self.manager.save_motor_result(f"tremor_{hand_var.get().replace('-', '_')}", averaged)
                trial_label.config(text=f"Trial: {TRIALS_PER_TEST} / {TRIALS_PER_TEST}")
                result_text.insert(
                    tk.END,
                    f"\nAveraged participant tremor result:\n{json.dumps(averaged, indent=2)}\n",
                )
                result_text.see(tk.END)
                messagebox.showinfo("Tremor Complete", "All 3 tremor trials are complete.")
            else:
                trial_label.config(text=f"Trial: {state['trial'] + 1} / {TRIALS_PER_TEST}")
                result_text.insert(tk.END, "\nPress Start Trial to begin the next tremor trial.\n")
                result_text.see(tk.END)

        def start_test():
            if state["running"]:
                return

            if state["trial"] >= TRIALS_PER_TEST:
                state["trial"] = 0
                state["trial_results"] = []
                progress["value"] = 0
                result_text.delete("1.0", tk.END)
                trial_label.config(text=f"Trial: 1 / {TRIALS_PER_TEST}")

            canvas.delete("all")
            state["test"] = TremorRateTest(hand=hand_var.get())
            state["start_time"] = time.perf_counter()
            state["running"] = True
            result_text.insert(tk.END, f"\nTremor trial {state['trial'] + 1} started...\n")
            result_text.see(tk.END)
            update_timer()
            self.after(TREMOR_DURATION_SECONDS * 1000, finish_test)

        canvas.bind("<Motion>", on_motion)
        ttk.Button(frame, text="Start Trial", command=start_test).pack(anchor="w", pady=4)
        self._set_content(frame)

    def show_tracing_test(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Tracing Precision Test", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            frame,
            text=(
                "Instructions:\n"
                "1. Press and hold the left mouse button.\n"
                "2. Trace the blue guide shape as closely as possible from start to finish.\n"
                "3. Release the mouse button when the shape is complete.\n"
                "4. Complete all 3 tracing shapes. Your averaged result will be saved automatically."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        trial_label = ttk.Label(frame, text=f"Shape / Trial: 1 / {TRIALS_PER_TEST}")
        trial_label.pack(anchor="w")

        progress = ttk.Progressbar(frame, maximum=TRIALS_PER_TEST, length=300)
        progress.pack(anchor="w", pady=(4, 10))

        canvas = tk.Canvas(frame, width=760, height=340, bg="white", highlightthickness=1, highlightbackground="#999")
        canvas.pack(pady=10)

        result_text = tk.Text(frame, height=14, width=92)
        result_text.pack(fill="both", expand=True)

        tracing_paths = [
            [(80, 170), (220, 170), (360, 170), (500, 170), (640, 170)],
            [(100, 260), (180, 120), (260, 260), (340, 120), (420, 260), (500, 120), (580, 260)],
            [(120, 250), (120, 120), (260, 120), (260, 250), (400, 250), (400, 120), (540, 120)],
        ]

        state = {
            "trial": 0,
            "trial_results": [],
            "running": False,
            "start_time": None,
            "test": None,
        }

        def draw_current_path() -> None:
            canvas.delete("all")
            current_path = tracing_paths[state["trial"]]
            for i in range(1, len(current_path)):
                x1, y1 = current_path[i - 1]
                x2, y2 = current_path[i]
                canvas.create_line(x1, y1, x2, y2, width=4, fill="blue")
            x0, y0 = current_path[0]
            canvas.create_oval(x0 - 6, y0 - 6, x0 + 6, y0 + 6, fill="green")
            ttk_text = f"Trace shape {state['trial'] + 1} of {TRIALS_PER_TEST}"
            result_text.insert(tk.END, f"\n{ttk_text}\n")
            result_text.see(tk.END)

        def start_trace(_event=None):
            if state["trial"] >= TRIALS_PER_TEST:
                return
            state["test"] = TracingPrecisionTest(target_path=tracing_paths[state["trial"]])
            state["test"].reset()
            state["running"] = True
            state["start_time"] = time.perf_counter()
            result_text.insert(tk.END, f"Tracing capture started for shape {state['trial'] + 1}...\n")
            result_text.see(tk.END)

        def trace_motion(event):
            if state["running"] and state["start_time"] is not None and state["test"] is not None:
                timestamp = time.perf_counter() - state["start_time"]
                state["test"].add_sample(timestamp, event.x, event.y)
                r = 2
                canvas.create_oval(event.x - r, event.y - r, event.x + r, event.y + r, fill="black", outline="")

        def stop_trace(_event=None):
            if not state["running"] or state["test"] is None:
                return

            state["running"] = False
            result = state["test"].finalize()
            state["trial_results"].append(result)
            state["trial"] += 1
            progress["value"] = state["trial"]

            result_text.insert(
                tk.END,
                f"\nShape {state['trial']} result:\n{json.dumps(result.to_dict(), indent=2)}\n",
            )
            result_text.see(tk.END)

            if state["trial"] >= TRIALS_PER_TEST:
                averaged = average_tracing_results(state["trial_results"])
                self.manager.save_motor_result("tracing_precision", averaged)
                trial_label.config(text=f"Shape / Trial: {TRIALS_PER_TEST} / {TRIALS_PER_TEST}")
                result_text.insert(
                    tk.END,
                    f"\nAveraged participant tracing result:\n{json.dumps(averaged, indent=2)}\n",
                )
                result_text.see(tk.END)
                messagebox.showinfo("Tracing Complete", "All 3 tracing shapes are complete.")
            else:
                trial_label.config(text=f"Shape / Trial: {state['trial'] + 1} / {TRIALS_PER_TEST}")
                draw_current_path()

        draw_current_path()

        canvas.bind("<ButtonPress-1>", start_trace)
        canvas.bind("<B1-Motion>", trace_motion)
        canvas.bind("<ButtonRelease-1>", stop_trace)
        self._set_content(frame)

    def show_results(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Unified PADM Results", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 8))

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True)

        summary_tab = ttk.Frame(notebook, padding=8)
        graphs_tab = ttk.Frame(notebook, padding=8)

        notebook.add(summary_tab, text="Raw Results")
        notebook.add(graphs_tab, text="Graphs")

        text = tk.Text(summary_tab, width=100, height=32)
        text.pack(fill="both", expand=True)
        text.insert(tk.END, self.manager.export_json())

        motor_results = self.manager.export_dict().get("motor_results", {})

        tapping = motor_results.get("tapping_dominant") or motor_results.get("tapping_non_dominant")
        tremor = motor_results.get("tremor_dominant") or motor_results.get("tremor_non_dominant")
        tracing = motor_results.get("tracing_precision")

        self._render_metric_plot(
            graphs_tab,
            title="Tapping Test - Taps Per Second",
            y_label="Taps / second",
            participant_value=tapping.get("taps_per_second") if tapping else None,
        )
        self._render_metric_plot(
            graphs_tab,
            title="Tremor Test - Estimated Frequency",
            y_label="Frequency (Hz)",
            participant_value=tremor.get("estimated_frequency_hz") if tremor else None,
        )
        self._render_metric_plot(
            graphs_tab,
            title="Tracing Test - Mean Deviation",
            y_label="Deviation",
            participant_value=tracing.get("mean_deviation") if tracing else None,
        )

        self._set_content(frame)


if __name__ == "__main__":
    app = PADMApp()
    app.mainloop()