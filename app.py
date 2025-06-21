# app.py
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import os
import json
from git_helper import GitHelper

APP_CONFIG_FILE = "config.json"

class PermutationManager(tk.Tk):
    # ... __init__, _load_config, _save_config are unchanged ...
    def __init__(self):
        super().__init__()
        self.title("Permutation Manager")
        self.geometry("1000x600")
        self.project_root, self.git_helper, self.branches, self.current_branch, self.history = None, None, [], "", []
        self._load_config()
        self._create_widgets()
        if self.project_root and os.path.exists(self.project_root): self._initialize_project(self.project_root)
        else: self.status_bar.config(text="Welcome! Select your single project folder to begin.")
    def _load_config(self):
        try:
            with open(APP_CONFIG_FILE, "r") as f: self.project_root = json.load(f).get("project_root")
        except (FileNotFoundError, json.JSONDecodeError): self.project_root = None
    def _save_config(self):
        with open(APP_CONFIG_FILE, "w") as f: json.dump({"project_root": self.project_root}, f, indent=2)

    def _create_widgets(self):
        # ... UI layout ...
        self.main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left_frame = ttk.Frame(self.main_pane, padding=10)
        self.main_pane.add(left_frame, weight=1)
        proj_frame = ttk.LabelFrame(left_frame, text="Project Folder", padding=10)
        proj_frame.pack(fill=tk.X, pady=(0, 10))
        self.proj_label = ttk.Label(proj_frame, text="No project selected.", wraplength=350)
        self.proj_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(proj_frame, text="Change", command=self._select_project).pack(side=tk.RIGHT)
        exp_frame = ttk.LabelFrame(left_frame, text="Current Experiment", padding=10)
        exp_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.exp_list = tk.Listbox(exp_frame, exportselection=False, font=("Segoe UI", 10))
        self.exp_list.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        self.exp_list.bind("<<ListboxSelect>>", self._on_experiment_select)
        exp_button_frame = ttk.Frame(exp_frame)
        exp_button_frame.pack(fill=tk.X)
        self.switch_button = ttk.Button(exp_button_frame, text="Switch to Selected", command=self._switch_experiment, state=tk.DISABLED)
        self.switch_button.pack(side=tk.LEFT, expand=True, fill=tk.X)
        action_button_frame = ttk.Frame(left_frame)
        action_button_frame.pack(fill=tk.X, pady=5)
        ttk.Button(action_button_frame, text="New Experiment", command=self._new_experiment).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(action_button_frame, text="Delete Selected", command=self._delete_experiment).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        snap_frame = ttk.LabelFrame(left_frame, text="Save Snapshot", padding=10)
        snap_frame.pack(fill=tk.X)
        self.commit_msg = tk.Text(snap_frame, height=4)
        self.commit_msg.pack(fill=tk.X, expand=True, pady=(0, 5))
        self.save_button = ttk.Button(snap_frame, text="Save Current Version", command=self._save_snapshot, state=tk.NORMAL)
        self.save_button.pack(fill=tk.X)
        right_frame = ttk.Frame(self.main_pane, padding=10)
        self.main_pane.add(right_frame, weight=2)
        hist_frame = ttk.LabelFrame(right_frame, text="History", padding=10)
        hist_frame.pack(fill=tk.BOTH, expand=True)
        self.hist_label = ttk.Label(hist_frame, text="Select an experiment to see its history")
        self.hist_label.pack(fill=tk.X, pady=(0, 5))
        self.hist_list = tk.Listbox(hist_frame)
        self.hist_list.pack(fill=tk.BOTH, expand=True)
        hist_button_frame = ttk.Frame(hist_frame)
        hist_button_frame.pack(fill=tk.X, pady=(5,0))
        ttk.Button(hist_button_frame, text="Create New Experiment from this Version", command=self._create_from_history).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5,0))
        # --- MODIFIED: Renamed button and command ---
        ttk.Button(hist_button_frame, text="Force Restore This Version", command=self._force_restore_snapshot).pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.status_bar = ttk.Label(self, text="Welcome!", relief=tk.SUNKEN, anchor=tk.W, padding=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # --- MODIFIED: This is the heavy-handed restore function ---
    def _force_restore_snapshot(self):
        hist_indices = self.hist_list.curselection()
        if not hist_indices:
            self._show_error("Please select the historical version you want to restore.")
            return

        commit_to_restore = self.history[hist_indices[0]]
        commit_hash = commit_to_restore['hash']
        commit_subject = commit_to_restore['subject']

        # The big, scary, necessary warning
        warning_message = (
            f"You are about to force restore the experiment '{self.current_branch}' to the version:\n\n"
            f"'{commit_subject}'\n\n"
            "**WARNING:** This will permanently delete all newer snapshots on this experiment. "
            "It will also discard any unsaved changes you have.\n\n"
            "This action CANNOT BE UNDONE.\n\n"
            "Are you absolutely sure you want to proceed?"
        )
        
        if not messagebox.askyesno("Confirm Destructive Action", warning_message, icon='warning'):
            return

        # Call the heavy-handed helper method
        result = self.git_helper.force_reset_to_commit(commit_hash)

        if result["success"]:
            self.status_bar.config(text=f"Successfully restored to version {commit_hash}.")
            self.update_ui_state() # Crucial to refresh the history list
        else:
            self._show_error(result["error"])

    # ... All other methods are unchanged and work with this model ...
    def _initialize_project(self, path):
        self.project_root, self.git_helper = path, GitHelper(path)
        self.proj_label.config(text=self.project_root)
        result = self.git_helper.initialize_repo()
        if not result["success"]: self._show_error(f"Failed to initialize project:\n{result['error']}"); return
        self._save_config()
        self.update_ui_state()
    def update_ui_state(self):
        if not self.git_helper: return
        branch_result = self.git_helper.get_branches()
        if not branch_result["success"]: self._show_error(branch_result["error"]); return
        self.branches, self.current_branch = branch_result["data"]["all"], branch_result["data"]["current"]
        selected_indices = self.exp_list.curselection()
        self.exp_list.delete(0, tk.END)
        for i, branch in enumerate(self.branches):
            self.exp_list.insert(tk.END, branch)
            if branch == self.current_branch: self.exp_list.itemconfig(i, {'bg':'#e8f0fe', 'fg':'#000000'})
        if selected_indices: self.exp_list.selection_set(selected_indices[0])
        self.hist_label.config(text=f"History for '{self.current_branch}'")
        hist_result = self.git_helper.get_history(self.current_branch)
        self.hist_list.delete(0, tk.END)
        if hist_result["success"]:
            self.history = hist_result["data"]
            for item in self.history: self.hist_list.insert(tk.END, f"[{item['date']}] {item['subject']}")
        self.status_bar.config(text=f"Active experiment: {self.current_branch}")
        if self.git_helper.has_changes(): self.status_bar.config(text=f"Active experiment: {self.current_branch} (You have unsaved changes)")
        self._on_experiment_select()
    def _on_experiment_select(self, event=None):
        indices = self.exp_list.curselection()
        if not indices: self.switch_button.config(state=tk.DISABLED); return
        selected_branch = self.branches[indices[0]]
        self.switch_button.config(state=tk.DISABLED if selected_branch == self.current_branch else tk.NORMAL)
    def _switch_experiment(self):
        indices = self.exp_list.curselection()
        if not indices: return
        target_branch = self.branches[indices[0]]
        if self.git_helper.has_changes():
            response = messagebox.askyesnocancel("Unsaved Changes",f"You have unsaved changes in '{self.current_branch}'.\n\nYES - Save them as a snapshot before switching.\nNO - Permanently discard the changes and switch.\nCANCEL - Do not switch.")
            if response is None: return
            if response is True:
                if not self._save_snapshot(): return
            else: self.git_helper.discard_changes()
        result = self.git_helper.switch_branch(target_branch)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
    def _save_snapshot(self):
        message = self.commit_msg.get("1.0", tk.END).strip()
        if not message: self._show_error("Please provide a description for this snapshot."); return False
        result = self.git_helper.commit(message)
        if result["success"]: self.commit_msg.delete("1.0", tk.END); self.update_ui_state(); return True
        else: self._show_error(result['error']); return False
    def _new_experiment(self):
        name = simpledialog.askstring("New Experiment", "Enter name for new experiment:")
        if not name or " " in name:
            if name is not None: self._show_error("Invalid name.")
            return
        result = self.git_helper.create_branch(name, start_point=self.current_branch)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
    def _delete_experiment(self):
        indices = self.exp_list.curselection()
        if not indices: return
        branch_to_delete = self.branches[indices[0]]
        if branch_to_delete == 'main': self._show_error("'main' experiment cannot be deleted."); return
        if branch_to_delete == self.current_branch: self._show_error("Cannot delete the active experiment. Switch to another first."); return
        if not messagebox.askyesno("Confirm Deletion", f"Permanently delete the experiment '{branch_to_delete}'?"): return
        result = self.git_helper.delete_branch(branch_to_delete)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
    def _create_from_history(self):
        hist_indices = self.hist_list.curselection()
        if not hist_indices: self._show_error("Please select a version from the history list."); return
        commit_hash = self.history[hist_indices[0]]['hash']
        name = simpledialog.askstring("New Experiment", "Enter name for the new experiment to be created from this old version:")
        if not name or " " in name:
            if name is not None: self._show_error("Invalid name.")
            return
        result = self.git_helper.create_branch_from_commit(name, commit_hash)
        if result["success"]: self.update_ui_state()
        else: self._show_error(result["error"])
    def _show_error(self, message):
        messagebox.showerror("Error", message)
        self.status_bar.config(text=f"Error: {message[:100].replace(chr(10), ' ')}...")
    
    def _select_project(self):
        path = filedialog.askdirectory(title="Select Your Single Project Folder")
        if path: self._initialize_project(path)