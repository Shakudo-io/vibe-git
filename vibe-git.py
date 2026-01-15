#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.10"
# dependencies = ["textual>=0.50.0"]
# ///
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.actions import SkipAction
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable, Footer, Header, Input, Label, Static, TabbedContent, TabPane,
    Button, Select, Switch, Rule
)
from textual.coordinate import Coordinate
from textual.worker import Worker, WorkerState


# =============================================================================
# Configuration System
# =============================================================================

AI_CLI_OPTIONS = [
    ("opencode", "OpenCode"),
    ("opencode-shared", "OpenCode (Shared Server)"),
    ("claude", "Claude Code"),
    ("gemini", "Gemini CLI"),
    ("codex", "Codex CLI"),
]

CONFIG_DIR = Path.home() / ".config" / "vibe-git"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    """Application configuration with persistence."""
    default_ai_cli: str = "opencode"
    shared_opencode_enabled: bool = False
    
    @classmethod
    def load(cls) -> "AppConfig":
        """Load config from disk or return defaults."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                return cls(
                    default_ai_cli=data.get("default_ai_cli", "opencode"),
                    shared_opencode_enabled=data.get("shared_opencode_enabled", False),
                )
            except (json.JSONDecodeError, IOError):
                pass
        return cls()
    
    def save(self) -> None:
        """Save config to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "default_ai_cli": self.default_ai_cli,
                "shared_opencode_enabled": self.shared_opencode_enabled,
            }, f, indent=2)


# =============================================================================
# AI CLI Launcher Functions
# =============================================================================

def is_inside_zellij() -> bool:
    """Check if running inside a zellij session."""
    return "ZELLIJ" in os.environ


def get_ai_cli_command(cli_name: str) -> list[str]:
    """Get the command to run for a given AI CLI."""
    commands = {
        "opencode": ["opencode"],
        "opencode-shared": ["opencode-shared"],
        "claude": ["claude"],
        "gemini": ["gemini"],
        "codex": ["codex"],
    }
    return commands.get(cli_name, ["opencode"])


