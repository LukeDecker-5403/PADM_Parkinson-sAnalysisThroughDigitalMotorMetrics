"""
padm_ui_layout.py

Updated PADM interface module.

This file keeps the existing backend files in place and improves the UI workflow:
- Professional sidebar/home layout with softer colors and disclaimers
- Participant setup with clearer instructions and internal participant ID generation
- Tapping workflow: left, right, and alternating tapping, each repeated 3 times
- Tremor workflow: visible Start Trial button, smaller capture area, no raw output box
- Tracing workflow: 4 shapes including a circular task, no raw output box
- Cognitive workflow: clearer instructions, progress tracking, autosave behavior
- Results workflow: no raw results tab; raw JSON is hidden behind Ctrl+Shift+R
- Similarity scoring workflow: normalized motor/cognitive components + PPMI mobility curve comparison

Run from the project folder with:
python padm_ui_layout.py
"""

from __future__ import annotations

import json
import math
import os
import random
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, Optional

try:
    from PIL import Image, ImageTk
except Exception:  # PIL is optional for the icon only
    Image = None
    ImageTk = None

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from padm_motor_tests import (
    TappingSpeedTest,
    TremorRateTest,
    TracingPrecisionTest,
    average_tapping_results,
    average_tremor_results,
    average_tracing_results,
)
from padm_data_integration import ParticipantProfile, PADMAssessmentManager
from padm_scoring_model import calculate_padm_similarity, validate_required_workflow
from padmCognitiveTests import (
    CognitiveAssessmentSession,
    ReactionTimeTest,
    SequenceMemoryTest,
    SymbolMatchingTest,
)


TAPPING_DURATION_SECONDS = 10
TREMOR_DURATION_SECONDS = 8
MOTOR_TRIALS_PER_TASK = 3
TRACING_TRIALS = 4
COGNITIVE_TRIALS_PER_TEST = 3

APP_BG = "#eef5f1"
SIDEBAR_BG = "#dcebe3"
CARD_BG = "#ffffff"
ACCENT = "#2f6f5e"
ACCENT_DARK = "#214f43"
MUTED = "#5f6f68"
SOFT_BLUE = "#e9f2fb"
SOFT_GREEN = "#e8f5ee"
WARNING_BG = "#fff8e6"


