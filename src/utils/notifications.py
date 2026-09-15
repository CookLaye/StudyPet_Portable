"""
Unified Notification System for StudyPet.
Handles system-level toast notifications via plyer and standard UI dialogs via tkinter.
"""
import tkinter as tk
from tkinter import messagebox
from plyer import notification as plyer_notify
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
        win.title("Camera Permission")
        win.resizable(False, False)
        win.geometry(f"{int(win.winfo_screenwidth() * 0.3)}x{int(win.winfo_screenheight() * 0.3)}")
        win.attributes('-topmost', True)

        container = tk.Frame(win, padx=20, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(container, text="📷 Camera Access for Study Session",
                 font=("Arial", 12, "bold")).pack(pady=(0, 15))

        msg_text = ("Would you like to enable camera access during study sessions?\n\n"
                   "🔍 This feature helps track your focus and attention by monitoring when you're at your desk.\n\n"
                   "🔒 Your privacy is respected - no recordings or images are saved. The camera is only used to detect presence.")
        tk.Label(container, text=msg_text, wraplength=350, justify=tk.LEFT).pack(pady=(0, 20))

        btn_frame = tk.Frame(container)
        btn_frame.pack()

        def on_accept():
            win.destroy()
            if choice_callback: choice_callback(True, None)

        def on_decline():
            win.destroy()
            if choice_callback: choice_callback(False, None)

        tk.Button(btn_frame, text="Enable", command=on_accept, bg='#4CAF50', fg='white', padx=20).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Not Now", command=on_decline, padx=20).pack(side=tk.LEFT, padx=10)

if __name__ == "__main__":
    # Quick test
    root = tk.Tk()
    root.withdraw()
    NotificationManager.notify("Test", "This is a system notification!")
    print("Notification sent.")
    root.destroy()
