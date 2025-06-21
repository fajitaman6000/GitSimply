# git_helper.py
import subprocess
import os
import shlex

# --- NEW: Shared constant for the metadata directory ---
SESSION_META_DIR = ".manager_meta"

class GitHelper:
    def __init__(self, project_root):
        if not os.path.isdir(project_root): raise FileNotFoundError(f"Project root does not exist: {project_root}")
        self.project_root = project_root

    def _run_command(self, command):
        try:
            cmd_list = ["git"] + shlex.split(command)
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                cmd_list, cwd=self.project_root, capture_output=True, text=True, check=True, encoding='utf-8', startupinfo=startupinfo)
            return {"success": True, "output": result.stdout.strip()}
        except subprocess.CalledProcessError as e:
            cmd_str = " ".join(e.cmd)
            error_message = f"Command failed:\n`{cmd_str}`\n\nError Details:\n{e.stderr.strip()}"
            return {"success": False, "error": error_message}
        except FileNotFoundError: return {"success": False, "error": "Git command not found. Is Git installed?"}

    # --- MODIFIED: Fixes initialization and the "unsaved changes" bug ---
    def initialize_repo(self):
        """
        Initializes a Git repository if one doesn't exist, or ensures an
        existing one is configured correctly for this app.
        - Creates a .gitignore to exclude manager-specific files.
        - Creates an initial commit with the project's current state.
        """
        is_new_repo = not os.path.exists(os.path.join(self.project_root, ".git"))

        if is_new_repo:
            self._run_command("init -b main")
            self._run_command("config user.name 'VibeCoder'")
            self._run_command("config user.email 'vibecoder@example.com'")

        # Ensure .gitignore exists and contains our entry for both new and existing repos.
        # This prevents session files from polluting git status, fixing the primary bug.
        gitignore_path = os.path.join(self.project_root, ".gitignore")
        entry_to_add = f"\n# Permutation Manager Files\n{SESSION_META_DIR}/\n"
        
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w") as f:
                f.write(entry_to_add.lstrip())
        else:
            with open(gitignore_path, "r+") as f:
                content = f.read()
                if SESSION_META_DIR not in content:
                    f.write(entry_to_add) # Appends to the end

        if is_new_repo:
            self._run_command("add .")
            # Create an initial commit with the actual project state.
            commit_res = self._run_command("commit -m 'Initial Commit'")
            if not commit_res["success"] and "nothing to commit" in commit_res.get("error", ""):
                # This can happen if the folder is empty. Create an empty commit
                # so that git log and other commands work correctly from the start.
                return self._run_command("commit --allow-empty -m 'Initial Commit'")
            return commit_res
        
        return {"success": True}


    def get_current_state(self):
        branch_res = self._run_command("rev-parse --abbrev-ref HEAD")
        if not branch_res["success"]: return branch_res
        current_ref = branch_res["output"]
        return {"success": True, "data": {"current_ref": current_ref, "is_detached": current_ref == "HEAD"}}

    def commit(self, message):
        self._run_command("add .")
        return self._run_command(f"commit -m {shlex.quote(message)}")

    # --- MODIFIED: Accepts a commit message to align with its usage in app.py ---
    def restore_and_commit_past_state(self, branch_to_restore_on, old_commit_hash, new_commit_message):
        """Checks out a branch, overwrites its files with an old state, and commits it."""
        # 1. Ensure we are on the correct branch.
        checkout_res = self.checkout(branch_to_restore_on)
        if not checkout_res["success"]: return checkout_res

        # 2. Overwrite working directory files with the state from the old commit.
        # The '-- .' is crucial: it applies the changes without moving the HEAD.
        restore_res = self._run_command(f"checkout {shlex.quote(old_commit_hash)} -- .")
        if not restore_res["success"]: return restore_res

        # 3. Commit this as a new state.
        return self.commit(new_commit_message)

    # ... All other methods are unchanged and correct ...
    def get_all_branches(self):
        return self._run_command("branch --format='%(refname:short)'")
    def has_changes(self):
        return bool(self._run_command("status --porcelain")["output"])
    def checkout(self, target):
        return self._run_command(f"checkout {shlex.quote(target)}")
    def create_branch(self, new_branch_name, start_point='main'):
        return self._run_command(f"checkout -b {shlex.quote(new_branch_name)} {shlex.quote(start_point)}")
    def delete_branch(self, branch_name):
        return self._run_command(f"branch -D {shlex.quote(branch_name)}")
    def get_history(self, branch_name):
        sep, date_format = "|||GIT_SEP|||", "--date=format-local:'%Y-%m-%d %I:%M %p'"
        command = f"log {shlex.quote(branch_name)} --pretty=format:'%h{sep}%ad{sep}%s' {date_format} --"
        result = self._run_command(command)
        history = []
        if result["success"] and result["output"]:
            for line in result["output"].split('\n'):
                parts = line.split(sep)
                if len(parts) == 3: history.append({"hash": parts[0], "date": parts[1], "subject": parts[2]})
        return {"success": True, "data": history}
    def discard_changes(self):
        return self._run_command("reset --hard HEAD")