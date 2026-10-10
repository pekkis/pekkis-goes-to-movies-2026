#!/usr/bin/env python3
"""Has this exact commit already passed the heavy Checks on a push to another branch?

    python3 scripts/ci_verified.py SHA CURRENT_RUN_ID

Run by ci.yml on a push to main, and only there. The delivery routine pushes a branch,
reads its Checks, then fast-forwards main to the same commit, so the suite, the drift
check and both browser engines ran on that exact tree minutes earlier. Those three test
the tip's tree and nothing else, so an identical SHA that passed them needs no second
run. The inline-JavaScript check and the design and CACHE gates are not decided here:
they read the push's own `before..after` range, commit by commit, and always run on main.

The answer is "skip" only on positive evidence, and "run everything" otherwise:

- the newest completed Checks run for this SHA from a push to a branch other than main,
  this run excluded, concluded success;
- no newer run for this SHA from such a push is failed, cancelled or still running;
- its `check`, `browser (chromium)` and `browser (webkit)` jobs each succeeded, and the
  unit-suite step and both browser-suite steps ran and succeeded rather than being
  skipped, so a run that itself skipped them never vouches for another.

A missing run, an unreadable answer or any error in the lookup is the full run. Writes
`skip=true|false` and `reason=...` to $GITHUB_OUTPUT when that is set, and prints both.
Exit 0 always: an answer it cannot give is "false", never a failed job.
"""
import json
import os
import sys
import urllib.request

WORKFLOW = ".github/workflows/ci.yml"
REQUIRED = {
    "check": "Unit suite",
    "browser (chromium)": "Browser suite",
    "browser (webkit)": "Browser suite",
}


def decide(runs, jobs_of, current_run_id):
    """-> (skip, reason). `runs` are the API's workflow runs for one SHA; `jobs_of(run)`
    returns that run's jobs. Pure apart from `jobs_of`, which may raise."""
    current = str(current_run_id)
    pushed = [r for r in runs
              if r.get("path") == WORKFLOW and r.get("event") == "push"
              and r.get("head_branch") not in (None, "", "main")
              and str(r.get("id")) != current]
    if not pushed:
        return False, "no Checks run for this commit from a branch push"
    pushed.sort(key=lambda r: (r.get("run_started_at") or r.get("created_at") or "",
                               r.get("id") or 0), reverse=True)
    newest = pushed[0]
    # A run still queued or in progress has no conclusion yet, so this refuses it too.
    if newest.get("conclusion") != "success":
        return False, (f"run {newest.get('id')} for this commit is {newest.get('status')}, "
                       f"concluded {newest.get('conclusion')}")
    jobs = {j.get("name"): j for j in jobs_of(newest)}
    for name, step_prefix in REQUIRED.items():
        job = jobs.get(name)
        if job is None or job.get("conclusion") != "success":
            return False, f"run {newest['id']} has no successful '{name}' job"
        steps = [s for s in job.get("steps") or []
                 if (s.get("name") or "").startswith(step_prefix)]
        if not steps or any(s.get("conclusion") != "success" for s in steps):
            return False, f"run {newest['id']}: '{name}' did not run '{step_prefix}'"
    return True, (f"run {newest['id']} on {newest['head_branch']} passed the suite, the "
                  f"drift check and both browser engines on this exact commit")


def _get(url, token):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "kino-ci-verified",
        "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"), strict=False)


def main(argv):
    sha, current = argv[1], argv[2]
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    try:
        if not (repo and token and len(sha) == 40):
            raise RuntimeError("no repository, token or full SHA to look up")
        runs = _get(f"{api}/repos/{repo}/actions/runs?head_sha={sha}&event=push"
                    f"&per_page=100", token).get("workflow_runs") or []
        skip, reason = decide(runs, lambda r: _get(r["jobs_url"] + "?per_page=100",
                                                   token).get("jobs") or [], current)
    except Exception as e:                    # the lookup failing is the full run
        skip, reason = False, f"lookup unavailable ({type(e).__name__}: {e})"
    print(f"skip={'true' if skip else 'false'}\nreason={reason}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"skip={'true' if skip else 'false'}\nreason={reason}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
