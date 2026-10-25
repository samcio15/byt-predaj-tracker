"""Parser tests against pages saved from nehnutelnosti.sk (Oct 2026).
If the site changes its layout, live runs dump the new page into data/debug/;
save it here as a new fixture and fix the parser."""
from pathlib import Path

from tracker.evaluate import evaluate
from tracker.main import prefilter
from tracker.sources import nehnutelnosti as n

F = Path(__file__).parent / "fixtures"


def read(name):
    return (F / name).read_text(encoding="utf-8")


def test_list_cards():
    cards = n.parse_list(read("sale_list.html"), 3)
    assert len(cards) == 29
    c = next(c for c in cards if "Juo9VPJPBNW" in c["id"])
    assert (c["price"], c["area"], c["room_line"]) == (277990, 69.7, "3 izbový byt")
    assert n.district_of(c["location"]) == "Petržalka"
    assert n.last_page(read("sale_list.html")) == 33
    # Location must not be taken from a title that mentions Bratislava.
    c = next(c for c in cards if c["title"].startswith("3 izb. byt s loggiou"))
    assert n.district_of(c["location"]) == "Rača"
    # Price on request
    c = next(c for c in cards if "Landererova" in c["location"])
    assert c["price"] is None and c["price_on_request"]


def test_detail_params():
    d = n.parse_detail(read("sale_detail.html"))
    p = d["params"]
    assert p["Podlažie"] == "11/14 + výťah"
    assert p["Plocha pivnice"] == "3 m²"
    assert d["structured_condition"] == "Kompletná rekonštrukcia"
    assert d["detail_price"] == 277990
    assert d["is_agency"] is True and d["inactive"] is False


def test_medvedova_end_to_end():
    card = next(c for c in n.parse_list(read("sale_list.html"), 3) if "Juo9VPJPBNW" in c["id"])
    assert prefilter(card)
    rec = {**card, **n.parse_detail(read("sale_detail.html"))}
    e = evaluate(rec)
    assert e["status"] == "match"
    assert (e["district"], e["rooms"], e["floor"], e["balcony"], e["cellar"], e["condition"]) == \
        ("Petržalka", 3, 10, True, True, "renovated")
    assert e["ppm2"] == 3988


def test_rules():
    base = {"source": "nehnutelnosti", "title": "3-izbový byt", "room_line": "3 izbový byt",
            "location": "Exnárova, Bratislava-Ružinov, okres Bratislava II", "area": 70,
            "price": 250000, "structured_condition": "Kompletná rekonštrukcia",
            "detail_text": "Byt na 4. poschodí, loggia, pivnica."}
    assert evaluate(base)["status"] == "match"
    assert evaluate({**base, "price": 285000})["status"] == "near"
    assert "too expensive" in evaluate({**base, "price": 295000})["excluded"][0]
    assert "suspiciously low" in evaluate({**base, "price": 199000})["excluded"][0]
    assert evaluate({**base, "area": 58})["status"] == "excluded"
    assert evaluate({**base, "structured_condition": "Pôvodný stav"})["status"] == "excluded"
    assert evaluate({**base, "detail_text": "Byt na zvýšenom prízemí, loggia."})["status"] == "excluded"
    assert evaluate({**base, "detail_text": "Byt na 4. poschodí, loggia."})["status"] == "match"  # cellar not required
    assert evaluate({**base, "location": "Bratislava-Staré Mesto, okres Bratislava I"})["status"] == "excluded"
    # 3,5-room flat filed in the 4-room category
    four = {**base, "room_line": "4 izbový byt", "category": 4}
    assert evaluate(four)["status"] == "excluded"
    assert evaluate({**four, "title": "Predaj 3,5-izbového bytu"})["rooms"] == 3.5
    assert evaluate({**four, "title": "Predaj 3,5-izbového bytu"})["status"] == "match"
    # Price on request -> needs check
    e = evaluate({**base, "price": None, "price_on_request": True})
    assert e["status"] == "check" and "price (on request)" in e["unknown"]
