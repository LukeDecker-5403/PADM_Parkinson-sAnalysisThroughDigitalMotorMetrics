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

from padm_motor_tests import TappingSpeedTest, TremorRateTest, TracingPrecisionTest
from padm_data_integration import ParticipantProfile, PADMAssessmentManager


class PADMApp(tk.Tk):
    """Minimal PADM interface scaffold connected to motor-test data collection."""

    def __init__(self):
        super().__init__()
        self.title("PADM - Parkinson's Analysis Through Digital Motor Metrics")
        self.geometry("1000x700")

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

    def show_home(self) -> None:
        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="PADM Interface Layout", font=("Arial", 20, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(
            frame,
            text=(
                "This UI scaffold covers the spreadsheet items for interface layout and motor-test integration.\n\n"
                "Current connected flows:\n"
                "• Participant profile setup\n"
                "• Tapping speed data capture\n"
                "• Tremor motion capture from cursor movement\n"
                "• Tracing precision capture on canvas\n"
                "• Unified session export / result preview"
            ),
            justify="left",
        ).pack(anchor="w")
        self._set_content(frame)

    def show_participant_setup(self) -> None:
        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Participant Setup", font=("Arial", 18, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        fields = {
            "Participant ID": tk.StringVar(),
            "Age": tk.StringVar(),
            "Sex": tk.StringVar(),
            "Handedness": tk.StringVar(value="right"),
            "Sleep Quality (1-10)": tk.StringVar(),
            "Genetic Predisposition (yes/no)": tk.StringVar(value="no"),
        }

        for idx, (label, var) in enumerate(fields.items(), start=1):
            ttk.Label(frame, text=label).grid(row=idx, column=0, sticky="w", pady=4, padx=(0, 8))
            ttk.Entry(frame, textvariable=var, width=32).grid(row=idx, column=1, sticky="w", pady=4)

        def save_participant() -> None:
            participant_id = fields["Participant ID"].get().strip() or "participant_001"
            age_raw = fields["Age"].get().strip()
            sleep_raw = fields["Sleep Quality (1-10)"].get().strip()
            genetic = fields["Genetic Predisposition (yes/no)"].get().strip().lower() in {"yes", "y", "true", "1"}

            profile = ParticipantProfile(
                participant_id=participant_id,
                age=int(age_raw) if age_raw else None,
                sex=fields["Sex"].get().strip() or None,
                handedness=fields["Handedness"].get().strip() or None,
                sleep_quality=int(sleep_raw) if sleep_raw else None,
                genetic_predisposition=genetic,
            )
            self.manager = PADMAssessmentManager(profile)
            messagebox.showinfo("Saved", f"Participant {participant_id} is ready.")

        ttk.Button(frame, text="Save Participant", command=save_participant).grid(row=10, column=0, columnspan=2, sticky="w", pady=12)
        self._set_content(frame)

    def show_tapping_test(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Tapping Speed Test", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 8))

        hand_var = tk.StringVar(value="dominant")
        ttk.Label(frame, text="Hand").pack(anchor="w")
        ttk.Combobox(frame, textvariable=hand_var, values=["dominant", "non_dominant"], state="readonly").pack(anchor="w", pady=(0, 10))

        instructions = ttk.Label(frame, text="Press Start, then tap the SPACEBAR or Tap button for 10 seconds.")
        instructions.pack(anchor="w")

        result_text = tk.Text(frame, height=12, width=80)
        result_text.pack(fill="both", expand=True, pady=10)

        state = {"test": None, "start_time": None, "running": False}

        def record_tap(_event=None):
            if state["running"] and state["test"] is not None and state["start_time"] is not None:
                timestamp = time.perf_counter() - state["start_time"]
                state["test"].record_tap(timestamp)

        def finish_test():
            if not state["running"] or state["test"] is None:
                return
            state["running"] = False
            result = state["test"].finalize()
            self.manager.save_motor_result(f"tapping_{hand_var.get()}", result)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, json.dumps(result.to_dict(), indent=2))

        def start_test():
            state["test"] = TappingSpeedTest(hand=hand_var.get())
            state["start_time"] = time.perf_counter()
            state["running"] = True
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, "Tapping test started...\n")
            self.after(10000, finish_test)

        ttk.Button(frame, text="Start", command=start_test).pack(anchor="w", pady=4)
        ttk.Button(frame, text="Tap", command=record_tap).pack(anchor="w", pady=4)
        frame.bind_all("<space>", record_tap)
        self._set_content(frame)

    def show_tremor_test(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Tremor Rate Test", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(frame, text="Move the cursor naturally inside the canvas for 8 seconds.").pack(anchor="w")

        hand_var = tk.StringVar(value="dominant")
        ttk.Combobox(frame, textvariable=hand_var, values=["dominant", "non_dominant"], state="readonly").pack(anchor="w", pady=(4, 10))

        canvas = tk.Canvas(frame, width=600, height=350, bg="white", highlightthickness=1, highlightbackground="#999")
        canvas.pack(pady=10)

        result_text = tk.Text(frame, height=12, width=80)
        result_text.pack(fill="both", expand=True)

        state = {"test": None, "start_time": None, "running": False}

        def on_motion(event):
            if state["running"] and state["test"] is not None and state["start_time"] is not None:
                timestamp = time.perf_counter() - state["start_time"]
                state["test"].add_sample(timestamp, event.x, event.y)
                r = 2
                canvas.create_oval(event.x - r, event.y - r, event.x + r, event.y + r)

        def finish_test():
            if not state["running"] or state["test"] is None:
                return
            state["running"] = False
            result = state["test"].finalize()
            self.manager.save_motor_result(f"tremor_{hand_var.get()}", result)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, json.dumps(result.to_dict(), indent=2))

        def start_test():
            canvas.delete("all")
            state["test"] = TremorRateTest(hand=hand_var.get())
            state["start_time"] = time.perf_counter()
            state["running"] = True
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, "Tremor capture started...\n")
            self.after(8000, finish_test)

        canvas.bind("<Motion>", on_motion)
        ttk.Button(frame, text="Start", command=start_test).pack(anchor="w", pady=4)
        self._set_content(frame)

    def show_tracing_test(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Tracing Precision Test", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(frame, text="Hold mouse button and trace the blue guide line.").pack(anchor="w")

        canvas = tk.Canvas(frame, width=700, height=350, bg="white", highlightthickness=1, highlightbackground="#999")
        canvas.pack(pady=10)

        target_path = [(80, 175), (220, 120), (360, 220), (500, 140), (620, 180)]
        for i in range(1, len(target_path)):
            x1, y1 = target_path[i - 1]
            x2, y2 = target_path[i]
            canvas.create_line(x1, y1, x2, y2, width=4, fill="blue")

        result_text = tk.Text(frame, height=12, width=80)
        result_text.pack(fill="both", expand=True)

        tracing_test = TracingPrecisionTest(target_path=target_path)
        state = {"running": False, "start_time": None}

        def start_trace(_event=None):
            tracing_test.reset()
            state["running"] = True
            state["start_time"] = time.perf_counter()
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, "Tracing capture started...\n")

        def trace_motion(event):
            if state["running"] and state["start_time"] is not None:
                timestamp = time.perf_counter() - state["start_time"]
                tracing_test.add_sample(timestamp, event.x, event.y)
                r = 2
                canvas.create_oval(event.x - r, event.y - r, event.x + r, event.y + r, fill="black")

        def stop_trace(_event=None):
            if not state["running"]:
                return
            state["running"] = False
            result = tracing_test.finalize()
            self.manager.save_motor_result("tracing_precision", result)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, json.dumps(result.to_dict(), indent=2))

        canvas.bind("<ButtonPress-1>", start_trace)
        canvas.bind("<B1-Motion>", trace_motion)
        canvas.bind("<ButtonRelease-1>", stop_trace)
        self._set_content(frame)

    def show_results(self) -> None:
        if not self._require_manager():
            return

        frame = ttk.Frame(self.content)
        ttk.Label(frame, text="Unified PADM Results", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 8))

        text = tk.Text(frame, width=100, height=35)
        text.pack(fill="both", expand=True)
        text.insert(tk.END, self.manager.export_json())
        self._set_content(frame)


if __name__ == "__main__":
    app = PADMApp()
    app.mainloop()