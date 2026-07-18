# luma-outages

Scrapes LUMA (Puerto Rico power utility) outage data hourly and pushes JSON
snapshots to a **separate** repo, `rubenvarela/luma-outages-data`. This repo
is code only - it never accumulates the scraped data itself (aside from the
local, gitignored disk output any run produces).

## Two independent collectors, same codebase

The same `main.py` runs in two places, on purpose, for redundancy:

- A home server (Synology NAS, x86_64), via DSM Task Scheduler running
  `bash /var/services/homes/zenva/luma-outages/run.bash`.
- This repo's GitHub Actions workflow, `cron: '36 * * * *'` (deliberately
  offset from the server's ~:00 schedule).

Both must run the exact same code from this repo - not drifted local copies.
That drift is literally why this whole setup needed fixing once: the server
had accumulated local `if True:` patches bypassing dead env-var checks,
never synced back here. `run.bash` lives in this repo specifically so
deploying is "clone this repo + `uv` installed + a local `env` file" -
nothing else should ever need unversioned, server-only patching again.

**Checking the server side is actually running**: the data repo's commit
history alone can't tell you which collector produced a given commit (both
write identically-formatted messages). Check DSM's Task Scheduler "View
Result" for this task (captures stdout/stderr per run), and/or the
freshness of the most recent file under the server's local
`{year}/{month}/{day}/` output directory.

## Dedup logic - deliberate tradeoffs, don't "fix" without discussing first

`_should_write` in `main.py` skips the GitHub push only when both towns and
clients data are unchanged from the last snapshot *and* the current hour
already has an entry for both. Otherwise it writes both together. This
guarantees: at least one entry per hour even when nothing changed, immediate
capture of a real mid-hour change, and full coverage if one collector dies
(the survivor sees no entry for the hour and writes anyway).

Two things that look like bugs but are accepted tradeoffs:

- **Towns/clients are always written as a matched pair**, never
  independently - even though this means a rare partial-write failure (one
  `create_file` succeeds, the next fails) causes an unnecessary duplicate
  write on the next same-hour run. Decoupling the writes would eliminate
  that duplicate but reintroduce mismatched timestamps between the two
  files, which was an explicit requirement. Keep the pairing.
- **No locking between the two collectors.** GitHub documents that
  scheduled runs can be delayed, which could in theory let both collectors
  decide "no entry yet" and both write. Accepted as low-probability, not
  solved with real locking.

Also known and still open, lower priority: in the common "nothing changed"
case, `_check_type` still does 2 separate `get_contents` calls (one per
type) for the same directory instead of fetching once and splitting
locally.

## Disk write vs. GitHub push

Disk write is unconditional - happens every run, everywhere, including on
GitHub Actions' ephemeral runner (harmless; discarded when the runner is
destroyed). Pushing to GitHub is gated purely on `ghtoken` being present in
the environment - there's no separate on/off flag. `load_dotenv('env')`
fills in `ghtoken` from a local `env` file if it isn't already set (e.g. by
GitHub Actions, which sets it directly via `secrets.GHTOKEN`).

`env.example`'s placeholder (`ghtoken="GITHUB TOKEN"`) is a non-empty
string, so an unedited copy will attempt to authenticate with that literal
value and crash loudly rather than silently no-op. Known, accepted.

**Two different tokens are in play** - easy to conflate: `ghtoken` /
`secrets.GHTOKEN` is used by `main.py` to push to `luma-outages-data`. The
workflow's separate "Record heartbeat" step pushes to *this* repo using
GitHub Actions' own default `GITHUB_TOKEN`, unrelated to `GHTOKEN`.

## The heartbeat step

The workflow commits a timestamp to `status/last-run.txt` in this repo on
every run (`if: always()`). This is not incidental - GitHub auto-disables
scheduled workflows after 60 days with no activity in the *host* repo, and
since this workflow's actual writes go to a different repo, this one would
otherwise look inactive and get disabled (which is exactly what had
happened before this existed). Don't remove it as "dead code."

## Dependencies and Python version

`uv` + `pyproject.toml` + `uv.lock` + `.python-version` (pinned to 3.14),
not `requirements.txt`. Deliberately migrated for exact dependency pinning,
since this script runs unattended for potentially years at a stretch - a
bad transitive dependency update shouldn't be able to silently break it.

## Testing

No committed test suite exists (no `tests/` directory, no CI test step).
The dedup logic was validated with an ad hoc offline harness (an in-memory
fake GitHub repo, no network) covering ~12 scenarios, but that harness was
never added to this repo. Before trusting a change to the dedup logic:
test offline against a fake repo first, then read-only against the live
`luma-outages-data` repo (safe, unauthenticated - it's public), then push
and verify with a real `workflow_dispatch` run plus checking
`luma-outages-data`'s actual commit history. A green checkmark on the
workflow run doesn't prove the write happened or that dedup decided
correctly - only checking the downstream repo does.
