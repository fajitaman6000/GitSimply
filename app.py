# app.py, Please give all changes to this script in WHOLE. Do not give snippets. Respond with the script as a whole pasteable unit without comments made to omit parts like "... rest of xyz method remains the same"
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import os
import json
import platform
import subprocess
import re
from git_helper import GitHelper, SESSION_META_DIR

APP_CONFIG_FILE = "config.json"
SESSION_FILE = "session.json"

class PermutationManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GitSimply")
        self.geometry("1100x550")
        self.minsize(900, 500)

        self.project_root, self.git_helper, self.active_branch = None, None, ""
        self.is_detached, self.detached_from_branch = False, ""
        self.detached_commit_info, self.is_viewing_latest = {}, False
        self.history, self.current_head_hash = [], None

        self._load_config()
        self._create_widgets()

        if self.project_root and os.path.exists(self.project_root):
            self._show_main_interface()
            self._initialize_project(self.project_root)
        else:
            self._show_welcome_screen()

    def _show_welcome_screen(self):
        self.main_pane.pack_forget()
        self.status_bar.pack_forget()
        self.top_frame.pack_forget()
        self.welcome_frame.pack(fill=tk.BOTH, expand=True)

    def _show_main_interface(self):
        self.welcome_frame.pack_forget()
        self.top_frame.pack(fill=tk.X)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

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
                self._clear_session_state()
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
                pass
        if clear_vars:
            self.detached_from_branch = ""
            self.detached_commit_info = {}
            self.is_viewing_latest = False

    def _initialize_project(self, path):
        self._show_main_interface()
        self.project_root, self.git_helper = path, GitHelper(path)
        self.proj_label.config(text=self.project_root)
        result = self.git_helper.initialize_repo()
        if not result["success"]: self._show_error(f"Failed to initialize project:\n{result['error']}"); return

        self._load_session_state()
        self._save_config()
        self.update_ui_state()

    def update_ui_state(self):
        if not self.git_helper: return
        state_res = self.git_helper.get_current_state()
        if not state_res["success"]: self._show_error(state_res["error"]); return

        hash_res = self.git_helper.get_current_commit_hash()
        if not hash_res["success"]: self._show_error(hash_res["error"]); return
        self.current_head_hash = hash_res["output"]

        has_changes = self.git_helper.has_changes()
        if has_changes:
            self.unsaved_changes_label.pack(fill=tk.X, pady=(2, 5))
        else:
            self.unsaved_changes_label.pack_forget()

        self.is_detached = state_res["data"]["is_detached"]
        if self.is_detached:
            if not self.detached_from_branch or not self.detached_commit_info:
                if has_changes:
                    msg = ("The app was closed unexpectedly while you were viewing a past version, and you have unsaved work.\n\n"
                           "To protect your work, you must save it to a new branch.\n\n"
                           "Please enter a name for this new 'recovery' branch.")
                    
                    branch_name = self._prompt_for_new_branch_name("Recover Unsaved Work", msg)

                    if not branch_name:
                        discard_msg = ("To protect your project, you must either save your unsaved work to a new branch or discard it.\n\n"
                                       "If you choose 'OK', the changes from your last session will be PERMANENTLY DISCARDED and you will be returned to the 'main' branch.")
                        if messagebox.askokcancel("Action Required", discard_msg, icon='warning', parent=self):
                            self.git_helper.discard_changes()
                            self.git_helper.checkout('main')
                            self._clear_session_state()
                            self.update_ui_state()
                        else:
                            messagebox.showerror("Exiting", "The application cannot continue in this unstable state. Please restart and save your work to a new branch.", parent=self)
                            self.destroy()
                        return

                    result = self.git_helper.create_branch(branch_name, start_point=self.current_head_hash)
                    if not result['success']:
                        self._show_error(f"Failed to create recovery branch '{branch_name}':\n{result['error']}")
                        return
                    
                    commit_res = self.git_helper.commit("Recovered unsaved work from unexpected shutdown")
                    if not commit_res['success']:
                        self._show_error(f"Created recovery branch '{branch_name}' but failed to commit the snapshot.\nYour changes are still present but are uncommitted.\n\nError: {commit_res['error']}")
                    
                    messagebox.showinfo("Work Saved", f"Your unsaved work has been safely stored in a new branch named '{branch_name}'. The app will now load this new branch.", parent=self)
                else:
                    messagebox.showwarning("Unstable State", "The app was closed in an unusual state with no unsaved changes. Returning to the 'main' branch for safety.", parent=self)
                    self.git_helper.checkout('main')

                self._clear_session_state()
                self.update_ui_state()
                return

            self._show_detached_view()
        else:
            self._clear_session_state()
            self.active_branch = state_res["data"]["current_ref"]
            self._show_main_view()

    def _load_historical_version(self):
        selected_items = self.hist_list.selection()
        if not selected_items:
            self._show_error("Please select a version from the history list to view.")
            return
        selected_item = selected_items[0]

        unsaved_status = self._handle_unsaved_changes()
        if unsaved_status in ["cancel", "branch_created"]:
            return

        all_items = self.hist_list.get_children('')
        try:
            selected_index = all_items.index(selected_item)
        except ValueError:
            self._show_error("Could not find the selected item. Please refresh and try again.")
            return

        self.detached_commit_info = self.history[selected_index]
        
        if not self.is_detached:
            self.detached_from_branch = self.active_branch

        self.is_viewing_latest = (selected_index == 0)

        self._save_session_state()

        result = self.git_helper.checkout(self.detached_commit_info['hash'])
        if result["success"]:
            self.update_ui_state()
        else:
            self._clear_session_state() # Clear potentially bad state
            self._show_error(result["error"])
            self.update_ui_state() # Refresh to a safe state

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
        if not messagebox.askyesno("Confirm Restore", confirm_msg, parent=self): return
        
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
            self._clear_session_state()
            self.update_ui_state()
            self.status_bar.config(text="Successfully restored state as a new snapshot.")
        else:
            self._show_error(result["error"])
            self._return_to_current()

    def _new_branch_from_detached(self):
        branch_name = self._prompt_for_new_branch_name(
            "New Branch From Past",
            "Create a new branch starting from the currently loaded past state.\n\nEnter a name for the new branch:"
        )
        if not branch_name:
            return False

        result = self.git_helper.create_branch(branch_name, start_point=self.detached_commit_info['hash'])
        if not result["success"]:
            self._show_error(result['error'])
            self.update_ui_state()
            return False

        if self.git_helper.has_changes():
            commit_message = simpledialog.askstring("Save Initial Snapshot", f"You have changes made while viewing the past.\n\nEnter a description to save them as the first snapshot on branch '{branch_name}':", parent=self)
            if commit_message:
                commit_res = self.git_helper.commit(commit_message)
                if not commit_res["success"]:
                    self._show_error(f"Created branch '{branch_name}' but failed to save snapshot:\n{commit_res['error']}")
            else:
                 messagebox.showwarning("Changes Not Saved", f"Branch '{branch_name}' was created, but your unsaved changes were NOT saved as a snapshot. They remain as uncommitted changes.", parent=self)
        
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
        # --- Welcome Screen (initially hidden) ---
        self.welcome_frame = ttk.Frame(self, padding=40)
        ttk.Label(self.welcome_frame, text="Welcome to GitSimply", font=("Segoe UI", 24, "bold")).pack(pady=(0, 10))
        ttk.Label(self.welcome_frame, text="A simple 'save game' system for your code.", font=("Segoe UI", 12)).pack(pady=(0, 30))
        ttk.Label(self.welcome_frame, text="To get started, select your single project folder.\nThis should be the main folder containing all your work.", justify=tk.CENTER).pack(pady=(0, 15))
        ttk.Button(self.welcome_frame, text="Select Project Folder", command=self._select_project, style="Accent.TButton").pack(pady=10)
        self.style = ttk.Style(self)
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        # --- Main UI ---
        self.top_frame = ttk.Frame(self, padding=(10, 10, 10, 0));
        proj_frame = ttk.LabelFrame(self.top_frame, text="Project Folder", padding=5); proj_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.proj_label = ttk.Label(proj_frame, text="No project selected.", anchor=tk.W); self.proj_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(proj_frame, text="Change", command=self._select_project).pack(side=tk.RIGHT)
        self.main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.left_pane = ttk.Frame(self.main_pane, padding=10); self.main_pane.add(self.left_pane, weight=1)
        
        # --- Main (Branch) View ---
        self.main_view_frame = ttk.Frame(self.left_pane)
        exp_frame = ttk.LabelFrame(self.main_view_frame, text="Branches (Experiments)", padding=10); exp_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.exp_list = tk.Listbox(exp_frame, exportselection=False, font=("Segoe UI Bold", 10)); self.exp_list.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        self.exp_list.bind("<<ListboxSelect>>", self._on_branch_select)
        exp_action_frame = ttk.Frame(exp_frame); exp_action_frame.pack(fill=tk.X)
        self.switch_button = ttk.Button(exp_action_frame, text="Switch to Selected Branch", command=self._switch_branch, state=tk.DISABLED); self.switch_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.delete_button = ttk.Button(exp_action_frame, text="Delete Selected Branch", command=self._delete_branch, state=tk.DISABLED); self.delete_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))
        action_frame = ttk.Frame(self.main_view_frame); action_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(35,0))
        ttk.Button(action_frame, text="Branch from Current State", command=self._new_branch).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(action_frame, text="Save Current State as Snapshot", command=self._save_snapshot).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))
        
        # --- Detached (Past Version) View ---
        self.detached_view_frame = ttk.Frame(self.left_pane)
        detached_label_frame = ttk.LabelFrame(self.detached_view_frame, text="-- PAST VERSION LOADED --", padding=10); detached_label_frame.pack(fill=tk.BOTH, expand=True)
        self.detached_info_label = ttk.Label(detached_label_frame, text="WITHIN BRANCH:\nSnapshot:", justify=tk.LEFT, font=("Segoe UI", 10, "bold")); self.detached_info_label.pack(anchor=tk.W, pady=5)
        ttk.Separator(detached_label_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(detached_label_frame, text="You are inside a read-only copy of a past state.\nEdits made here will be lost unless you save them to a new branch.", justify=tk.LEFT, wraplength=300).pack(anchor=tk.W, pady=5)
        self.restore_button = ttk.Button(detached_label_frame, text="Restore this State as New Snapshot", command=self._restore_state_as_new_snapshot); self.restore_button.pack(fill=tk.X, pady=2)
        ttk.Button(detached_label_frame, text="Start New Branch from Here", command=self._new_branch_from_detached).pack(fill=tk.X, pady=2)
        ttk.Separator(detached_label_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Button(detached_label_frame, text="Return to Present", command=self._return_to_current).pack(fill=tk.X, side=tk.BOTTOM, pady=2)
        
        # --- Right Pane (History) ---
        right_pane = ttk.Frame(self.main_pane, padding=10); self.main_pane.add(right_pane, weight=3)
        hist_frame = ttk.LabelFrame(right_pane, text="Snapshots within current branch", padding=10); hist_frame.pack(fill=tk.BOTH, expand=True)
        self.hist_label = ttk.Label(hist_frame, text="..."); self.hist_label.pack(fill=tk.X)
        self.unsaved_changes_label = ttk.Label(hist_frame, text="You have unsaved changes.", foreground="red", font=("Segoe UI", 9, "bold"))
        hist_tree_container = ttk.Frame(hist_frame)
        hist_tree_container.pack(fill=tk.BOTH, expand=True, pady=5)
        self.hist_list = ttk.Treeview(hist_tree_container, columns=('date', 'subject'), show='headings', selectmode='browse')
        self.hist_list.heading('date', text='Timestamp')
        self.hist_list.heading('subject', text='Snapshot Description')
        self.hist_list.column('date', width=160, stretch=tk.NO, anchor=tk.W)
        self.hist_list.column('subject', stretch=tk.YES, anchor=tk.W)
        self.hist_list.bind("<<TreeviewSelect>>", self._on_history_select)
        scrollbar = ttk.Scrollbar(hist_tree_container, orient="vertical", command=self.hist_list.yview)
        self.hist_list.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hist_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.hist_list.tag_configure('oddrow', background='#E6F2FF')
        self.hist_list.tag_configure('evenrow', background="#C2CDD6")
        self.hist_list.tag_configure('current_snapshot', background="#E4FFDD", font=('Segoe UI', 10, 'bold'))
        
        hist_action_frame = ttk.Frame(hist_frame); hist_action_frame.pack(fill=tk.X)
        self.history_action_button = ttk.Button(hist_action_frame, text="Enter Selected Snapshot", command=self._load_historical_version)
        self.history_action_button.pack(expand=True, fill=tk.X)
        self.status_bar = ttk.Label(self, text="Welcome!", relief=tk.SUNKEN, anchor=tk.W, padding=5)

    def _get_selected_branch_name(self):
        indices = self.exp_list.curselection()
        if not indices:
            return None
        full_text = self.exp_list.get(indices[0])
        return full_text.split(':')[-1].strip()

    def _select_project(self):
        path = filedialog.askdirectory(title="Select Your Single Project Folder", parent=self)
        if path: self._initialize_project(path)

    def _show_main_view(self):
        self.detached_view_frame.pack_forget(); self.main_view_frame.pack(fill=tk.BOTH, expand=True)
        branch_res = self.git_helper.get_all_branches()
        if not branch_res["success"]: self._show_error(branch_res["error"]); return
        self.exp_list.delete(0, tk.END)
        branches = sorted([b for b in branch_res["output"].split('\n') if b])
        for i, branch in enumerate(branches):
            is_active = branch == self.active_branch
            display_text = f" << CURRENTLY LOADED>>: {branch}" if is_active else f"   {branch}"
            self.exp_list.insert(tk.END, display_text)
            if is_active:
                # --- FIX: Removed invalid 'font' option for itemconfig ---
                self.exp_list.itemconfig(i, {'bg':'#e0e8f0'})
        self._update_history_for_branch(self.active_branch)
        self._on_branch_select()

    def _show_detached_view(self):
        self.main_view_frame.pack_forget(); self.detached_view_frame.pack(fill=tk.BOTH, expand=True)
        info_text = (f"WITHIN BRANCH: {self.detached_from_branch}\n" f"LOADED SNAPSHOT: '{self.detached_commit_info.get('subject', 'N/A')}'")
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
                is_current_snapshot = False
                if self.is_detached:
                    # In detached mode, highlight the specific commit being viewed
                    if item['hash'] == self.detached_commit_info.get('hash'):
                        is_current_snapshot = True
                else:
                    # In normal mode, the "current" snapshot is the latest one (HEAD)
                    if i == 0:
                        is_current_snapshot = True
                
                tags_to_apply = []
                if is_current_snapshot:
                    tags_to_apply.append('current_snapshot')
                else:
                    tags_to_apply.append('oddrow' if i % 2 != 0 else 'evenrow')

                self.hist_list.insert('', 'end', values=(f" {item['date']}", f" {item['subject']}"), tags=tuple(tags_to_apply))
        else:
            self.history = []
            self._show_error(hist_res["error"])
        self._on_history_select()

    def _on_history_select(self, event=None):
        if not self.history_action_button.winfo_exists(): return
        
        selected_items = self.hist_list.selection()
        if not selected_items:
            self.history_action_button.config(state=tk.DISABLED)
            return
        
        selected_item = selected_items[0]
        all_items = self.hist_list.get_children('')
        try:
            selected_index = all_items.index(selected_item)
            selected_hash = self.history[selected_index]['hash']
        except (ValueError, IndexError):
            self.history_action_button.config(state=tk.DISABLED)
            return

        is_currently_viewed = False
        if self.is_detached:
            if selected_hash == self.detached_commit_info.get('hash'):
                is_currently_viewed = True
        else:
            if selected_hash == self.current_head_hash:
                is_currently_viewed = True

        if is_currently_viewed:
            self.history_action_button.config(state=tk.DISABLED, text="Currently Inside Snapshot")
        else:
            self.history_action_button.config(state=tk.NORMAL, text="Enter Selected Snapshot")
    
    def _handle_unsaved_changes(self):
        if self.git_helper.has_changes():
            if self.is_detached:
                msg = ("You have made changes while viewing a past version.\n\n"
                       "YES - Create a new branch from this point to save them.\n"
                       "NO - Permanently discard the changes.\n"
                       "CANCEL - Do nothing.")
                response = messagebox.askyesnocancel("Unsaved Changes", msg, parent=self)
                if response is None: return "cancel"
                if response is True: return "branch_created" if self._new_branch_from_detached() else "cancel"
                else: self.git_helper.discard_changes(); return "discarded"
            else:
                msg = (f"You have unsaved changes in '{self.active_branch}'.\n\n"
                       "YES - Save them as a snapshot first.\n"
                       "NO - Permanently discard the changes.\n"
                       "CANCEL - Do nothing.")
                response = messagebox.askyesnocancel("Unsaved Changes", msg, parent=self)
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

    def _prompt_for_new_branch_name(self, title, prompt):
        """Prompts user for a new branch name with validation, returns name or None."""
        all_branches = []
        branch_res = self.git_helper.get_all_branches()
        if branch_res["success"]:
            all_branches = branch_res["output"].split('\n')

        while True:
            name = simpledialog.askstring(title, prompt, parent=self)
            if name is None: return None
            
            # Validation checks
            if not name.strip():
                messagebox.showerror("Invalid Name", "Branch names cannot be empty.", parent=self)
                continue
            if re.search(r'\s', name):
                messagebox.showerror("Invalid Name", "Branch names cannot contain spaces.", parent=self)
                continue
            if re.search(r'[\~^:?*\[\\@]', name) or ".." in name:
                messagebox.showerror("Invalid Name", "Branch names cannot contain special characters like ~ : ? * [ \\ ^ @ or consecutive dots (..).", parent=self)
                continue
            if name.startswith('/') or name.endswith('/'):
                messagebox.showerror("Invalid Name", "Branch names cannot start or end with a slash.", parent=self)
                continue
            if name in all_branches:
                messagebox.showerror("Name Exists", f"A branch named '{name}' already exists. Please choose a different name.", parent=self)
                continue
            return name

    def _new_branch(self):
        branch_name = self._prompt_for_new_branch_name(
            "Create New Branch",
            f"Create a new branch based on the current state of '{self.active_branch}'.\n\nEnter a name for the new branch:"
        )
        if not branch_name: return

        result = self.git_helper.create_branch(branch_name, start_point=self.active_branch)
        if not result["success"]:
            self._show_error(result['error'])
            return
        
        if self.git_helper.has_changes():
            commit_message = simpledialog.askstring("Save Initial Snapshot", f"You have uncommitted changes.\n\nEnter a description to save them as the first snapshot on the new branch '{branch_name}':", parent=self)
            if commit_message:
                commit_res = self.git_helper.commit(commit_message)
                if not commit_res["success"]:
                    self._show_error(f"Created branch '{branch_name}' but failed to save snapshot:\n{commit_res['error']}")
            else:
                messagebox.showwarning("Changes Not Saved", f"Branch '{branch_name}' was created, but your unsaved changes were NOT saved as a snapshot. They remain as uncommitted changes.", parent=self)
        
        self.update_ui_state()

    def _save_snapshot(self):
        if not self.git_helper.has_changes():
            messagebox.showinfo("No Changes", "There are no changes to save.", parent=self)
            return False
            
        message = simpledialog.askstring(f"Save Snapshot in '{self.active_branch}'", "Enter a short description for the history:", parent=self)
        if not message: return False
        result = self.git_helper.commit(message)
        if result["success"]: self.update_ui_state(); return True
        else: self._show_error(result['error']); return False

    def _delete_branch(self):
        branch_to_delete = self._get_selected_branch_name()
        if not branch_to_delete or branch_to_delete == self.active_branch or branch_to_delete == 'main':
            return
        
        is_merged_res = self.git_helper.is_branch_merged_into_any_other(branch_to_delete)
        if not is_merged_res["success"]:
            self._show_error(f"Could not determine if branch is safe to delete.\n{is_merged_res['error']}")
            return

        if not is_merged_res["is_merged"]:
            warning_msg = (f"WARNING: The branch '{branch_to_delete}' contains work that does NOT appear in any other branch.\n\n"
                           f"Deleting it will likely cause PERMANENT DATA LOSS.\n\n"
                           f"Are you absolutely sure you want to delete this branch?")
            if not messagebox.askyesno("Potential Data Loss", warning_msg, icon='warning', parent=self):
                return
        else:
            if not messagebox.askyesno("Confirm Deletion", f"Permanently delete the branch '{branch_to_delete}'? This cannot be undone.", parent=self):
                return
        
        result = self.git_helper.delete_branch(branch_to_delete)
        if result["success"]: 
            self.update_ui_state()
        else: 
            self._show_error(result["error"])
        
    def _show_error(self, message):
        simple_message = message
        
        if "nothing to commit, working tree clean" in message:
            messagebox.showinfo("No Changes", "There are no changes to save in the current branch.", parent=self)
            return

        if ".git/index.lock" in message:
            simple_message = "The application seems to be busy or was closed improperly.\n\nPlease wait a moment and try again. If the problem continues, restarting your computer may help."
        elif "did not match any file(s) known to git" in message:
            simple_message = "The file or state you are trying to restore could not be found. It may have been part of a deleted branch or there was an error reading the project history."
        elif "is not a commit and a branch" in message and "cannot be created" in message:
            simple_message = "The name you chose for the branch is invalid. Please avoid special characters and spaces."
        elif "A branch named" in message and "already exists" in message:
            simple_message = "A branch with that name already exists. Please choose a different name."
        elif "invalid refspec" in message:
            simple_message = f"The name specified is not a valid reference. This can happen with invalid branch or commit names.\n\nDetails: {message}"


        messagebox.showerror("Error", simple_message, parent=self)