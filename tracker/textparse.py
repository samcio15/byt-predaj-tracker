"""Extract listing facts from Slovak free text.

Every function works on text normalised by `norm()` (lowercase, no diacritics)
and returns None when the text does not say, so callers can tell
"unknown" apart from "no".
"""
from __future__ import annotations

import re
import unicodedata

from . import config

# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

def norm(text: str | None) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().replace(" ", " ").replace(" ", " ")
    t = re.sub(r"\b(eur|euro|eurami|eur\.)\b", "€", t)
    t = re.sub(r"(?<=\d) (?=\d{3}\b)", "", t)       # "277 990" -> "277990"
    t = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", t)       # "277.990" -> "277990"
    t = re.sub(r"(?<=\d)[.,]-", "", t)               # "650,-" -> "650"
    t = re.sub(r"[ \t]+", " ", t)
    return t


# --------------------------------------------------------------------------- #
# Price and area
# --------------------------------------------------------------------------- #

def price_line(line: str) -> float | None:
    """A line that is only a price, e.g. '277 990 €' or '233 623,04 €'. Not '€/m²'."""
    t = (line or "").replace(" ", " ").strip()
    m = re.fullmatch(r"(\d[\d .]*)(?:,(\d{1,2}))?\s*€", t)
    if not m:
        return None
    whole = re.sub(r"\D", "", m.group(1))
    return float(whole) + (float("0." + m.group(2)) if m.group(2) else 0.0)


def area_line(line: str) -> float | None:
    """A line that is only an area, e.g. '69.7 m²'."""
    t = (line or "").replace(" ", " ").strip()
    m = re.fullmatch(r"(\d{2,3}(?:[.,]\d{1,2})?)\s*m²", t)
    return float(m.group(1).replace(",", ".")) if m else None


def area_m2(text: str) -> float | None:
    t = norm(text)
    m = re.search(r"(?:uzitkov\w*|podlahov\w*|celkov\w*)\s+ploch\w*\s*:?\s*(\d{2,3}(?:[.,]\d{1,2})?)\s*m", t)
    if not m:
        m = re.search(r"(\d{2,3}(?:[.,]\d{1,2})?)\s*(?:m2|m²|m\^2)", t)
    return float(m.group(1).replace(",", ".")) if m else None


# --------------------------------------------------------------------------- #
# Rooms
# --------------------------------------------------------------------------- #

_HALF_ROOM = re.compile(
    r"\b([1-5])\s*[,.]\s*5\s*[-–]?\s*(?:izb|i\b)"
    r"|\b([1-5])\s*a\s*pol\s*[-–]?\s*izb"
    r"|\b(jeden|dva|tri|styri)\s*a\s*pol\s*izb|\b(jedenapol|dvaapol|triapol|styriapol)\w*")
_WORDS = {"jeden": 1, "dva": 2, "tri": 3, "styri": 4,
          "jedenapol": 1, "dvaapol": 2, "triapol": 3, "styriapol": 4}


def half_rooms(*texts: str) -> float | None:
    """'3,5-izbový', '3,5 i', '3 a pol izbový', 'trojapolizbový' -> 3.5"""
    for raw in texts:
        m = _HALF_ROOM.search(norm(raw))
        if m:
            g = next(x for x in m.groups() if x)
            return (int(g) if g.isdigit() else _WORDS[g]) + 0.5
    return None


def portal_rooms(line: str | None) -> int | None:
    """The portal's own category line, e.g. '3 izbový byt'."""
    m = re.match(r"\s*(\d)\s*izbov", norm(line or ""))
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------- #
# Floor  (Slovak: prizemie = 0, 1. poschodie = first floor above ground)
# --------------------------------------------------------------------------- #

_ORDINALS = {"prv": 1, "druh": 2, "tret": 3, "stvrt": 4, "piat": 5, "siest": 6,
             "siedm": 7, "osm": 8, "devat": 9, "desiat": 10}


def floor(text: str) -> tuple[int | None, str]:
    """Return (poschodie, note) from free text. note explains ambiguity."""
    t = norm(text)
    candidates = []  # (position, value, note)

    for m in re.finditer(r"(\d{1,2})\s*\.\s*(?:poschod|posch\b)|(\d{1,2})\s+poschod(?!ov)", t):
        candidates.append((m.start(), int(m.group(1) or m.group(2)), ""))
    for m in re.finditer(r"poschodie\s*:\s*(\d{1,2})\b", t):
        candidates.append((m.start(), int(m.group(1)), ""))
    for m in re.finditer(r"(\d{1,2})\s*\.?\s*np\b", t):                  # nadzemne podlazie
        candidates.append((m.start(), int(m.group(1)) - 1, ""))
    for m in re.finditer(r"(\d{1,2})\s*\.\s*(?:nadzemn\w* )?podlaz", t):
        candidates.append((m.start(), *_podlazie(int(m.group(1)))))
    for m in re.finditer(r"\b(" + "|".join(_ORDINALS) + r")\w*\s+(poschod|nadzemn)", t):
        n = _ORDINALS[m.group(1)]
        candidates.append((m.start(), n - 1 if m.group(2) == "nadzemn" else n, ""))
    for m in re.finditer(r"\b(?:na|v)\s+(?:zvysen\w*\s+|vyvysen\w*\s+)?prizem|\bsuteren", t):
        candidates.append((m.start(), 0, ""))

    if candidates:
        candidates.sort(key=lambda c: c[0])
        _, val, note = candidates[0]
        return val, note
    if re.search(r"\bprizem", t):
        return 0, ""
    return None, ""


