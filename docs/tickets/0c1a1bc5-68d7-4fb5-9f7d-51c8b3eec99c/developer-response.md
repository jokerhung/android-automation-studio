# Ticket #2 - Response to system test feedback

Date: 2026-10-28

## Status and root cause

**Acceptance remains blocked.** The latest check confirms the tester's revised
findings: both root installers and the new helpers still return HTTP 404, so
installation fails before any installer code executes. ZIP and tar.gz branch
archives now return HTTP 200 to HEAD requests. The previous all-404 observation
is historical and does not describe the current public revision.

The published `tray_controller.py` and `daemon_client.py` return HTTP 200 but
differ from this checkout. The selected configuration, dependency manifests and
lock files return HTTP 200 and match. The release checker still exits **4**.
The current problem is an incomplete public implementation, not an unavailable
branch archive.

A 404 does not distinguish a missing repository, branch or file from a repository
that cannot be read anonymously. There is no evidence supporting substitution of
another repository or branch. Local code changes cannot publish those resources.
No commit, push, merge, reset or repository access change was performed.

No additional runtime code change is justified by this feedback: changing a
local installer cannot fix a remote 404 that prevents that installer being
downloaded. Publication remains a separate release step under the ticket plan.

## Follow-up to the revised tester report

- Reread the ticket requirements, design, implementation plan and system cases.
- Reran the existing release checker with `--timeout 10`; confirmed the exact
  missing/mismatched/matching resource groups above and exit code 4.
- Corrected the current release status in `README.md`, `docs/installation.md`
  and this response. No new code or tests were added in this follow-up; the
  checks below describe the previous implementation round.
- Kept the tester's report and its 2 PASS / 1 FAIL / 29 BLOCKED result unchanged.

## Changes for this feedback

- `scripts/check_installer_release.py`: read-only, anonymous download check;
  compares selected published text files with the checkout while tolerating
  CRLF/LF, checks both archive URLs with HEAD, and fails on missing/mismatched
  resources. It does not run installers or publish anything.
- `tests/unit/test_installer_release_check.py`: verifies 404 failure, helper
  mismatch, line ending tolerance, HEAD behavior, required resources and invalid
  repository arguments.
- `.github/workflows/installer.yml`: runs the new tests and offers a manual
  `verify_public` download gate after publication.
- `README.md`, `README_VI.md`, `docs/installation.md`: put the current publication
  blocker before Internet commands and describe the release check.
- This response records the actual outcome. The tester's system test report is
  unchanged.

## Verification performed for this feedback

| Check | Result |
| --- | --- |
| New release checker tests | 6 passed; one Google SDK deprecation warning |
| Ruff lint and format check for both new Python files | Passed |
| Anonymous release check, timeout 10 seconds | Failed as expected: HTTP 404, exit 4 |

These are developer checks, not a replacement for the tester's system evidence.
No new frontend or application runtime change was made for this feedback.

## Run and remaining acceptance work

From `C:\hungnm\artemis`, check publication with:

```powershell
.venv/Scripts/python.exe -B scripts/check_installer_release.py --timeout 10
```

For the current source checkout, start the existing application with:

```powershell
.\start.bat
```

This local checkout command does not verify Internet installation. See
`docs/installation.md` for installed-instance start/status/stop/restart commands,
public installation commands and local/LAN URL behavior.

The release owner must make the installers and complete source/helpers available
at the documented anonymous URLs from the same revision, then rerun the checker.
Only after the download gate passes can the public installation commands be
retested. A passing gate only verifies selected text downloads and archive HEAD
availability; it does not verify archive extraction, builds or installation.

Clean Windows 11/Ubuntu/macOS installations, second-device LAN access, reruns and
configuration preservation, error scenarios, and browsing without credentials or
an Android device still require the ticket's system tests. None is declared
passed here. The existing 2 PASS / 1 FAIL / 29 BLOCKED system result remains in
effect pending tester execution.
