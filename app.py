# app.py, Please give all changes to this script in WHOLE. Do not give snippets. Respond with the script as a whole pasteable unit without comments made to omit parts like "... rest of xyz method remains the same"
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import os
import json
import platform
import subprocess
from git_helper import GitHelper, SESSION_META_DIR

APP_CONFIG_FILE = "config.json"
# --- The session directory is now imported from git_helper ---
SESSION_FILE = "session.json"

class PermutationManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Permutation Manager")
        self.geometry("1100x550")

        self.project_root, self.git_helper, self.active_branch = None, None, ""
        self.is_detached, self.detached_from_branch = False, ""
        self.detached_commit_info, self.is_viewing_latest = {}, False
        self.history = []

        self._load_config()
        self._create_widgets()

        if self.project_root and os.path.exists(self.project_root):
            self._initialize_project(self.project_root)
        else:
            self.main_view_frame.pack_forget()
            self.detached_view_frame.pack_forget()

    # --- NEW: Methods to handle saving and loading session state ---
    def _get_session_path(self):
        if not self.project_root: return None
        return os.path.join(self.project_root, SESSION_META_DIR, SESSION_FILE)

    def _load_session_state(self):
        path = self._get_session_path()
        if path and os.path.exists(path):
            try:
                with open(path, "r") as f:
                    session_data = json.load(f)
                    self.detached_from_branch = session_data.get("detached_from_branch", "")
                    self.detached_commit_info = session_data.get("detached_commit_info", {})
                    self.is_viewing_latest = session_data.get("is_viewing_latest", False)
            except (json.JSONDecodeError, FileNotFoundError):
                self._clear_session_state() # Clear corrupted session
        else:
            self._clear_session_state(clear_vars=True)

    def _save_session_state(self):
        path = self._get_session_path()
        if not path: return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        session_data = {
            "detached_from_branch": self.detached_from_branch,
            "detached_commit_info": self.detached_commit_info,
            "is_viewing_latest": self.is_viewing_latest
        }
        with open(path, "w") as f:
            json.dump(session_data, f, indent=2)

    def _clear_session_state(self, clear_vars=True):
        path = self._get_session_path()
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass # Ignore if file is in use, etc.
        if clear_vars:
            self.detached_from_branch = ""
            self.detached_commit_info = {}
            self.is_viewing_latest = False

    def _initialize_project(self, path):
        self.project_root, self.git_helper = path, GitHelper(path)
        self.proj_label.config(text=self.project_root)
        result = self.git_helper.initialize_repo()
        if not result["success"]: self._show_error(f"Failed to initialize:\n{result['error']}"); return

        # --- MODIFIED: Load session state before updating UI ---
        self._load_session_state()
        self._save_config()
        self.update_ui_state()

    # --- MODIFIED: This is now the single source of truth for UI state ---
    def update_ui_state(self):
        if not self.git_helper: return
        state_res = self.git_helper.get_current_state()
        if not state_res["success"]: self._show_error(state_res["error"]); return

        self.is_detached = state_res["data"]["is_detached"]
        if self.is_detached:
            # If we are detached but have no session info, something is wrong. Force return.
            if not self.detached_from_branch or not self.detached_commit_info:
                messagebox.showwarning("Unstable State", "The app was closed in an unusual state. Returning to the 'main' branch for safety.")
                self.git_helper.checkout('main')
                self._clear_session_state()
                # Rerun the state check
                self.update_ui_state()
                return
            self._show_detached_view()
        else:
            # If we are not detached, there should be no session file. Clean it up.
            self._clear_session_state()
            self.active_branch = state_res["data"]["current_ref"]
            self._show_main_view()

    # --- MODIFIED: Fixes Treeview index bug and handles unsaved changes correctly ---
    def _load_historical_version(self):
        selected_item = self.hist_list.focus()
        if not selected_item:
            self._show_error("Please select a version from the history list to view.")
            return

        # Handle unsaved changes *before* proceeding
        unsaved_status = self._handle_unsaved_changes()
        if unsaved_status in ["cancel", "branch_created"]:
            return

        # FIX: Get the numerical index by finding the item ID in the tuple of all children
        all_items = self.hist_list.get_children()
        try:
            selected_index = all_items.index(selected_item)
        except ValueError:
            self._show_error("Could not find the selected item. Please refresh and try again.")
            return

        self.detached_commit_info = self.history[selected_index]
        self.detached_from_branch = self.active_branch
        self.is_viewing_latest = (selected_index == 0)

        # Save state *before* performing the action
        self._save_session_state()

        result = self.git_helper.checkout(self.detached_commit_info['hash'])
        if result["success"]:
            self.update_ui_state()
        else:
            self._clear_session_state()
            self._show_error(result["error"])
            self.update_ui_state()

    # --- MODIFIED: Clears session state on successful exit from "time machine" ---
    def _return_to_current(self):
        unsaved_status = self._handle_unsaved_changes()
        if unsaved_status in ["cancel", "branch_created"]:
            return

        result = self.git_helper.checkout(self.detached_from_branch)
        if result["success"]:
            self._clear_session_state()
            self.update_ui_state()
        else:
            self._show_error(result["error"])

    def _restore_state_as_new_snapshot(self):
        confirm_msg = f"This will create a new snapshot on the '{self.detached_from_branch}' branch that is an exact copy of the version you are viewing. Proceed?"
        if not messagebox.askyesno("Confirm Restore", confirm_msg): return
        
        unsaved_status = self._handle_unsaved_changes()
        if unsaved_status in ["cancel", "branch_created"]:
            return

        old_subject = self.detached_commit_info.get('subject', 'an old version')
        new_commit_message = f"Restored state to: '{old_subject}'"
        result = self.git_helper.restore_and_commit_past_state(
            branch_to_restore_on=self.detached_from_branch,
            old_commit_hash=self.detached_commit_info['hash'],
            new_commit_message=new_commit_message
        )
        if result["success"]:
            self._clear_session_state() # Clear state on success
            self.update_ui_state()
            self.status_bar.config(text="Successfully restored state as a new snapshot.")
        else:
            self._show_error(result["error"])
            self._return_to_current()

    # --- MODIFIED: Now always prompts for a commit message ---
    def _new_branch_from_detached(self):
        branch_name = simpledialog.askstring("New Branch From Past", "Create a new branch starting from the currently loaded past state.\n\nEnter a name for the new branch:")
        if not branch_name or " " in branch_name:
            if branch_name is not None: self._show_error("Invalid name.")
            return False

        commit_message = simpledialog.askstring("Initial Snapshot", f"This snapshot will contain any modifications you've made.\n\nEnter a description for the first snapshot on branch '{branch_name}':")
        if not commit_message:
            messagebox.showinfo("Cancelled", "Branch creation cancelled because no description was provided.")
            return False

        # Create a new branch from the detached HEAD and switch to it
        result = self.git_helper.create_branch(branch_name, start_point=self.detached_commit_info['hash'])
        if not result["success"]:
            self._show_error(result['error'])
            self.update_ui_state() # Go back to a known state
            return False

        # Now on the new branch, commit the current state as the initial snapshot
        commit_result = self.git_helper.commit(commit_message)
        if not commit_result["success"] and "nothing to commit" not in commit_result.get("error", ""):
            self._show_error(f"Created branch '{branch_name}' but failed to save snapshot:\n{commit_result['error']}")

        self._clear_session_state()
        self.update_ui_state()
        return True

    def _load_config(self):
        try:
            with open(APP_CONFIG_FILE, "r") as f: self.project_root = json.load(f).get("project_root")
        except (FileNotFoundError, json.JSONDecodeError): self.project_root = None
    def _save_config(self):
        with open(APP_CONFIG_FILE, "w") as f: json.dump({"project_root": self.project_root}, f, indent=2)
    def _create_widgets(self):
        top_frame = ttk.Frame(self, padding=(10, 10, 10, 0)); top_frame.pack(fill=tk.X)
        proj_frame = ttk.LabelFrame(top_frame, text="Project Folder", padding=5); proj_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.proj_label = ttk.Label(proj_frame, text="No project selected.", anchor=tk.W); self.proj_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(proj_frame, text="Change", command=self._select_project).pack(side=tk.RIGHT)
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL); main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.left_pane = ttk.Frame(main_pane, padding=10); main_pane.add(self.left_pane, weight=1)
        self.main_view_frame = ttk.Frame(self.left_pane)
        exp_frame = ttk.LabelFrame(self.main_view_frame, text="Branches", padding=10); exp_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.exp_list = tk.Listbox(exp_frame, exportselection=False, font=("Segoe UI Bold", 10)); self.exp_list.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        self.exp_list.bind("<<ListboxSelect>>", self._on_branch_select)
        exp_action_frame = ttk.Frame(exp_frame); exp_action_frame.pack(fill=tk.X)
        self.switch_button = ttk.Button(exp_action_frame, text="Load Selected Branch", command=self._switch_branch, state=tk.DISABLED); self.switch_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.delete_button = ttk.Button(exp_action_frame, text="Delete Selected Branch", command=self._delete_branch, state=tk.DISABLED); self.delete_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))
        action_frame = ttk.Frame(self.main_view_frame); action_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(35,0))
        ttk.Button(action_frame, text="Branch from Current State", command=self._new_branch).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(action_frame, text=(f"Save Snapshot to Current Branch"), command=self._save_snapshot).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))
        self.detached_view_frame = ttk.Frame(self.left_pane)
        detached_label_frame = ttk.LabelFrame(self.detached_view_frame, text="-- PAST VERSION LOADED --", padding=10); detached_label_frame.pack(fill=tk.BOTH, expand=True)
        self.detached_info_label = ttk.Label(detached_label_frame, text="WITHIN BRANCH:\nSnapshot:", justify=tk.LEFT, font=("Segoe UI", 10, "bold")); self.detached_info_label.pack(anchor=tk.W, pady=5)
        ttk.Separator(detached_label_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(detached_label_frame, text="What do you want to do?", justify=tk.LEFT).pack(anchor=tk.W, pady=5)
        self.restore_button = ttk.Button(detached_label_frame, text="Restore this State as New Snapshot", command=self._restore_state_as_new_snapshot); self.restore_button.pack(fill=tk.X, pady=2)
        ttk.Button(detached_label_frame, text="Start New Branch from Here", command=self._new_branch_from_detached).pack(fill=tk.X, pady=2)
        ttk.Separator(detached_label_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Button(detached_label_frame, text="Return to Present", command=self._return_to_current).pack(fill=tk.X, side=tk.BOTTOM, pady=2)
        right_pane = ttk.Frame(main_pane, padding=10); main_pane.add(right_pane, weight=3)
        hist_frame = ttk.LabelFrame(right_pane, text="Snapshots within current branch", padding=10); hist_frame.pack(fill=tk.BOTH, expand=True)
        self.hist_label = ttk.Label(hist_frame, text="..."); self.hist_label.pack(fill=tk.X)
        hist_tree_container = ttk.Frame(hist_frame)
        hist_tree_container.pack(fill=tk.BOTH, expand=True, pady=5)
        self.hist_list = ttk.Treeview(hist_tree_container, columns=('date', 'subject'), show='headings', selectmode='browse')
        self.hist_list.heading('date', text='Timestamp')
        self.hist_list.heading('subject', text='Snapshot Description')
        self.hist_list.column('date', width=160, stretch=tk.NO, anchor=tk.W)
        self.hist_list.column('subject', stretch=tk.YES, anchor=tk.W)
        scrollbar = ttk.Scrollbar(hist_tree_container, orient="vertical", command=self.hist_list.yview)
        self.hist_list.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hist_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.hist_list.tag_configure('oddrow', background='#E6F2FF')
        self.hist_list.tag_configure('evenrow', background="#C2CDD6")
        
        hist_action_frame = ttk.Frame(hist_frame); hist_action_frame.pack(fill=tk.X)
        ttk.Button(hist_action_frame, text="Load Selected Snapshot", command=self._load_historical_version).pack(expand=True, fill=tk.X)
        self.status_bar = ttk.Label(self, text="Welcome!", relief=tk.SUNKEN, anchor=tk.W, padding=5); self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _get_selected_branch_name(self):
        """Gets the clean branch name from the branch listbox selection."""
        indices = self.exp_list.curselection()
        if not indices:
            return None
        full_text = self.exp_list.get(indices[0])
        return full_text.split(':')[-1].strip()

    def _select_project(self):
        path = filedialog.askdirectory(title="Select Your Single Project Folder")
        if path: self._initialize_project(path)
    def _show_main_view(self):
        self.detached_view_frame.pack_forget(); self.main_view_frame.pack(fill=tk.BOTH, expand=True)
        branch_res = self.git_helper.get_all_branches()
        if not branch_res["success"]: self._show_error(branch_res["error"]); return
        self.exp_list.delete(0, tk.END)
        for i, branch in enumerate(branch_res["output"].split('\n')):
            is_active = branch == self.active_branch
            display_text = f" <<CURRENTLY LOADED>>: {branch}" if is_active else f"   {branch}"
            self.exp_list.insert(tk.END, display_text)
            if is_active:
                self.exp_list.itemconfig(i, {'bg':'#e0e8f0'})
        self._update_history_for_branch(self.active_branch)
        self._on_branch_select()

    def _show_detached_view(self):
        self.main_view_frame.pack_forget(); self.detached_view_frame.pack(fill=tk.BOTH, expand=True)
        info_text = (f"WITHIN BRANCH: {self.detached_from_branch}\n" f"Loaded snapshot name: '{self.detached_commit_info.get('subject', 'N/A')}'")
        self.detached_info_label.config(text=info_text)
        self.restore_button.config(state=tk.DISABLED if self.is_viewing_latest else tk.NORMAL)
        self._update_history_for_branch(self.detached_from_branch)
    def _update_history_for_branch(self, branch_name):
        self.hist_label.config(text=f"'{branch_name}'")
        hist_res = self.git_helper.get_history(branch_name)
        for item in self.hist_list.get_children():
            self.hist_list.delete(item)
        if hist_res["success"]:
            self.history = hist_res["data"]
            for i, item in enumerate(self.history):
                tag = 'oddrow' if i % 2 != 0 else 'evenrow'
                self.hist_list.insert('', 'end', values=(f" {item['date']}", f" {item['subject']}"), tags=(tag,))
        else:
            self.history = []
            self._show_error(hist_res["error"])
    
    # --- MODIFIED: Handles unsaved changes differently in detached state ---
    def _handle_unsaved_changes(self):
        if self.git_helper.has_changes():
            if self.is_detached:
                msg = ("You have made changes while viewing a past version.\n\n"
                       "YES - Create a new branch from this point to save them.\n"
                       "NO - Permanently discard the changes.\n"
                       "CANCEL - Do nothing.")
                response = messagebox.askyesnocancel("Unsaved Changes", msg)
                if response is None:
                    return "cancel"
                if response is True:
                    # _new_branch_from_detached returns True on success, False on cancel/fail
                    return "branch_created" if self._new_branch_from_detached() else "cancel"
                else:
                    self.git_helper.discard_changes()
                    return "discarded"
            else: # Original logic for when on a normal branch
                msg = (f"You have unsaved changes in '{self.active_branch}'.\n\n"
                       "YES - Save them as a snapshot first.\n"
                       "NO - Permanently discard the changes.\n"
                       "CANCEL - Do nothing.")
                response = messagebox.askyesnocancel("Unsaved Changes", msg)
                if response is None: return "cancel"
                if response is True: return "saved" if self._save_snapshot() else "cancel"
                else: self.git_helper.discard_changes(); return "discarded"
        return "clean"
    
    def _on_branch_select(self, event=None):
        selected_branch = self._get_selected_branch_name()
        if not selected_branch:
            self.switch_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
            return
        
        is_active = selected_branch == self.active_branch
        is_main = selected_branch == 'main'
        self.switch_button.config(state=tk.DISABLED if is_active else tk.NORMAL)
        self.delete_button.config(state=tk.DISABLED if is_active or is_main else tk.NORMAL)

    def _switch_branch(self):
        target_branch = self._get_selected_branch_name()
        if not target_branch or target_branch == self.active_branch:
            return

        unsaved_status = self._handle_unsaved_changes()
        if unsaved_status in ["cancel", "branch_created"]:
            return

        result = self.git_helper.checkout(target_branch)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])

    # --- MODIFIED: Always prompts for a commit message when branching ---
    def _new_branch(self):
        branch_name = simpledialog.askstring("New Branch", f"Create a new branch based on the current state of '{self.active_branch}'.\n\nEnter a name for the new branch:")
        if not branch_name or " " in branch_name:
            if branch_name is not None: self._show_error("Invalid name.")
            return

        # Any unsaved changes will be carried to the new branch and committed.
        if self.git_helper.has_changes():
            commit_prompt = f"You have unsaved changes that will be included.\n\nEnter a description for the first snapshot on branch '{branch_name}':"
        else:
            commit_prompt = f"Enter a description for the first snapshot on branch '{branch_name}':"
        
        commit_message = simpledialog.askstring("Initial Snapshot", commit_prompt)
        if not commit_message:
            messagebox.showinfo("Cancelled", "Branch creation cancelled because no initial snapshot description was provided.")
            return

        result = self.git_helper.create_branch(branch_name, start_point=self.active_branch)
        if not result["success"]:
            self._show_error(result['error'])
            return

        commit_result = self.git_helper.commit(commit_message)
        if not commit_result["success"] and "nothing to commit" not in commit_result.get("error", ""):
            self._show_error(f"Created branch '{branch_name}' but failed to save snapshot:\n{commit_result['error']}")
        
        self.update_ui_state()

    def _save_snapshot(self):
        if not self.git_helper.has_changes():
            messagebox.showinfo("No Changes", "There are no changes to save.")
            return False
            
        message = simpledialog.askstring(f"Save Snapshot in '{self.active_branch}'", "Enter a short description for the history:")
        if not message: return False
        result = self.git_helper.commit(message)
        if result["success"]: self.update_ui_state(); return True
        else: self._show_error(result['error']); return False

    def _delete_branch(self):
        branch_to_delete = self._get_selected_branch_name()
        if not branch_to_delete or branch_to_delete == self.active_branch or branch_to_delete == 'main':
            return
        
        if not messagebox.askyesno("Confirm Deletion", f"Permanently delete the branch '{branch_to_delete}'? This cannot be undone."): return
        result = self.git_helper.delete_branch(branch_to_delete)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
        
    def _show_error(self, message): messagebox.showerror("Error", message)