# app.py
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import os
import json
import platform
import subprocess
from git_helper import GitHelper

APP_CONFIG_FILE = "config.json"

class PermutationManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Permutation Manager")
        self.geometry("1100x550")
        
        # State variables
        self.project_root, self.git_helper, self.active_branch = None, None, ""
        self.is_detached, self.detached_from_branch, self.detached_hash = False, "", ""
        self.history = []
        
        self._load_config()
        self._create_widgets()
        
        if self.project_root and os.path.exists(self.project_root):
            self._initialize_project(self.project_root)
        else:
            self.main_view_frame.pack_forget()
            self.detached_view_frame.pack_forget()

    def _load_config(self):
        try:
            with open(APP_CONFIG_FILE, "r") as f: self.project_root = json.load(f).get("project_root")
        except (FileNotFoundError, json.JSONDecodeError): self.project_root = None

    def _save_config(self):
        with open(APP_CONFIG_FILE, "w") as f: json.dump({"project_root": self.project_root}, f, indent=2)

    def _create_widgets(self):
        # --- Top Level Panes ---
        top_frame = ttk.Frame(self, padding=(10, 10, 10, 0))
        top_frame.pack(fill=tk.X)
        proj_frame = ttk.LabelFrame(top_frame, text="Project Folder", padding=5)
        proj_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.proj_label = ttk.Label(proj_frame, text="No project selected.", anchor=tk.W)
        self.proj_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(proj_frame, text="Change", command=self._select_project).pack(side=tk.RIGHT)
        
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left Pane (Container for dynamic views) ---
        self.left_pane = ttk.Frame(main_pane, padding=10)
        # --- FIX: Changed weight to make left pane slimmer ---
        main_pane.add(self.left_pane, weight=1)

        # --- View 1: Main Control View ---
        self.main_view_frame = ttk.Frame(self.left_pane)
        exp_frame = ttk.LabelFrame(self.main_view_frame, text="Experiments", padding=10)
        exp_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.exp_list = tk.Listbox(exp_frame, exportselection=False, font=("Segoe UI", 10))
        self.exp_list.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        self.exp_list.bind("<<ListboxSelect>>", self._on_experiment_select)
        
        # --- FIX: New button layout for experiments ---
        exp_action_frame = ttk.Frame(exp_frame)
        exp_action_frame.pack(fill=tk.X)
        self.switch_button = ttk.Button(exp_action_frame, text="Switch To", command=self._switch_experiment, state=tk.DISABLED)
        self.switch_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.delete_button = ttk.Button(exp_action_frame, text="Delete", command=self._delete_experiment, state=tk.DISABLED)
        self.delete_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        action_frame = ttk.Frame(self.main_view_frame)
        action_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(action_frame, text="New Experiment", command=self._new_experiment).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(action_frame, text="Save Snapshot", command=self._save_snapshot).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        # --- View 2: Detached Head "Time Machine" View ---
        self.detached_view_frame = ttk.Frame(self.left_pane)
        # ... (This view is unchanged) ...
        detached_label_frame = ttk.LabelFrame(self.detached_view_frame, text="-- VIEWING A PAST VERSION --", padding=10)
        detached_label_frame.pack(fill=tk.BOTH, expand=True)
        self.detached_info_label = ttk.Label(detached_label_frame, text="From experiment:\nCommit:", justify=tk.LEFT, font=("Segoe UI", 10, "bold"))
        self.detached_info_label.pack(anchor=tk.W, pady=5)
        ttk.Separator(detached_label_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(detached_label_frame, text="What do you want to do?", justify=tk.LEFT).pack(anchor=tk.W, pady=5)
        ttk.Button(detached_label_frame, text="Make This the Current Version", command=self._make_this_current).pack(fill=tk.X, pady=2)
        ttk.Button(detached_label_frame, text="Start New Experiment from Here", command=self._new_experiment_from_detached).pack(fill=tk.X, pady=2)
        ttk.Separator(detached_label_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Button(detached_label_frame, text="Return to Present", command=self._return_to_current).pack(fill=tk.X, side=tk.BOTTOM, pady=2)


        # --- Right Pane (History) ---
        right_pane = ttk.Frame(main_pane, padding=10)
        # --- FIX: Changed weight to make right pane wider ---
        main_pane.add(right_pane, weight=3)
        hist_frame = ttk.LabelFrame(right_pane, text="History", padding=10)
        hist_frame.pack(fill=tk.BOTH, expand=True)
        self.hist_label = ttk.Label(hist_frame, text="...")
        self.hist_label.pack(fill=tk.X)
        self.hist_list = tk.Listbox(hist_frame)
        self.hist_list.pack(fill=tk.BOTH, expand=True, pady=5)
        hist_action_frame = ttk.Frame(hist_frame)
        hist_action_frame.pack(fill=tk.X)
        # --- FIX: Simplified history actions ---
        ttk.Button(hist_action_frame, text="View this Version", command=self._load_historical_version).pack(expand=True, fill=tk.X)

    def _select_project(self):
        path = filedialog.askdirectory(title="Select Your Single Project Folder")
        if path: self._initialize_project(path)
    def _initialize_project(self, path):
        self.project_root, self.git_helper = path, GitHelper(path)
        self.proj_label.config(text=self.project_root)
        result = self.git_helper.initialize_repo()
        if not result["success"]: self._show_error(f"Failed to initialize:\n{result['error']}"); return
        self._save_config()
        self.update_ui_state()
    def update_ui_state(self):
        if not self.git_helper: return
        state_res = self.git_helper.get_current_state()
        if not state_res["success"]: self._show_error(state_res["error"]); return
        self.is_detached = state_res["data"]["is_detached"]
        if self.is_detached:
            self.active_branch = self.detached_from_branch
            self.detached_hash = state_res["data"]["current_ref"]
            self._show_detached_view()
        else:
            self.active_branch = state_res["data"]["current_ref"]
            self._show_main_view()
    def _show_main_view(self):
        self.detached_view_frame.pack_forget()
        self.main_view_frame.pack(fill=tk.BOTH, expand=True)
        branch_res = self.git_helper.get_all_branches()
        if not branch_res["success"]: self._show_error(branch_res["error"]); return
        self.exp_list.delete(0, tk.END)
        for i, branch in enumerate(branch_res["output"].split('\n')):
            display_text = f" * {branch}" if branch == self.active_branch else f"   {branch}"
            self.exp_list.insert(tk.END, display_text)
            if branch == self.active_branch:
                self.exp_list.itemconfig(i, {'bg':'#e8f0fe'})
        self._update_history_for_branch(self.active_branch)
    def _show_detached_view(self):
        self.main_view_frame.pack_forget()
        self.detached_view_frame.pack(fill=tk.BOTH, expand=True)
        info_text = (f"From experiment: {self.detached_from_branch}\n"
                     f"Commit: {self.detached_hash}")
        self.detached_info_label.config(text=info_text)
        self._update_history_for_branch(self.detached_from_branch)
    def _update_history_for_branch(self, branch_name):
        self.hist_label.config(text=f"History for '{branch_name}'")
        hist_res = self.git_helper.get_history(branch_name)
        self.hist_list.delete(0, tk.END)
        if hist_res["success"]:
            self.history = hist_res["data"]
            for item in self.history: self.hist_list.insert(tk.END, f"[{item['date']}] {item['subject']}")
        else: self._show_error(hist_res["error"])
    def _handle_unsaved_changes(self):
        if self.git_helper.has_changes():
            response = messagebox.askyesnocancel("Unsaved Changes",
                f"You have unsaved changes in '{self.active_branch}'.\n\nYES - Save them as a snapshot first.\nNO - Permanently discard the changes.\nCANCEL - Do nothing.")
            if response is None: return "cancel"
            if response is True: return "saved" if self._save_snapshot() else "cancel"
            else: self.git_helper.discard_changes(); return "discarded"
        return "clean"
    def _on_experiment_select(self, event=None):
        indices = self.exp_list.curselection()
        if not indices:
            self.switch_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
            return
        selected_branch = self.exp_list.get(indices[0]).strip().lstrip('* ')
        is_active = selected_branch == self.active_branch
        is_main = selected_branch == 'main'
        self.switch_button.config(state=tk.DISABLED if is_active else tk.NORMAL)
        self.delete_button.config(state=tk.DISABLED if is_active or is_main else tk.NORMAL)
    def _switch_experiment(self):
        indices = self.exp_list.curselection()
        if not indices: return
        target_branch = self.exp_list.get(indices[0]).strip().lstrip('* ')
        if self._handle_unsaved_changes() == "cancel": return
        result = self.git_helper.checkout(target_branch)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
    def _load_historical_version(self):
        hist_indices = self.hist_list.curselection()
        if not hist_indices: self._show_error("Please select a version from the history list to view."); return
        if self._handle_unsaved_changes() == "cancel": return
        
        # --- FIX: Correctly get the hash from the self.history data structure ---
        selected_index = hist_indices[0]
        commit_hash = self.history[selected_index]['hash']
        # --- END FIX ---
        
        self.detached_from_branch = self.active_branch
        result = self.git_helper.checkout(commit_hash)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
    def _return_to_current(self):
        result = self.git_helper.checkout(self.detached_from_branch)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
    def _make_this_current(self):
        warning = f"This will force the '{self.detached_from_branch}' experiment back to this point in time, DELETING all newer snapshots on this experiment. This cannot be undone. Proceed?"
        if not messagebox.askyesno("Confirm Destructive Action", warning, icon='warning'): return
        result = self.git_helper.force_reset_to_commit(self.detached_from_branch, self.detached_hash)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
    def _new_experiment_from_detached(self):
        self._create_experiment(start_point=self.detached_hash)
    def _new_experiment(self):
        self._create_experiment(start_point=self.active_branch)
    def _create_experiment(self, start_point):
        name = simpledialog.askstring("New Experiment", "Enter a name for the new experiment:")
        if not name or " " in name:
            if name is not None: self._show_error("Invalid name.")
            return
        result = self.git_helper.create_branch(name, start_point=start_point)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
    def _save_snapshot(self):
        message = simpledialog.askstring("Save Snapshot", "Enter a short description for the history:")
        if not message: return False
        result = self.git_helper.commit(message)
        if result["success"]: self.update_ui_state(); return True
        else: self._show_error(result['error']); return False
    def _delete_experiment(self):
        indices = self.exp_list.curselection()
        if not indices: return
        branch_to_delete = self.exp_list.get(indices[0]).strip().lstrip('* ')
        if not messagebox.askyesno("Confirm Deletion", f"Permanently delete the experiment '{branch_to_delete}'? This cannot be undone."): return
        result = self.git_helper.delete_branch(branch_to_delete)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
    def _show_error(self, message):
        messagebox.showerror("Error", message)