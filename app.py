# app.py
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import os
import json
from git_manager import GitManager

CONFIG_FILE = "config.json"

class GitVibeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GitVibe - Code Permutation Manager")
        self.geometry("900x600")

        self.project_root = None
        self.git_manager = None
        self.worktrees = []
        self.history = []

        self._load_config()
        self._create_widgets()

        if self.project_root and os.path.exists(self.project_root):
            self._initialize_project(self.project_root)
        else:
            self.status_bar.config(text="Please select a project folder to begin.")

    def _load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                self.project_root = config.get("project_root")
        except (FileNotFoundError, json.JSONDecodeError):
            self.project_root = None

    def _save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"project_root": self.project_root}, f)
            
    def _create_widgets(self):
        # Main layout
        self.main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left Pane (Experiments & Actions) ---
        left_frame = ttk.Frame(self.main_pane, padding=10)
        self.main_pane.add(left_frame, weight=1)

        # Project Selection
        proj_frame = ttk.LabelFrame(left_frame, text="Project", padding=10)
        proj_frame.pack(fill=tk.X, pady=(0, 10))
        self.proj_label = ttk.Label(proj_frame, text="No project selected.", wraplength=250)
        self.proj_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(proj_frame, text="Change Folder", command=self._select_project).pack(side=tk.RIGHT)

        # Experiments List
        exp_frame = ttk.LabelFrame(left_frame, text="Experiments", padding=10)
        exp_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.exp_list = tk.Listbox(exp_frame, exportselection=False)
        self.exp_list.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.exp_list.bind("<<ListboxSelect>>", self._on_experiment_select)
        
        exp_button_frame = ttk.Frame(exp_frame)
        exp_button_frame.pack(side=tk.RIGHT, padx=(5,0), fill=tk.Y)
        ttk.Button(exp_button_frame, text="New", command=self._new_experiment).pack(fill=tk.X)
        ttk.Button(exp_button_frame, text="Delete", command=self._delete_experiment).pack(fill=tk.X, pady=5)
        
        # Snapshot (Commit) Area
        snap_frame = ttk.LabelFrame(left_frame, text="Save Snapshot", padding=10)
        snap_frame.pack(fill=tk.X)
        self.commit_msg = tk.Text(snap_frame, height=4)
        self.commit_msg.pack(fill=tk.X, expand=True, pady=(0, 5))
        ttk.Button(snap_frame, text="Save Current Version", command=self._save_snapshot).pack(fill=tk.X)

        # --- Right Pane (History) ---
        right_frame = ttk.Frame(self.main_pane, padding=10)
        self.main_pane.add(right_frame, weight=2)
        
        hist_frame = ttk.LabelFrame(right_frame, text="History", padding=10)
        hist_frame.pack(fill=tk.BOTH, expand=True)
        
        self.hist_label = ttk.Label(hist_frame, text="Select an experiment to see its history")
        self.hist_label.pack(fill=tk.X, pady=(0, 5))
        
        self.hist_list = tk.Listbox(hist_frame)
        self.hist_list.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(hist_frame, text="Create New Experiment from this Version", command=self._create_from_history).pack(fill=tk.X, pady=(5,0))

        # --- Status Bar ---
        self.status_bar = ttk.Label(self, text="Welcome!", relief=tk.SUNKEN, anchor=tk.W, padding=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _select_project(self):
        path = filedialog.askdirectory(title="Select Main Project Folder")
        if path:
            self._initialize_project(path)
    
    def _initialize_project(self, path):
        try:
            self.project_root = path
            self.git_manager = GitManager(self.project_root)
            self.proj_label.config(text=f"Current: {self.project_root}")
            
            # This will create the .git dir and a 'main_codebase' if they don't exist
            result = self.git_manager.initialize_repo()
            if not result["success"]:
                self._show_error(result["error"])
                return

            self._save_config()
            self._refresh_experiment_list()
            self.status_bar.config(text=f"Project loaded: {self.project_root}")
        except Exception as e:
            self._show_error(str(e))

    def _refresh_experiment_list(self):
        self.exp_list.delete(0, tk.END)
        self.hist_list.delete(0, tk.END)
        self.hist_label.config(text="Select an experiment to see its history")
        
        result = self.git_manager.get_worktrees()
        if result["success"]:
            self.worktrees = result["data"]
            for wt in self.worktrees:
                self.exp_list.insert(tk.END, wt["branch"])
        else:
            self._show_error(result["error"])

    def _on_experiment_select(self, event=None):
        selected_indices = self.exp_list.curselection()
        if not selected_indices:
            return
        
        idx = selected_indices[0]
        branch_name = self.worktrees[idx]["branch"]
        self.hist_label.config(text=f"History for '{branch_name}'")
        self._refresh_history_list(branch_name)

    def _refresh_history_list(self, branch_name):
        self.hist_list.delete(0, tk.END)
        result = self.git_manager.get_history(branch_name)
        if result["success"]:
            self.history = result["data"]
            for item in self.history:
                display_text = f"[{item['date']}] {item['subject']}"
                self.hist_list.insert(tk.END, display_text)
        else:
            self._show_error(result["error"])

    def _new_experiment(self):
        name = simpledialog.askstring("New Experiment", "Enter a name for the new experiment (no spaces):")
        if not name or " " in name:
            if name is not None:
                self._show_error("Invalid name. Please use a single word.")
            return

        result = self.git_manager.add_worktree_from_branch(name)
        if result["success"]:
            self.status_bar.config(text=f"Created new experiment '{name}'.")
            self._refresh_experiment_list()
        else:
            # A common "error" is that the branch exists but the worktree doesn't.
            # This is a good time to create the worktree from the existing branch.
            if "is already checked out" in result["error"]:
                 res = self.git_manager.add_worktree_from_branch(name)
                 if res["success"]:
                    self.status_bar.config(text=f"Created worktree for existing experiment '{name}'.")
                    self._refresh_experiment_list()
                 else:
                    self._show_error(res["error"])
            else:
                self._show_error(result["error"])

    def _delete_experiment(self):
        selected_indices = self.exp_list.curselection()
        if not selected_indices:
            self._show_error("Please select an experiment to delete.")
            return

        idx = selected_indices[0]
        wt = self.worktrees[idx]

        if wt['branch'] == 'main':
            self._show_error("The 'main' branch and its folder ('main_codebase') cannot be deleted from this app.")
            return

        if not messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete the '{wt['branch']}' experiment folder? This cannot be undone."):
            return

        prune = messagebox.askyesno("Delete History?", f"Also permanently delete the history for '{wt['branch']}'? \n\n(Choose 'No' if you might want to bring this experiment back later).")
        
        result = self.git_manager.remove_worktree(wt['path'], wt['branch'], prune_branch=prune)
        if result["success"]:
            self.status_bar.config(text=f"Deleted experiment '{wt['branch']}'.")
            self._refresh_experiment_list()
        else:
            self._show_error(result["error"])

    def _save_snapshot(self):
        selected_indices = self.exp_list.curselection()
        if not selected_indices:
            self._show_error("Please select which experiment you are saving.")
            return
        
        message = self.commit_msg.get("1.0", tk.END).strip()
        if not message:
            self._show_error("Please provide a description for this snapshot.")
            return
            
        idx = selected_indices[0]
        wt = self.worktrees[idx]
        
        result = self.git_manager.commit(wt['path'], message)
        if result["success"]:
            self.status_bar.config(text=f"Snapshot saved in '{wt['branch']}'.")
            self.commit_msg.delete("1.0", tk.END)
            self._refresh_history_list(wt['branch']) # Refresh history to show the new commit
        else:
            self._show_error(result['error'])

    def _create_from_history(self):
        selected_indices = self.hist_list.curselection()
        if not selected_indices:
            self._show_error("Please select a version from the history list.")
            return
        
        idx = selected_indices[0]
        commit_hash = self.history[idx]['hash']

        name = simpledialog.askstring("New Experiment", "Enter a name for the new experiment based on this old version:")
        if not name or " " in name:
            if name is not None: self._show_error("Invalid name. Please use a single word.")
            return

        # 1. Create the new branch from the old commit
        res1 = self.git_manager.create_branch_from_commit(name, commit_hash)
        if not res1["success"] and "already exists" not in res1["error"]:
            self._show_error(res1["error"])
            return
        
        # 2. Create the worktree for the new branch
        res2 = self.git_manager.add_worktree_from_branch(name)
        if res2["success"]:
            self.status_bar.config(text=f"Created experiment '{name}' from an old version.")
            self._refresh_experiment_list()
        else:
            self._show_error(res2["error"])

    def _show_error(self, message):
        messagebox.showerror("Error", message)
        self.status_bar.config(text=f"Error: {message[:100]}...")