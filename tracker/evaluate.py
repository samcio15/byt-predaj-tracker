"""Turn a raw listing into a verdict: match / near / check / excluded."""
from __future__ import annotations

from . import config
from . import textparse as tp
from .sources import nehnutelnosti


def rooms_of(rec: dict) -> float | None:
    """Portal category, upgraded to N,5 when the title or text says so."""
    base = tp.portal_rooms(rec.get("room_line")) or rec.get("category")
    half = tp.half_rooms(rec.get("title", ""), rec.get("card_text", ""), rec.get("detail_text", ""))
    if half is not None and base is not None and abs(half - base) <= 1:
        return half
    return base


def evaluate(rec: dict) -> dict:
    title = rec.get("title", "")
    body = rec.get("detail_text") or rec.get("card_text", "")
    full = f"{title}\n{body}"
    params = rec.get("params") or {}

    excluded, unknown, flags = [], [], []

    if rec.get("inactive") or tp.is_unavailable(title):
        excluded.append("reserved, sold or no longer listed")

    dist = nehnutelnosti.district_of(rec.get("location"))
    if not dist:
        excluded.append("district not on your list")

    rooms = rooms_of(rec)
    if rooms is None:
        unknown.append("rooms")
    elif rooms not in config.ROOMS:
        excluded.append(f"{rooms:g} rooms")

    area = rec.get("area") or tp.area_line(params.get("Plocha bytu", "")) or tp.area_m2(body)
    if area is None:
        unknown.append("size")
    elif area < config.MIN_AREA:
        excluded.append(f"{area:g} m² (under {config.MIN_AREA})")

    price = rec.get("price") or rec.get("detail_price")
    if price is None:
        unknown.append("price (on request)" if rec.get("price_on_request") else "price")
    elif price < config.PRICE_MIN:
        excluded.append(f"suspiciously low ({price:,.0f} €)".replace(",", " "))
    elif price > config.NEAR_MISS_MAX:
        excluded.append(f"too expensive ({price:,.0f} €)".replace(",", " "))

    # Floor: explicit text ("10. poschodie") first, then the portal's fields.
    fl, note = tp.floor(full)
    if fl is None:
        fl, note2 = tp.structured_floor(params.get("Podlažie"), params.get("Umiestnenie"))
        note = note or note2
    if fl is None:
        unknown.append("floor" + (f" ({note})" if note else ""))
    elif fl < config.MIN_FLOOR:
        excluded.append("prízemie" if fl == 0 else f"{fl}. poschodie")

    bal = tp.balcony(full)
    if bal is False:
        excluded.append("no balcony")
    elif bal is None:
        unknown.append("balcony")

    cond = tp.condition(full, rec.get("structured_condition"))
    if cond == "original":
        excluded.append("original condition (pôvodný stav)")
    elif cond is None:
        unknown.append("condition")

    if excluded:
        status = "excluded"
    elif unknown:
        status = "check"
    elif price <= config.PRICE_MAX:
        status = "match"
    else:
        status = "near"

    return {
        "status": status,
        "district": dist,
        "rooms": rooms,
        "area": area,
        "price": price,
        "ppm2": round(price / area) if price and area else None,
        "floor": fl,
        "balcony": bal,
        "cellar": tp.cellar(full),
        "condition": cond,
        "excluded": excluded,
        "unknown": unknown,
        "flags": flags,
    }
