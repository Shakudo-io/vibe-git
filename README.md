<p align="center">
  <img src="logo.png" alt="vibe-git logo" width="200">
</p>

# vibe-git

> *This TUI app was vibe coded on a [Shakudo](https://www.shakudo.io) development session using [OpenCode](https://github.com/opencode-ai/opencode) and [Oh-My-OpenCode](https://github.com/code-yeongyu/oh-my-opencode).*

A powerful terminal UI (TUI) for managing multiple Git repositories and GitHub Pull Requests simultaneously.

<table>
<tr>
<td width="50%" align="center">
<strong>Repositories Tab</strong><br>
<img src="demo-repos.gif" alt="Repositories tab demo" width="100%">
</td>
<td width="50%" align="center">
<strong>Pull Requests Tab</strong><br>
<img src="demo-prs.gif" alt="PRs tab demo" width="100%">
</td>
</tr>
</table>

## Installation

<details>
<summary><strong>For Humans</strong> (step-by-step guide)</summary>

### Prerequisites

- **Python 3.11+**
- **Git** installed and configured
- **GitHub CLI (`gh`)** - required for PR features

### Step 1: Install GitHub CLI (for PR features)

```bash
# macOS
brew install gh

# Ubuntu/Debian
sudo apt install gh

# Then authenticate
gh auth login
```

### Step 2: Clone and Run

```bash
# Clone the repo
git clone https://github.com/Shakudo-io/vibe-git.git
cd vibe-git

# Run with uv (recommended - auto-installs dependencies)
./vibe-git.py ~/your-projects-folder

# Or install dependencies manually and run
pip install textual
python vibe-git.py ~/your-projects-folder
```

### Step 3: Create an alias (optional)

```bash
# Add to your ~/.bashrc or ~/.zshrc
alias vibe='python /path/to/vibe-git.py'

# Then use anywhere
vibe ~/projects
```

</details>

<details open>
<summary><strong>For AI Agents</strong> (copy-paste ready)</summary>

```bash
# One-liner: clone and run
git clone https://github.com/Shakudo-io/vibe-git.git /tmp/vibe-git && uv run /tmp/vibe-git/vibe-git.py .

# Or if already cloned, just run:
uv run vibe-git.py /path/to/scan

# Requires: git, gh (GitHub CLI authenticated), Python 3.11+
# The script uses inline dependencies (PEP 723) - uv handles everything automatically
```

</details>

---

## Why vibe-git?

**Built for the age of AI-assisted development.**

When you're vibe coding with tools like [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview), [OpenCode](https://github.com/opencode-ai/opencode), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [Codex](https://openai.com/index/openai-codex/), or similar AI coding assistants, you often end up with multiple workstreams across different repositories and branches. Each AI session might be working on a different feature, bug fix, or experiment.

**The problem**: Keeping track of all these parallel workstreams becomes chaotic. Which branches have uncommitted changes? Which PRs are open? What needs to be pushed? What's out of sync with remote?

**vibe-git solves this** by giving you a single dashboard to:
- See the status of all your local repositories at a glance
- View all your open GitHub PRs across all repos
- Perform bulk git operations (pull, push, rebase, stash, discard)
- Checkout PRs directly to worktrees for isolated development
- Manage your git workflow without leaving the terminal

## Features

### Repository Management Tab

View and manage all Git repositories in a directory:

| Feature | Description |
|---------|-------------|
| **Status Overview** | See branch, sync status, and changes for every repo |
| **Bulk Operations** | Select multiple repos and perform actions on all at once |
| **Smart Sync Detection** | Shows if repos are ahead, behind, diverged, or in sync |
| **Worktree Support** | Detects and displays Git worktrees alongside main repos |
| **Filter/Search** | Quickly filter repos by name |

**Repository Status Indicators:**
- `Clean` - No uncommitted changes
- `Modified` - Has uncommitted changes  
- `Ahead` / `Behind` / `Diverged` - Sync status with remote
- `Local only` - No remote tracking branch
- `Needs rebase` - Behind main branch

**Keyboard Shortcuts (Repositories Tab):**

| Key | Action |
|-----|--------|
| `p` | Pull from remote |
| `r` | Rebase/Sync with main branch |
| `f` | Force push to remote |
| `c` | Create remote branch |
| `s` | Stash changes |
| `d` | Discard changes |
| `X` | Reset to remote (hard reset) |
| `D` | Delete local folder |
| `w` | Create [Speckit](https://github.com/github/spec-kit) feature (auto-numbered) |

### GitHub PRs Tab

View and manage all your open Pull Requests across all repositories:

| Feature | Description |
|---------|-------------|
| **Cross-Repo PR View** | See all your open PRs in one place |
| **Local Status Detection** | Shows if PR branch is checked out locally |
| **One-Click Checkout** | Checkout any PR to a worktree instantly |
| **Bulk Close** | Close multiple stale PRs at once |
| **Browser Integration** | Open PRs in browser with one key |

**PR Status Indicators:**
- `Checked out` - Branch is currently checked out locally
- `Available` - Repo exists locally, can create worktree
- `Not cloned` - Repo not present locally (will clone on checkout)

**Keyboard Shortcuts (PRs Tab):**

| Key | Action |
|-----|--------|
| `o` | Checkout PR to worktree |
| `b` | Open PR in browser |
| `C` | Close PR(s) |

### Global Shortcuts

| Key | Action |
|-----|--------|
| `Tab` | Switch between Repositories and PRs tabs |
| `Space` | Toggle selection on current row |
| `a` | Select all visible items |
| `/` | Start filtering/searching |
| `Escape` | Clear filter or selection |
| `R` | Refresh data |
| `?` | Show help |
| `q` | Quit (double-tap to confirm) |

## Usage

### Basic Usage

```bash
# Run in current directory
python vibe-git.py

# Run in specific directory
python vibe-git.py ~/projects

# Run from anywhere with alias
alias vibe='python /path/to/vibe-git.py'
vibe ~/code
```

### Typical Workflow

1. **Start vibe-git** in your projects directory
2. **Review status** of all repos on the Repositories tab
3. **Select repos** that need action (Space to select, `a` for all)
4. **Perform bulk operations** (pull, push, rebase, etc.)
5. **Switch to PRs tab** (Tab key) to see open pull requests
6. **Checkout PRs** you want to work on (`o` key)
7. **Close stale PRs** you no longer need (`C` key)

### Worktree Workflow

vibe-git creates worktrees with a flat naming convention for easy management:

```
~/projects/
├── myrepo/                    # Main repo (on main branch)
├── myrepo-feat-new-feature/   # Worktree for feature branch
├── myrepo-fix-bug-123/        # Worktree for bugfix branch
└── myrepo-experiment-ai/      # Worktree for experiment
```

This keeps all your workstreams visible and accessible without nested folder structures.

### Speckit Integration

vibe-git integrates with [Speckit](https://github.com/github/spec-kit) (GitHub's Specification-Driven Development toolkit) to streamline AI-assisted feature development.

**Why Speckit?** When working with AI coding agents, having a structured specification workflow ensures:
- Consistent feature organization across parallel workstreams
- Clear separation between spec → plan → tasks → implementation phases
- Auto-numbered branches prevent naming conflicts

**How it works:** Press `w` on any repo to create a Speckit-compliant feature:

1. **Enter a feature description** (e.g., "User authentication with OAuth")
2. **vibe-git automatically:**
   - Detects the next available feature number (scans branches + specs)
   - Generates a semantic branch name: `001-user-authentication-oauth`
   - Creates a worktree: `myrepo-001-user-authentication-oauth/`
   - Sets up the spec structure: `specs/001-user-authentication-oauth/spec.md`
   - Copies `.specify/` templates if they exist

**Result:**
```
myrepo-001-user-authentication-oauth/
├── .specify/                           # Templates (if present in source)
│   └── templates/
└── specs/
    └── 001-user-authentication-oauth/
        └── spec.md                     # Ready for /speckit.specify
```

Then in your AI agent session:
```bash
cd myrepo-001-user-authentication-oauth
/speckit.specify   # Refine the spec
/speckit.plan      # Generate implementation plan
/speckit.tasks     # Break down into tasks
/speckit.implement # Execute the plan
```

**Branch naming:** Feature descriptions are converted to branch names by:
- Extracting meaningful words (filtering stop words like "the", "a", "with")
- Keeping 2-4 significant words
- Joining with dashes: `"Build dashboard for analytics"` → `002-dashboard-analytics`

## Architecture

<p align="center">
  <img src="architecture.png" alt="vibe-git architecture" width="700">
</p>

**vibe-git** is built with:
- **[Textual](https://textual.textualize.io/)** - Modern Python TUI framework
- **Git CLI** - For all repository operations (pull, push, rebase, stash, etc.)
- **GitHub CLI (`gh`)** - For PR management and authentication
- **File System Scanner** - Discovers `.git` folders recursively in your project directory

## Tips for AI-Assisted Development

### Managing Multiple AI Sessions

When using multiple AI coding sessions in parallel:

1. **Use worktrees** - Each AI session can work in its own worktree
2. **Name branches descriptively** - e.g., `feat/claude-auth-system`, `fix/copilot-perf-issue`
3. **Check vibe-git frequently** - See which sessions have made progress
4. **Bulk operations** - Pull all repos before starting new sessions

### Recommended Directory Structure

```
~/ai-projects/
├── project-a/                 # Main branch
├── project-a-claude-feature/  # Claude Code working on feature
├── project-a-copilot-tests/   # Copilot writing tests
├── project-b/                 # Another project
└── project-b-codex-refactor/  # Codex refactoring
```

Run `vibe-git ~/ai-projects` to see everything at once.

## Troubleshooting

### "gh: command not found"

Install the GitHub CLI:
```bash
# macOS
brew install gh

# Ubuntu/Debian  
sudo apt install gh

# Then authenticate
gh auth login
```

### PRs not showing up

1. Ensure you're authenticated: `gh auth status`
2. PRs are fetched for the authenticated user only
3. Only open PRs are shown

### Worktree creation fails

Common causes:
- Branch already checked out elsewhere
- Branch name conflicts
- Insufficient permissions

Check the error message in the results modal for details.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

MIT License - see [LICENSE](LICENSE) file.

## Credits

Developed at [Shakudo](https://www.shakudo.io) - the platform for deploying and managing AI/ML infrastructure.

---

**Happy vibe coding!**
