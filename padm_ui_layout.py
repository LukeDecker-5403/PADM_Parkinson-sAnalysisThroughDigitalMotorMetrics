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
5. Cognitive testing interface connected to backend cognitive assessment logic
6. Results display and session export

Note:
This UI acts as a control layer only. It does not compute metrics directly.
All analysis is handled by backend modules.
"""

from __future__ import annotations

import json
import time
import random
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os

from padm_motor_tests import (
    TappingSpeedTest,
    TremorRateTest,
    TracingPrecisionTest,
    average_tapping_results,
    average_tremor_results,
    average_tracing_results,
)
from padm_data_integration import ParticipantProfile, PADMAssessmentManager
from padmCognitiveTests import (
    ReactionTimeTest,
    SequenceMemoryTest,
    SymbolMatchingTest,
    CognitiveAssessmentSession,
)

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

        # Set custom icon if available
        icon_formats = ["padm_icon.png", "padm_icon.jpg", "padm_icon.ico"]
        icon_path = None
        for icon_file in icon_formats:
            potential_path = os.path.join(os.path.dirname(__file__), icon_file)
            if os.path.exists(potential_path):
                icon_path = potential_path
                break
        
        if icon_path:
            try:
                img = Image.open(icon_path)
                img.thumbnail((32, 32), Image.Resampling.LANCZOS)
                self.photo_image = ImageTk.PhotoImage(img)
                self.iconphoto(False, self.photo_image)
            except Exception:
                pass

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
            ("--- Motorskills Tests ---", None),
            ("Tapping Test", self.show_tapping_test),
            ("Tremor Test", self.show_tremor_test),
            ("Tracing Test", self.show_tracing_test),
            ("--- Cognitive Testing ---", None),
            ("Cognitive Tests", self.show_cognitive_tests),
            ("Results", self.show_results),
        ]

        for text, command in buttons:
            if command is None:
                ttk.Label(self.sidebar, text=text, font=("Arial", 10, "bold")).pack(
                    anchor="w", pady=(8, 2)
                )
            else:
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
                "trial averaging, progress indicators, cognitive test integration, and graph-based results.\n\n"
                "Current connected flows:\n"
                "• Participant profile setup\n"
                "• Tapping speed data capture over 3 trials\n"
                "• Tremor motion capture over 3 trials\n"
                "• Tracing precision capture with multiple shapes over 3 trials\n"
                "• Cognitive testing backend integration\n"
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
            info_text = f"Trace shape {state['trial'] + 1} of {TRIALS_PER_TEST}"
            result_text.insert(tk.END, f"\n{info_text}\n")
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

    def show_cognitive_tests(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Cognitive Testing", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            frame,
            text=(
                "This section includes:\n"
                "• Short-term memory testing\n"
                "• Reaction time testing\n"
                "• Processing speed / symbol matching\n\n"
                "Complete each task and save the cognitive results to the active participant session."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True)

        reaction_tab = ttk.Frame(notebook, padding=10)
        memory_tab = ttk.Frame(notebook, padding=10)
        symbol_tab = ttk.Frame(notebook, padding=10)

        notebook.add(reaction_tab, text="Reaction Time")
        notebook.add(memory_tab, text="Memory")
        notebook.add(symbol_tab, text="Processing Speed")

        cognitive_session = CognitiveAssessmentSession()

        # ---------------- REACTION TIME TAB ----------------
        ttk.Label(reaction_tab, text="Reaction Time Test", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            reaction_tab,
            text=(
                "Press Start Trial. Wait for the GO signal, then press React as quickly as possible.\n"
                f"Complete {TRIALS_PER_TEST} trials, then save the result."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        reaction_status = ttk.Label(reaction_tab, text="Press Start Trial to begin.")
        reaction_status.pack(anchor="w", pady=(0, 6))

        reaction_progress = ttk.Progressbar(reaction_tab, maximum=TRIALS_PER_TEST, length=300)
        reaction_progress.pack(anchor="w", pady=(0, 8))

        reaction_text = tk.Text(reaction_tab, height=12, width=90)
        reaction_text.pack(fill="both", expand=True, pady=(8, 8))

        reaction_state = {
            "backend": ReactionTimeTest(),
            "trial": 0,
            "stimulus_time": None,
            "waiting": False,
        }

        def reaction_show_go():
            reaction_state["stimulus_time"] = time.perf_counter()
            reaction_state["waiting"] = False
            reaction_status.config(text="GO! Press React now.")

        def start_reaction_trial():
            if reaction_state["trial"] >= TRIALS_PER_TEST:
                reaction_text.insert(tk.END, "\nAll reaction trials are already complete.\n")
                reaction_text.see(tk.END)
                return

            reaction_state["stimulus_time"] = None
            reaction_state["waiting"] = True
            reaction_status.config(text="Wait for GO...")
            delay_ms = random.randint(1500, 3500)
            self.after(delay_ms, reaction_show_go)

        def record_reaction():
            if reaction_state["trial"] >= TRIALS_PER_TEST:
                return

            if reaction_state["waiting"]:
                reaction_status.config(text="Too early. Wait for GO.")
                reaction_text.insert(tk.END, "\nFalse start detected.\n")
                reaction_text.see(tk.END)
                return

            if reaction_state["stimulus_time"] is None:
                return

            response_time = time.perf_counter()
            reaction_state["backend"].record_trial(reaction_state["stimulus_time"], response_time)
            reaction_state["trial"] += 1
            reaction_progress["value"] = reaction_state["trial"]
            rt_ms = (response_time - reaction_state["stimulus_time"]) * 1000.0

            reaction_text.insert(
                tk.END,
                f"\nTrial {reaction_state['trial']} reaction time: {rt_ms:.2f} ms\n",
            )
            reaction_text.see(tk.END)

            reaction_state["stimulus_time"] = None
            reaction_status.config(
                text=f"Trial {reaction_state['trial']} complete."
                if reaction_state["trial"] < TRIALS_PER_TEST
                else "All reaction trials complete. Save result."
            )

        def save_reaction_result():
            result = reaction_state["backend"].finalize()
            cognitive_session.save_result("reaction_time", result)

            self.manager.save_cognitive_result("reaction_time", result)

            reaction_text.insert(
                tk.END,
                f"\nSaved reaction result:\n{json.dumps(result.to_dict(), indent=2)}\n",
            )
            reaction_text.see(tk.END)

        reaction_button_row = ttk.Frame(reaction_tab)
        reaction_button_row.pack(anchor="w", pady=(0, 8))

        ttk.Button(reaction_button_row, text="Start Trial", command=start_reaction_trial).pack(side="left", padx=(0, 8))
        ttk.Button(reaction_button_row, text="React", command=record_reaction).pack(side="left", padx=(0, 8))
        ttk.Button(reaction_button_row, text="Save Reaction Result", command=save_reaction_result).pack(side="left")

        # ---------------- MEMORY TAB ----------------
        ttk.Label(memory_tab, text="Short-Term Memory Test", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            memory_tab,
            text=(
                "A digit sequence will appear briefly.\n"
                "Memorize it, then type it back in the box.\n"
                f"Complete {TRIALS_PER_TEST} rounds, then save the result."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        memory_sequence_label = ttk.Label(memory_tab, text="", font=("Courier New", 18, "bold"))
        memory_sequence_label.pack(anchor="w", pady=(0, 8))

        memory_entry = ttk.Entry(memory_tab, width=30)
        memory_entry.pack(anchor="w", pady=(0, 8))

        memory_progress = ttk.Progressbar(memory_tab, maximum=TRIALS_PER_TEST, length=300)
        memory_progress.pack(anchor="w", pady=(0, 8))

        memory_text = tk.Text(memory_tab, height=12, width=90)
        memory_text.pack(fill="both", expand=True, pady=(8, 8))

        memory_state = {
            "backend": SequenceMemoryTest(),
            "round": 0,
            "current_sequence": [],
        }

        def start_memory_round():
            if memory_state["round"] >= TRIALS_PER_TEST:
                memory_text.insert(tk.END, "\nAll memory rounds are already complete.\n")
                memory_text.see(tk.END)
                return

            seq_len = 3 + memory_state["round"]
            memory_state["current_sequence"] = [random.randint(0, 9) for _ in range(seq_len)]
            memory_sequence_label.config(text=" ".join(map(str, memory_state["current_sequence"])))
            memory_entry.delete(0, tk.END)
            memory_text.insert(
                tk.END,
                f"\nMemory round {memory_state['round'] + 1} started. Sequence length: {seq_len}\n",
            )
            memory_text.see(tk.END)

            def hide_sequence():
                memory_sequence_label.config(text="Enter the sequence now")

            self.after(3000, hide_sequence)

        def submit_memory_round():
            if memory_state["round"] >= TRIALS_PER_TEST:
                return

            raw = memory_entry.get().strip().replace(" ", "")
            if not raw.isdigit():
                messagebox.showerror("Invalid Input", "Please enter digits only.")
                return

            user_sequence = [int(ch) for ch in raw]
            expected_sequence = memory_state["current_sequence"]
            memory_state["backend"].record_round(expected_sequence, user_sequence)
            is_correct = expected_sequence == user_sequence

            memory_state["round"] += 1
            memory_progress["value"] = memory_state["round"]

            memory_text.insert(
                tk.END,
                f"\nRound {memory_state['round']} submitted."
                f"\nExpected: {expected_sequence}"
                f"\nEntered:  {user_sequence}"
                f"\nCorrect: {is_correct}\n",
            )
            memory_text.see(tk.END)

            memory_entry.delete(0, tk.END)
            memory_sequence_label.config(text="")

        def save_memory_result():
            result = memory_state["backend"].finalize()
            cognitive_session.save_result("sequence_memory", result)

            self.manager.save_cognitive_result("sequence_memory", result)

            memory_text.insert(
                tk.END,
                f"\nSaved memory result:\n{json.dumps(result.to_dict(), indent=2)}\n",
            )
            memory_text.see(tk.END)

        memory_button_row = ttk.Frame(memory_tab)
        memory_button_row.pack(anchor="w", pady=(0, 8))

        ttk.Button(memory_button_row, text="Start Memory Round", command=start_memory_round).pack(side="left", padx=(0, 8))
        ttk.Button(memory_button_row, text="Submit Round", command=submit_memory_round).pack(side="left", padx=(0, 8))
        ttk.Button(memory_button_row, text="Save Memory Result", command=save_memory_result).pack(side="left")

        # ---------------- SYMBOL MATCHING TAB ----------------
        ttk.Label(symbol_tab, text="Processing Speed Test", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            symbol_tab,
            text=(
                "Decide whether the two symbols match.\n"
                "Press Same or Different for each pair.\n"
                "When all items are complete, save the result."
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        symbol_pair_label = ttk.Label(symbol_tab, text="Press Start Test", font=("Arial", 18, "bold"))
        symbol_pair_label.pack(anchor="w", pady=(0, 8))

        symbol_progress = ttk.Progressbar(symbol_tab, maximum=10, length=300)
        symbol_progress.pack(anchor="w", pady=(0, 8))

        symbol_text = tk.Text(symbol_tab, height=12, width=90)
        symbol_text.pack(fill="both", expand=True, pady=(8, 8))

        symbol_state = {
            "backend": SymbolMatchingTest(),
            "started": False,
            "total_items": 10,
            "answered": 0,
            "current_pair": None,
        }

        def next_symbol_item():
            if symbol_state["answered"] >= symbol_state["total_items"]:
                symbol_pair_label.config(text="All items complete. Save result.")
                return

            choices = ["@", "#", "$", "%", "&", "*"]
            left = random.choice(choices)
            is_same = random.choice([True, False])
            right = left if is_same else random.choice([c for c in choices if c != left])

            symbol_state["current_pair"] = {
                "left": left,
                "right": right,
                "is_same": is_same,
            }
            symbol_pair_label.config(text=f"{left}        {right}")

        def start_symbol_test():
            symbol_state["backend"].reset()
            symbol_state["backend"].start(time.perf_counter())
            symbol_state["started"] = True
            symbol_state["answered"] = 0
            symbol_progress["value"] = 0
            symbol_text.delete("1.0", tk.END)
            next_symbol_item()

        def answer_symbol(user_says_same: bool):
            if not symbol_state["started"] or symbol_state["current_pair"] is None:
                return

            actual_same = symbol_state["current_pair"]["is_same"]
            correct = user_says_same == actual_same
            symbol_state["backend"].record_response(correct)

            symbol_state["answered"] += 1
            symbol_progress["value"] = symbol_state["answered"]

            symbol_text.insert(
                tk.END,
                f"\nItem {symbol_state['answered']}: "
                f"user said {'same' if user_says_same else 'different'} | "
                f"actual was {'same' if actual_same else 'different'} | "
                f"correct={correct}\n",
            )
            symbol_text.see(tk.END)

            if symbol_state["answered"] >= symbol_state["total_items"]:
                symbol_state["backend"].stop(time.perf_counter())
                symbol_pair_label.config(text="All items complete. Save result.")
            else:
                next_symbol_item()

        def save_symbol_result():
            result = symbol_state["backend"].finalize()
            cognitive_session.save_result("symbol_matching", result)

            self.manager.save_cognitive_result("symbol_matching", result)

            symbol_text.insert(
                tk.END,
                f"\nSaved processing speed result:\n{json.dumps(result.to_dict(), indent=2)}\n",
            )
            symbol_text.see(tk.END)

        symbol_button_row = ttk.Frame(symbol_tab)
        symbol_button_row.pack(anchor="w", pady=(0, 8))

        ttk.Button(symbol_button_row, text="Start Test", command=start_symbol_test).pack(side="left", padx=(0, 8))
        ttk.Button(symbol_button_row, text="Same", command=lambda: answer_symbol(True)).pack(side="left", padx=(0, 8))
        ttk.Button(symbol_button_row, text="Different", command=lambda: answer_symbol(False)).pack(side="left", padx=(0, 8))
        ttk.Button(symbol_button_row, text="Save Result", command=save_symbol_result).pack(side="left")

        self._set_content(frame)

    def show_results(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Unified PADM Results", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 8))

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True)

        summary_tab = ttk.Frame(notebook, padding=8)
        motor_graphs_tab = ttk.Frame(notebook, padding=8)
        cognitive_graphs_tab = ttk.Frame(notebook, padding=8)

        notebook.add(summary_tab, text="Raw Results")
        notebook.add(motor_graphs_tab, text="Motor Graphs")
        notebook.add(cognitive_graphs_tab, text="Cognitive Graphs")

        text = tk.Text(summary_tab, width=100, height=32)
        text.pack(fill="both", expand=True)
        text.insert(tk.END, self.manager.export_json())

        export_data = self.manager.export_dict()
        motor_results = export_data.get("motor_results", {})
        cognitive_results = export_data.get("cognitive_results", {})

        tapping = motor_results.get("tapping_dominant") or motor_results.get("tapping_non_dominant")
        tremor = motor_results.get("tremor_dominant") or motor_results.get("tremor_non_dominant")
        tracing = motor_results.get("tracing_precision")

        reaction = cognitive_results.get("reaction_time")
        memory = cognitive_results.get("sequence_memory")
        symbol = cognitive_results.get("symbol_matching")

        # ---------------- MOTOR GRAPHS ----------------
        self._render_metric_plot(
            motor_graphs_tab,
            title="Tapping Test - Taps Per Second",
            y_label="Taps / second",
            participant_value=tapping.get("taps_per_second") if tapping else None,
        )
        self._render_metric_plot(
            motor_graphs_tab,
            title="Tremor Test - Estimated Frequency",
            y_label="Frequency (Hz)",
            participant_value=tremor.get("estimated_frequency_hz") if tremor else None,
        )
        self._render_metric_plot(
            motor_graphs_tab,
            title="Tracing Test - Mean Deviation",
            y_label="Deviation",
            participant_value=tracing.get("mean_deviation") if tracing else None,
        )

        # ---------------- COGNITIVE SUMMARY ----------------
        ttk.Label(
            cognitive_graphs_tab,
            text="Cognitive Results Overview",
            font=("Arial", 16, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        cognitive_summary = tk.Text(cognitive_graphs_tab, width=100, height=12)
        cognitive_summary.pack(fill="x", expand=False, pady=(0, 12))

        if cognitive_results:
            cognitive_summary.insert(tk.END, json.dumps(cognitive_results, indent=2))
        else:
            cognitive_summary.insert(tk.END, "No cognitive results available yet.")

        # ---------------- COGNITIVE GRAPHS ----------------
        self._render_metric_plot(
            cognitive_graphs_tab,
            title="Reaction Time - Average Reaction Time",
            y_label="Milliseconds",
            participant_value=reaction.get("average_reaction_time_ms") if reaction else None,
        )
        self._render_metric_plot(
            cognitive_graphs_tab,
            title="Memory Test - Accuracy",
            y_label="Accuracy",
            participant_value=memory.get("accuracy") if memory else None,
        )
        self._render_metric_plot(
            cognitive_graphs_tab,
            title="Memory Test - Longest Correct Span",
            y_label="Span Length",
            participant_value=memory.get("longest_correct_span") if memory else None,
        )
        self._render_metric_plot(
            cognitive_graphs_tab,
            title="Processing Speed - Accuracy",
            y_label="Accuracy",
            participant_value=symbol.get("accuracy") if symbol else None,
        )
        self._render_metric_plot(
            cognitive_graphs_tab,
            title="Processing Speed - Items Per Second",
            y_label="Items / second",
            participant_value=symbol.get("items_per_second") if symbol else None,
        )

        self._set_content(frame)


if __name__ == "__main__":
    app = PADMApp()
    app.mainloop()