def launch_ai_cli_zellij(cli_name: str, working_dir: Path, tab_name: str) -> tuple[bool, str]:
    cmd = get_ai_cli_command(cli_name)
    
    args_line = ""
    if len(cmd) > 1:
        quoted_args = " ".join(f'"{a}"' for a in cmd[1:])
        args_line = f"args {quoted_args}"
    
    layout_content = f'''layout {{
    tab name="{tab_name}" {{
        pane command="{cmd[0]}" cwd="{working_dir}" {{
            {args_line}
        }}
    }}
}}
'''
    
    try:
        # Write temporary layout file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.kdl', delete=False) as f:
            f.write(layout_content)
            layout_path = f.name
        
        # Create new tab with the layout
        result = subprocess.run(
            ["zellij", "action", "new-tab", "--layout", layout_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Clean up temp file
        os.unlink(layout_path)
        
        if result.returncode == 0:
            return True, f"Launched {cli_name} in new zellij tab"
        else:
            return False, result.stderr.strip() or "Failed to create zellij tab"
    except subprocess.TimeoutExpired:
        return False, "Zellij command timed out"
    except Exception as e:
        return False, str(e)


def start_shared_opencode(scan_dir: Path) -> tuple[bool, str, subprocess.Popen | None]:
    """Start opencode-shared server in the scan directory."""
    try:
        # Check if opencode-shared is available
        which_result = subprocess.run(["which", "opencode-shared"], capture_output=True)
        if which_result.returncode != 0:
            return False, "opencode-shared not found in PATH", None
        
        # Start the shared server in background
        proc = subprocess.Popen(
            ["opencode-shared"],
            cwd=scan_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent process
        )
        return True, f"Started opencode-shared (PID: {proc.pid})", proc
    except Exception as e:
        return False, str(e), None


def stop_shared_opencode(proc: subprocess.Popen | None) -> tuple[bool, str]:
    """Stop the shared opencode server."""
    if proc is None:
        return False, "No shared opencode process to stop"
    
    try:
        proc.terminate()
        proc.wait(timeout=5)
        return True, "Stopped opencode-shared"
    except subprocess.TimeoutExpired:
        proc.kill()
        return True, "Force killed opencode-shared"
    except Exception as e:
        return False, str(e)

# Manga adventurer running animation frames
ADVENTURER_FRAMES = [
    r"""
              ╭─────────────────────────────────────╮
              │      ⚔️  Fetching git repos...      │
              ╰─────────────────────────────────────╯
    
                        ╱▔▔▔▔╲
                       ▕ ◕◡◕ ▏    ∠)
                    ╭───▔▔▔▔▔───╮//
                    │  ╱│       │
                    │ ╱ │  ⚡   │
                    ╰───────────╯
                      ╱ │ ╲
                     ╱  │  ╲
                    ◢   ▼   ◣
    """,
    r"""
              ╭─────────────────────────────────────╮
              │      ⚔️  Fetching git repos...      │
              ╰─────────────────────────────────────╯
    
                         ╱▔▔▔▔╲
                        ▕ ◕ω◕ ▏   ─═∠)
                     ╭───▔▔▔▔▔───╮ ╱
                     │    ╲│     │╱
                     │  ⚡  │     │
                     ╰───────────╯
                       ╱│    ╲
                      ╱ │     ╲
                     ◢      ▼   ◣
    """,
    r"""
              ╭─────────────────────────────────────╮
              │      ⚔️  Fetching git repos...      │
              ╰─────────────────────────────────────╯
    
                          ╱▔▔▔▔╲    ✨
                         ▕ ●▽● ▏  ∠)
                      ╭───▔▔▔▔▔───╮
                      │   /│\     │
                      │  ⚡ │     │
                      ╰───────────╯
                         /│\
                        / │ \
                       ◢  ▼  ◣
    """,
    r"""
              ╭─────────────────────────────────────╮
              │      ⚔️  Fetching git repos...      │
              ╰─────────────────────────────────────╯
    
                       ╱▔▔▔▔╲
               (∠─   ▕ ◕◡◕ ▏
                 ╲╭───▔▔▔▔▔───╮
                  │     │╲    │
                  │   ⚡ │ ╲   │
                  ╰───────────╯
                     ╱  │  ╲
                    ╱   │   ╲
                   ◢    ▼    ◣
    """,
]

# Alternative: Simple ninja/samurai
NINJA_FRAMES = [
    r"""
       ▄▄▄
      (◉_◉)    ╱
    ━━╋━━╋━━ ⚔╱
       ┃     ╱
      ╱ ╲   •  scanning...
     ╱   ╲
    👟    👟
    """,
    r"""
       ▄▄▄
      (◉_◉)
    ━━╋━━╋━━⚔
       ┃    ╲  scanning...
      ╱ ╲    •
     ╱   ╲
    👟    👟
    """,
    r"""
       ▄▄▄      
      (◉_◉)  ⚡
    ━━╋━━╋━━
       ┃  ⚔    scanning...
      ╱ ╲  ╲
     ╱   ╲  •
    👟    👟
    """,
    r"""
       ▄▄▄
      (◉_◉)
    ━╋━━━╋━⚔
       ┃   |  scanning...
      ╱ ╲  •
     ╱   ╲
    👟    👟
    """,
]

# Cute running character
RUNNER_FRAMES = [
    r"""
        ╭─────────────────────────────────╮
        │   🔍 Scanning git repos...      │
        ╰─────────────────────────────────╯
        
              ⚡        
           \O/    ══════════════▶
            |     
           / \    
    ──────────────────────────────────────
    """,
    r"""
        ╭─────────────────────────────────╮
        │   🔍 Scanning git repos...      │
        ╰─────────────────────────────────╯
        
                   ⚡   
            \O      ══════════════▶
             |\    
            / \   
    ──────────────────────────────────────
    """,
    r"""
        ╭─────────────────────────────────╮
        │   🔍 Scanning git repos...      │
        ╰─────────────────────────────────╯
        
                        ⚡
             O/   ══════════════▶
            /|    
            /|    
    ──────────────────────────────────────
    """,
    r"""
        ╭─────────────────────────────────╮
        │   🔍 Scanning git repos...      │
        ╰─────────────────────────────────╯
        
                             ⚡
              O    ══════════════▶
             /|\   
             / \   
    ──────────────────────────────────────
    """,
]

# Git-themed animation
GIT_FRAMES = [
    r"""
    
          ╭──────────────────────────────────╮
          │                                  │
          │     ┏━━━━━━━━━━━━━━━━━━━━━━━┓    │
          │     ┃  ◉──◉──◉   fetching  ┃    │
          │     ┃     ╲      remotes   ┃    │
          │     ┃      ◉──◉            ┃    │
          │     ┗━━━━━━━━━━━━━━━━━━━━━━━┛    │
          │           ⣾  scanning...        │
          ╰──────────────────────────────────╯
    
    """,
    r"""
    
          ╭──────────────────────────────────╮
          │                                  │
          │     ┏━━━━━━━━━━━━━━━━━━━━━━━┓    │
          │     ┃  ◉──◉──◉   fetching  ┃    │
          │     ┃     ╲      remotes   ┃    │
          │     ┃      ◉──◉            ┃    │
          │     ┗━━━━━━━━━━━━━━━━━━━━━━━┛    │
          │           ⣽  scanning...        │
          ╰──────────────────────────────────╯
    
    """,
    r"""
    
          ╭──────────────────────────────────╮
          │                                  │
          │     ┏━━━━━━━━━━━━━━━━━━━━━━━┓    │
          │     ┃  ◉──◉──◉   fetching  ┃    │
          │     ┃     ╲      remotes   ┃    │
          │     ┃      ◉──◉            ┃    │
          │     ┗━━━━━━━━━━━━━━━━━━━━━━━┛    │
          │           ⣻  scanning...        │
          ╰──────────────────────────────────╯
    
    """,
    r"""
    
          ╭──────────────────────────────────╮
          │                                  │
          │     ┏━━━━━━━━━━━━━━━━━━━━━━━┓    │
          │     ┃  ◉──◉──◉   fetching  ┃    │
          │     ┃     ╲      remotes   ┃    │
          │     ┃      ◉──◉            ┃    │
          │     ┗━━━━━━━━━━━━━━━━━━━━━━━┛    │
          │           ⢿  scanning...        │
          ╰──────────────────────────────────╯
    
    """,
    r"""
    
          ╭──────────────────────────────────╮
          │                                  │
          │     ┏━━━━━━━━━━━━━━━━━━━━━━━┓    │
          │     ┃  ◉──◉──◉   fetching  ┃    │
          │     ┃     ╲      remotes   ┃    │
          │     ┃      ◉──◉            ┃    │
          │     ┗━━━━━━━━━━━━━━━━━━━━━━━┛    │
          │           ⡿  scanning...        │
          ╰──────────────────────────────────╯
    
    """,
    r"""
    
          ╭──────────────────────────────────╮
          │                                  │
          │     ┏━━━━━━━━━━━━━━━━━━━━━━━┓    │
          │     ┃  ◉──◉──◉   fetching  ┃    │
          │     ┃     ╲      remotes   ┃    │
          │     ┃      ◉──◉            ┃    │
          │     ┗━━━━━━━━━━━━━━━━━━━━━━━┛    │
          │           ⣟  scanning...        │
          ╰──────────────────────────────────╯
    
    """,
    r"""
    
          ╭──────────────────────────────────╮
          │                                  │
          │     ┏━━━━━━━━━━━━━━━━━━━━━━━┓    │
          │     ┃  ◉──◉──◉   fetching  ┃    │
          │     ┃     ╲      remotes   ┃    │
          │     ┃      ◉──◉            ┃    │
          │     ┗━━━━━━━━━━━━━━━━━━━━━━━┛    │
          │           ⣯  scanning...        │
          ╰──────────────────────────────────╯
    
    """,
    r"""
    
          ╭──────────────────────────────────╮
          │                                  │
          │     ┏━━━━━━━━━━━━━━━━━━━━━━━┓    │
          │     ┃  ◉──◉──◉   fetching  ┃    │
          │     ┃     ╲      remotes   ┃    │
          │     ┃      ◉──◉            ┃    │
          │     ┗━━━━━━━━━━━━━━━━━━━━━━━┛    │
          │           ⣷  scanning...        │
          ╰──────────────────────────────────╯
    
    """,
]

LOADING_FRAMES = GIT_FRAMES  # Change this to use different animation


def colorize_sync(status: str) -> Text:
    """Color code sync status."""
    if status == "Synced":
        return Text(status, style="green")
    elif status == "-":
        return Text(status, style="dim")
    elif "Diverged" in status:
        return Text(status, style="bold red")
    elif "Behind" in status:
        return Text(status, style="red")
    elif "Ahead" in status:
        return Text(status, style="yellow")
    return Text(status)


def colorize_rebase(status: str) -> Text:
    """Color code rebase status."""
    if status == "Rebased":
        return Text(status, style="green")
    elif status == "-":
        return Text(status, style="dim")
    elif "Behind" in status:
        return Text(status, style="red")
    elif "No " in status:
        return Text(status, style="dim yellow")
    return Text(status)


@dataclass
class RepoStatus:
    name: str
    path: Path
    type_label: str
    branch: str
    remote_exists: bool
    sync_status: str
    rebase_status: str
    pr_status: str
    main_branch: str
    has_changes: bool

    def can_pull(self) -> bool:
        return self.why_not_pull() is None

    def why_not_pull(self) -> str | None:
        if not self.remote_exists:
            return "no remote branch"
        if "Behind" not in self.sync_status:
            return "already synced"
        if "Diverged" in self.sync_status:
            return "diverged (use force push)"
        if self.has_changes:
            return "has uncommitted changes"
        return None

    def can_rebase(self) -> bool:
        return self.why_not_rebase() is None

    def why_not_rebase(self) -> str | None:
        is_on_main = self.branch in (self.main_branch, "main", "dev", "master")
        if is_on_main:
            return "on main branch"
        if self.has_changes:
            return "has uncommitted changes"
        is_behind_remote = "Behind" in self.sync_status and "Diverged" not in self.sync_status
        is_behind_main = self.sync_status in ("Synced", "-") and "Behind" in self.rebase_status
        if not (is_behind_remote or is_behind_main):
            return "already rebased"
        return None

    def can_force_push(self) -> bool:
        return self.why_not_force_push() is None

    def why_not_force_push(self) -> str | None:
        if not self.remote_exists:
            return "no remote branch"
        is_protected = self.branch in ("main", "master", "dev")
        if is_protected:
            return "protected branch"
        if "Ahead" not in self.sync_status and "Diverged" not in self.sync_status:
            return "nothing to push"
        return None

    def can_create_remote(self) -> bool:
        return self.why_not_create_remote() is None

    def why_not_create_remote(self) -> str | None:
        if self.remote_exists:
            return "remote already exists"
        if self.branch in ("HEAD", "DETACHED"):
            return "detached HEAD"
        return None

    def can_stash(self) -> bool:
        return self.why_not_stash() is None

    def why_not_stash(self) -> str | None:
        if not self.has_changes:
            return "no changes to stash"
        return None

    def can_discard(self) -> bool:
        return self.why_not_discard() is None

    def why_not_discard(self) -> str | None:
        if not self.has_changes:
            return "no changes to discard"
        return None

    def can_reset_to_remote(self) -> bool:
        return self.why_not_reset_to_remote() is None

    def why_not_reset_to_remote(self) -> str | None:
        if not self.remote_exists:
            return "no remote branch to reset to"
        return None

    def can_delete_local(self) -> bool:
        return self.why_not_delete_local() is None

    def why_not_delete_local(self) -> str | None:
        if not self.remote_exists:
            return "no remote branch (data would be lost)"
        if self.has_changes:
            return "has uncommitted changes"
        if self.sync_status != "Synced":
            return f"not synced with remote ({self.sync_status})"
        return None

    def can_create_worktree(self) -> bool:
        return self.why_not_create_worktree() is None

    def why_not_create_worktree(self) -> str | None:
        if self.type_label == "Worktree":
            return "already a worktree"
        if self.branch in ("HEAD", "DETACHED"):
            return "detached HEAD"
        return None


@dataclass
class PRStatus:
    """Represents an open PR from GitHub."""
    number: int
    title: str
    branch: str
    repo_name: str  # e.g., "monorepo"
    repo_full_name: str  # e.g., "devsentient/monorepo"
    url: str
    local_status: str  # "Not cloned", "Available", "Checked out"
    local_path: Path | None  # Path if checked out locally


def run_git(args: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            # On failure, prefer stderr (where git errors go), fall back to stdout
            error = result.stderr.strip() or result.stdout.strip()
            # Extract the most useful part (look for 'fatal:', 'error:', etc.)
            for line in error.split('\n'):
                if line.startswith(('fatal:', 'error:', 'warning:')):
                    return False, line
            # If no specific error line, return last non-empty line
            lines = [l for l in error.split('\n') if l.strip()]
            return False, lines[-1] if lines else "Unknown error"
    except subprocess.TimeoutExpired:
        return False, "Command timed out after 30s"
    except Exception as e:
        return False, str(e)


def get_main_branch(repo_path: Path, is_worktree: bool) -> str:
    """Determine the main branch for a repo. For monorepo and its worktrees, use 'dev'."""
    # Check if this repo itself is monorepo
    if "monorepo" in repo_path.name:
        return "dev"
    
    # For worktrees, check if parent repo is monorepo
    if is_worktree:
        git_file = repo_path / ".git"
        if git_file.is_file():
            try:
                content = git_file.read_text().strip()
                if content.startswith("gitdir:"):
                    # Extract path: gitdir: /path/to/parent/.git/worktrees/<name>
                    worktree_git_dir = Path(content.split(":", 1)[1].strip())
                    # Go up from .git/worktrees/<name> to find parent repo
                    # worktree_git_dir is like: /root/gitrepos/monorepo/.git/worktrees/evolve-idle-game
                    parent_repo = worktree_git_dir.parent.parent.parent
                    if "monorepo" in parent_repo.name:
                        return "dev"
            except Exception:
                pass
    
    return "main"


def has_uncommitted_changes(repo_path: Path) -> bool:
    ok, output = run_git(["status", "--porcelain"], repo_path)
    if not ok:
        return True
    for line in output.splitlines():
        if line and not line.startswith("??") and not line.startswith("!!"):
            return True
    return False


def get_pr_status(branch: str, cwd: Path) -> str:
    if branch in ("main", "dev", "master", "DETACHED", "HEAD"):
        return "-"
    if subprocess.run(["which", "gh"], capture_output=True).returncode != 0:
        return "?"
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--state", "all", "--json", "state,number", "--limit", "1"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        import json
        prs = json.loads(result.stdout) if result.stdout else []
        if not prs:
            return "No PR"
        pr = prs[0]
        state_map = {"OPEN": "Open", "MERGED": "Merged", "CLOSED": "Closed"}
        return f"{state_map.get(pr.get('state', ''), 'PR')} #{pr.get('number', '')}"
    except:
        return "?"


def fetch_open_prs() -> list[dict]:
    """Fetch open PRs authored by current user across all repos using gh CLI."""
    import json
    
    if subprocess.run(["which", "gh"], capture_output=True).returncode != 0:
        return []
    
    try:
        # Use gh search prs for cross-repo search
        result = subprocess.run(
            ["gh", "search", "prs", "--author", "@me", "--state", "open",
             "--json", "number,title,repository,url", "--limit", "100"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        return json.loads(result.stdout) if result.stdout else []
    except Exception:
        return []


def get_pr_branch(repo_full_name: str, pr_number: int) -> str | None:
    """Get the branch name for a specific PR."""
    import json
    
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--repo", repo_full_name,
             "--json", "headRefName"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout) if result.stdout else {}
        return data.get("headRefName")
    except Exception:
        return None


def sanitize_branch_for_path(branch: str) -> str:
    """Convert branch name to safe folder name (replace / with -)."""
    return branch.replace("/", "-")


def get_next_feature_number(repo_path: Path, scan_dir: Path) -> int:
    """Get next available speckit feature number by scanning branches and specs."""
    highest = 0
    
    # Check git branches
    ok, branches = run_git(["branch", "-a"], repo_path)
    if ok:
        for line in branches.splitlines():
            clean = line.strip().lstrip("* ").replace("remotes/origin/", "")
            import re
            match = re.match(r"^(\d{3})-", clean)
            if match:
                num = int(match.group(1))
                highest = max(highest, num)
    
    # Check specs directories in scan_dir
    for item in scan_dir.iterdir():
        if not item.is_dir():
            continue
        specs_dir = item / "specs"
        if specs_dir.exists():
            for spec_item in specs_dir.iterdir():
                if spec_item.is_dir():
                    import re
                    match = re.match(r"^(\d{3})-", spec_item.name)
                    if match:
                        num = int(match.group(1))
                        highest = max(highest, num)
    
    return highest + 1


def generate_speckit_branch_name(description: str) -> str:
    """Generate semantic branch suffix from description (2-4 meaningful words)."""
    stop_words = {
        "i", "a", "an", "the", "to", "for", "of", "in", "on", "at", "by", "with",
        "from", "is", "are", "was", "were", "be", "been", "being", "have", "has",
        "had", "do", "does", "did", "will", "would", "should", "could", "can",
        "may", "might", "must", "shall", "this", "that", "these", "those", "my",
        "your", "our", "their", "want", "need", "add", "get", "set", "build",
        "create", "implement", "develop", "make", "new"
    }
    
    import re
    words = re.findall(r"[a-zA-Z]+", description.lower())
    meaningful = [w for w in words if w not in stop_words and len(w) >= 3]
    
    if not meaningful:
        meaningful = [w for w in words if len(w) >= 2][:3]
    
    result = "-".join(meaningful[:4]) if meaningful else "feature"
    return result


def create_speckit_worktree(repo: "RepoStatus", description: str, scan_dir: Path) -> tuple[bool, str]:
    """Create a speckit-compliant worktree with spec structure."""
    import shutil
    
    if not description or not description.strip():
        return False, "Feature description cannot be empty"
    
    description = description.strip()
    
    # Get next feature number
    feature_num = get_next_feature_number(repo.path, scan_dir)
    feature_num_str = f"{feature_num:03d}"
    
    # Generate branch name
    branch_suffix = generate_speckit_branch_name(description)
    branch_name = f"{feature_num_str}-{branch_suffix}"
    
    # Check if branch already exists
    ok, existing = run_git(["branch", "--list", branch_name], repo.path)
    if ok and existing:
        return False, f"Branch '{branch_name}' already exists"
    
    ok, remote_existing = run_git(["ls-remote", "--heads", "origin", branch_name], repo.path)
    if ok and branch_name in remote_existing:
        return False, f"Remote branch 'origin/{branch_name}' already exists"
    
    # Worktree path
    worktree_folder = f"{repo.name}-{branch_name}"
    worktree_path = scan_dir / worktree_folder
    
    if worktree_path.exists():
        return False, f"Path already exists: {worktree_path}"
    
    # Create worktree with new branch
    ok, output = run_git(["worktree", "add", "-b", branch_name, str(worktree_path)], repo.path)
    if not ok:
        return False, f"Worktree creation failed: {output}"
    
    # Create speckit structure
    specs_dir = worktree_path / "specs" / branch_name
    specs_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy spec template or create default
    template_path = repo.path / ".specify" / "templates" / "spec-template.md"
    spec_file = specs_dir / "spec.md"
    
    if template_path.exists():
        shutil.copy(template_path, spec_file)
    else:
        spec_file.write_text(f"""# Feature: {description}

## Overview

[NEEDS CLARIFICATION: Detailed requirements]

## User Stories

### US1: [Primary User Story]

**As a** [user type]
**I want** [capability]
**So that** [benefit]

#### Acceptance Criteria
- [ ] [Criterion 1]
- [ ] [Criterion 2]

## Success Criteria

- **SC-001**: [Measurable metric]

## Out of Scope

- [Explicitly excluded items]
""")
    
    # Copy .specify directory if it exists in source repo
    source_specify = repo.path / ".specify"
    target_specify = worktree_path / ".specify"
    if source_specify.exists() and not target_specify.exists():
        shutil.copytree(source_specify, target_specify)
    
    return True, f"Created speckit worktree:\n  Branch: {branch_name}\n  Path: {worktree_path}\n  Spec: {spec_file}"


def detect_pr_local_status(pr_branch: str, repo_name: str, scan_dir: Path) -> tuple[str, Path | None]:
    """
    Detect if a PR branch exists locally.
    Returns (status, path) where status is one of:
    - "Checked out": Branch is currently checked out in some directory
    - "Available": Repo exists locally (can create worktree for this branch)
    - "Not cloned": Repo doesn't exist locally
    
    For "Checked out": path is the directory where the branch is checked out
    For "Available": path is the main repo (preferred) or a worktree
    """
    main_repo_path: Path | None = None
    worktree_path: Path | None = None
    
    for item in scan_dir.iterdir():
        if not item.is_dir():
            continue
        git_path = item / ".git"
        if not git_path.exists():
            continue
        
        # Check the origin URL to see if this belongs to our repo
        ok, remote_url = run_git(["remote", "get-url", "origin"], item)
        if not ok or repo_name not in remote_url:
            continue
        
        # This directory is related to our repo - check what branch is checked out
        ok, current_branch = run_git(["branch", "--show-current"], item)
        current_branch = current_branch.strip() if ok else ""
        
        # If this directory has the PR branch checked out, we found it!
        if current_branch == pr_branch:
            return "Checked out", item
        
        # Track the main repo (exact name match) vs worktrees
        if item.name == repo_name:
            main_repo_path = item
        elif worktree_path is None:
            worktree_path = item
    
    # Prefer main repo over worktree for "Available" status
    if main_repo_path:
        return "Available", main_repo_path
    if worktree_path:
        return "Available", worktree_path
    
    return "Not cloned", None


def clone_repo_with_worktree(repo_full_name: str, pr_branch: str, scan_dir: Path) -> tuple[bool, str, Path | None]:
    """
    Clone a repo and create a worktree for the PR branch.
    Returns (success, message, worktree_path).
    """
    import shutil
    
    repo_name = repo_full_name.split("/")[-1]
    
    # First, check if repo already exists
    main_repo_path = scan_dir / repo_name
    
    if not main_repo_path.exists():
        # Clone the repo first
        clone_url = f"git@github.com:{repo_full_name}.git"
        ok, output = run_git(["clone", clone_url, str(main_repo_path)], scan_dir)
        if not ok:
            # Try HTTPS as fallback
            clone_url = f"https://github.com/{repo_full_name}.git"
            ok, output = run_git(["clone", clone_url, str(main_repo_path)], scan_dir)
            if not ok:
                return False, f"Clone failed: {output}", None
    
    # Fetch all branches
    run_git(["fetch", "--all"], main_repo_path)
    
    # Check if branch exists on remote
    ok, remote_branches = run_git(["branch", "-r"], main_repo_path)
    if not ok or f"origin/{pr_branch}" not in remote_branches:
        return False, f"Branch {pr_branch} not found on remote", None
    
    # Create worktree for the PR branch (use flat folder name)
    worktree_folder = f"{repo_name}-{sanitize_branch_for_path(pr_branch)}"
    worktree_path = scan_dir / worktree_folder
    
    if worktree_path.exists():
        return False, f"Path already exists: {worktree_path}", None
    
    # Create worktree tracking the remote branch
    ok, output = run_git(["worktree", "add", "--track", "-b", pr_branch, 
                          str(worktree_path), f"origin/{pr_branch}"], main_repo_path)
    if not ok:
        # Try without creating new branch (branch might exist locally)
        ok, output = run_git(["worktree", "add", str(worktree_path), pr_branch], main_repo_path)
        if not ok:
            return False, f"Worktree creation failed: {output}", None
    
    return True, f"Created worktree at {worktree_path}", worktree_path


def checkout_pr_to_worktree(pr: PRStatus, scan_dir: Path) -> tuple[bool, str]:
    """Checkout a PR to a worktree. Clone repo first if needed."""
    if pr.local_status == "Checked out":
        return False, "Already checked out"
    
    # Get the branch name if we don't have it
    branch = pr.branch
    if not branch:
        branch = get_pr_branch(pr.repo_full_name, pr.number)
        if not branch:
            return False, "Could not determine PR branch name"
    
    if pr.local_status == "Not cloned":
        # Need to clone first
        return clone_repo_with_worktree(pr.repo_full_name, branch, scan_dir)
    
    elif pr.local_status == "Available":
        # Repo exists, just create worktree
        if pr.local_path:
            # Use flat folder name: repo-branch (with slashes replaced)
            worktree_folder = f"{pr.repo_name}-{sanitize_branch_for_path(branch)}"
            worktree_path = scan_dir / worktree_folder
            if worktree_path.exists():
                return False, f"Path already exists: {worktree_path}"
            
            # Fetch to ensure we have the branch
            run_git(["fetch", "--all"], pr.local_path)
            
            # Create worktree
            ok, output = run_git(["worktree", "add", "--track", "-b", branch,
                                  str(worktree_path), f"origin/{branch}"], pr.local_path)
            if not ok:
                ok, output = run_git(["worktree", "add", str(worktree_path), branch], pr.local_path)
                if not ok:
                    return False, f"Worktree creation failed: {output}"
            
            return True, f"Created worktree at {worktree_path}"
        else:
            # Fallback: clone and create worktree
            return clone_repo_with_worktree(pr.repo_full_name, branch, scan_dir)
    
    return False, "Unknown local status"


def open_in_browser(url: str) -> tuple[bool, str]:
    """Open URL in default browser."""
    import webbrowser
    try:
        webbrowser.open(url)
        return True, "Opened in browser"
    except Exception as e:
        return False, str(e)


def close_pr(repo_full_name: str, pr_number: int) -> tuple[bool, str]:
    """Close a PR using gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "pr", "close", str(pr_number), "--repo", repo_full_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, f"PR #{pr_number} closed"
        else:
            error = result.stderr.strip() or result.stdout.strip()
            # Extract useful error message
            for line in error.split('\n'):
                if line.strip():
                    return False, line.strip()
            return False, "Unknown error"
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def check_repo(repo_path: Path, is_worktree: bool) -> RepoStatus | None:
    type_label = "Worktree" if is_worktree else "Repo"
    name = repo_path.name
    main_branch = get_main_branch(repo_path, is_worktree)

    ok, branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    if not ok:
        return None
    branch = branch or "DETACHED"

    run_git(["fetch", "--all", "--quiet"], repo_path)

    ok, remote_check = run_git(["ls-remote", "--heads", "origin", branch], repo_path)
    remote_exists = branch in remote_check if ok else False
    remote_branch = f"origin/{branch}"

    sync_status = "-"
    if remote_exists:
        ok, local_commit = run_git(["rev-parse", "HEAD"], repo_path)
        ok2, remote_commit = run_git(["rev-parse", remote_branch], repo_path)

        if ok and ok2 and local_commit == remote_commit:
            sync_status = "Synced"
        else:
            ok, ahead = run_git(["rev-list", "--count", f"{remote_branch}..HEAD"], repo_path)
            ahead = int(ahead) if ok and ahead.isdigit() else 0
            ok, behind = run_git(["rev-list", "--count", f"HEAD..{remote_branch}"], repo_path)
            behind = int(behind) if ok and behind.isdigit() else 0

            if ahead > 0 and behind > 0:
                sync_status = f"Diverged (+{ahead}/-{behind})"
            elif ahead > 0:
                sync_status = f"Ahead (+{ahead})"
            elif behind > 0:
                sync_status = f"Behind (-{behind})"
            else:
                sync_status = "Synced"

    origin_main = f"origin/{main_branch}"
    is_on_main_branch = branch in (main_branch, "main", "dev", "master")

    if is_on_main_branch:
        rebase_status = "-"
    else:
        ok, _ = run_git(["rev-parse", origin_main], repo_path)
        if ok:
            ok, main_commit = run_git(["rev-parse", origin_main], repo_path)
            ok2, merge_base = run_git(["merge-base", "HEAD", origin_main], repo_path)

            if ok and ok2 and merge_base == main_commit:
                rebase_status = "Rebased"
            else:
                ok, behind_main = run_git(["rev-list", "--count", f"HEAD..{origin_main}"], repo_path)
                behind_main = int(behind_main) if ok and behind_main.isdigit() else 0
                rebase_status = f"Behind {main_branch} (-{behind_main})"
        else:
            rebase_status = f"No {main_branch}"

    pr_status = get_pr_status(branch, repo_path)
    has_changes = has_uncommitted_changes(repo_path)

    return RepoStatus(
        name=name,
        path=repo_path,
        type_label=type_label,
        branch=branch,
        remote_exists=remote_exists,
        sync_status=sync_status,
        rebase_status=rebase_status,
        pr_status=pr_status,
        main_branch=main_branch,
        has_changes=has_changes,
    )


def scan_repos(scan_dir: Path, max_workers: int = 16) -> list[RepoStatus]:
    """Scan all git repos in parallel."""
    # Collect repos to scan
    to_scan: list[tuple[Path, bool]] = []
    for item in sorted(scan_dir.iterdir()):
        git_path = item / ".git"
        if not git_path.exists():
            continue
        is_worktree = git_path.is_file()
        to_scan.append((item, is_worktree))
    
    if not to_scan:
        return []
    
    # Scan all repos in parallel
    repos: list[RepoStatus] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_repo, repo_path, is_worktree): repo_path
            for repo_path, is_worktree in to_scan
        }
        for future in as_completed(futures):
            status = future.result()
            if status:
                repos.append(status)
    
    return repos


def pull_rebase(repo: RepoStatus) -> tuple[bool, str]:
    run_git(["fetch", "origin"], repo.path)
    ok, output = run_git(["pull", "--rebase", "origin", repo.branch], repo.path)
    if ok:
        return True, "Pulled successfully"
    run_git(["rebase", "--abort"], repo.path)
    return False, output or "Pull failed"


def rebase_on_main(repo: RepoStatus) -> tuple[bool, str]:
    run_git(["fetch", "origin"], repo.path)
    
    if "Behind" in repo.sync_status and "Diverged" not in repo.sync_status:
        ok, output = run_git(["pull", "--rebase", "origin", repo.branch], repo.path)
        if not ok:
            run_git(["rebase", "--abort"], repo.path)
            return False, output or "Pull failed"
        return True, f"Pulled from origin/{repo.branch}"
    
    origin_main = f"origin/{repo.main_branch}"
    ok, output = run_git(["rebase", origin_main], repo.path)
    if ok:
        return True, f"Rebased on {origin_main}"
    run_git(["rebase", "--abort"], repo.path)
    return False, output or "Rebase failed"


def force_push(repo: RepoStatus) -> tuple[bool, str]:
    ok, output = run_git(["push", "--force-with-lease", "origin", repo.branch], repo.path)
    if ok:
        return True, "Force pushed successfully"
    return False, output or "Push failed"


def create_remote(repo: RepoStatus) -> tuple[bool, str]:
    ok, output = run_git(["push", "-u", "origin", repo.branch], repo.path)
    if ok:
        return True, "Remote branch created"
    return False, output or "Push failed"


def stash_changes(repo: RepoStatus) -> tuple[bool, str]:
    ok, output = run_git(["stash", "push", "-m", "Auto-stash by git-status-tui"], repo.path)
    if ok:
        return True, "Changes stashed"
    return False, output or "Stash failed"


def discard_changes(repo: RepoStatus) -> tuple[bool, str]:
    ok1, _ = run_git(["checkout", "--", "."], repo.path)
    ok2, _ = run_git(["clean", "-fd"], repo.path)
    if ok1 and ok2:
        return True, "Changes discarded"
    return False, "Discard failed"


def reset_to_remote(repo: RepoStatus) -> tuple[bool, str]:
    """Reset repo to match remote state exactly. DESTRUCTIVE: loses all local changes and commits."""
    # Fetch latest from remote
    ok, output = run_git(["fetch", "origin"], repo.path)
    if not ok:
        return False, f"Fetch failed: {output}"
    
    # Hard reset to remote branch
    ok, output = run_git(["reset", "--hard", f"origin/{repo.branch}"], repo.path)
    if not ok:
        return False, f"Reset failed: {output}"
    
    # Clean untracked files and directories
    ok, output = run_git(["clean", "-fd"], repo.path)
    if not ok:
        return False, f"Clean failed: {output}"
    
    return True, f"Reset to origin/{repo.branch}"


def delete_local_folder(repo: RepoStatus) -> tuple[bool, str]:
    """Delete local repo/worktree folder. Safe: only works if fully synced with remote."""
    import shutil
    
    if repo.type_label == "Worktree":
        # For worktrees, find the main repo and remove the worktree properly
        ok, git_dir = run_git(["rev-parse", "--git-dir"], repo.path)
        if ok and git_dir:
            # The .git file points to the main repo's worktree directory
            # We need to run worktree remove from the main repo
            git_file = repo.path / ".git"
            if git_file.is_file():
                content = git_file.read_text().strip()
                if content.startswith("gitdir:"):
                    # Extract path and find main repo
                    worktree_git_dir = Path(content.split(":", 1)[1].strip())
                    # Go up from .git/worktrees/<name> to find main repo
                    main_repo = worktree_git_dir.parent.parent.parent
                    if main_repo.exists():
                        ok, output = run_git(["worktree", "remove", "--force", str(repo.path)], main_repo)
                        if ok:
                            return True, f"Worktree removed: {repo.name}"
                        return False, f"Worktree remove failed: {output}"
        # Fallback: just delete the folder
        try:
            shutil.rmtree(repo.path)
            return True, f"Worktree folder deleted: {repo.name}"
        except Exception as e:
            return False, f"Delete failed: {e}"
    else:
        # Regular repo - just delete the folder
        try:
            shutil.rmtree(repo.path)
            return True, f"Repo deleted: {repo.name}"
        except Exception as e:
            return False, f"Delete failed: {e}"


def create_branch_worktree(repo: RepoStatus, branch_name: str) -> tuple[bool, str]:
    """Create a new branch and worktree from the current repo."""
    # Validate branch name
    if not branch_name or not branch_name.strip():
        return False, "Branch name cannot be empty"
    
    branch_name = branch_name.strip()
    
    # Check if branch already exists
    ok, existing = run_git(["branch", "--list", branch_name], repo.path)
    if ok and existing:
        return False, f"Branch '{branch_name}' already exists"
    
    # Check if remote branch exists
    ok, remote_existing = run_git(["ls-remote", "--heads", "origin", branch_name], repo.path)
    if ok and branch_name in remote_existing:
        return False, f"Remote branch 'origin/{branch_name}' already exists"
    
    # Worktree path is sibling to current repo (use flat folder name)
    worktree_folder = f"{repo.name}-{sanitize_branch_for_path(branch_name)}"
    worktree_path = repo.path.parent / worktree_folder
    
    if worktree_path.exists():
        return False, f"Path already exists: {worktree_path}"
    
    # Create worktree with new branch
    ok, output = run_git(["worktree", "add", "-b", branch_name, str(worktree_path)], repo.path)
    if ok:
        return True, f"Created worktree at {worktree_path}"
    return False, f"Worktree creation failed: {output}"


class ResultsModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
    ]

    def __init__(self, title: str, results: list[tuple[str, bool, str]]) -> None:
        super().__init__()
        self.title_text = title
        self.results = results

    def compose(self) -> ComposeResult:
        success = sum(1 for _, ok, _ in self.results if ok)
        failed = len(self.results) - success

        lines = [f"[bold]{self.title_text}[/bold]\n"]
        for name, ok, msg in self.results:
            icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
            lines.append(f"{icon} {name}: {msg}")
        lines.append(f"\n[bold]Summary:[/bold] [green]{success} succeeded[/green], [red]{failed} failed[/red]")
        lines.append("\n[dim]Press Enter or Escape to close[/dim]")

        with Container(id="results-modal"):
            yield Static("\n".join(lines), id="results-content")

    def action_dismiss(self) -> None:
        self.app.pop_screen()


class ConfirmModal(ModalScreen):
    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, message: str, dangerous: bool = False) -> None:
        super().__init__()
        self.title_text = title
        self.message = message
        self.dangerous = dangerous

    def compose(self) -> ComposeResult:
        style = "[bold red]" if self.dangerous else "[bold]"
        content = f"{style}{self.title_text}[/]\n\n{self.message}\n\n"
        if self.dangerous:
            content += "[yellow]Press 'y' to confirm, 'n' or Escape to cancel[/yellow]"
        else:
            content += "[dim]Press 'y' to confirm, 'n' or Escape to cancel[/dim]"

        with Container(id="confirm-modal"):
            yield Static(content, id="confirm-content")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class InputModal(ModalScreen):
    """Modal for getting text input from user."""
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, prompt: str, placeholder: str = "") -> None:
        super().__init__()
        self.title_text = title
        self.prompt = prompt
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Container(id="input-modal"):
            yield Static(f"[bold]{self.title_text}[/bold]\n\n{self.prompt}", id="input-prompt")
            yield Input(placeholder=self.placeholder, id="modal-input")
            yield Static("\n[dim]Press Enter to confirm, Escape to cancel[/dim]", id="input-hint")

    def on_mount(self) -> None:
        self.query_one("#modal-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "modal-input":
            self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class HelpModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        help_text = """[bold cyan]═══ Git Status TUI Help ═══[/bold cyan]

[bold]Navigation[/bold]
  [yellow]Tab[/yellow]      Switch between Repos/PRs/Config tabs
  [yellow]↑/↓[/yellow]      Move cursor up/down
  [yellow]Space[/yellow]    Select item & move down
  [yellow]Enter[/yellow]    Select item (or focus settings on Config)
  [yellow]a[/yellow]        Select/deselect all
  [yellow]Esc[/yellow]      Clear filter or selection
  [yellow]/[/yellow]        Filter by name

[bold]Repos Tab Actions[/bold]
  [yellow]p[/yellow]        Pull (git pull --rebase)
  [yellow]r[/yellow]        Rebase/Sync on main
  [yellow]f[/yellow]        Force push [red](dangerous)[/red]
  [yellow]c[/yellow]        Create remote branch
  [yellow]w[/yellow]        [cyan]Speckit feature[/cyan] (###-branch + spec)
  [yellow]s[/yellow]        Stash changes
  [yellow]d[/yellow]        Discard changes [red](dangerous)[/red]
  [yellow]D[/yellow]        Delete local (if synced) [red](dangerous)[/red]
  [yellow]X[/yellow]        Reset to remote [red](DESTRUCTIVE)[/red]
  [yellow]A[/yellow]        [cyan]Launch AI CLI[/cyan] in selected repo

[bold]PRs Tab Actions[/bold]
  [yellow]o[/yellow]        Checkout PR to worktree
  [yellow]b[/yellow]        Open PR in browser

[bold]Config Tab[/bold]
  [yellow]Enter[/yellow]    Focus settings
  [yellow]↑/↓[/yellow]      Navigate between settings
  Configure default AI CLI and shared OpenCode settings

[bold]Other[/bold]
  [yellow]R[/yellow]        Refresh current tab
  [yellow]?[/yellow]        Show this help
  [yellow]q[/yellow]        Quit

[dim]Press Esc or Enter to close[/dim]"""

        with Container(id="help-modal"):
            yield Static(help_text, id="help-content")

    def action_dismiss(self) -> None:
        self.app.pop_screen()


class AICliPickerModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_default: str) -> None:
        super().__init__()
        self.current_default = current_default

    def compose(self) -> ComposeResult:
        with Container(id="ai-picker-modal"):
            yield Static("[bold]Select AI CLI to launch[/bold]\n", id="ai-picker-title")
            for cli_id, cli_name in AI_CLI_OPTIONS:
                marker = " [green](default)[/green]" if cli_id == self.current_default else ""
                yield Button(f"{cli_name}{marker}", id=f"ai-btn-{cli_id}", classes="ai-picker-btn")
            yield Static("\n[dim]Press Escape to cancel[/dim]", id="ai-picker-hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("ai-btn-"):
            cli_id = event.button.id.replace("ai-btn-", "")
            self.dismiss(cli_id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class GitStatusApp(App):
    ENABLE_COMMAND_PALETTE = False  # Disable Ctrl+P command palette
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main-container {
        height: 100%;
    }
    
    #loading-container {
        width: 100%;
        height: 100%;
        align: center middle;
        layout: vertical;
    }
    
    #loading-inner {
        width: auto;
        height: auto;
        align: center middle;
    }
    
    #loading-animation {
        width: auto;
        height: auto;
        text-align: center;
        color: $text;
    }
    
    #filter-bar {
        dock: top;
        height: 3;
        background: $primary-background;
        padding: 0 1;
        display: none;
    }
    
    #filter-bar.visible {
        display: block;
    }
    
    #filter-input {
        width: 100%;
    }
    
    #status-bar {
        dock: bottom;
        height: 3;
        background: $primary-background;
        padding: 0 1;
    }
    
    #status-bar Label {
        width: 100%;
    }
    
    TabbedContent {
        height: 1fr;
    }
    
    ContentSwitcher {
        height: 1fr;
    }
    
    TabPane {
        height: 1fr;
        padding: 0;
    }
    
    #repo-table, #pr-table {
        height: 1fr;
    }
    
    DataTable {
        height: 1fr;
    }
    
    DataTable > .datatable--cursor {
        background: $accent;
    }
    
    #results-modal, #confirm-modal {
        align: center middle;
        width: 80%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }
    
    #results-content, #confirm-content {
        width: 100%;
        height: auto;
    }
    
    #help-modal {
        align: center middle;
        width: 55;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }
    
    #help-content {
        width: 100%;
        height: auto;
    }
    
    #input-modal {
        align: center middle;
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }
    
    #input-prompt {
        width: 100%;
        height: auto;
    }
    
    #modal-input {
        width: 100%;
        margin: 1 0;
    }
    
    #input-hint {
        width: 100%;
        height: auto;
    }
    
    #ai-picker-modal {
        align: center middle;
        width: 50;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }
    
    .ai-picker-btn {
        width: 100%;
        margin: 0 0 1 0;
    }
    
    #config-container {
        padding: 2 4;
        height: 100%;
    }
    
    .config-section {
        margin: 0 0 2 0;
        padding: 1 2;
        border: round $primary;
    }
    
    .config-section-title {
        text-style: bold;
        margin: 0 0 1 0;
    }
    
    .config-row {
        height: 3;
        margin: 0 0 1 0;
    }
    
    .config-label {
        width: 30;
        padding: 0 1;
    }
    
    .config-value {
        width: 1fr;
    }
    
    #shared-opencode-status {
        padding: 0 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "request_quit", "Quit"),
        Binding("tab", "switch_tab", "Switch Tab", priority=True),
        Binding("slash", "start_filter", "Filter", key_display="/"),
        Binding("question_mark", "show_help", "Help", key_display="?"),
        Binding("p", "pull", "Pull"),
        Binding("r", "rebase", "Rebase/Sync"),
        Binding("f", "force_push", "Force Push"),
        Binding("c", "create_remote", "Create Remote"),
        Binding("s", "stash", "Stash"),
        Binding("d", "discard", "Discard"),
        Binding("X", "reset_to_remote", "Reset to Remote"),
        Binding("D", "delete_local", "Delete Local"),
        Binding("w", "create_worktree", "New Worktree"),
        Binding("A", "launch_ai_cli", "Launch AI CLI"),
        Binding("o", "checkout_pr", "Checkout PR"),
        Binding("b", "open_pr_browser", "Open in Browser"),
        Binding("C", "close_pr", "Close PR"),
        Binding("space", "toggle_select", "Select", show=False),
        Binding("a", "select_all", "Select All"),
        Binding("escape", "clear_filter", "Clear", show=False),
        Binding("enter", "activate", "Select/Activate", show=False, priority=True),
        Binding("down", "nav_down", show=False, priority=True),
        Binding("up", "nav_up", show=False, priority=True),
        Binding("R", "refresh", "Refresh"),
    ]

    def __init__(self, scan_dir: Path) -> None:
        super().__init__()
        self.scan_dir = scan_dir
        self.config = AppConfig.load()
        self.all_repos: list[RepoStatus] = []
        self.repos: list[RepoStatus] = []
        self.selected: set[str] = set()
        self.all_prs: list[PRStatus] = []
        self.prs: list[PRStatus] = []
        self.selected_prs: set[int] = set()
        self.filter_text: str = ""
        self.filter_visible: bool = False
        self.animation_frame = 0
        self.animation_timer = None
        self.is_loading: bool = True
        self.active_tab: str = "repos"
        self.shared_opencode_proc: subprocess.Popen | None = None
        self.pending_ai_launch: tuple[str, Path] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            with Container(id="loading-container"):
                with Vertical(id="loading-inner"):
                    yield Static(LOADING_FRAMES[0], id="loading-animation")
            with Horizontal(id="filter-bar"):
                yield Input(placeholder="Filter by name...", id="filter-input")
            with TabbedContent(initial="repos"):
                with TabPane("Repositories", id="repos"):
                    yield DataTable(id="repo-table", cursor_type="row")
                with TabPane("My Open PRs", id="prs"):
                    yield DataTable(id="pr-table", cursor_type="row")
                with TabPane("Config", id="config"):
                    with VerticalScroll(id="config-container"):
                        yield Static("[bold cyan]AI CLI Settings[/bold cyan]", classes="config-section-title")
                        with Horizontal(classes="config-row"):
                            yield Static("Default AI CLI:", classes="config-label")
                            yield Select(
                                [(name, cli_id) for cli_id, name in AI_CLI_OPTIONS],
                                value=self.config.default_ai_cli,
                                id="default-ai-cli-select",
                                classes="config-value"
                            )
                        yield Rule()
                        yield Static("[bold cyan]Shared OpenCode Server[/bold cyan]", classes="config-section-title")
                        with Horizontal(classes="config-row"):
                            yield Static("Enable shared OpenCode:", classes="config-label")
                            yield Switch(value=self.config.shared_opencode_enabled, id="shared-opencode-switch")
                        yield Static(
                            f"When enabled, starts opencode-shared server in: {self.scan_dir}",
                            id="shared-opencode-status"
                        )
                        yield Rule()
                        yield Static("[bold cyan]Environment[/bold cyan]", classes="config-section-title")
                        zellij_status = "[green]Yes[/green]" if is_inside_zellij() else "[dim]No[/dim]"
                        yield Static(f"Running inside Zellij: {zellij_status}", id="zellij-status")
                        yield Static(f"Config file: {CONFIG_FILE}", id="config-file-path")
            with Horizontal(id="status-bar"):
                yield Label("", id="status-label")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Git Repository Status"
        self.sub_title = str(self.scan_dir)
        # Disable filter input until explicitly opened
        filter_input = self.query_one("#filter-input", Input)
        filter_input.disabled = True
        self.refresh_repos()

    def show_loading(self, show: bool) -> None:
        self.is_loading = show
        loading = self.query_one("#loading-container", Container)
        tabbed = self.query_one(TabbedContent)
        loading.display = show
        tabbed.display = not show
        
        # Start/stop animation
        if show:
            self.animation_frame = 0
            self.animation_timer = self.set_interval(0.15, self._animate_loading)
        elif self.animation_timer:
            self.animation_timer.stop()
            self.animation_timer = None

    def _animate_loading(self) -> None:
        """Cycle through animation frames."""
        self.animation_frame = (self.animation_frame + 1) % len(LOADING_FRAMES)
        try:
            animation = self.query_one("#loading-animation", Static)
            animation.update(LOADING_FRAMES[self.animation_frame])
        except Exception:
            pass  # Widget may not exist yet

    def action_switch_tab(self) -> None:
        if self._filter_has_focus():
            return
        tabbed = self.query_one(TabbedContent)
        tab_order = ["repos", "prs", "config"]
        current_idx = tab_order.index(self.active_tab) if self.active_tab in tab_order else 0
        next_idx = (current_idx + 1) % len(tab_order)
        tabbed.active = tab_order[next_idx]

    def action_focus_next(self) -> None:
        self.action_switch_tab()

    def action_activate(self) -> None:
        if self._filter_has_focus():
            return
        
        if self.active_tab == "config":
            select = self.query_one("#default-ai-cli-select", Select)
            switch = self.query_one("#shared-opencode-switch", Switch)
            select_focused = select.has_focus or select.has_focus_within
            switch_focused = switch.has_focus or switch.has_focus_within
            if switch_focused:
                switch.toggle()
            elif not select_focused:
                select.focus()
        else:
            self.action_toggle_select()

    def action_nav_down(self) -> None:
        if self.active_tab == "config":
            select = self.query_one("#default-ai-cli-select", Select)
            switch = self.query_one("#shared-opencode-switch", Switch)
            select_focused = select.has_focus or select.has_focus_within
            switch_focused = switch.has_focus or switch.has_focus_within
            if select_focused:
                if select.expanded:
                    raise SkipAction()
                switch.focus()
                return
            elif switch_focused:
                return
            select.focus()
            return
        if self.active_tab in ("repos", "prs"):
            table_id = "#repo-table" if self.active_tab == "repos" else "#pr-table"
            table = self.query_one(table_id, DataTable)
            table.action_cursor_down()
            return
        raise SkipAction()

    def action_nav_up(self) -> None:
        if self.active_tab == "config":
            select = self.query_one("#default-ai-cli-select", Select)
            switch = self.query_one("#shared-opencode-switch", Switch)
            select_focused = select.has_focus or select.has_focus_within
            switch_focused = switch.has_focus or switch.has_focus_within
            if switch_focused:
                select.focus()
                return
            elif select_focused:
                if select.expanded:
                    raise SkipAction()
                return
            switch.focus()
            return
        if self.active_tab in ("repos", "prs"):
            table_id = "#repo-table" if self.active_tab == "repos" else "#pr-table"
            table = self.query_one(table_id, DataTable)
            table.action_cursor_up()
            return
        raise SkipAction()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self.active_tab = event.pane.id or "repos"
        self.filter_text = ""
        if self.filter_visible:
            self.action_clear_filter()
        
        if self.active_tab == "repos":
            table = self.query_one("#repo-table", DataTable)
            if not self.is_loading:
                table.focus()
        elif self.active_tab == "prs":
            table = self.query_one("#pr-table", DataTable)
            if not self.is_loading:
                table.focus()
            if not self.all_prs:
                self.refresh_prs()
        
        self.update_status()

    def refresh_repos(self) -> None:
        self.show_loading(True)
        self.run_worker(self._scan_repos_worker, exclusive=True, thread=True, name="_scan_repos_worker")

    def refresh_prs(self) -> None:
        self.show_loading(True)
        self.run_worker(self._scan_prs_worker, exclusive=True, thread=True, name="_scan_prs_worker")

    def _scan_repos_worker(self) -> list[RepoStatus]:
        return scan_repos(self.scan_dir)

    def _scan_prs_worker(self) -> list[PRStatus]:
        """Fetch open PRs and detect their local status."""
        raw_prs = fetch_open_prs()
        prs: list[PRStatus] = []
        
        for pr_data in raw_prs:
            repo_info = pr_data.get("repository", {})
            repo_name = repo_info.get("name", "")
            repo_full_name = repo_info.get("nameWithOwner", "")
            pr_number = pr_data.get("number", 0)
            
            # Get branch name for this PR
            branch = get_pr_branch(repo_full_name, pr_number) or ""
            
            # Detect local status
            local_status, local_path = detect_pr_local_status(branch, repo_name, self.scan_dir)
            
            prs.append(PRStatus(
                number=pr_number,
                title=pr_data.get("title", ""),
                branch=branch,
                repo_name=repo_name,
                repo_full_name=repo_full_name,
                url=pr_data.get("url", ""),
                local_status=local_status,
                local_path=local_path,
            ))
        
        return prs

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.SUCCESS:
            if event.worker.name == "_scan_repos_worker":
                self._populate_repo_table(event.worker.result)
            elif event.worker.name == "_scan_prs_worker":
                self._populate_pr_table(event.worker.result)

    def _sort_repos(self, repos: list[RepoStatus]) -> list[RepoStatus]:
        """Sort repos by rebase status, then sync status, then name."""
        def sort_key(r: RepoStatus) -> tuple:
            # Rebase priority: 0=needs rebase, 1=no main branch, 2=rebased/on main
            if "Behind" in r.rebase_status:
                rebase_priority = 0
            elif "No " in r.rebase_status:
                rebase_priority = 1
            else:  # Rebased or "-"
                rebase_priority = 2
            
            # Sync priority: 0=diverged, 1=behind, 2=ahead, 3=synced/no remote
            if "Diverged" in r.sync_status:
                sync_priority = 0
            elif "Behind" in r.sync_status:
                sync_priority = 1
            elif "Ahead" in r.sync_status:
                sync_priority = 2
            else:
                sync_priority = 3
            
            return (rebase_priority, sync_priority, r.name.lower())
        
        return sorted(repos, key=sort_key)

    def _sort_prs(self, prs: list[PRStatus]) -> list[PRStatus]:
        """Sort PRs by local status (not checked out first), then repo, then PR number."""
        def sort_key(p: PRStatus) -> tuple:
            # Status priority: 0=not cloned (need action), 1=available, 2=checked out
            if p.local_status == "Not cloned":
                status_priority = 0
            elif p.local_status == "Available":
                status_priority = 1
            else:
                status_priority = 2
            
            return (status_priority, p.repo_name.lower(), -p.number)
        
        return sorted(prs, key=sort_key)

    def _apply_filter(self) -> list[RepoStatus]:
        """Filter repos based on current filter text."""
        if not self.filter_text:
            return self.all_repos[:]
        filter_lower = self.filter_text.lower()
        return [r for r in self.all_repos if filter_lower in r.name.lower() or filter_lower in r.branch.lower()]

    def _apply_pr_filter(self) -> list[PRStatus]:
        """Filter PRs based on current filter text."""
        if not self.filter_text:
            return self.all_prs[:]
        filter_lower = self.filter_text.lower()
        return [p for p in self.all_prs if 
                filter_lower in p.repo_name.lower() or 
                filter_lower in p.title.lower() or
                filter_lower in p.branch.lower()]

    def _colorize_local_status(self, status: str) -> Text:
        """Color code PR local status."""
        if status == "Checked out":
            return Text(status, style="green")
        elif status == "Available":
            return Text(status, style="yellow")
        else:  # Not cloned
            return Text(status, style="dim red")

    def _populate_repo_table(self, repos: list[RepoStatus] | None = None) -> None:
        table = self.query_one("#repo-table", DataTable)
        table.clear(columns=True)
        table.add_columns("☑", "Type", "Name", "Branch", "Remote?", "Sync", "Rebase", "PR", "Changes")

        # If new repos provided, store them; otherwise use existing
        if repos is not None:
            self.all_repos = self._sort_repos(repos)
        
        # Apply filter
        self.repos = self._apply_filter()

        for repo in self.repos:
            selected = "☑" if repo.name in self.selected else "☐"
            remote = Text("Yes", style="green") if repo.remote_exists else Text("No", style="dim")
            changes = Text("Yes", style="yellow") if repo.has_changes else Text("-", style="dim")
            table.add_row(
                selected,
                repo.type_label,
                repo.name,
                repo.branch[:30],
                remote,
                colorize_sync(repo.sync_status),
                colorize_rebase(repo.rebase_status),
                repo.pr_status,
                changes,
                key=repo.name,
            )

        self.show_loading(False)
        # Only focus table if filter input doesn't have focus and we're on repos tab
        if not self._filter_has_focus() and self.active_tab == "repos":
            table.focus()
        self.update_status()

    def _populate_pr_table(self, prs: list[PRStatus] | None = None) -> None:
        """Populate the PRs table."""
        table = self.query_one("#pr-table", DataTable)
        table.clear(columns=True)
        table.add_columns("☑", "Repo", "PR#", "Title", "Branch", "Local Status", "Local Path")

        # If new PRs provided, store them; otherwise use existing
        if prs is not None:
            self.all_prs = self._sort_prs(prs)
        
        # Apply filter
        self.prs = self._apply_pr_filter()

        for pr in self.prs:
            selected = "☑" if pr.number in self.selected_prs else "☐"
            local_path_str = str(pr.local_path.name) if pr.local_path else "-"
            table.add_row(
                selected,
                pr.repo_name,
                f"#{pr.number}",
                pr.title[:40] + ("..." if len(pr.title) > 40 else ""),
                pr.branch[:20] + ("..." if len(pr.branch) > 20 else ""),
                self._colorize_local_status(pr.local_status),
                Text(local_path_str, style="cyan") if pr.local_path else Text("-", style="dim"),
                key=str(pr.number),
            )

        self.show_loading(False)
        # Only focus table if filter input doesn't have focus and we're on PRs tab
        if not self._filter_has_focus() and self.active_tab == "prs":
            table.focus()
        self.update_status()

    def update_status(self) -> None:
        label = self.query_one("#status-label", Label)
        if self.active_tab == "repos":
            count = len(self.selected)
            if count == 0:
                label.update(f"{len(self.repos)} repos | Space: select | A: AI CLI | Tab: next | R: refresh")
            else:
                label.update(f"{count} selected | A: AI CLI | Actions: p/r/f/c/s/d | Esc: clear")
        elif self.active_tab == "prs":
            count = len(self.selected_prs)
            if count == 0:
                label.update(f"{len(self.prs)} PRs | Space: select | o: checkout | b: browser | Tab: next")
            else:
                label.update(f"{count} selected | o: checkout | b: browser | C: close | Esc: clear")
        else:
            label.update("Config | Tab: next | ?: help")

    def get_selected_repos(self) -> list[RepoStatus]:
        return [r for r in self.repos if r.name in self.selected]

    def get_selected_prs(self) -> list[PRStatus]:
        return [p for p in self.prs if p.number in self.selected_prs]

    def _filter_has_focus(self) -> bool:
        """Check if filter input is currently focused."""
        try:
            filter_input = self.query_one("#filter-input", Input)
            return filter_input.has_focus
        except Exception:
            return False

    def action_toggle_select(self) -> None:
        if self._filter_has_focus():
            return
        
        if self.active_tab == "repos":
            table = self.query_one("#repo-table", DataTable)
            if table.cursor_row is not None and table.cursor_row < len(self.repos):
                repo = self.repos[table.cursor_row]
                if repo.name in self.selected:
                    self.selected.discard(repo.name)
                else:
                    self.selected.add(repo.name)
                
                selected_char = "☑" if repo.name in self.selected else "☐"
                table.update_cell_at(Coordinate(table.cursor_row, 0), selected_char)
                self.update_status()
                
                # Auto-advance to next row
                if table.cursor_row < len(self.repos) - 1:
                    table.move_cursor(row=table.cursor_row + 1)
        else:  # PRs tab
            table = self.query_one("#pr-table", DataTable)
            if table.cursor_row is not None and table.cursor_row < len(self.prs):
                pr = self.prs[table.cursor_row]
                if pr.number in self.selected_prs:
                    self.selected_prs.discard(pr.number)
                else:
                    self.selected_prs.add(pr.number)
                
                selected_char = "☑" if pr.number in self.selected_prs else "☐"
                table.update_cell_at(Coordinate(table.cursor_row, 0), selected_char)
                self.update_status()
                
                # Auto-advance to next row
                if table.cursor_row < len(self.prs) - 1:
                    table.move_cursor(row=table.cursor_row + 1)

    def action_select_all(self) -> None:
        if self._filter_has_focus():
            return
        
        if self.active_tab == "repos":
            table = self.query_one("#repo-table", DataTable)
            if len(self.selected) == len(self.repos):
                self.selected.clear()
            else:
                self.selected = {r.name for r in self.repos}
            
            for i, repo in enumerate(self.repos):
                selected_char = "☑" if repo.name in self.selected else "☐"
                table.update_cell_at(Coordinate(i, 0), selected_char)
        else:  # PRs tab
            table = self.query_one("#pr-table", DataTable)
            if len(self.selected_prs) == len(self.prs):
                self.selected_prs.clear()
            else:
                self.selected_prs = {p.number for p in self.prs}
            
            for i, pr in enumerate(self.prs):
                selected_char = "☑" if pr.number in self.selected_prs else "☐"
                table.update_cell_at(Coordinate(i, 0), selected_char)
        
        self.update_status()

    def action_clear_selection(self) -> None:
        if self.active_tab == "repos":
            table = self.query_one("#repo-table", DataTable)
            self.selected.clear()
            for i in range(len(self.repos)):
                table.update_cell_at(Coordinate(i, 0), "☐")
        else:  # PRs tab
            table = self.query_one("#pr-table", DataTable)
            self.selected_prs.clear()
            for i in range(len(self.prs)):
                table.update_cell_at(Coordinate(i, 0), "☐")
        self.update_status()

    def action_start_filter(self) -> None:
        """Show filter input and focus it."""
        if self._filter_has_focus():
            return
        filter_bar = self.query_one("#filter-bar", Horizontal)
        filter_bar.add_class("visible")
        self.filter_visible = True
        filter_input = self.query_one("#filter-input", Input)
        filter_input.disabled = False
        filter_input.focus()

    def action_clear_filter(self) -> None:
        """Clear filter and hide filter bar, or clear selection if no filter."""
        if self.filter_visible:
            self.filter_text = ""
            filter_input = self.query_one("#filter-input", Input)
            filter_input.value = ""
            filter_input.disabled = True
            filter_bar = self.query_one("#filter-bar", Horizontal)
            filter_bar.remove_class("visible")
            self.filter_visible = False
            if not self.is_loading:
                if self.active_tab == "repos":
                    self._populate_repo_table()
                else:
                    self._populate_pr_table()
            # Focus appropriate table
            if self.active_tab == "repos":
                table = self.query_one("#repo-table", DataTable)
            else:
                table = self.query_one("#pr-table", DataTable)
            table.focus()
        else:
            # Clear selection if filter not visible
            self.action_clear_selection()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes."""
        if event.input.id == "filter-input" and not self.is_loading:
            self.filter_text = event.value
            if self.active_tab == "repos":
                self._populate_repo_table()
            else:
                self._populate_pr_table()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter-input":
            if self.active_tab == "repos":
                table = self.query_one("#repo-table", DataTable)
            else:
                table = self.query_one("#pr-table", DataTable)
            table.focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "default-ai-cli-select" and event.value:
            self.config.default_ai_cli = str(event.value)
            self.config.save()
            self.notify(f"Default AI CLI set to: {event.value}", severity="information")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "shared-opencode-switch":
            self.config.shared_opencode_enabled = event.value
            self.config.save()
            if event.value:
                ok, msg, proc = start_shared_opencode(self.scan_dir)
                self.shared_opencode_proc = proc
                if ok:
                    self.notify(msg, severity="information")
                else:
                    self.notify(f"Failed: {msg}", severity="error")
            else:
                ok, msg = stop_shared_opencode(self.shared_opencode_proc)
                self.shared_opencode_proc = None
                self.notify(msg, severity="information")

    def on_key(self, event) -> None:
        if self.filter_visible and not self._filter_has_focus():
            key = event.key
            if len(key) == 1 and key.isprintable():
                filter_input = self.query_one("#filter-input", Input)
                filter_input.focus()

    def action_request_quit(self) -> None:
        """Handle quit request - require double press to quit."""
        import time
        now = time.time()
        if hasattr(self, '_last_quit_time') and now - self._last_quit_time < 1.5:
            self.exit()
        else:
            self._last_quit_time = now
            self.notify("Press again to quit", severity="warning", timeout=1.5)

    def action_help_quit(self) -> None:
        """Override Textual's default ctrl+c handler to also use double-tap quit."""
        self.action_request_quit()

    def action_refresh(self) -> None:
        if self._filter_has_focus():
            return
        if self.active_tab == "repos":
            self.refresh_repos()
        else:
            self.refresh_prs()

    def action_show_help(self) -> None:
        """Show help modal."""
        if self._filter_has_focus():
            return
        self.push_screen(HelpModal())

    def execute_action(
        self, check_fn, reason_fn, action_fn, action_name: str, dangerous: bool = False
    ) -> None:
        if self._filter_has_focus():
            return
        if self.active_tab != "repos":
            return
        selected = self.get_selected_repos()
        if not selected:
            self.notify("No repos selected", severity="warning")
            return

        eligible = [r for r in selected if check_fn(r)]
        skipped = [(r, reason_fn(r)) for r in selected if not check_fn(r)]
        
        if not eligible:
            self.notify(f"No selected repos can {action_name.lower()}", severity="warning")
            return

        msg = f"Will {action_name.lower()} {len(eligible)} repo(s):\n"
        msg += "\n".join(f"  • {r.name} ({r.branch})" for r in eligible[:10])
        if len(eligible) > 10:
            msg += f"\n  ... and {len(eligible) - 10} more"
        
        if skipped:
            msg += f"\n\n[dim]Skipped {len(skipped)} repo(s):[/dim]"
            for repo, reason in skipped[:5]:
                msg += f"\n[dim]  • {repo.name}: {reason}[/dim]"
            if len(skipped) > 5:
                msg += f"\n[dim]  ... and {len(skipped) - 5} more[/dim]"

        def do_action(confirmed: bool) -> None:
            if not confirmed:
                return
            results = []
            for repo in eligible:
                ok, message = action_fn(repo)
                results.append((repo.name, ok, message))
            self.push_screen(ResultsModal(f"{action_name} Results", results))
            self.refresh_repos()

        self.push_screen(ConfirmModal(action_name, msg, dangerous=dangerous), do_action)

    def action_pull(self) -> None:
        self.execute_action(lambda r: r.can_pull(), lambda r: r.why_not_pull(), pull_rebase, "Pull")

    def action_rebase(self) -> None:
        self.execute_action(lambda r: r.can_rebase(), lambda r: r.why_not_rebase(), rebase_on_main, "Rebase/Sync")

    def action_force_push(self) -> None:
        self.execute_action(lambda r: r.can_force_push(), lambda r: r.why_not_force_push(), force_push, "Force Push", dangerous=True)

    def action_create_remote(self) -> None:
        self.execute_action(lambda r: r.can_create_remote(), lambda r: r.why_not_create_remote(), create_remote, "Create Remote")

    def action_stash(self) -> None:
        self.execute_action(lambda r: r.can_stash(), lambda r: r.why_not_stash(), stash_changes, "Stash")

    def action_discard(self) -> None:
        self.execute_action(lambda r: r.can_discard(), lambda r: r.why_not_discard(), discard_changes, "Discard Changes", dangerous=True)

    def action_reset_to_remote(self) -> None:
        self.execute_action(
            lambda r: r.can_reset_to_remote(),
            lambda r: r.why_not_reset_to_remote(),
            reset_to_remote,
            "Reset to Remote (DESTRUCTIVE)",
            dangerous=True
        )

    def action_delete_local(self) -> None:
        self.execute_action(
            lambda r: r.can_delete_local(),
            lambda r: r.why_not_delete_local(),
            delete_local_folder,
            "Delete Local (safe - synced with remote)",
            dangerous=True
        )

    def action_create_worktree(self) -> None:
        """Create a speckit-compliant worktree with auto-numbered branch."""
        if self._filter_has_focus():
            return
        if self.active_tab != "repos":
            return
        
        selected = self.get_selected_repos()
        if not selected:
            self.notify("No repos selected", severity="warning")
            return
        
        if len(selected) > 1:
            self.notify("Select only one repo for creating worktree", severity="warning")
            return
        
        repo = selected[0]
        reason = repo.why_not_create_worktree()
        if reason:
            self.notify(f"Cannot create worktree: {reason}", severity="warning")
            return
        
        next_num = get_next_feature_number(repo.path, self.scan_dir)
        
        def handle_description(description: str | None) -> None:
            if not description:
                return
            
            ok, message = create_speckit_worktree(repo, description, self.scan_dir)
            if ok:
                self.notify(message, severity="information")
            else:
                self.notify(f"Failed: {message}", severity="error")
            self.refresh_repos()
        
        self.push_screen(
            InputModal(
                "Create Speckit Feature",
                f"Create feature #{next_num:03d} from [bold]{repo.name}[/bold]\n\nDescribe the feature (will auto-generate branch name):",
                placeholder="e.g., User authentication with OAuth..."
            ),
            handle_description
        )

    def action_launch_ai_cli(self) -> None:
        if self._filter_has_focus():
            return
        if self.active_tab != "repos":
            return
        
        selected = self.get_selected_repos()
        if not selected:
            self.notify("No repos selected", severity="warning")
            return
        
        if len(selected) > 1:
            self.notify("Select only one repo to launch AI CLI", severity="warning")
            return
        
        repo = selected[0]
        
        def handle_cli_choice(cli_id: str | None) -> None:
            if not cli_id:
                return
            self._execute_ai_launch(cli_id, repo.path, repo.name)
        
        self.push_screen(AICliPickerModal(self.config.default_ai_cli), handle_cli_choice)

    def _execute_ai_launch(self, cli_id: str, working_dir: Path, repo_name: str) -> None:
        if is_inside_zellij():
            tab_name = f"{cli_id}: {repo_name}"
            ok, msg = launch_ai_cli_zellij(cli_id, working_dir, tab_name)
            if ok:
                self.notify(msg, severity="information")
            else:
                self.notify(f"Failed: {msg}", severity="error")
        else:
            self.pending_ai_launch = (cli_id, working_dir)
            self.exit()

    def action_checkout_pr(self) -> None:
        if self._filter_has_focus():
            return
        if self.active_tab != "prs":
            return
        
        selected = self.get_selected_prs()
        if not selected:
            self.notify("No PRs selected", severity="warning")
            return
        
        # Filter to PRs that can be checked out
        eligible = [p for p in selected if p.local_status != "Checked out"]
        skipped = [p for p in selected if p.local_status == "Checked out"]
        
        if not eligible:
            self.notify("All selected PRs are already checked out", severity="warning")
            return
        
        msg = f"Will checkout {len(eligible)} PR(s) to worktrees:\n"
        for pr in eligible[:10]:
            action = "clone + worktree" if pr.local_status == "Not cloned" else "worktree"
            msg += f"  • {pr.repo_name} #{pr.number}: {pr.branch} ({action})\n"
        if len(eligible) > 10:
            msg += f"  ... and {len(eligible) - 10} more\n"
        
        if skipped:
            msg += f"\n[dim]Skipped {len(skipped)} already checked out[/dim]"
        
        def do_checkout(confirmed: bool) -> None:
            if not confirmed:
                return
            results = []
            for pr in eligible:
                ok, message = checkout_pr_to_worktree(pr, self.scan_dir)
                results.append((f"{pr.repo_name} #{pr.number}", ok, message))
            self.push_screen(ResultsModal("Checkout Results", results))
            # Refresh both tabs since repos changed
            self.refresh_repos()
            self.all_prs.clear()  # Force PR refresh
        
        self.push_screen(ConfirmModal("Checkout PRs", msg), do_checkout)

    def action_open_pr_browser(self) -> None:
        """Open selected PRs in browser."""
        if self._filter_has_focus():
            return
        if self.active_tab != "prs":
            return
        
        selected = self.get_selected_prs()
        if not selected:
            self.notify("No PRs selected", severity="warning")
            return
        
        results = []
        for pr in selected:
            ok, msg = open_in_browser(pr.url)
            results.append((f"{pr.repo_name} #{pr.number}", ok, msg))
        
        if len(selected) == 1:
            if results[0][1]:
                self.notify(f"Opened PR #{selected[0].number} in browser", severity="information")
            else:
                self.notify(f"Failed to open: {results[0][2]}", severity="error")
        else:
            self.push_screen(ResultsModal("Open in Browser Results", results))

    def action_close_pr(self) -> None:
        """Close selected PRs."""
        if self._filter_has_focus():
            return
        if self.active_tab != "prs":
            return
        
        selected = self.get_selected_prs()
        if not selected:
            self.notify("No PRs selected", severity="warning")
            return
        
        # Build confirmation message
        pr_list = "\n".join(f"  • {pr.repo_name} #{pr.number}: {pr.title[:50]}" for pr in selected)
        msg = f"Close {len(selected)} PR(s)?\n\n{pr_list}"
        
        def do_close(confirmed: bool) -> None:
            if not confirmed:
                return
            
            results = []
            for pr in selected:
                ok, message = close_pr(pr.repo_full_name, pr.number)
                results.append((f"{pr.repo_name} #{pr.number}", ok, message))
            
            if len(selected) == 1:
                if results[0][1]:
                    self.notify(f"Closed PR #{selected[0].number}", severity="information")
                else:
                    self.notify(f"Failed: {results[0][2]}", severity="error")
            else:
                self.push_screen(ResultsModal("Close PR Results", results))
            
            # Clear selection and refresh PRs
            self.selected_prs.clear()
            self.all_prs.clear()  # Force PR refresh on next view
            self.refresh_prs()
        
        self.push_screen(ConfirmModal("Close PRs", msg), do_close)


def main():
    scan_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    scan_dir = scan_dir.resolve()
    app = GitStatusApp(scan_dir)
    app.run()
    
    if app.pending_ai_launch:
        cli_id, working_dir = app.pending_ai_launch
        cmd = get_ai_cli_command(cli_id)
        print(f"\n🚀 Launching {cli_id} in {working_dir}...\n")
        os.chdir(working_dir)
        os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()
