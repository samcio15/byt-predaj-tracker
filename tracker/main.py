"""One run: crawl -> prefilter -> detail -> evaluate -> history -> alert -> page.

Usage:
  python -m tracker.main                 # live run
  python -m tracker.main --offline DIR   # use saved HTML fixtures (testing)
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config, notify, render, store
from . import textparse as tp
from .evaluate import evaluate, rooms_of
from .fetch import Fetcher
from .sources import nehnutelnosti as source

log = logging.getLogger("tracker")
REMOVED_WINDOW_DAYS = 60


# --------------------------------------------------------------------------- #
# Prefilter: cheap checks on list cards before fetching detail pages
# --------------------------------------------------------------------------- #

def prefilter(card: dict) -> bool:
    if not source.district_of(card.get("location")) or tp.is_unavailable(card.get("title", "")):
        return False
    price = card.get("price")
    if price is not None and not config.PRICE_MIN <= price <= config.NEAR_MISS_MAX:
        return False
    area = card.get("area")
    if area is not None and area < config.MIN_AREA:
        return False
    return rooms_of(card) in config.ROOMS


# --------------------------------------------------------------------------- #
# Offline fetcher for tests / demo
# --------------------------------------------------------------------------- #

class FixtureFetcher:
    def __init__(self, folder: Path):
        self.f = folder

    def get(self, url, params=None):
        if "nehnutelnosti.sk/vysledky/3-izbove" in url and not (params or {}).get("page"):
            return (self.f / "sale_list.html").read_text(encoding="utf-8")
        if "nehnutelnosti.sk/detail/Juo9VPJPBNW" in url:
            return (self.f / "sale_detail.html").read_text(encoding="utf-8")
        return None


# --------------------------------------------------------------------------- #
# View model for page + alerts
# --------------------------------------------------------------------------- #

RANK = {"match": 0, "near": 1, "check": 2, "excluded": 3}


def build_rows(state: dict, today: str) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for r in state["listings"].values():
        groups.setdefault(r["group"], []).append(r)
    rows = []
    cutoff = (date.fromisoformat(today) - timedelta(days=REMOVED_WINDOW_DAYS)).isoformat()
    for gid, recs in groups.items():
        active = [r for r in recs if r.get("active")]
        if active:
            rep = min(active, key=lambda r: (RANK[r["eval"]["status"]], len(r["eval"]["unknown"])))
            section, end = rep["eval"]["status"], today
        else:
            rep = max(recs, key=lambda r: r.get("removed_on") or "")
            if (rep.get("removed_on") or "") < cutoff or rep["eval"]["status"] == "excluded":
                continue
            section, end = "removed", rep["removed_on"]
        e = rep["eval"]
        prices = [p for _, p in rep["price_history"] if p]
        rows.append({
            "section": section, "title": rep["title"], "group": gid,
            "district": e["district"], "rooms": e["rooms"], "area": e["area"], "price": e["price"],
            "ppm2": e["ppm2"], "floor": e["floor"], "balcony": e["balcony"], "cellar": e["cellar"],
            "condition": e["condition"], "flags": e["flags"], "unknown": e["unknown"],
            "excluded": e["excluded"], "history": rep["price_history"],
            "drop": (prices[0] - prices[-1]) if len(prices) > 1 else 0,
            "first_price": prices[0] if prices else None,
            "days": store.days_between(store.group_first_seen(state, gid), end),
            "links": [{"source": r["source"], "url": r["url"]}
                      for r in sorted(recs, key=lambda r: not r.get("active"))],
        })
    return rows


def diff_alerts(state: dict, rows: list[dict], today: str):
    notified = set(state.get("notified", []))
    new, new_check = [], 0
    for row in rows:
        gid = row["group"]
        if row["section"] in ("match", "near") and gid not in notified:
            new.append(row)
            notified.add(gid)
        elif row["section"] == "check" and gid + ":check" not in notified:
            new_check += 1
            notified.add(gid + ":check")
    drops = []
    for row in rows:
        h = row["history"]
        if (row["section"] in ("match", "near", "check") and len(h) >= 2 and h[-1][0] == today
                and h[-1][1] and h[-2][1] and h[-1][1] < h[-2][1]):
            drops.append((row, h[-2][1]))
    state["notified"] = sorted(notified)
    return new, drops, new_check


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def run(fetcher, today: str, send_alerts: bool = True) -> dict:
    state = store.load()
    first_run = not state["runs"]
    warnings = []

    cards, complete = source.fetch_all(fetcher)
    if not cards:
        warnings.append("⚠️ nehnutelnosti.sk returned no listings. The site may be blocking the "
                        "tracker or changed its layout; see data/debug in the run artifacts.")
    details = 0
    for card in cards:
        old = state["listings"].get(card["id"])
        if old is None and not prefilter(card):
            continue
        rec = dict(card)
        need_detail = (old is None or not old.get("detail_text")
                       or old.get("parser_version") != config.PARSER_VERSION)
        if need_detail:
            html = fetcher.get(card["url"])
            details += 1
            if html:
                d = source.parse_detail(html)
                rec.update({k: v for k, v in d.items() if v not in (None, "", {})})
                rec["parser_version"] = config.PARSER_VERSION
        else:
            for k in ("detail_text", "params", "is_agency", "structured_condition", "inactive",
                      "detail_price", "parser_version"):
                if rec.get(k) in (None, ""):
                    rec[k] = old.get(k)
            if not rec.get("room_line"):
                rec["room_line"] = old.get("room_line")
        rec["eval"] = evaluate(rec)
        rec["fp"] = store.fingerprint(rec.get("detail_text") or "")
        store.upsert(state, rec, today)
    if complete and cards:
        store.mark_missing(state, {c["id"] for c in cards}, today)
    log.info("%d cards, %d detail pages, complete=%s", len(cards), details, complete)

    # Re-evaluate everything so rule changes in config apply to old listings too.
    for rec in state["listings"].values():
        rec["eval"] = evaluate(rec)

    rows = build_rows(state, today)
    new, drops, new_check = diff_alerts(state, rows, today)
    if send_alerts:
        page = os.getenv("PAGE_URL")
        if first_run:
            total = sum(1 for r in rows if r["section"] in ("match", "near"))
            msgs = notify.build_messages([], [], 0, page, first_run_total=total)
        else:
            msgs = notify.build_messages(new, drops, new_check, page)
        notify.send(warnings + msgs)

    state["runs"] = (state["runs"] + [{"date": today, "cards": len(cards), "complete": complete,
                                       "details": details}])[-60:]
    store.save(state)
    render.render(rows, datetime.now().astimezone().strftime("%-d %b %Y, %H:%M"))
    counts = {s: sum(1 for r in rows if r["section"] == s)
              for s in ("match", "near", "check", "removed", "excluded")}
    log.info("Done: %s", counts)
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", type=Path, help="folder with saved HTML fixtures")
    ap.add_argument("--no-alerts", action="store_true")
    ap.add_argument("--today", help="override date (YYYY-MM-DD), for testing")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    fetcher = FixtureFetcher(a.offline) if a.offline else Fetcher()
    run(fetcher, a.today or date.today().isoformat(), send_alerts=not a.no_alerts)


if __name__ == "__main__":
    main()
