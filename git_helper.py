# git_helper.py
import subprocess
import os
import shlex

# Define the metadata directory name as a constant
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

    # --- NEW: Ensures the metadata directory is ignored by Git ---
    def _ensure_meta_is_ignored(self):
        gitignore_path = os.path.join(self.project_root, ".gitignore")
        ignore_entry = f"{SESSION_META_DIR}/\n"
        
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r+') as f:
                lines = f.readlines()
                if not any(SESSION_META_DIR in line for line in lines):
                    f.write(f"\n# Permutation Manager metadata\n{ignore_entry}")
        else:
            with open(gitignore_path, 'w') as f:
                f.write(f"# Permutation Manager metadata\n{ignore_entry}")

    def initialize_repo(self):
        if os.path.exists(os.path.join(self.project_root, ".git")):
            self._ensure_meta_is_ignored() # Also run for existing repos
            return {"success": True}
        
        self._run_command("init -b main")
        self._run_command("config user.name 'VibeCoder'")
        self._run_command("config user.email 'vibecoder@example.com'")
        self._ensure_meta_is_ignored() # CRITICAL: Ignore metadata
        
        with open(os.path.join(self.project_root, "README.md"), "w") as f: f.write("# My Project\n")
        self._run_command("add README.md .gitignore")
        return self._run_command("commit -m 'Initial Commit'")

    # ... All other methods are unchanged ...
    def get_current_state(self):
        branch_res = self._run_command("rev-parse --abbrev-ref HEAD")
        if not branch_res["success"]: return branch_res
        current_ref = branch_res["output"]
        return {"success": True, "data": {"current_ref": current_ref, "is_detached": current_ref == "HEAD"}}
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
    def commit(self, message):
        self._run_command("add .")
        return self._run_command(f"commit -m {shlex.quote(message)}")
    def discard_changes(self):
        return self._run_command("reset --hard HEAD")
    def restore_and_commit_past_state(self, branch_to_restore_on, old_commit_hash, new_commit_message):
        self.checkout(branch_to_restore_on)
        self._run_command(f"checkout {shlex.quote(old_commit_hash)} -- .")
        return self.commit(new_commit_message)