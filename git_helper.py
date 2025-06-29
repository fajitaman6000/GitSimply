# git_helper.py Please give all changes to this script in WHOLE. Do not give snippets. Respond with the script as a whole pasteable unit without comments made to omit parts like "... rest of xyz method remains the same"
import subprocess
import os
import shlex

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

    def initialize_repo(self):
        """
        Initializes a Git repository if one doesn't exist, or ensures an
        existing one is configured correctly for this app.
        - Creates a comprehensive .gitignore to exclude common and app-specific files.
        - Creates an initial commit with the project's current state.
        """
        is_new_repo = not os.path.exists(os.path.join(self.project_root, ".git"))

        if is_new_repo:
            init_res = self._run_command("init -b main")
            if not init_res["success"]: return init_res
            self._run_command("config user.name 'GitSimply'")
            self._run_command("config user.email 'user@gitsimply.local'")

        # --- FIX: Create a comprehensive, user-friendly .gitignore ---
        gitignore_path = os.path.join(self.project_root, ".gitignore")
        
        # Define the block of text we want to ensure is in the gitignore.
        # The header acts as a unique identifier for our block.
        gitignore_block = f"""
# --- GitSimply Managed ---
# These entries are automatically managed by GitSimply to ignore app files,
# caches, and other common files that should not be versioned.

# Application-specific
{SESSION_META_DIR}/
config.json
gitsimply_crash.log

# Python
__pycache__/
*.pyc
.venv/
venv/
env/

# OS-specific
.DS_Store
Thumbs.db
# --- End GitSimply Managed ---
"""
        
        needs_write = True
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding='utf-8') as f:
                content = f.read()
                # Check for our unique header to see if our block is already there.
                if "# --- GitSimply Managed ---" in content:
                    needs_write = False
        
        if needs_write:
            with open(gitignore_path, "a", encoding='utf-8') as f:
                # Add a newline before our block if the file is not empty and doesn't end with one.
                if os.path.getsize(gitignore_path) > 0:
                    f.seek(0, os.SEEK_END)
                    f.seek(f.tell() - 1, os.SEEK_SET)
                    if f.read(1) != '\n':
                        f.write('\n')
                f.write(gitignore_block.strip() + "\n")


        if is_new_repo:
            self._run_command("add .gitignore")
            self._run_command("commit -m 'Initial commit: Add .gitignore for GitSimply'")

            # Now, add all other files that might exist
            self._run_command("add .")
            commit_res = self._run_command("commit -m 'Initial Project State'")
            # It's not an error if there were no other files to commit
            if not commit_res["success"] and "nothing to commit" in commit_res.get("error", ""):
                return {"success": True}
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

    def restore_and_commit_past_state(self, branch_to_restore_on, old_commit_hash, new_commit_message):
        """Checks out a branch, overwrites its files with an old state, and commits it."""
        checkout_res = self.checkout(branch_to_restore_on)
        if not checkout_res["success"]: return checkout_res

        restore_res = self._run_command(f"checkout {shlex.quote(old_commit_hash)} -- .")
        if not restore_res["success"]: return restore_res

        return self.commit(new_commit_message)
    
    def is_branch_merged_into_any_other(self, branch_to_check):
        """Checks if a branch's history is contained in any other branch."""
        all_branches_res = self.get_all_branches()
        if not all_branches_res["success"]:
            return {"success": False, "error": all_branches_res["error"]}
        
        all_branches = all_branches_res["output"].split('\n')
        other_branches = [b for b in all_branches if b != branch_to_check and b]

        if not other_branches:
            # If there are no other branches, it can't be merged into them.
            return {"success": True, "is_merged": False}

        # Check if `branch_to_check` is an ancestor of any other branch.
        for other_branch in other_branches:
            # Get list of branches that are fully merged into `other_branch`.
            merged_list_res = self._run_command(f"branch --merged {shlex.quote(other_branch)}")
            if not merged_list_res["success"]:
                # If we can't check, assume the worst to be safe.
                return {"success": False, "error": f"Failed to check merge status against branch '{other_branch}'."}
            
            # The output contains branch names, prefixed with '*' if it's the current one.
            merged_branches = [b.strip().replace('* ', '') for b in merged_list_res["output"].split('\n')]
            
            if branch_to_check in merged_branches:
                # We found one! Its work is contained elsewhere, so it's safe to delete.
                return {"success": True, "is_merged": True}
        
        # We looped through all other branches and none contained this one's work.
        return {"success": True, "is_merged": False}


    def get_all_branches(self):
        return self._run_command("branch --format='%(refname:short)'")
    def has_changes(self):
        return bool(self._run_command("status --porcelain")["output"])
    def checkout(self, target):
        return self._run_command(f"checkout {shlex.quote(target)}")
    def create_branch(self, new_branch_name, start_point='main'):
        return self._run_command(f"branch {shlex.quote(new_branch_name)} {shlex.quote(start_point)}")
    def delete_branch(self, branch_name):
        return self._run_command(f"branch -D {shlex.quote(branch_name)}")
    def get_current_commit_hash(self):
        """Returns the full hash of the current commit (HEAD)."""
        return self._run_command("rev-parse HEAD")
    def get_history(self, branch_name):
        sep, date_format = "|||GIT_SEP|||", "--date=format-local:'%Y-%m-%d %I:%M %p'"
        command = f"log {shlex.quote(branch_name)} --pretty=format:'%H{sep}%ad{sep}%s' {date_format} --"
        result = self._run_command(command)
        history = []
        if result["success"] and result["output"]:
            for line in result["output"].split('\n'):
                parts = line.split(sep)
                if len(parts) == 3: history.append({"hash": parts[0], "date": parts[1], "subject": parts[2]})
        # Git log provides newest first, which is the order we use.
        return {"success": True, "data": history}

    def discard_changes(self):
        """Resets modified files and removes all untracked files and directories."""
        reset_res = self._run_command("reset --hard HEAD")
        if not reset_res["success"]:
            return reset_res
        # -f is for files, -d is for directories. This is a destructive but necessary operation
        # to fulfill the user's request to "permanently discard" changes.
        return self._run_command("clean -fd")