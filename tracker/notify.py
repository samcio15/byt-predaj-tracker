"""Telegram alerts. Needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars."""
from __future__ import annotations

import html
import logging
import os

import requests

log = logging.getLogger(__name__)
MAX_LEN = 3900  # Telegram limit is 4096 characters


def eur(x: float | None) -> str:
    return "?" if x is None else f"{x:,.0f} €".replace(",", " ")


def _row(r: dict) -> str:
    """r is a page row (see main.build_rows)."""
    bits = [r.get("district") or "?",
            f"{r['area']:g} m²" if r.get("area") else None,
            f"{eur(r['ppm2'])}/m²" if r.get("ppm2") else None,
            f"{r['floor']}. posch." if r.get("floor") is not None else None,
            "pivnica" if r.get("cellar") else None]
    line = f"<b>{html.escape(eur(r['price']))}</b>  " + html.escape(", ".join(b for b in bits if b))
    url = r["links"][0]["url"]
    return f"{line}\n<a href=\"{html.escape(url)}\">{html.escape(r['title'][:70])}</a>"


def build_messages(new: list[dict], drops: list[tuple[dict, float]], new_check: int,
                   page_url: str | None, first_run_total: int | None = None) -> list[str]:
    parts = []
    if first_run_total is not None:
        parts.append(f"🏠 3-room flat tracker is running. {first_run_total} listings currently "
                     "match or nearly match. From now on you get new listings and price drops here.")
    else:
        for r in new:
            tag = "🆕" if r["section"] == "match" else "🟡 near miss"
            parts.append(f"{tag}\n{_row(r)}")
        for r, old in drops:
            cut = old - r["price"]
            parts.append(f"📉 price drop −{eur(cut)} (from {eur(old)}), listed {r['days']} days\n{_row(r)}")
        if new_check:
            parts.append(f"🔍 {new_check} new listing(s) need a manual check.")
    if not parts:
        return []
    if page_url:
        parts.append(f"<a href=\"{html.escape(page_url)}\">Open full list</a>")
    msgs, cur = [], ""
    for p in parts:
        if len(cur) + len(p) + 2 > MAX_LEN:
            msgs.append(cur)
            cur = ""
        cur += p + "\n\n"
    if cur.strip():
        msgs.append(cur)
    return msgs


def send(messages: list[str]) -> None:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        log.info("Telegram not configured; would send %d message(s):", len(messages))
        for m in messages:
            log.info("\n%s", m)
        return
    for m in messages:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={
            "chat_id": chat, "text": m, "parse_mode": "HTML",
            "disable_web_page_preview": "true"}, timeout=20)
        if not r.ok:
            log.error("Telegram error %s: %s", r.status_code, r.text[:300])
