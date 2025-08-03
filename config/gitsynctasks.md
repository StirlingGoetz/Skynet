# Agent Zero Task Re-Creation Prompt: Skynet Git Sync Automation

Objective
Recreate two tasks inside a fresh Agent Zero container to keep GitHub in sync with /a0 and to enable disaster recovery.

Context and assumptions
- Working directory for git checkout must be inside the container: /root/work_Skynet
- GitHub repository: https://github.com/StirlingGoetz/Skynet.git
- Authentication: Use HTTPS credential store at /root/.git-credentials with:
  https://StirlingGoetz:YOUR_GITHUB_PAT@github.com
  Then configure: git config --global credential.helper 'store --file /root/.git-credentials'
- Default branch should be detected from origin/HEAD; fallback to main.
- Non-destructive policy: Do NOT delete repository contents during routine sync; only update paths we mirror from /a0.
- Directories to mirror routinely: /a0/config → repo/config, /a0/juiceshop → repo/juiceshop (recursive).

Instructions to Agent Zero
1) Ensure credentials
- Create /root/.git-credentials containing the GitHub handle and current Personal Access Token (PAT):
  https://StirlingGoetz:YOUR_GITHUB_PAT@github.com
- Run: git config --global credential.helper 'store --file /root/.git-credentials'

2) Create the scheduled task (every 15 minutes): “Sync /a0 → GitHub (non-destructive dir sync) - Skynet”
System prompt:
You are an automation agent running inside a Kali Linux container with root access. Use bash and git to synchronize directories.

Task prompt:
Execute a non-destructive directory sync pushing updates from /a0 to the GitHub repo StirlingGoetz/Skynet.

Requirements:
- Working directory: /root/work_Skynet (do not create a git repo in /a0)
- Auth: Use HTTPS credentials stored at /root/.git-credentials. Ensure: git config --global credential.helper 'store --file /root/.git-credentials'
- Repo URL: https://github.com/StirlingGoetz/Skynet.git
- Default branch: detect origin/HEAD; fallback to main
- Non-destructive: Do NOT delete repo contents. Only copy/update the specified directories from /a0 into the repo working tree.

Directories to sync each run:
- /a0/config → repo/config (recursive)
- /a0/juiceshop → repo/juiceshop (recursive)

Steps each run:
1) Ensure credential helper points to /root/.git-credentials
2) If /root/work_Skynet is not a git repo, clone the repo there; otherwise fetch and pull default branch
3) Checkout default branch
4) Create target directories as needed and recursively copy from /a0/config to config and /a0/juiceshop to juiceshop (preserve structure). Skip if source dir missing.
5) Stage only the changed files (git add config juiceshop); if there are changes, commit with message "Automated sync: update directories from /a0" and push
6) Exit 0 if no changes

Reference script:
set -euo pipefail
REPO_URL="https://github.com/StirlingGoetz/Skynet.git"
WORKDIR="/root/work_Skynet"
mkdir -p /root
if ! git config --global credential.helper | grep -q '/root/.git-credentials'; then
  git config --global credential.helper 'store --file /root/.git-credentials'
fi
if [ ! -d "$WORKDIR/.git" ]; then
  rm -rf "$WORKDIR" && mkdir -p "$WORKDIR"
  GIT_TERMINAL_PROMPT=0 git clone "$REPO_URL" "$WORKDIR"
fi
cd "$WORKDIR"
DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@' || true)
[ -n "$DEFAULT_BRANCH" ] || DEFAULT_BRANCH="main"
GIT_TERMINAL_PROMPT=0 git checkout "$DEFAULT_BRANCH" || git checkout -b "$DEFAULT_BRANCH"
GIT_TERMINAL_PROMPT=0 git pull origin "$DEFAULT_BRANCH" --rebase || true
# Non-destructive recursive copy from /a0 to repo
if [ -d "/a0/config" ]; then mkdir -p config && cp -a /a0/config/. config/; fi
if [ -d "/a0/juiceshop" ]; then mkdir -p juiceshop && cp -a /a0/juiceshop/. juiceshop/; fi
# Stage and commit if changed
git add config juiceshop || true
if ! git diff --cached --quiet; then
  git config user.name >/dev/null 2>&1 || git config user.name "Agent Zero"
  git config user.email >/dev/null 2>&1 || git config user.email "StirlingGoetz@users.noreply.github.com"
  git commit -m "Automated sync: update directories from /a0"
  GIT_TERMINAL_PROMPT=0 git push origin "$DEFAULT_BRANCH"
fi
exit 0

Schedule:
- Cron: */15 * * * *
- dedicated_context: true

3) Create the adhoc task: “Recover /a0 from GitHub (full directories, on demand) - Skynet”
System prompt:
You are an automation agent running inside a Kali Linux container with root access. Use bash and git to restore directories from GitHub to /a0.

Task prompt:
Restore directories from the GitHub repo StirlingGoetz/Skynet into /a0 (non-destructive overwrite), on demand.

Requirements:
- Working directory: /root/work_Skynet
- Auth: Use HTTPS credentials stored at /root/.git-credentials
- Repo URL: https://github.com/StirlingGoetz/Skynet.git
- Default branch: detect origin/HEAD; fallback to main
- Non-destructive: Do not delete anything under /a0. Only overwrite files present in the repo under the target directories.

Directories to restore:
- repo/config → /a0/config (recursive)
- repo/juiceshop → /a0/juiceshop (recursive)

Reference script:
set -euo pipefail
REPO_URL="https://github.com/StirlingGoetz/Skynet.git"
WORKDIR="/root/work_Skynet"
mkdir -p /root
if ! git config --global credential.helper | grep -q '/root/.git-credentials'; then
  git config --global credential.helper 'store --file /root/.git-credentials'
fi
if [ ! -d "$WORKDIR/.git" ]; then
  rm -rf "$WORKDIR" && mkdir -p "$WORKDIR"
  GIT_TERMINAL_PROMPT=0 git clone "$REPO_URL" "$WORKDIR"
fi
cd "$WORKDIR"
DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@' || true)
[ -n "$DEFAULT_BRANCH" ] || DEFAULT_BRANCH="main"
GIT_TERMINAL_PROMPT=0 git checkout "$DEFAULT_BRANCH" || git checkout -b "$DEFAULT_BRANCH"
GIT_TERMINAL_PROMPT=0 git pull origin "$DEFAULT_BRANCH" --rebase || true
# Restore directories non-destructively
mkdir -p /a0/config /a0/juiceshop
if [ -d "config" ]; then cp -a config/. /a0/config/; else echo "Warning: repo missing config/"; fi
if [ -d "juiceshop" ]; then cp -a juiceshop/. /a0/juiceshop/; else echo "Warning: repo missing juiceshop/"; fi
exit 0

Notes
- Replace YOUR_GITHUB_PAT with a valid PAT before creation.
- If you rotate the PAT, update /root/.git-credentials accordingly.
- The scheduled task is non-destructive and only mirrors the specified directories.
- The recovery task is adhoc and restores from GitHub into /a0 non-destructively.
