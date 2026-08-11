#!/usr/bin/env python3
"""Create branches for an issue and update aiobmsble references.

Usage: scripts/create_issue_branch.py ISSUE_NUMBER

Requires: python3 -c "import keyring; keyring.set_password('github', 'my_pat', 'ghp_yourtokenhere')"
"""
import json
import logging
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any

import keyring
import requests

GITHUB_API: str = "https://api.github.com"
LOG: logging.Logger = logging.getLogger(__name__)
GIT_BIN: str = shutil.which("git") or "git"
PERMISSION_DENIED: int = 403


def getenv(name: str) -> str:
    """Return environment variable or exit with error.

    Raises SystemExit when variable is not set.
    """
    value = os.getenv(name)
    if not value:
        LOG.error("Environment variable %s is required", name)
        raise SystemExit(1)
    return value


def sanitize_title(title: str, maxlen: int = 50) -> str:
    """Return a URL/branch-safe lowercase slug of the title."""
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rstrip("-")
    return s


def gh_request(
    token: str,
    method: str,
    path: str,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Perform a GitHub API request and return parsed JSON as dict."""
    url = GITHUB_API + path
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.request(method, url, headers=headers, json=json_data, timeout=30)
    if not resp.ok:
        LOG.debug("GitHub response: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()
    return dict(resp.json())


def get_branch_sha(token: str, owner: str, repo: str, branch: str = "main") -> str:
    """Return commit SHA for given branch on remote repository."""
    data = gh_request(token, "GET", f"/repos/{owner}/{repo}/git/refs/heads/{branch}")
    return str(data["object"]["sha"])


def create_branch(
    token: str,
    owner: str,
    repo: str,
    branch_name: str,
    sha: str,
) -> None:
    """Create a branch ref in the remote repo using the GitHub API.

    Non-fatal if branch already exists.
    """
    ref = f"/repos/{owner}/{repo}/git/refs"
    payload: dict[str, str] = {"ref": f"refs/heads/{branch_name}", "sha": sha}
    try:
        gh_request(token, "POST", ref, json_data=payload)
        LOG.info("Created branch %s/%s@%s", owner, repo, branch_name)
    except requests.HTTPError as exc:  # pragma: no cover - network error
        if exc.response is not None and exc.response.status_code in {422, 409}:
            LOG.info("Branch %s already exists in %s/%s", branch_name, owner, repo)
        else:
            LOG.exception(
                "Failed creating branch %s in %s/%s",
                branch_name,
                owner,
                repo,
            )
            raise


def post_issue_comment(
    token: str,
    owner: str,
    repo: str,
    issue_number: str,
    body: str,
) -> bool:
    """Post a comment on the issue.

    Return True on success, False on failure.
    """
    path = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"

    try:
        gh_request(token, "POST", path, json_data={"body": body})
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == PERMISSION_DENIED:
            LOG.warning("Insufficient token scope to post issue comment (403)")
            return False

        LOG.exception("Failed posting issue comment for %s", issue_number)
        return False
    else:
        LOG.info("Posted comment to issue %s", issue_number)
        return True


def replace_requirements(branch_name: str) -> bool:
    """Replace aiobmsble branch reference in `requirements.txt`.

    Returns True when a change was written.
    """
    req_path = Path.cwd() / "requirements.txt"
    text = req_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changed = False
    pattern = re.compile(
        r"^\s*aiobmsble(?:\s*(?:==|~=|>=|<=|!=|>|<)[^\s#]+)?(?:\s*#.*)?$",
    )
    new_lines: list[str] = []

    for line in lines:
        if pattern.match(line):
            comment = ""
            if "#" in line:
                _, _, comment_text = line.partition("#")
                comment = f" #{comment_text.rstrip()}" if comment_text else ""
            new_line = (
                f"aiobmsble @ git+https://github.com/patman15/aiobmsble.git@{branch_name}"
                + comment
            )
            if line.endswith("\n"):
                new_line += "\n"
            new_lines.append(new_line)
            changed = True
        else:
            new_lines.append(line)

    if not changed:
        LOG.warning("No aiobmsble reference updated in requirements.txt")
        return False

    req_path.write_text("".join(new_lines), encoding="utf-8")
    LOG.info("Updated requirements.txt to use branch %s", branch_name)
    return True


def replace_manifest(branch_name: str) -> bool:
    """Update `custom_components/bms_ble/manifest.json` aiobmsble reference.

    Returns True when a change was written.
    """
    manifest_path = Path.cwd() / "custom_components" / "bms_ble" / "manifest.json"
    try:
        data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        LOG.error(
            "Failed to parse %s: %s at line %s column %s",
            manifest_path,
            exc.msg,
            exc.lineno,
            exc.colno,
        )
        raise

    changed = False
    pattern = re.compile(
        r"^aiobmsble(?:\s*(?:==|~=|>=|<=|!=|>|<)[^\s]+)?|^aiobmsble\s*@\s*git\+https://github.com/patman15/aiobmsble.git@.+$",
    )

    def fix_entry(entry: str) -> str:
        if pattern.match(entry.strip()):
            return f"aiobmsble @ git+https://github.com/patman15/aiobmsble.git@{branch_name}"
        return entry

    reqs = data.get("requirements")
    if isinstance(reqs, list):
        new_reqs: list[str] = [fix_entry(str(x)) for x in reqs]
        if new_reqs != reqs:
            data["requirements"] = new_reqs
            changed = True
    elif isinstance(reqs, str):
        new_req = fix_entry(reqs)
        if new_req != reqs:
            data["requirements"] = new_req
            changed = True

    if changed:
        dump = json.dumps(data, indent=2, ensure_ascii=False)
        manifest_path.write_text(dump, encoding="utf-8")
        LOG.info("Updated manifest.json to use branch %s", branch_name)
        return True

    LOG.warning("No aiobmsble reference updated in manifest.json")
    return False


def git_has_uncommitted_changes() -> bool:
    """Return True when the repository has uncommitted changes."""
    cp = subprocess.run(
        [GIT_BIN, "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(cp.stdout.strip())


def run_git_args(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the CompletedProcess."""
    # replace 'git' with resolved GIT_BIN for safety
    if args and args[0] == "git":
        args = [GIT_BIN, *args[1:]]
    LOG.debug("Running git: %s", " ".join(shlex.quote(a) for a in args))
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=check,
    )


