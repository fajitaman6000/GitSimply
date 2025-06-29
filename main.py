# main.py Please give all changes to this script in WHOLE. Do not give snippets. Respond with the script as a whole pasteable unit without comments made to omit parts like "... rest of xyz method remains the same"
# AGAIN, THIS SCRIPT SHOULD BE DELIVERED BACK TO USER WITHOUT ANY OMISSION EXCEPT LINES WHICH ARE INTENTIONALLY DELETED
# IF THIS FILE IS UNCHANGED **DO NOT RETURN IT**
import traceback
from app import PermutationManager
from tkinter import messagebox
import os
import signal
import platform

def get_app_config_dir():
    """Gets the application-specific config directory path."""
    if platform.system() == "Windows":
        app_data = os.getenv('APPDATA', os.path.expanduser("~"))
        return os.path.join(app_data, "GitSimply")
    elif platform.system() == "Darwin": # macOS
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "GitSimply")
    else: # Linux and other UNIX-like
        return os.path.join(os.path.expanduser("~"), ".config", "gitsimply")

if __name__ == "__main__":
    try:
        app = PermutationManager()
        signal.signal(signal.SIGINT, lambda sig, frame: app.destroy())
        app.mainloop()
    except Exception as e:
        # --- FIX: Log the full traceback to a file and show a user-friendly message ---
        print("--- A CRITICAL ERROR OCCURRED ---")
        traceback.print_exc()
        print("---------------------------------")
        
        # Create a user-friendly message and a detailed log
        full_traceback = "".join(traceback.format_exc())
        
        try:
            app_dir = get_app_config_dir()
            os.makedirs(app_dir, exist_ok=True)
            error_log_path = os.path.join(app_dir, "gitsimply_crash.log")
            
            with open(error_log_path, "w", encoding='utf-8') as f:
                f.write(full_traceback)
            
            user_message = (
                "The application has encountered a critical error and needs to close.\n\n"
                "A detailed error log has been saved to:\n"
                f"{os.path.abspath(error_log_path)}\n\n"
                "Please provide this file if you are reporting the issue."
            )
        except Exception: # In case we can't even write the log file
            user_message = (
                "The application has encountered a critical error and cannot continue.\n\n"
                "The error details could not be saved to a log file.\n\n"
                f"Error: {e}"
            )
        messagebox.showerror("Critical Error", user_message)