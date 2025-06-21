# main.py Please give all changes to this script in WHOLE. Do not give snippets. Respond with the script as a whole pasteable unit without comments made to omit parts like "... rest of xyz method remains the same"
# AGAIN, THIS SCRIPT SHOULD BE DELIVERED BACK TO USER WITHOUT ANY OMISSION EXCEPT LINES WHICH ARE INTENTIONALLY DELETED
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