# git_helper.py
import subprocess
import os
import shlex

class GitHelper:
    # ... __init__, _run_command, initialize_repo, discard_changes, and most other methods are unchanged ...
    def __init__(self, project_root):
        if not os.path.isdir(project_root): raise FileNotFoundError(f"Project root does not exist: {project_root}")
        self.project_root = project_root
    def _run_command(self, command):
        try:
            cmd_list = ["git"] + shlex.split(command)
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                cmd_list, cwd=self.project_root, capture_output=True, text=True, check=True,
                encoding='utf-8', startupinfo=startupinfo)
            return {"success": True, "output": result.stdout.strip()}
        except subprocess.CalledProcessError as e:
            cmd_str = " ".join(e.cmd)
            if "nothing to commit" in e.stdout or "nothing to commit" in e.stderr:
                return {"success": False, "error": "No changes to save. Please modify or add files before creating a snapshot."}
            error_message = f"Command failed with exit code {e.returncode}:\n`{cmd_str}`\n\nError Details:\n{e.stderr.strip()}"
            return {"success": False, "error": error_message}
        except FileNotFoundError: return {"success": False, "error": "Git command not found. Is Git installed?"}
    def initialize_repo(self):
        if os.path.exists(os.path.join(self.project_root, ".git")): return {"success": True, "output": "Repository already exists."}
        self._run_command("init -b main")
        name_check = self._run_command("config user.name")
        email_check = self._run_command("config user.email")
        if not name_check.get("output"): self._run_command("config user.name 'VibeCoder'")
        if not email_check.get("output"): self._run_command("config user.email 'vibecoder@example.com'")
        with open(os.path.join(self.project_root, ".gitkeep"), "w") as f: pass
        self._run_command("add .gitkeep")
        return self._run_command("commit -m 'Initial Commit'")
    def discard_changes(self):
        return self._run_command("reset --hard HEAD")
    def get_branches(self):
        result = self._run_command("branch")
        if not result["success"]: return result
        branches, current_branch = [], ""
        for line in result["output"].split('\n'):
            if line.startswith('* '):
                current_branch = line[2:].strip()
                branches.append(current_branch)
            else: branches.append(line.strip())
        return {"success": True, "data": {"all": branches, "current": current_branch}}
    def has_changes(self):
        result = self._run_command("status --porcelain")
        return result["success"] and bool(result["output"])
    def switch_branch(self, branch_name):
        return self._run_command(f"checkout {shlex.quote(branch_name)}")
    def create_branch(self, new_branch_name, start_point='main'):
        return self._run_command(f"checkout -b {shlex.quote(new_branch_name)} {shlex.quote(start_point)}")
    def create_branch_from_commit(self, new_branch_name, commit_hash):
        return self._run_command(f"checkout -b {shlex.quote(new_branch_name)} {shlex.quote(commit_hash)}")
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

    # --- MODIFIED: Replaced revert_commit with the heavy-handed version ---
    def force_reset_to_commit(self, commit_hash):
        """
        HEAVY-HANDED: Resets the current branch to a specific commit.
        This DELETES any newer history on this branch and discards all current changes.
        """
        return self._run_command(f"reset --hard {shlex.quote(commit_hash)}")