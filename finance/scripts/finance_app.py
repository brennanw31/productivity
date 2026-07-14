#!/usr/bin/env python3
"""Basic Tkinter launcher for finance scripts."""

import os
import subprocess
import sys
import threading


if sys.version_info[0] < 3:
    try:
        raise SystemExit(subprocess.call(["py", "-3", os.path.abspath(__file__)] + sys.argv[1:]))
    except Exception as exc:
        sys.stderr.write("This launcher requires Python 3. Run: py -3 finance/scripts/finance_app.py\n")
        sys.stderr.write(str(exc) + "\n")
        raise SystemExit(1)

import tkinter as tk
from tkinter import messagebox


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINANCE_DIR = os.path.dirname(SCRIPT_DIR)
REPO_DIR = os.path.dirname(FINANCE_DIR)


SCRIPTS = [
    ("Parse Transactions", [sys.executable, os.path.join(SCRIPT_DIR, "parse_transactions.py")]),
    ("Aggregate Transactions", [sys.executable, os.path.join(SCRIPT_DIR, "aggregate_transactions.py")]),
    ("Generate Finance HTML Report", [sys.executable, os.path.join(SCRIPT_DIR, "generate_main_checking_spending_chart.py")]),
    ("Generate House Model", [sys.executable, os.path.join(SCRIPT_DIR, "generate_house_model.py")]),
]


class FinanceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Finance Scripts")
        self.geometry("760x420")

        button_frame = tk.Frame(self)
        button_frame.pack(fill=tk.X, padx=8, pady=8)

        for label, command in SCRIPTS:
            button = tk.Button(button_frame, text=label, command=lambda c=command: self.run_script(c))
            button.pack(side=tk.LEFT, padx=4)

        self.output = tk.Text(self, wrap=tk.WORD)
        self.output.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def append_output(self, text):
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

    def set_buttons_enabled(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        for child in self.winfo_children()[0].winfo_children():
            child.configure(state=state)

    def run_script(self, command):
        self.set_buttons_enabled(False)
        self.append_output("\nRunning: {}\n".format(" ".join(command)))
        if os.path.basename(command[1]) == "generate_main_checking_spending_chart.py":
            self.append_output("If uncategorized items exist, questionnaire windows will open. Use Skip or Abort to continue.\n")
        thread = threading.Thread(target=self._run_script_thread, args=(command,), daemon=True)
        thread.start()

    def _run_script_thread(self, command):
        try:
            completed = subprocess.run(
                command,
                cwd=REPO_DIR,
                text=True,
                capture_output=True,
                check=False,
            )
        except Exception as exc:
            self.after(0, self._finish_script, command, 1, "", str(exc))
            return

        self.after(0, self._finish_script, command, completed.returncode, completed.stdout, completed.stderr)

    def _finish_script(self, command, returncode, stdout, stderr):
        if stdout:
            self.append_output(stdout)
        if stderr:
            self.append_output(stderr)
        self.append_output("Finished with exit code {}.\n".format(returncode))
        self.set_buttons_enabled(True)
        if returncode != 0:
            messagebox.showerror("Script Failed", "{} exited with code {}.".format(os.path.basename(command[1]), returncode))


def main():
    if "--list-scripts" in sys.argv:
        for label, _command in SCRIPTS:
            print(label)
        return 0

    app = FinanceApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())