def _podlazie(n: int) -> tuple[int | None, str]:
    """'N. podlažie' is used both as N. poschodie and as N. nadzemné podlažie.
    Trust it only when both readings agree on pass/fail."""
    if n - 1 >= config.MIN_FLOOR:
        return n - 1, ""
    if n < config.MIN_FLOOR:
        return n, ""
    return None, f"'{n}. podlažie' could be {n - 1}. or {n}. poschodie"


def structured_floor(podlazie: str | None, umiestnenie: str | None) -> tuple[int | None, str]:
    """Portal fields: 'Podlažie: 11/14 + výťah', 'Umiestnenie: Ďalšie nadzemné podlažie'."""
    u = norm(umiestnenie)
    if re.search(r"prizem|suteren|prv\w* nadzemn|podzemn", u):
        return 0, ""
    m = re.match(r"\s*(-?\d{1,2})", podlazie or "")
    if m:
        return _podlazie(int(m.group(1)))
    return None, ""


# --------------------------------------------------------------------------- #
# Balcony and cellar
# --------------------------------------------------------------------------- #

def balcony(text: str) -> bool | None:
    t = norm(text)
    t = re.sub(r"francuzsk\w*\s+(?:balkon\w*|okn\w*|dver\w*)", " ", t)
    if re.search(r"\bbez\s+(?:balkon|lodzi|loggi|terasy)|\bnema\s+(?:ziaden\s+)?(?:balkon|lodzi)"
                 r"|balkon\w*\s*:\s*nie", t):
        return False
    if re.search(r"balkon|lodzi|lodza|loggi|terasa|terasou|terasy\b|teras\w*", t):
        return True
    return None


def cellar(text: str) -> bool | None:
    t = norm(text)
    if re.search(r"\bbez\s+(?:pivnic|kobk)|\bnema\s+(?:ziadn\w*\s+)?(?:pivnic|kobk)|pivnic\w*\s*:\s*nie", t):
        return False
    if re.search(r"pivnic|pivnicn\w*|\bkobk|\bkobka|skladov\w* priestor\w* (?:v|na) (?:suteren|prizem)", t):
        return True
    return None


# --------------------------------------------------------------------------- #
# Condition
# --------------------------------------------------------------------------- #

_STRUCTURED_CONDITION = {
    "kompletna rekonstrukcia": "renovated",
    "ciastocna rekonstrukcia": "partial",
    "novostavba": "new",
    "vo vystavbe": "new",
    "developersky projekt": "new",
    "povodny stav": "original",
}


def condition(text: str, structured: str | None = None) -> str | None:
    """'renovated' | 'partial' | 'new' | 'original' | None"""
    if structured:
        s = norm(structured).strip()
        for key, val in _STRUCTURED_CONDITION.items():
            if key in s:
                return val
    t = norm(text)
    negative = re.search(
        r"povodn\w* stav|povodnom stave|pred rekonstrukci|(?:vhodn\w*|urcen\w*) na rekonstrukci"
        r"|(?:potrebuje|vyzaduje|nutn\w*)\s+(?:\w+\s+)?rekonstrukci", t)
    if re.search(r"novostavb|nov\w* bytov\w* dom|nov\w* projekt", t):
        return "new"
    if re.search(r"ciastocn\w*\s+(?:zre|re)konstru|ciastocne prerob", t):
        return "partial"
    full = re.search(
        r"(?:kompletn\w*|celkov\w*|komplet\w*|luxusn\w*|nedavn\w*|citliv\w*|nov\w*)\s+(?:zre|re)konstru"
        r"|po\s+(?:kompletnej\s+|celkovej\s+|novej\s+|nedavnej\s+)?rekonstrukci"
        r"|zrekonstruovan|prerobe|renovovan|kompletne prerob|presiel\w*\s+(?:\w+\s+)?rekonstrukci", t)
    if full:
        return "partial" if negative else "renovated"
    if re.search(r"rekonstru", t) and not negative:
        return "partial"
    if negative:
        return "original"
    return None


# --------------------------------------------------------------------------- #
# District
# --------------------------------------------------------------------------- #

def district_from_text(*texts: str) -> str | None:
    for raw in texts:
        t = norm(raw)
        best = None
        for name, pats in config.DISTRICTS.items():
            for p in pats:
                m = re.search(p, t)
                if m and (best is None or m.start() < best[0]):
                    best = (m.start(), name)
        if best:
            return best[1]
    return None


# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #

def is_unavailable(title: str) -> bool:
    """Title marks the flat as already reserved or sold."""
    return re.search(r"\b(rezervovan\w*|predan[ey]\b|predana\b|predany\b|sold)\b", norm(title)) is not None
