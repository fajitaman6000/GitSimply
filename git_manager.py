# git_manager.py
import subprocess
import os
import shlex

class GitManager:
    """Handles all Git command interactions for the application."""
    def __init__(self, project_root):
        if not os.path.isdir(project_root):
            raise FileNotFoundError(f"Project root does not exist: {project_root}")
        self.project_root = project_root
        self.main_worktree_path = os.path.join(self.project_root, "main_codebase")

    def _run_command(self, command, working_dir=None):
        """A helper to run shell commands and return output."""
        if working_dir is None:
            working_dir = self.project_root
        
        try:
            # Using shlex.split for safer command construction
            cmd_list = ["git"] + shlex.split(command)
            result = subprocess.run(
                cmd_list,
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8'
            )
            return {"success": True, "output": result.stdout.strip()}
        except subprocess.CalledProcessError as e:
            error_message = e.stderr.strip() if e.stderr else "An unknown git error occurred."
            return {"success": False, "error": error_message}
        except FileNotFoundError:
            return {"success": False, "error": "Git command not found. Is Git installed and in your system's PATH?"}

    def initialize_repo(self):
        """Initializes a git repo if one doesn't exist."""
        git_dir = os.path.join(self.project_root, ".git")
        if not os.path.exists(git_dir):
            self._run_command("init")
            # Create the main codebase folder and initial commit
            if not os.path.exists(self.main_worktree_path):
                os.makedirs(self.main_worktree_path)
                with open(os.path.join(self.main_worktree_path, ".gitkeep"), "w") as f:
                    pass
                self._run_command(f"add .", working_dir=self.main_worktree_path)
                self._run_command(f"commit -m 'Initial commit: Setup main codebase'", working_dir=self.main_worktree_path)
            return self._run_command(f"worktree add {shlex.quote(self.main_worktree_path)} main")
        return {"success": True, "output": "Repository already exists."}
    
    def get_worktrees(self):
        """Lists all current worktrees."""
        result = self._run_command("worktree list --porcelain")
        if not result["success"]:
            return result
        
        worktrees = []
        if result["output"]:
            for block in result["output"].strip().split('\n\n'):
                lines = block.split('\n')
                path = lines[0].split(' ')[1]
                branch = lines[2].split(' ')[1]
                worktrees.append({"path": path, "branch": os.path.basename(branch)})
        return {"success": True, "data": worktrees}

    def add_worktree_from_branch(self, branch_name):
        """Creates a new worktree from an existing branch."""
        path = os.path.join(self.project_root, branch_name)
        if os.path.exists(path):
            return {"success": False, "error": f"A folder named '{branch_name}' already exists."}
        return self._run_command(f"worktree add {shlex.quote(path)} {shlex.quote(branch_name)}")

    def create_branch_from_commit(self, new_branch_name, commit_hash):
        """Creates a new branch from a specific commit hash."""
        return self._run_command(f"branch {shlex.quote(new_branch_name)} {shlex.quote(commit_hash)}")
    
    def remove_worktree(self, path, branch_name, prune_branch=False):
        """Removes a worktree and optionally the associated branch."""
        # Force remove in case of uncommitted changes, common in this workflow
        result = self._run_command(f"worktree remove -f {shlex.quote(path)}")
        if result["success"] and prune_branch:
             # Use -D to force delete the branch
            self._run_command(f"branch -D {shlex.quote(branch_name)}")
        return result

    def get_history(self, branch_name):
        """Gets the commit history for a specific branch."""
        # Use a unique separator to avoid issues with commit messages containing '|'
        sep = "|||GIT_SEP|||"
        result = self._run_command(f"log {shlex.quote(branch_name)} --pretty=format:'%h{sep}%ad{sep}%s' --date=short")
        if not result["success"]:
            return result
            
        history = []
        if result["output"]:
            for line in result["output"].split('\n'):
                parts = line.split(sep)
                if len(parts) == 3:
                    history.append({"hash": parts[0], "date": parts[1], "subject": parts[2]})
        return {"success": True, "data": history}

    def commit(self, worktree_path, message):
        """Stages all changes and commits them in a specific worktree."""
        add_result = self._run_command("add .", working_dir=worktree_path)
        if not add_result["success"]:
            return add_result
        return self._run_command(f"commit -m {shlex.quote(message)}", working_dir=worktree_path)