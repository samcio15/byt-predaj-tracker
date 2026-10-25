"""nehnutelnosti.sk: list pages -> cards, detail page -> parameters + description.

Parsing is text-based (anchor links + visible text), not tied to CSS class
names, because the site uses generated class names that change often.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .. import config
from ..fetch import dump_debug
from ..textparse import area_line, norm, price_line

log = logging.getLogger(__name__)
SOURCE = "nehnutelnosti"
_DETAIL_RE = re.compile(r"/detail/([A-Za-z0-9_-]{6,})/")
_CONDITIONS = ("Kompletná rekonštrukcia", "Čiastočná rekonštrukcia", "Novostavba",
               "Pôvodný stav", "Vo výstavbe")
_BADGES = {"PREMIUM", "TOP", "NOVÉ", "NOVINKA", "Info v RK"}


def _location(lines: list[str]) -> str:
    for ln in lines:
        if "okres Bratislava" in ln:
            return ln
    for ln in lines:
        if re.search(r"Bratislava-[A-ZÁ-Ž]", ln):
            return ln
    return ""


def _card_facts(lines: list[str]) -> dict:
    room_line = next((ln for ln in lines if re.fullmatch(r"\d\s*izbový byt", ln.strip())), None)
    return {
        "price": next((p for ln in lines if (p := price_line(ln)) is not None), None),
        "area": next((a for ln in lines if (a := area_line(ln)) is not None), None),
        "room_line": room_line,
        "price_on_request": any(ln.strip() in ("Info v RK", "Cena dohodou", "Cena na vyžiadanie")
                                for ln in lines),
    }


def parse_list(html: str, category: int | None = None) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _DETAIL_RE.search(href)
        if not m or "developersky-projekt" in href:
            continue
        nid = m.group(1)
        if nid in seen:
            continue
        seen.add(nid)
        # Climb to the largest ancestor that contains only this listing.
        node = a
        while node.parent is not None:
            others = [x for x in node.parent.find_all("a", href=True)
                      if (mm := _DETAIL_RE.search(x["href"])) and mm.group(1) != nid
                      and "developersky-projekt" not in x["href"]]
            if others:
                break
            node = node.parent
        lines = [ln.strip() for ln in node.get_text("\n", strip=True).split("\n") if ln.strip()]
        title = next((ln for ln in lines if ln not in _BADGES and len(ln) > 15), "")
        url = href if href.startswith("http") else "https://www.nehnutelnosti.sk" + href
        out.append({
            "id": f"{SOURCE}:{nid}",
            "source": SOURCE,
            "url": url.split("?")[0],
            "title": title,
            "location": _location(lines),
            "card_text": "\n".join(lines),
            "category": category,
            **_card_facts(lines),
        })
    if not out:
        dump_debug(f"nehnutelnosti_list_empty_{category}.html", html)
    return out


def last_page(html: str) -> int:
    pages = [int(p) for p in re.findall(r"[?&]page=(\d+)", html)]
    return min(max(pages, default=1), config.MAX_PAGES)


def _params(lines: list[str]) -> dict[str, str]:
    """'Key:' line followed by its value line, from the header down to the description."""
    start = next((i for i, ln in enumerate(lines) if re.search(r"na (?:predaj|prenájom)$", ln)), None)
    if start is None:
        return {}
    end = lines.index("Popis nehnuteľnosti") if "Popis nehnuteľnosti" in lines[start:] else start + 60
    out = {}
    block = lines[start:end]
    for i, ln in enumerate(block[:-1]):
        if ln.endswith(":"):
            out.setdefault(ln.rstrip(": ").strip(), block[i + 1])
    return out


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "svg", "noscript"]):
        t.decompose()
    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).split("\n") if ln.strip()]
    text = "\n".join(lines)

    desc = ""
    if "Popis nehnuteľnosti" in lines:
        start = lines.index("Popis nehnuteľnosti") + 1
        end = len(lines)
        for stop in ("Čítať ďalej", "Nenašli ste všetky informácie?", "Lokalita"):
            if stop in lines[start:]:
                end = min(end, lines.index(stop, start))
        desc = "\n".join(lines[start:end])
    if not desc:
        dump_debug("nehnutelnosti_detail_nodesc.html", html)

    params = _params(lines)
    h1 = soup.find("h1")
    head_start = next((i for i, ln in enumerate(lines) if h1 and ln == h1.get_text(strip=True)), 0)
    head = lines[head_start:head_start + 12]
    return {
        "detail_text": "\n".join(f"{k}: {v}" for k, v in params.items()) + "\n" + desc,
        "params": params,
        "structured_condition": next((c for c in _CONDITIONS if c in head), None),
        "room_line": next((ln for ln in head if re.fullmatch(r"\d\s*izbový byt", ln)), None),
        "detail_price": next((p for ln in head if (p := price_line(ln)) is not None), None),
        "is_agency": True if ("Profil realitnej kancelárie" in text or "MAKLÉR" in lines) else None,
        "inactive": "už nie je aktuálny" in text,
        "location": _location(head) or None,
    }


def fetch_all(fetcher) -> tuple[list[dict], bool]:
    """Return (cards, complete). complete=False if any page failed."""
    cards, complete = [], True
    for base, category in config.LIST_URLS:
        first = fetcher.get(base)
        if first is None:
            complete = False
            continue
        batch = parse_list(first, category)
        if not batch:
            complete = False
            continue
        cards.extend(batch)
        for page in range(2, last_page(first) + 1):
            html = fetcher.get(base, params={"page": page})
            if html is None:
                complete = False
                break
            batch = parse_list(html, category)
            if not batch:
                break
            cards.extend(batch)
    uniq = {}
    for c in cards:
        uniq.setdefault(c["id"], c)
    log.info("nehnutelnosti: %d cards (complete=%s)", len(uniq), complete)
    return list(uniq.values()), complete


def district_of(location: str | None) -> str | None:
    m = re.search(r"Bratislava\s*-\s*([^,]+)", location or "")
    if not m:
        return None
    loc = norm(m.group(1))
    for name in config.DISTRICTS:
        if norm(name) in loc:
            return name
    return None
