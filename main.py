# main.py
import traceback
from app import PermutationManager
from tkinter import messagebox

if __name__ == "__main__":
    try:
        app = PermutationManager()
        app.mainloop()
    except Exception as e:
        # --- FIX: Print the full traceback to the console first ---
        print("--- A CRITICAL ERROR OCCURRED ---")
        traceback.print_exc()
        print("---------------------------------")
        
        # Then, create the message for the GUI dialog
        error_message = "An unexpected critical error occurred.\n\n"
        error_message += "".join(traceback.format_exc())
        messagebox.showerror("Critical Error", error_message)