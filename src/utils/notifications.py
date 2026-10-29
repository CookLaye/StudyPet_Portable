"""
Unified Notification System for StudyPet.
Handles system-level toast notifications via plyer and standard UI dialogs via tkinter.
"""
import tkinter as tk
from tkinter import messagebox
from plyer import notification as plyer_notify
import subprocess
import sys
import threading

class NotificationManager:
    """
    Single source of truth for all application notifications.
    """

    APP_NAME = "StudyPet"
    APP_ICON = None # Path to .ico file if available

    @staticmethod
    def notify(title: str, message: str):
        """
        Sends a native Windows system notification (Toast).
        Use this for non-blocking updates and alerts.
        """
        def _fire():
            try:
                if sys.platform == "darwin":
                    # STUDYPET-LAUNCHER-FIX: plyer needs the pyobjus package on macOS (not installed), so
                    # use the notification command that ships with every Mac instead.
                    def esc(value):
                        return str(value).replace("\\", "\\\\").replace('"', '\\"')
                    shown_title = title if title else NotificationManager.APP_NAME
                    script = f'display notification "{esc(message)}" with title "{esc(shown_title)}"'
                    subprocess.run(["osascript", "-e", script], check=False, timeout=5)
                    return
                plyer_notify.notify(
                    title=title if title else NotificationManager.APP_NAME,
                    message=message,
                    app_name=NotificationManager.APP_NAME,
                    app_icon=NotificationManager.APP_ICON,
                    timeout=10 # Seconds notification stays on screen
                )
            except Exception as e:
                print(f"[NotificationManager] Failed to send system notification: {e}")

        threading.Thread(target=_fire, daemon=True).start()

    @staticmethod
    def alert(title: str, message: str):
        """
        Shows a blocking information dialog.
        Use this for critical information that MUST be acknowledged.
        """
        messagebox.showinfo(title, message)

    @staticmethod
    def warn(title: str, message: str):
        """
        Shows a blocking warning dialog.
        """
        messagebox.showwarning(title, message)

    @staticmethod
    def error(title: str, message: str):
        """
        Shows a blocking error dialog.
        """
        messagebox.showerror(title, message)

    @staticmethod
    def confirm(title: str, message: str) -> bool:
        """
        Shows a blocking confirmation dialog (Yes/No).
        Returns True if user clicked Yes, False otherwise.
        """
        return messagebox.askyesno(title, message)

    @staticmethod
    def ask_question(title: str, message: str) -> bool:
        """
        Shows a blocking question dialog (Yes/No).
        """
        return messagebox.askyesno(title, message)

# For backward compatibility with existing calls to StudyPetNotification
class StudyPetNotification:
    @staticmethod
    def show_notification(parent, title="StudyPet", message="", duration=4000):
        # Redirect to the new NotificationManager
        NotificationManager.notify(title, message)

    @staticmethod
    def show_camera_permission(parent, choice_callback=None):
        """
        Custom interactive dialog for camera permission.
        Maintained as a custom UI element as it requires user interaction.
        """
        win = tk.Toplevel(parent)
        win.title("📷 Focus Tracking for Study Sessions")
        win.resizable(False, False)
        win.attributes("-topmost", True)

        container = tk.Frame(win, padx=20, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(container, text="📷 Focus Tracking for Study Sessions",
                 font=("Arial", 12, "bold")).pack(pady=(0, 15))

        msg_text = ("While a work session runs, StudyPet can use your camera to check that you are looking at the screen.\n\n"
                   "⚠️ If you look away too often, your pet will warn you. After a few warnings the session ends and earns no points.\n\n"
                   "🔒 Everything is processed on this computer. No video or pictures are saved. The camera is off during breaks and pauses.\n\n"
                   "You can switch this off any time with the checkbox under the timer buttons.")
        tk.Label(container, text=msg_text, wraplength=350, justify=tk.LEFT).pack(pady=(0, 20))

        btn_frame = tk.Frame(container)
        btn_frame.pack()

        def on_accept():
            win.destroy()
            if choice_callback: choice_callback(True, None)

        def on_decline():
            win.destroy()
            if choice_callback: choice_callback(False, None)

        tk.Button(btn_frame, text="Enable", command=on_accept, bg="#4CAF50", fg="white", padx=20).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Not Now", command=on_decline, padx=20).pack(side=tk.LEFT, padx=10)

        # FOCUS-DIALOG-AUTOSIZE: fit the window to its text, centre it, and treat the X button as "Not Now"
        win.protocol("WM_DELETE_WINDOW", on_decline)
        win.update_idletasks()
        w = max(win.winfo_reqwidth(), int(win.winfo_screenwidth() * 0.3))
        h = win.winfo_reqheight()
        win.geometry(f"{w}x{h}+{max(0, (win.winfo_screenwidth() - w) // 2)}+{max(0, (win.winfo_screenheight() - h) // 2)}")

if __name__ == "__main__":
    # Quick test
    root = tk.Tk()
    root.withdraw()
    NotificationManager.notify("Test", "This is a system notification!")
    print("Notification sent.")
    root.destroy()
