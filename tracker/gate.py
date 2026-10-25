"""Decide whether this scheduled run should do the work.

GitHub's scheduler only knows UTC and can't express "every 3 days" across
month ends, so the workflow fires at 15:00 and 16:00 UTC every day and this
gate lets through only the first firing at or after 17:00 Bratislava time,
once at least RUN_EVERY_DAYS have passed since the last run.
Manual runs (the "Run workflow" button) always go through.

Writes run=true|false to $GITHUB_OUTPUT.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import config, store


def should_run(now: datetime, last_run: str | None, manual: bool) -> tuple[bool, str]:
    if manual:
        return True, "manual run"
    if now.hour < config.RUN_AT_HOUR:
        return False, f"too early ({now:%H:%M}, runs from {config.RUN_AT_HOUR}:00)"
    if last_run is None:
        return True, "no previous run"
    days = (now.date() - date.fromisoformat(last_run)).days
    if days < config.RUN_EVERY_DAYS:
        return False, f"last run {days} day(s) ago, runs every {config.RUN_EVERY_DAYS}"
    return True, f"last run {days} days ago"


def main():
    now = datetime.now(ZoneInfo("Europe/Bratislava"))
    runs = store.load()["runs"]
    ok, why = should_run(now, runs[-1]["date"] if runs else None,
                         os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch")
    print(f"{'RUN' if ok else 'SKIP'}: {why}")
    out = os.getenv("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"run={'true' if ok else 'false'}\n")


if __name__ == "__main__":
    main()