class PADMApp(tk.Tk):
    """PADM user interface connected to the existing motor/cognitive backends."""

    def __init__(self):
        super().__init__()
        self.title("PADM - Parkinson's Analysis Through Digital Motor Metrics")
        self.geometry("1260x820")
        self.minsize(1100, 720)
        self.configure(bg=APP_BG)

        self.manager: PADMAssessmentManager | None = None
        self.current_frame: ttk.Frame | None = None
        self._raw_result_key_sequence = "<Control-Shift-R>"

        self._configure_styles()
        self._set_icon_if_available()
        self._build_shell()
        self.show_home()

    # ------------------------------------------------------------------
    # SHELL / STYLE HELPERS
    # ------------------------------------------------------------------
    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background=APP_BG)
        style.configure("Sidebar.TFrame", background=SIDEBAR_BG)
        style.configure("Card.TFrame", background=CARD_BG, relief="flat")
        style.configure("TLabel", background=APP_BG, foreground="#1d2925", font=("Segoe UI", 10))
        style.configure("Sidebar.TLabel", background=SIDEBAR_BG, foreground="#1d2925", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=APP_BG, foreground="#10231e", font=("Segoe UI", 23, "bold"))
        style.configure("Section.TLabel", background=APP_BG, foreground="#10231e", font=("Segoe UI", 14, "bold"))
        style.configure("CardTitle.TLabel", background=CARD_BG, foreground="#10231e", font=("Segoe UI", 13, "bold"))
        style.configure("CardText.TLabel", background=CARD_BG, foreground="#24352f", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=APP_BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Accent.TButton", foreground=[("active", "white")], background=[("active", ACCENT_DARK)])
        style.configure("Sidebar.TButton", font=("Segoe UI", 10), padding=(8, 7))
        style.configure("TNotebook", background=APP_BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("green.Horizontal.TProgressbar", troughcolor="#d7e6dd", background=ACCENT, bordercolor="#d7e6dd")

    def _set_icon_if_available(self) -> None:
        if Image is None or ImageTk is None:
            return
        icon_formats = ["padm_icon.png", "padm_icon.jpg", "padm_icon.ico"]
        for icon_file in icon_formats:
            icon_path = os.path.join(os.path.dirname(__file__), icon_file)
            if os.path.exists(icon_path):
                try:
                    img = Image.open(icon_path)
                    img.thumbnail((32, 32), Image.Resampling.LANCZOS)
                    self.photo_image = ImageTk.PhotoImage(img)
                    self.iconphoto(False, self.photo_image)
                except Exception:
                    pass
                break

    def _build_shell(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.sidebar = ttk.Frame(self, padding=16, style="Sidebar.TFrame")
        self.sidebar.grid(row=0, column=0, sticky="ns")

        ttk.Label(self.sidebar, text="🌷 PADM", style="Sidebar.TLabel", font=("Segoe UI", 20, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        ttk.Label(
            self.sidebar,
            text="Digital Motor Metrics",
            style="Sidebar.TLabel",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 16))

        buttons = [
            ("Home", self.show_home),
            ("Participant Setup", self.show_participant_setup),
            ("Motorskills Tests", None),
            ("Tapping Test", self.show_tapping_test),
            ("Tremor Test", self.show_tremor_test),
            ("Tracing Test", self.show_tracing_test),
            ("Cognitive Testing", None),
            ("Cognitive Tests", self.show_cognitive_tests),
            ("Results", self.show_results),
        ]

        for text, command in buttons:
            if command is None:
                ttk.Label(
                    self.sidebar,
                    text=text,
                    style="Sidebar.TLabel",
                    font=("Segoe UI", 10, "bold"),
                ).pack(anchor="w", pady=(16, 5))
            else:
                ttk.Button(self.sidebar, text=text, command=command, style="Sidebar.TButton").pack(fill="x", pady=4)

        self.content_outer = ttk.Frame(self, padding=18, style="App.TFrame")
        self.content_outer.grid(row=0, column=1, sticky="nsew")
        self.content_outer.columnconfigure(0, weight=1)
        self.content_outer.rowconfigure(0, weight=1)

        # Scrollable content prevents lower controls from disappearing on smaller screens.
        self.canvas_container = tk.Canvas(self.content_outer, bg=APP_BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.content_outer, orient="vertical", command=self.canvas_container.yview)
        self.scrollable_content = ttk.Frame(self.canvas_container, style="App.TFrame")
        self.scrollable_window = self.canvas_container.create_window((0, 0), window=self.scrollable_content, anchor="nw")
        self.canvas_container.configure(yscrollcommand=self.scrollbar.set)
        self.canvas_container.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.scrollable_content.bind("<Configure>", self._update_scrollregion)
        self.canvas_container.bind("<Configure>", self._resize_scrollable_window)

        self.content = self.scrollable_content

    def _update_scrollregion(self, _event=None) -> None:
        self.canvas_container.configure(scrollregion=self.canvas_container.bbox("all"))

    def _resize_scrollable_window(self, event) -> None:
        self.canvas_container.itemconfigure(self.scrollable_window, width=event.width)

    def _set_content(self, frame: ttk.Frame) -> None:
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame
        self.current_frame.pack(fill="both", expand=True)
        self.after(50, self._update_scrollregion)
        self.canvas_container.yview_moveto(0)

    def _card(self, parent: tk.Widget, padding: int = 14) -> ttk.Frame:
        card = ttk.Frame(parent, padding=padding, style="Card.TFrame")
        card.pack(fill="x", pady=(0, 12))
        return card

    def _require_manager(self) -> bool:
        if self.manager is None:
            messagebox.showwarning("Participant Setup Needed", "Please complete Participant Setup before running tests.")
            self.show_participant_setup()
            return False
        return True

    @staticmethod
    def _safe_metric(result: Optional[Dict[str, Any]], key: str) -> Optional[float]:
        if not result:
            return None
        value = result.get(key)
        return value if isinstance(value, (int, float)) else None

    # ------------------------------------------------------------------
    # HOME / SETUP
    # ------------------------------------------------------------------
    def show_home(self) -> None:
        frame = ttk.Frame(self.content, style="App.TFrame")
        ttk.Label(frame, text="PADM", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(
            frame,
            text="Parkinson's Analysis Through Digital Motor Metrics",
            style="Section.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        intro = self._card(frame)
        ttk.Label(intro, text="Purpose of the Program", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            intro,
            text=(
                "PADM is a research prototype that collects digital motor and cognitive metrics from normal computer interactions, "
                "including tapping speed, touchpad/cursor movement, tracing precision, reaction time, memory, and processing speed. "
                "The goal is to produce structured comparison data for future dataset alignment and similarity-based research."
            ),
            style="CardText.TLabel",
            wraplength=880,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        disclaimer = self._card(frame)
        ttk.Label(disclaimer, text="Important Research Disclaimer", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            disclaimer,
            text=(
                "PADM is not a medical diagnostic tool. It does not diagnose, confirm, predict, or rule out Parkinson's disease. "
                "All results are research-oriented digital measurements intended for comparison, visualization, and model-development work only. "
                "Any medical concern should be discussed with a qualified healthcare professional."
            ),
            style="CardText.TLabel",
            wraplength=880,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        workflow = self._card(frame)
        ttk.Label(workflow, text="Workflow", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            workflow,
            text=(
                "1. Complete Participant Setup.\n"
                "2. Complete Motorskills Tests: tapping, tremor, and tracing.\n"
                "3. Complete Cognitive Tests: reaction time, memory, and processing speed.\n"
                "4. Review graph-based results in the Results section."
            ),
            style="CardText.TLabel",
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        button_row = ttk.Frame(frame, style="App.TFrame")
        button_row.pack(anchor="w", pady=(4, 0))
        ttk.Button(button_row, text="Begin Participant Setup", command=self.show_participant_setup, style="Accent.TButton").pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(
            button_row,
            text="About / GitHub",
            command=self._show_about_window,
            style="Accent.TButton",
        ).pack(side="left")

        self._set_content(frame)

    def _show_about_window(self) -> None:
        top = tk.Toplevel(self)
        top.title("About PADM")
        top.geometry("620x360")
        top.configure(bg=APP_BG)
        ttk.Label(top, text="About PADM", style="Title.TLabel").pack(anchor="w", padx=18, pady=(18, 8))
        ttk.Label(
            top,
            text=(
                "PADM is an independent-study research prototype focused on digital motor metrics and cognitive task data.\n\n"
                "GitHub/project link placeholder:\n"
                "Add your repository URL here after confirming the public GitHub link.\n\n"
                "Suggested link format: https://github.com/your-username/your-padm-repository"
            ),
            background=APP_BG,
            wraplength=560,
            justify="left",
        ).pack(anchor="w", padx=18, pady=8)

    def show_participant_setup(self) -> None:
        frame = ttk.Frame(self.content, style="App.TFrame")
        ttk.Label(frame, text="Participant Setup", style="Title.TLabel").pack(anchor="w", pady=(0, 8))

        instruction = self._card(frame)
        ttk.Label(instruction, text="Setup Instructions", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            instruction,
            text=(
                "Enter only the basic participant information needed to structure this research session. "
                "A participant ID will be generated automatically so the user does not need to create one manually."
            ),
            style="CardText.TLabel",
            wraplength=880,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        form = self._card(frame)
        form.columnconfigure(1, weight=1)

        auto_id = f"participant_{int(time.time())}"
        ttk.Label(form, text=f"Generated Participant ID: {auto_id}", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        age_var = tk.StringVar()
        sex_var = tk.StringVar(value="Prefer not to say")
        handedness_var = tk.StringVar(value="right")
        sleep_var = tk.StringVar(value="7")
        genetics_var = tk.StringVar(value="No")
        notes_var = tk.StringVar()

        rows = [
            ("Age", ttk.Entry(form, textvariable=age_var, width=28)),
            ("Sex", ttk.Combobox(form, textvariable=sex_var, values=["Male", "Female", "Other", "Prefer not to say"], state="readonly", width=25)),
            ("Dominant Hand", ttk.Combobox(form, textvariable=handedness_var, values=["right", "left", "ambidextrous"], state="readonly", width=25)),
            ("Sleep Quality (1-10)", ttk.Entry(form, textvariable=sleep_var, width=28)),
            ("Genetic Predisposition", ttk.Combobox(form, textvariable=genetics_var, values=["No", "Yes", "Unknown"], state="readonly", width=25)),
            ("Notes", ttk.Entry(form, textvariable=notes_var, width=60)),
        ]

        for i, (label, widget) in enumerate(rows, start=1):
            ttk.Label(form, text=label, style="CardText.TLabel").grid(row=i, column=0, sticky="w", pady=6, padx=(0, 12))
            widget.grid(row=i, column=1, sticky="w", pady=6)

        def save_profile() -> None:
            try:
                age = int(age_var.get()) if age_var.get().strip() else None
            except ValueError:
                messagebox.showerror("Invalid Age", "Age must be a whole number or left blank.")
                return

            try:
                sleep = int(sleep_var.get()) if sleep_var.get().strip() else None
            except ValueError:
                messagebox.showerror("Invalid Sleep Quality", "Sleep quality must be a whole number from 1-10 or left blank.")
                return

            genetics_raw = genetics_var.get()
            genetics = True if genetics_raw == "Yes" else False if genetics_raw == "No" else None

            profile = ParticipantProfile(
                participant_id=auto_id,
                age=age,
                sex=sex_var.get(),
                handedness=handedness_var.get(),
                sleep_quality=sleep,
                genetic_predisposition=genetics,
                notes=notes_var.get().strip(),
            )
            self.manager = PADMAssessmentManager(profile)
            messagebox.showinfo("Participant Saved", "Participant setup is complete. You can now begin testing.")
            self.show_tapping_test()

        ttk.Button(frame, text="Save Participant and Continue", command=save_profile, style="Accent.TButton").pack(
            anchor="w", pady=(2, 0)
        )
        self._set_content(frame)

    # ------------------------------------------------------------------
    # MOTOR TESTS
    # ------------------------------------------------------------------
    def show_tapping_test(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content, style="App.TFrame")
        ttk.Label(frame, text="Tapping Speed Test", style="Title.TLabel").pack(anchor="w", pady=(0, 8))

        instructions = self._card(frame)
        ttk.Label(instructions, text="Instructions", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            instructions,
            text=(
                "This test measures repeated tapping speed and timing consistency. You will complete three tapping sections: "
                "left hand, right hand, and alternating left/right tapping. Each section has 3 trials. "
                "Press Start Trial, then tap the spacebar as consistently and quickly as possible until the timer ends."
            ),
            style="CardText.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        status_card = self._card(frame)
        condition_label = ttk.Label(status_card, text="Section: Left Hand", style="CardTitle.TLabel")
        condition_label.pack(anchor="w")
        timer_label = ttk.Label(status_card, text=f"Time Remaining: {TAPPING_DURATION_SECONDS:.1f}s", style="CardText.TLabel")
        timer_label.pack(anchor="w", pady=(6, 0))
        trial_label = ttk.Label(status_card, text="Trial: 1 / 3", style="CardText.TLabel")
        trial_label.pack(anchor="w")
        total_label = ttk.Label(status_card, text="Overall Progress: 0 / 9 trials", style="CardText.TLabel")
        total_label.pack(anchor="w")
        tap_count_label = ttk.Label(status_card, text="Taps This Trial: 0", style="CardText.TLabel")
        tap_count_label.pack(anchor="w", pady=(6, 0))

        progress = ttk.Progressbar(status_card, maximum=9, length=440, style="green.Horizontal.TProgressbar")
        progress.pack(anchor="w", pady=(10, 4))

        result_summary = self._card(frame)
        ttk.Label(result_summary, text="Live Summary", style="CardTitle.TLabel").pack(anchor="w")
        summary_label = ttk.Label(
            result_summary,
            text="No trials completed yet.",
            style="CardText.TLabel",
            justify="left",
            wraplength=900,
        )
        summary_label.pack(anchor="w", pady=(6, 0))

        conditions = ["left", "right", "alternating"]
        state: Dict[str, Any] = {
            "condition_index": 0,
            "trial_index": 0,
            "completed_trials": 0,
            "running": False,
            "start_time": None,
            "test": None,
            "results_by_condition": {c: [] for c in conditions},
            "averages": {},
            "space_is_down": False,
        }

        def current_condition() -> str:
            return conditions[state["condition_index"]]

        def display_condition_name(condition: str) -> str:
            return {"left": "Left Hand", "right": "Right Hand", "alternating": "Alternating Tapping"}[condition]

        def refresh_labels() -> None:
            cond = current_condition()
            condition_label.config(text=f"Section: {display_condition_name(cond)}")
            trial_label.config(text=f"Trial: {state['trial_index'] + 1} / {MOTOR_TRIALS_PER_TASK}")
            total_label.config(text=f"Overall Progress: {state['completed_trials']} / 9 trials")
            progress["value"] = state["completed_trials"]

        def update_timer() -> None:
            if not state["running"] or state["start_time"] is None:
                return
            elapsed = time.perf_counter() - state["start_time"]
            remaining = max(0.0, TAPPING_DURATION_SECONDS - elapsed)
            timer_label.config(text=f"Time Remaining: {remaining:.1f}s")
            if remaining > 0:
                self.after(100, update_timer)

        def on_space_press(event=None):
            # Prevent operating-system key repeat from inflating taps/sec when the spacebar is held down.
            # A valid tap is counted once per press-release cycle.
            if state["space_is_down"]:
                return "break"
            state["space_is_down"] = True
            if state["running"] and state["start_time"] is not None and state["test"] is not None:
                timestamp = time.perf_counter() - state["start_time"]
                state["test"].record_tap(timestamp)
                tap_count_label.config(text=f"Taps This Trial: {len(state['test']._tap_times)}")
            return "break"

        def on_space_release(event=None):
            state["space_is_down"] = False
            return "break"

        def finish_trial() -> None:
            if not state["running"]:
                return
            state["running"] = False
            self.unbind("<space>")
            self.unbind("<KeyRelease-space>")
            state["space_is_down"] = False
            result = state["test"].finalize()
            cond = current_condition()
            state["results_by_condition"][cond].append(result)
            state["completed_trials"] += 1
            state["trial_index"] += 1

            if state["trial_index"] >= MOTOR_TRIALS_PER_TASK:
                averaged = average_tapping_results(state["results_by_condition"][cond], hand=cond)
                state["averages"][cond] = averaged
                self.manager.save_motor_result(f"tapping_{cond}", averaged)
                state["trial_index"] = 0
                state["condition_index"] += 1

            if state["condition_index"] >= len(conditions):
                summary_lines = ["Tapping test complete. Averaged results saved automatically:"]
                for cond, avg in state["averages"].items():
                    summary_lines.append(
                        f"- {display_condition_name(cond)}: {avg.get('taps_per_second', 0):.2f} taps/sec, "
                        f"avg interval={avg.get('average_interval_seconds')}"
                    )
                summary_label.config(text="\n".join(summary_lines))
                timer_label.config(text="Time Remaining: 0.0s")
                refresh_labels()
                messagebox.showinfo("Tapping Complete", "All tapping trials are complete and saved.")
                return

            summary_label.config(text=f"Trial saved. Next section/trial is ready: {display_condition_name(current_condition())}.")
            tap_count_label.config(text="Taps This Trial: 0")
            timer_label.config(text=f"Time Remaining: {TAPPING_DURATION_SECONDS:.1f}s")
            refresh_labels()

        def start_trial() -> None:
            if state["running"]:
                return
            if state["condition_index"] >= len(conditions):
                messagebox.showinfo("Complete", "All tapping sections are already complete.")
                return
            cond = current_condition()
            state["test"] = TappingSpeedTest(hand=cond)
            state["start_time"] = time.perf_counter()
            state["running"] = True
            tap_count_label.config(text="Taps This Trial: 0")
            summary_label.config(text="Tap the spacebar now. The trial will stop automatically.")
            self.focus_set()
            self.bind("<space>", on_space_press)
            self.bind("<KeyRelease-space>", on_space_release)
            update_timer()
            self.after(TAPPING_DURATION_SECONDS * 1000, finish_trial)

        ttk.Button(frame, text="Start Trial", command=start_trial, style="Accent.TButton").pack(anchor="w")
        refresh_labels()
        self._set_content(frame)

    def show_tremor_test(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content, style="App.TFrame")
        ttk.Label(frame, text="Tremor Rate Test", style="Title.TLabel").pack(anchor="w", pady=(0, 8))

        instructions = self._card(frame)
        ttk.Label(instructions, text="Instructions", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            instructions,
            text=(
                "Use an external touchpad when possible. Select the hand being tested, press Start Trial, then move naturally inside "
                "the small capture ball for 8 seconds. Keep your finger in the capture area until the trial ends. Complete 3 trials."
            ),
            style="CardText.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        controls = self._card(frame)
        hand_var = tk.StringVar(value="non-dominant")
        ttk.Label(controls, text="Handedness / Test Hand", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Combobox(controls, textvariable=hand_var, values=["dominant", "non-dominant"], state="readonly", width=24).pack(
            anchor="w", pady=(6, 8)
        )
        timer_label = ttk.Label(controls, text=f"Time Remaining: {TREMOR_DURATION_SECONDS:.1f}s", style="CardText.TLabel")
        timer_label.pack(anchor="w")
        trial_label = ttk.Label(controls, text="Trial: 1 / 3", style="CardText.TLabel")
        trial_label.pack(anchor="w")
        progress = ttk.Progressbar(controls, maximum=MOTOR_TRIALS_PER_TASK, length=420, style="green.Horizontal.TProgressbar")
        progress.pack(anchor="w", pady=(8, 8))
        status_label = ttk.Label(controls, text="Press Start Trial to begin.", style="CardText.TLabel")
        status_label.pack(anchor="w")

        start_button = ttk.Button(controls, text="Start Trial", style="Accent.TButton")
        start_button.pack(anchor="w", pady=(10, 0))

        capture_card = self._card(frame)
        ttk.Label(capture_card, text="Capture Area", style="CardTitle.TLabel").pack(anchor="w")
        canvas = tk.Canvas(capture_card, width=460, height=320, bg=CARD_BG, highlightthickness=0)
        canvas.pack(anchor="w", pady=(6, 0))

        state: Dict[str, Any] = {
            "trial": 0,
            "trial_results": [],
            "running": False,
            "start_time": None,
            "test": None,
        }

        def draw_capture_area(active: bool = False, x: Optional[float] = None, y: Optional[float] = None) -> None:
            canvas.delete("all")
            cx, cy, r = 230, 160, 105
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=SOFT_BLUE, outline=ACCENT, width=3)
            canvas.create_text(cx, cy - 135, text="Move naturally inside the circle", fill=MUTED, font=("Segoe UI", 10))
            ball_fill = ACCENT if active else "#9fb9af"
            bx, by = (x, y) if x is not None and y is not None else (cx, cy)
            canvas.create_oval(bx - 9, by - 9, bx + 9, by + 9, fill=ball_fill, outline="")

        def update_timer() -> None:
            if not state["running"] or state["start_time"] is None:
                return
            elapsed = time.perf_counter() - state["start_time"]
            remaining = max(0.0, TREMOR_DURATION_SECONDS - elapsed)
            timer_label.config(text=f"Time Remaining: {remaining:.1f}s")
            if remaining > 0:
                self.after(100, update_timer)

        def on_motion(event) -> None:
            if state["running"] and state["start_time"] is not None and state["test"] is not None:
                timestamp = time.perf_counter() - state["start_time"]
                state["test"].add_sample(timestamp, event.x, event.y)
                draw_capture_area(active=True, x=event.x, y=event.y)

        def finish_trial() -> None:
            if not state["running"]:
                return
            state["running"] = False
            result = state["test"].finalize()
            state["trial_results"].append(result)
            state["trial"] += 1
            progress["value"] = state["trial"]
            trial_label.config(text=f"Trial: {min(state['trial'] + 1, MOTOR_TRIALS_PER_TASK)} / {MOTOR_TRIALS_PER_TASK}")
            timer_label.config(text=f"Time Remaining: {TREMOR_DURATION_SECONDS:.1f}s")

            if state["trial"] >= MOTOR_TRIALS_PER_TASK:
                averaged = average_tremor_results(state["trial_results"], hand=hand_var.get())
                save_key = f"tremor_{hand_var.get().replace('-', '_')}"
                self.manager.save_motor_result(save_key, averaged)
                status_label.config(text="Tremor test complete. Averaged result saved automatically.")
                messagebox.showinfo("Tremor Complete", "All tremor trials are complete and saved.")
            else:
                status_label.config(text="Trial saved. Press Start Trial for the next trial.")
            draw_capture_area(active=False)

        def start_trial() -> None:
            if state["running"]:
                return
            if state["trial"] >= MOTOR_TRIALS_PER_TASK:
                messagebox.showinfo("Complete", "All tremor trials are already complete.")
                return
            state["test"] = TremorRateTest(hand=hand_var.get())
            state["start_time"] = time.perf_counter()
            state["running"] = True
            status_label.config(text="Trial running. Keep your finger moving naturally inside the capture ball.")
            trial_label.config(text=f"Trial: {state['trial'] + 1} / {MOTOR_TRIALS_PER_TASK}")
            draw_capture_area(active=True)
            update_timer()
            self.after(TREMOR_DURATION_SECONDS * 1000, finish_trial)

        canvas.bind("<Motion>", on_motion)
        start_button.configure(command=start_trial)
        draw_capture_area(False)
        self._set_content(frame)

    def show_tracing_test(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content, style="App.TFrame")
        ttk.Label(frame, text="Tracing Precision Test", style="Title.TLabel").pack(anchor="w", pady=(0, 8))

        instructions = self._card(frame)
        ttk.Label(instructions, text="Instructions", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            instructions,
            text=(
                "Press and hold the left mouse button, then trace the guide path as closely as possible. Release the mouse button when the shape is complete. "
                "You will complete 4 tracing tasks, including a circular path. The averaged tracing result saves automatically."
            ),
            style="CardText.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        controls = self._card(frame)
        trial_label = ttk.Label(controls, text=f"Shape / Trial: 1 / {TRACING_TRIALS}", style="CardTitle.TLabel")
        trial_label.pack(anchor="w")
        progress = ttk.Progressbar(controls, maximum=TRACING_TRIALS, length=420, style="green.Horizontal.TProgressbar")
        progress.pack(anchor="w", pady=(8, 6))
        status_label = ttk.Label(controls, text="Trace the visible guide shape.", style="CardText.TLabel")
        status_label.pack(anchor="w")

        canvas_card = self._card(frame)
        canvas = tk.Canvas(canvas_card, width=800, height=400, bg=CARD_BG, highlightthickness=1, highlightbackground="#b6c8bf")
        canvas.pack(anchor="w")

        circle_points = []
        cx, cy, r = 400, 200, 115
        for i in range(48):
            angle = 2 * math.pi * i / 48
            circle_points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        circle_points.append(circle_points[0])

        tracing_paths = [
            [(90, 200), (230, 200), (370, 200), (510, 200), (650, 200)],
            [(100, 310), (190, 110), (280, 310), (370, 110), (460, 310), (550, 110), (640, 310)],
            [(120, 300), (120, 110), (270, 110), (270, 300), (420, 300), (420, 110), (570, 110)],
            circle_points,
        ]

        state: Dict[str, Any] = {"trial": 0, "trial_results": [], "running": False, "start_time": None, "test": None}

        def draw_current_path() -> None:
            canvas.delete("all")
            current_path = tracing_paths[state["trial"]]
            for i in range(1, len(current_path)):
                x1, y1 = current_path[i - 1]
                x2, y2 = current_path[i]
                canvas.create_line(x1, y1, x2, y2, width=5, fill=ACCENT, smooth=True)
            x0, y0 = current_path[0]
            canvas.create_oval(x0 - 8, y0 - 8, x0 + 8, y0 + 8, fill="#2f9d68", outline="")
            canvas.create_text(400, 25, text=f"Trace shape {state['trial'] + 1} of {TRACING_TRIALS}", fill=MUTED, font=("Segoe UI", 12, "bold"))

        def start_trace(_event=None) -> None:
            if state["trial"] >= TRACING_TRIALS:
                return
            state["test"] = TracingPrecisionTest(target_path=tracing_paths[state["trial"]])
            state["test"].reset()
            state["running"] = True
            state["start_time"] = time.perf_counter()
            status_label.config(text=f"Capturing shape {state['trial'] + 1}. Release when complete.")

        def trace_motion(event) -> None:
            if state["running"] and state["start_time"] is not None and state["test"] is not None:
                timestamp = time.perf_counter() - state["start_time"]
                state["test"].add_sample(timestamp, event.x, event.y)
                canvas.create_oval(event.x - 2, event.y - 2, event.x + 2, event.y + 2, fill="#111111", outline="")

        def stop_trace(_event=None) -> None:
            if not state["running"] or state["test"] is None:
                return
            state["running"] = False
            result = state["test"].finalize()
            state["trial_results"].append(result)
            state["trial"] += 1
            progress["value"] = state["trial"]

            if state["trial"] >= TRACING_TRIALS:
                averaged = average_tracing_results(state["trial_results"])
                self.manager.save_motor_result("tracing_precision", averaged)
                trial_label.config(text=f"Shape / Trial: {TRACING_TRIALS} / {TRACING_TRIALS}")
                status_label.config(text="Tracing test complete. Averaged result saved automatically.")
                messagebox.showinfo("Tracing Complete", "All tracing shapes are complete and saved.")
            else:
                trial_label.config(text=f"Shape / Trial: {state['trial'] + 1} / {TRACING_TRIALS}")
                status_label.config(text="Shape saved. Trace the next visible guide shape.")
                draw_current_path()

        draw_current_path()
        canvas.bind("<ButtonPress-1>", start_trace)
        canvas.bind("<B1-Motion>", trace_motion)
        canvas.bind("<ButtonRelease-1>", stop_trace)
        self._set_content(frame)

    # ------------------------------------------------------------------
    # COGNITIVE TESTS
    # ------------------------------------------------------------------
    def show_cognitive_tests(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content, style="App.TFrame")
        ttk.Label(frame, text="Cognitive Testing", style="Title.TLabel").pack(anchor="w", pady=(0, 8))

        intro = self._card(frame)
        ttk.Label(intro, text="Instructions", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            intro,
            text=(
                "Complete the three cognitive tasks in order: reaction time, short-term memory, and processing speed. "
                "Each completed task autosaves into the active participant session. The top progress bar moves when each cognitive task is complete."
            ),
            style="CardText.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        progress_card = self._card(frame)
        cognitive_progress_label = ttk.Label(progress_card, text="Cognitive Progress: 0 / 3 tests complete", style="CardTitle.TLabel")
        cognitive_progress_label.pack(anchor="w")
        cognitive_progress = ttk.Progressbar(progress_card, maximum=3, length=460, style="green.Horizontal.TProgressbar")
        cognitive_progress.pack(anchor="w", pady=(8, 0))

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True, pady=(2, 0))
        reaction_tab = ttk.Frame(notebook, padding=12, style="App.TFrame")
        memory_tab = ttk.Frame(notebook, padding=12, style="App.TFrame")
        symbol_tab = ttk.Frame(notebook, padding=12, style="App.TFrame")
        notebook.add(reaction_tab, text="Reaction Time")
        notebook.add(memory_tab, text="Memory")
        notebook.add(symbol_tab, text="Processing Speed")

        cognitive_session = CognitiveAssessmentSession()
        saved_tests: set[str] = set()

        def mark_saved(test_name: str) -> None:
            saved_tests.add(test_name)
            cognitive_progress["value"] = len(saved_tests)
            cognitive_progress_label.config(text=f"Cognitive Progress: {len(saved_tests)} / 3 tests complete")

        # Reaction Time ---------------------------------------------------
        ttk.Label(reaction_tab, text="Reaction Time Test", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(
            reaction_tab,
            text=(
                "Press Start Trial. A large GO signal will appear after a random wait of 5-15 seconds. "
                "Press React as soon as GO appears. Complete 3 trials. Results autosave after the final trial."
            ),
            background=APP_BG,
            wraplength=880,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        reaction_status = ttk.Label(reaction_tab, text="Press Start Trial to begin.", style="Section.TLabel")
        reaction_status.pack(anchor="w", pady=(0, 8))
        reaction_go_label = tk.Label(reaction_tab, text="WAIT", bg=WARNING_BG, fg=ACCENT_DARK, font=("Segoe UI", 42, "bold"), width=12, height=2)
        reaction_go_label.pack(anchor="w", pady=(0, 10))
        reaction_progress = ttk.Progressbar(reaction_tab, maximum=COGNITIVE_TRIALS_PER_TEST, length=420, style="green.Horizontal.TProgressbar")
        reaction_progress.pack(anchor="w")
        reaction_trial_label = ttk.Label(reaction_tab, text="Trial: 1 / 3", background=APP_BG)
        reaction_trial_label.pack(anchor="w", pady=(4, 8))
        reaction_results_label = ttk.Label(reaction_tab, text="Reaction times will appear here after each trial.", background=APP_BG, justify="left")
        reaction_results_label.pack(anchor="w")

        reaction_state: Dict[str, Any] = {
            "backend": ReactionTimeTest(),
            "trial": 0,
            "stimulus_time": None,
            "waiting": False,
            "after_id": None,
            "times": [],
        }

        def autosave_reaction_if_done() -> None:
            if reaction_state["trial"] >= COGNITIVE_TRIALS_PER_TEST and "reaction_time" not in saved_tests:
                result = reaction_state["backend"].finalize()
                cognitive_session.save_result("reaction_time", result)
                self.manager.save_cognitive_result("reaction_time", result)
                mark_saved("reaction_time")
                reaction_status.config(text="Reaction time complete. Result autosaved.")

        def reaction_show_go() -> None:
            reaction_state["stimulus_time"] = time.perf_counter()
            reaction_state["waiting"] = False
            reaction_go_label.config(text="GO!", bg="#d9f5e6", fg="#126b45")
            reaction_status.config(text="GO! Press React now.")

        def start_reaction_trial() -> None:
            if reaction_state["trial"] >= COGNITIVE_TRIALS_PER_TEST:
                autosave_reaction_if_done()
                return
            if reaction_state["waiting"] or reaction_state["stimulus_time"] is not None:
                return
            reaction_go_label.config(text="WAIT", bg=WARNING_BG, fg=ACCENT_DARK)
            reaction_status.config(text="Wait for GO. Do not press early.")
            reaction_state["waiting"] = True
            delay_ms = random.randint(5000, 15000)
            reaction_state["after_id"] = self.after(delay_ms, reaction_show_go)

        def record_reaction() -> None:
            if reaction_state["trial"] >= COGNITIVE_TRIALS_PER_TEST:
                return
            if reaction_state["waiting"]:
                if reaction_state["after_id"] is not None:
                    self.after_cancel(reaction_state["after_id"])
                reaction_state["waiting"] = False
                reaction_go_label.config(text="EARLY", bg="#fde9e7", fg="#8f2d22")
                reaction_status.config(text="Too early. Press Start Trial again for this trial.")
                reaction_state["after_id"] = None
                return
            if reaction_state["stimulus_time"] is None:
                return
            response_time = time.perf_counter()
            reaction_state["backend"].record_trial(reaction_state["stimulus_time"], response_time)
            rt_ms = (response_time - reaction_state["stimulus_time"]) * 1000.0
            reaction_state["times"].append(rt_ms)
            reaction_state["trial"] += 1
            reaction_state["stimulus_time"] = None
            reaction_progress["value"] = reaction_state["trial"]
            reaction_trial_label.config(text=f"Trial: {min(reaction_state['trial'] + 1, COGNITIVE_TRIALS_PER_TEST)} / {COGNITIVE_TRIALS_PER_TEST}")
            reaction_results_label.config(text="\n".join([f"Trial {i + 1}: {v:.2f} ms" for i, v in enumerate(reaction_state["times"])]))
            reaction_go_label.config(text="DONE", bg=SOFT_GREEN, fg=ACCENT_DARK)
            if reaction_state["trial"] >= COGNITIVE_TRIALS_PER_TEST:
                autosave_reaction_if_done()
            else:
                reaction_status.config(text="Trial recorded. Press Start Trial for the next trial.")

        r_buttons = ttk.Frame(reaction_tab, style="App.TFrame")
        r_buttons.pack(anchor="w", pady=(10, 0))
        ttk.Button(r_buttons, text="Start Trial", command=start_reaction_trial, style="Accent.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(r_buttons, text="React", command=record_reaction, style="Accent.TButton").pack(side="left")

        # Memory ----------------------------------------------------------
        ttk.Label(memory_tab, text="Short-Term Memory Test", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(
            memory_tab,
            text=(
                "A sequence of digits will appear for 5 seconds. While the sequence is visible, the answer box is locked. "
                "After the sequence disappears, type the digits in the same order and submit. The test does not reveal correctness during testing."
            ),
            background=APP_BG,
            wraplength=880,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        memory_trial_label = ttk.Label(memory_tab, text="Trial: 1 / 3", style="Section.TLabel")
        memory_trial_label.pack(anchor="w")
        memory_progress = ttk.Progressbar(memory_tab, maximum=COGNITIVE_TRIALS_PER_TEST, length=420, style="green.Horizontal.TProgressbar")
        memory_progress.pack(anchor="w", pady=(6, 8))
        memory_sequence_label = tk.Label(memory_tab, text="Press Start Memory Round", bg=CARD_BG, fg=ACCENT_DARK, font=("Consolas", 34, "bold"), width=24, height=2)
        memory_sequence_label.pack(anchor="w", pady=(0, 10))
        memory_entry = ttk.Entry(memory_tab, width=32, state="disabled", font=("Segoe UI", 14))
        memory_entry.pack(anchor="w", pady=(0, 8))
        memory_status = ttk.Label(memory_tab, text="The answer box unlocks after the 5-second display period.", background=APP_BG)
        memory_status.pack(anchor="w")

        memory_state: Dict[str, Any] = {"backend": SequenceMemoryTest(), "round": 0, "current_sequence": [], "entry_open": False}

        def autosave_memory_if_done() -> None:
            if memory_state["round"] >= COGNITIVE_TRIALS_PER_TEST and "sequence_memory" not in saved_tests:
                result = memory_state["backend"].finalize()
                cognitive_session.save_result("sequence_memory", result)
                self.manager.save_cognitive_result("sequence_memory", result)
                mark_saved("sequence_memory")
                memory_status.config(text="Memory test complete. Result autosaved.")

        def unlock_memory_entry() -> None:
            memory_sequence_label.config(text="Enter sequence now")
            memory_entry.config(state="normal")
            memory_entry.focus_set()
            memory_state["entry_open"] = True
            memory_status.config(text="Type the digits in order, then press Submit Round.")

        def start_memory_round() -> None:
            if memory_state["round"] >= COGNITIVE_TRIALS_PER_TEST:
                autosave_memory_if_done()
                return
            if memory_state["entry_open"]:
                return
            seq_len = 3 + memory_state["round"]
            memory_state["current_sequence"] = [random.randint(0, 9) for _ in range(seq_len)]
            memory_sequence_label.config(text=" ".join(map(str, memory_state["current_sequence"])))
            memory_entry.config(state="disabled")
            memory_entry.delete(0, tk.END)
            memory_status.config(text="Memorize the sequence. Entry unlocks in 5 seconds.")
            self.after(5000, unlock_memory_entry)

        def submit_memory_round() -> None:
            if memory_state["round"] >= COGNITIVE_TRIALS_PER_TEST or not memory_state["entry_open"]:
                return
            raw = memory_entry.get().strip().replace(" ", "")
            if not raw.isdigit():
                messagebox.showerror("Invalid Input", "Please enter digits only.")
                return
            user_sequence = [int(ch) for ch in raw]
            expected = memory_state["current_sequence"]
            memory_state["backend"].record_round(expected, user_sequence)
            memory_state["round"] += 1
            memory_state["entry_open"] = False
            memory_entry.delete(0, tk.END)
            memory_entry.config(state="disabled")
            memory_progress["value"] = memory_state["round"]
            memory_trial_label.config(text=f"Trial: {min(memory_state['round'] + 1, COGNITIVE_TRIALS_PER_TEST)} / {COGNITIVE_TRIALS_PER_TEST}")
            if memory_state["round"] >= COGNITIVE_TRIALS_PER_TEST:
                memory_sequence_label.config(text="Complete")
                autosave_memory_if_done()
            else:
                memory_sequence_label.config(text="Round submitted")
                memory_status.config(text="Round submitted. Press Start Memory Round for the next sequence.")

        m_buttons = ttk.Frame(memory_tab, style="App.TFrame")
        m_buttons.pack(anchor="w", pady=(10, 0))
        ttk.Button(m_buttons, text="Start Memory Round", command=start_memory_round, style="Accent.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(m_buttons, text="Submit Round", command=submit_memory_round, style="Accent.TButton").pack(side="left")

        # Processing Speed ------------------------------------------------
        ttk.Label(symbol_tab, text="Processing Speed Test", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(
            symbol_tab,
            text=(
                "Compare the two items shown. Press Same if they match or Different if they do not. "
                "There are 3 trials: one symbol pair and two shape-based pairs. Results autosave after trial 3."
            ),
            background=APP_BG,
            wraplength=880,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        symbol_trial_label = ttk.Label(symbol_tab, text="Trial: 1 / 3", style="Section.TLabel")
        symbol_trial_label.pack(anchor="w")
        symbol_progress = ttk.Progressbar(symbol_tab, maximum=COGNITIVE_TRIALS_PER_TEST, length=420, style="green.Horizontal.TProgressbar")
        symbol_progress.pack(anchor="w", pady=(6, 8))
        symbol_pair_label = tk.Label(symbol_tab, text="Press Start Test", bg=CARD_BG, fg=ACCENT_DARK, font=("Segoe UI", 44, "bold"), width=20, height=2)
        symbol_pair_label.pack(anchor="w", pady=(0, 10))
        symbol_status = ttk.Label(symbol_tab, text="Press Start Test to begin.", background=APP_BG)
        symbol_status.pack(anchor="w")

        symbol_state: Dict[str, Any] = {
            "backend": SymbolMatchingTest(),
            "started": False,
            "answered": 0,
            "current_pair": None,
            "items": [
                ("@", "@", True),
                ("●", "■", False),
                ("▲", "▲", True),
            ],
        }

        def autosave_symbol_if_done() -> None:
            if symbol_state["answered"] >= COGNITIVE_TRIALS_PER_TEST and "symbol_matching" not in saved_tests:
                symbol_state["backend"].stop(time.perf_counter())
                result = symbol_state["backend"].finalize()
                cognitive_session.save_result("symbol_matching", result)
                self.manager.save_cognitive_result("symbol_matching", result)
                mark_saved("symbol_matching")
                symbol_status.config(text="Processing speed complete. Result autosaved.")

        def show_symbol_item() -> None:
            if symbol_state["answered"] >= COGNITIVE_TRIALS_PER_TEST:
                symbol_pair_label.config(text="Complete")
                return
            left, right, is_same = symbol_state["items"][symbol_state["answered"]]
            # Randomly invert truth for variety while keeping two shape trials.
            if symbol_state["answered"] == 0:
                is_same = random.choice([True, False])
                symbols = ["@", "#", "$", "%"]
                left = random.choice(symbols)
                right = left if is_same else random.choice([s for s in symbols if s != left])
            elif symbol_state["answered"] == 1:
                is_same = random.choice([True, False])
                left = "●"
                right = "●" if is_same else "■"
            else:
                is_same = random.choice([True, False])
                left = "▲"
                right = "▲" if is_same else "◆"
            symbol_state["current_pair"] = {"left": left, "right": right, "is_same": is_same}
            symbol_pair_label.config(text=f"{left}     {right}")
            symbol_trial_label.config(text=f"Trial: {symbol_state['answered'] + 1} / {COGNITIVE_TRIALS_PER_TEST}")

        def start_symbol_test() -> None:
            if symbol_state["started"]:
                return
            symbol_state["backend"].reset()
            symbol_state["backend"].start(time.perf_counter())
            symbol_state["started"] = True
            symbol_state["answered"] = 0
            symbol_progress["value"] = 0
            symbol_status.config(text="Choose Same or Different for the displayed pair.")
            show_symbol_item()

        def answer_symbol(user_says_same: bool) -> None:
            if not symbol_state["started"] or symbol_state["current_pair"] is None:
                return
            actual_same = symbol_state["current_pair"]["is_same"]
            symbol_state["backend"].record_response(user_says_same == actual_same)
            symbol_state["answered"] += 1
            symbol_progress["value"] = symbol_state["answered"]
            if symbol_state["answered"] >= COGNITIVE_TRIALS_PER_TEST:
                symbol_pair_label.config(text="Complete")
                autosave_symbol_if_done()
            else:
                symbol_status.config(text="Response recorded. Continue with the next pair.")
                show_symbol_item()

        s_buttons = ttk.Frame(symbol_tab, style="App.TFrame")
        s_buttons.pack(anchor="w", pady=(10, 0))
        ttk.Button(s_buttons, text="Start Test", command=start_symbol_test, style="Accent.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(s_buttons, text="Same", command=lambda: answer_symbol(True), style="Accent.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(s_buttons, text="Different", command=lambda: answer_symbol(False), style="Accent.TButton").pack(side="left")

        self._set_content(frame)

    # ------------------------------------------------------------------
    # RESULTS
    # ------------------------------------------------------------------
    def show_results(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content, style="App.TFrame")
        ttk.Label(frame, text="PADM Results", style="Title.TLabel").pack(anchor="w", pady=(0, 8))

        note = self._card(frame)
        ttk.Label(note, text="Results Notice", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            note,
            text=(
                "The graphs below visualize collected participant data, normalized PADM similarity components, and the local PPMI Neuro-QoL mobility reference curve. "
                "The similarity score is a research-prototype comparison score, not a diagnosis or medical prediction. "
                "Hold Ctrl+Shift+R on this Results page to open the raw JSON export."
            ),
            style="CardText.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        self.bind(self._raw_result_key_sequence, lambda _event: self._show_raw_results_window())

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True)
        summary_tab = ttk.Frame(notebook, padding=10, style="App.TFrame")
        motor_tab = ttk.Frame(notebook, padding=10, style="App.TFrame")
        cognitive_tab = ttk.Frame(notebook, padding=10, style="App.TFrame")
        ppmi_tab = ttk.Frame(notebook, padding=10, style="App.TFrame")
        notebook.add(summary_tab, text="Similarity Summary")
        notebook.add(motor_tab, text="Motorskill Results")
        notebook.add(cognitive_tab, text="Cognitive Test Results")
        notebook.add(ppmi_tab, text="PPMI Reference Curve")

        data = self.manager.export_dict()
        similarity = calculate_padm_similarity(data)
        workflow_check = validate_required_workflow(data)
        self._render_similarity_summary(summary_tab, similarity, workflow_check)
        self._render_ppmi_curve_plot(ppmi_tab, similarity)
        motor = data.get("motor_results", {})
        cognitive = data.get("cognitive_results", {})

        tapping_left = motor.get("tapping_left")
        tapping_right = motor.get("tapping_right")
        tapping_alt = motor.get("tapping_alternating")
        tremor = motor.get("tremor_dominant") or motor.get("tremor_non_dominant") or motor.get("tremor_non-dominant")
        tracing = motor.get("tracing_precision")

        reaction = cognitive.get("reaction_time")
        memory = cognitive.get("sequence_memory")
        symbol = cognitive.get("symbol_matching")

        self._render_metric_plot(
            motor_tab,
            title="Tapping Speed - Left Hand",
            y_label="Taps / second",
            participant_value=self._safe_metric(tapping_left, "taps_per_second"),
            healthy_baseline=5.0,
            pd_baseline=3.6,
        )
        self._render_metric_plot(
            motor_tab,
            title="Tapping Speed - Right Hand",
            y_label="Taps / second",
            participant_value=self._safe_metric(tapping_right, "taps_per_second"),
            healthy_baseline=5.0,
            pd_baseline=3.6,
        )
        self._render_metric_plot(
            motor_tab,
            title="Tapping Speed - Alternating",
            y_label="Taps / second",
            participant_value=self._safe_metric(tapping_alt, "taps_per_second"),
            healthy_baseline=4.6,
            pd_baseline=3.2,
        )
        self._render_metric_plot(
            motor_tab,
            title="Tremor Test - Estimated Frequency",
            y_label="Frequency (Hz)",
            participant_value=self._safe_metric(tremor, "estimated_frequency_hz"),
            healthy_baseline=1.0,
            pd_baseline=5.0,
        )
        self._render_metric_plot(
            motor_tab,
            title="Tracing Test - Mean Deviation",
            y_label="Deviation",
            participant_value=self._safe_metric(tracing, "mean_deviation"),
            healthy_baseline=12.0,
            pd_baseline=28.0,
        )

        self._render_metric_plot(
            cognitive_tab,
            title="Reaction Time - Average Reaction Time",
            y_label="Milliseconds",
            participant_value=self._safe_metric(reaction, "average_reaction_time_ms"),
            healthy_baseline=280.0,
            pd_baseline=430.0,
        )
        self._render_metric_plot(
            cognitive_tab,
            title="Memory Test - Accuracy",
            y_label="Accuracy",
            participant_value=self._safe_metric(memory, "accuracy"),
            healthy_baseline=0.85,
            pd_baseline=0.62,
        )
        self._render_metric_plot(
            cognitive_tab,
            title="Memory Test - Longest Correct Span",
            y_label="Span Length",
            participant_value=self._safe_metric(memory, "longest_correct_span"),
            healthy_baseline=5.0,
            pd_baseline=3.5,
        )
        self._render_metric_plot(
            cognitive_tab,
            title="Processing Speed - Accuracy",
            y_label="Accuracy",
            participant_value=self._safe_metric(symbol, "accuracy"),
            healthy_baseline=0.9,
            pd_baseline=0.68,
        )
        self._render_metric_plot(
            cognitive_tab,
            title="Processing Speed - Items Per Second",
            y_label="Items / second",
            participant_value=self._safe_metric(symbol, "items_per_second"),
            healthy_baseline=0.85,
            pd_baseline=0.55,
        )

        self._set_content(frame)


    @staticmethod
    def _format_missing_tests(test_names: list[str]) -> str:
        display = {
            "tapping_left": "left-hand tapping",
            "tapping_right": "right-hand tapping",
            "tapping_alternating": "alternating tapping",
            "tremor_test": "one tremor test",
            "tremor_dominant": "dominant-hand tremor",
            "tremor_non_dominant": "non-dominant-hand tremor",
            "tracing_precision": "tracing precision",
            "reaction_time": "reaction time",
            "sequence_memory": "sequence memory",
            "symbol_matching": "symbol matching",
        }
        return ", ".join(display.get(name, name.replace("_", " ")) for name in test_names)

    def _render_similarity_summary(
        self,
        parent: ttk.Frame,
        similarity: Dict[str, Any],
        workflow_check: Dict[str, Any],
    ) -> None:
        card = ttk.Frame(parent, padding=12, style="Card.TFrame")
        card.pack(fill="x", expand=False, pady=(0, 14))
        ttk.Label(card, text="PADM Similarity Score", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 4))

        score = similarity.get("overall_similarity_score_0_100")
        confidence = similarity.get("confidence", {})
        nearest = similarity.get("ppmi_reference", {}).get("nearest_visit")

        score_text = "Not enough scorable data yet" if score is None else f"{score:.2f} / 100"
        nearest_text = "No PPMI visit match available yet."
        if nearest:
            nearest_text = (
                f"Closest PPMI mobility reference point: {nearest.get('event_id')} "
                f"with mean impairment {nearest.get('mean_mobility_impairment_score'):.2f} "
                f"(difference {nearest.get('absolute_difference'):.2f})."
            )

        missing_motor = workflow_check.get("missing_motor_tests", [])
        missing_cognitive = workflow_check.get("missing_cognitive_tests", [])
        missing_text = "All major workflow tests are saved."
        if missing_motor or missing_cognitive:
            missing_text = (
                "Still missing: "
                + self._format_missing_tests(missing_motor + missing_cognitive)
                + ". Complete these to strengthen the score."
            )

        ttk.Label(
            card,
            text=(
                f"Overall prototype similarity score: {score_text}\n"
                f"Interpretation: {similarity.get('interpretation')}\n"
                f"Coverage: {confidence.get('completed_scorable_features', 0)} / {confidence.get('expected_scorable_features', 0)} scorable features "
                f"({confidence.get('level', 'unknown')})\n"
                f"{nearest_text}\n"
                f"{missing_text}\n\n"
                "This score is calculated from normalized motor and cognitive metrics using transparent prototype weights. "
                "Higher values indicate stronger similarity to the impairment-side anchors used in this research prototype."
            ),
            style="CardText.TLabel",
            wraplength=940,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        components = similarity.get("component_scores", [])
        if not components:
            return

        component_card = ttk.Frame(parent, padding=12, style="Card.TFrame")
        component_card.pack(fill="x", expand=False, pady=(0, 14))
        ttk.Label(component_card, text="Component Scores", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 4))

        columns = ("Metric", "Raw Value", "Score", "Weight")
        tree = ttk.Treeview(component_card, columns=columns, show="headings", height=min(12, len(components)))
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor="w", width=210 if col == "Metric" else 110)
        for component in components:
            tree.insert(
                "",
                "end",
                values=(
                    component.get("label"),
                    component.get("raw_value"),
                    component.get("impairment_score_0_100"),
                    component.get("weight"),
                ),
            )
        tree.pack(fill="x", expand=True, pady=(6, 0))

    def _render_ppmi_curve_plot(self, parent: ttk.Frame, similarity: Dict[str, Any]) -> None:
        card = ttk.Frame(parent, padding=12, style="Card.TFrame")
        card.pack(fill="x", expand=False, pady=(0, 14))
        ttk.Label(card, text="PPMI Neuro-QoL Mobility Reference Curve", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 4))

        ppmi = similarity.get("ppmi_reference", {})
        curve = ppmi.get("curve", [])
        participant_score = similarity.get("overall_similarity_score_0_100")

        if not curve:
            ttk.Label(
                card,
                text="PPMI reference curve file was not found or did not contain curve data.",
                style="CardText.TLabel",
            ).pack(anchor="w", pady=(6, 0))
            return

        labels = [str(row.get("event_id")) for row in curve]
        scores = [float(row.get("mean_mobility_impairment_score", 0.0)) for row in curve]
        x_values = list(range(len(labels)))

        fig, ax = plt.subplots(figsize=(9.0, 3.8), dpi=100)
        ax.plot(x_values, scores, marker="o", label="PPMI mean mobility impairment")

        if participant_score is not None:
            ax.axhline(float(participant_score), linestyle="--", label="Participant PADM similarity score")
            ax.text(
                len(x_values) - 1,
                float(participant_score),
                f" Participant {participant_score:.2f}",
                va="bottom",
                fontsize=9,
            )

        ax.set_xticks(x_values)
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_ylabel("Impairment score (0-100)")
        ax.set_title("PPMI Mobility Reference vs. PADM Participant Score")
        ax.grid(axis="y", alpha=0.25)
        ax.legend(loc="upper left")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        canvas.get_tk_widget().pack(anchor="w", fill="x", expand=True)
        plt.close(fig)

        ttk.Label(
            card,
            text=(
                "The PPMI curve is based on the local ppmi_mobility_reference_curve.json file. "
                "The participant line uses PADM's normalized prototype similarity score, so it is a visual comparison layer rather than a clinical equivalence claim."
            ),
            style="CardText.TLabel",
            wraplength=940,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

    def _show_raw_results_window(self) -> None:
        if self.manager is None:
            return
        top = tk.Toplevel(self)
        top.title("Raw PADM JSON Export")
        top.geometry("900x650")
        text = tk.Text(top, wrap="none")
        text.pack(fill="both", expand=True)
        text.insert(tk.END, self.manager.export_json())

    def _render_metric_plot(
        self,
        parent: ttk.Frame,
        title: str,
        y_label: str,
        participant_value: Optional[float],
        healthy_baseline: float,
        pd_baseline: float,
    ) -> None:
        card = ttk.Frame(parent, padding=12, style="Card.TFrame")
        card.pack(fill="x", expand=False, pady=(0, 14))
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 4))

        fig, ax = plt.subplots(figsize=(6.8, 3.0), dpi=100)
        labels = ["NPD Baseline", "Participant", "PD Projected"]
        display_values = [healthy_baseline, participant_value if participant_value is not None else 0.0, pd_baseline]
        bars = ax.bar(labels, display_values)
        ax.set_ylabel(y_label)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)

        max_value = max([healthy_baseline, pd_baseline] + ([participant_value] if participant_value is not None else []))
        ax.set_ylim(0, max(max_value * 1.20, 1.0))

        if participant_value is None:
            bars[1].set_alpha(0.15)
            ax.text(1, max_value * 0.45 if max_value > 0 else 0.5, "No participant data", ha="center", va="center", fontsize=10)

        for index, (bar, value) in enumerate(zip(bars, display_values)):
            if participant_value is None and index == 1:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        canvas.get_tk_widget().pack(anchor="w", fill="x", expand=True)
        plt.close(fig)


if __name__ == "__main__":
    app = PADMApp()
    app.mainloop()
