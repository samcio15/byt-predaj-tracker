import pytest

from tracker import textparse as tp


@pytest.mark.parametrize("line,expected", [
    ("277 990 €", 277990),
    ("233 623,04 €", 233623.04),
    ("3 988,38 €/m²", None),
    ("Info v RK", None),
])
def test_price_line(line, expected):
    assert tp.price_line(line) == expected


@pytest.mark.parametrize("line,expected", [("69.7 m²", 69.7), ("70 m²", 70), ("3 izbový byt", None)])
def test_area_line(line, expected):
    assert tp.area_line(line) == expected


@pytest.mark.parametrize("text,expected", [
    ("Predaj 3,5-izbového bytu v Ružinove", 3.5),
    ("3,5 izbový byt s loggiou", 3.5),
    ("3.5 izb. byt", 3.5),
    ("Ponúkame 3 a pol izbový byt", 3.5),
    ("2,5 izbový byt s balkónom", 2.5),
    ("3 izbový byt s loggiou", None),
])
def test_half_rooms(text, expected):
    assert tp.half_rooms(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Byt sa nachádza na 10. poschodí", 10),
    ("Poschodie: 10. zo 13 v bytovom dome", 10),
    ("na prízemí", 0),
    ("byt na zvýšenom prízemí", 0),
    ("byt na vyvýšenom prízemí", 0),
    ("byt je na 1. poschodí", 1),
    ("na prvom poschodí", 1),
    ("Byt sa nachádza na prvom nadzemnom podlaží (prízemí)", 0),
    ("na druhom nadzemnom podlaží", 1),
    ("na treťom poschodí 8-poschodového domu", 3),
    ("byt na 4.NP", 3),
    ("nachádza sa na 5. podlaží", 4),
    ("nachádza sa na 1. podlaží", 1),
    ("v 8 poschodovom dome", None),
    ("výťah ide až do pivnice", None),
])
def test_floor(text, expected):
    assert tp.floor(text)[0] == expected


def test_floor_ambiguous_podlazie():
    val, note = tp.floor("byt na 2. podlaží")
    assert val is None and "2. podlažie" in note


@pytest.mark.parametrize("podlazie,umiestnenie,expected", [
    ("11/14 + výťah", "Ďalšie nadzemné podlažie", 10),
    ("1/8", None, 1),
    ("2/8", None, None),             # 1. or 2. poschodie, can't tell
    ("0/4", None, 0),
    (None, "Prízemie", 0),
    (None, "Zvýšené prízemie", 0),
    (None, None, None),
])
def test_structured_floor(podlazie, umiestnenie, expected):
    assert tp.structured_floor(podlazie, umiestnenie)[0] == expected


@pytest.mark.parametrize("text,expected", [
    ("Plocha lodžie: 3 m²", True),
    ("byt s balkónom", True),
    ("byt bez balkóna", False),
    ("francúzsky balkón v spálni", None),
    ("pekný byt", None),
])
def test_balcony(text, expected):
    assert tp.balcony(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Plocha pivnice: 3 m²", True),
    ("Pivničná kobka: 3 m²", True),
    ("k bytu patrí kobka", True),
    ("byt je bez pivnice", False),
    ("pekný byt", None),
])
def test_cellar(text, expected):
    assert tp.cellar(text) == expected


@pytest.mark.parametrize("text,structured,expected", [
    ("", "Kompletná rekonštrukcia", "renovated"),
    ("", "Čiastočná rekonštrukcia", "partial"),
    ("", "Pôvodný stav", "original"),
    ("", "Vo výstavbe", "new"),
    ("byt prešiel kompletnou rekonštrukciou", None, "renovated"),
    ("byt v pôvodnom stave", None, "original"),
    ("pôvodný stav, kúpeľňa po rekonštrukcii", None, "partial"),
    ("pekný byt", None, None),
])
def test_condition(text, structured, expected):
    assert tp.condition(text, structured) == expected


def test_unavailable():
    assert tp.is_unavailable("REZERVOVANÉ 3-izbový byt")
    assert tp.is_unavailable("PREDANÉ - 3 izbový byt")
    assert not tp.is_unavailable("Predaj 3-izbového bytu")
    assert not tp.is_unavailable("Predám 3 izbový byt")