def branch_exists_locally(branch_name: str) -> bool:
    """Return True when a local branch exists."""
    cp = run_git_args(["git", "branch", "--list", branch_name], check=True)
    return bool(cp.stdout.strip())


def create_local_branch(branch_name: str) -> None:
    """Create or checkout a local branch from updated main."""
    stashed = False
    if git_has_uncommitted_changes():
        LOG.info("Stashing local changes")
        stash_msg = f"auto-stash for {branch_name}"
        run_git_args([
            "git",
            "stash",
            "push",
            "-u",
            "-m",
            stash_msg,
        ], check=True)
        stashed = True

    run_git_args(["git", "fetch", "origin"], check=True)
    run_git_args(["git", "checkout", "main"], check=True)
    run_git_args(["git", "pull", "origin", "main"], check=True)

    if branch_exists_locally(branch_name):
        run_git_args(["git", "checkout", branch_name], check=True)
        LOG.info("Checked out existing local branch %s", branch_name)
    else:
        run_git_args(["git", "checkout", "-b", branch_name], check=True)
        LOG.info("Created local branch %s", branch_name)

    if stashed:
        res = run_git_args(["git", "stash", "pop"], check=False)
        if res.returncode != 0:
            LOG.error("Conflict applying stash after creating branch; resolve manually")
            raise SystemExit(1)


def commit_and_push_branch(
    branch_name: str,
    commit_message: str,
    paths: list[str],
) -> None:
    """Commit staged changes on the current branch and push to origin."""
    run_git_args(["git", "add", *paths], check=True)
    run_git_args(["git", "commit", "-m", commit_message], check=True)
    run_git_args(["git", "push", "-u", "origin", branch_name], check=True)
    LOG.info("Pushed branch %s to origin", branch_name)



def main(argv: list[str] | None = None) -> None:
    """Run the main entry point.

    argv: list of CLI args without program name.
    """
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) < 1:
        LOG.error("Usage: create_issue_branch.py ISSUE_NUMBER")
        raise SystemExit(1)
    issue = str(argv[0])
    token: str | None = keyring.get_password("github", "bms_ble_pat")
    owner = "patman15"
    repo = "BMS_BLE-HA"
    aiobmsble_repo = "aiobmsble"

    if not token:
        LOG.error("GitHub token not found in keyring; please set it with keyring")
        raise SystemExit(1)

    issue_data = gh_request(token, "GET", f"/repos/{owner}/{repo}/issues/{issue}")
    title = str(issue_data.get("title", f"issue-{issue}"))
    sanitized = sanitize_title(title)
    branch_name = f"issue-{issue}-{sanitized}"
    short_sanitized = sanitize_title(title, maxlen=24)
    aiobranch = f"issue-{issue}-{short_sanitized}"

    LOG.info("Creating local branch %s", branch_name)
    create_local_branch(branch_name)

    LOG.info("Creating branch %s in %s/%s", owner, repo, branch_name)
    sha = get_branch_sha(token, owner, repo, branch="main")
    try:
        create_branch(token, owner, repo, branch_name, sha)
    except requests.RequestException:
        LOG.warning("Could not create branch in main repo; it may already exist")

    LOG.info("Creating branch %s in %s/%s", aiobranch, owner, aiobmsble_repo)
    try:
        ash = get_branch_sha(token, owner, aiobmsble_repo, branch="main")
        create_branch(token, owner, aiobmsble_repo, aiobranch, ash)
    except requests.RequestException:
        LOG.warning("Could not create branch in aiobmsble repo; it may already exist")

    changed_req = replace_requirements(aiobranch)
    changed_manifest = replace_manifest(aiobranch)

    if not (changed_req or changed_manifest):
        LOG.error("No changes made to requirements or manifest; aborting")
        raise SystemExit(1)

    commit_message = (
        f"Update aiobmsble reference to {owner}/{aiobmsble_repo}@{aiobranch} "
        f"for issue #{issue}"
    )
    paths = [
        "requirements.txt",
        str(Path("custom_components") / "bms_ble" / "manifest.json"),
    ]
    commit_and_push_branch(branch_name, commit_message, paths)

    body = (
        f"Created branch `{branch_name}` in `{owner}/{repo}` and "
        f"`{owner}/{aiobmsble_repo}` branch `{aiobranch}`. "
        "Updated `requirements.txt` and `custom_components/bms_ble/manifest.json`."
    )
    if not post_issue_comment(token, owner, repo, issue, body):
        LOG.warning("Could not post issue comment; consider updating token scopes")

    LOG.info("Done.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
