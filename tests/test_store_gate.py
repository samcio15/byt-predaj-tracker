from datetime import datetime
from zoneinfo import ZoneInfo

from tracker import config, store
from tracker.gate import should_run

BA = ZoneInfo("Europe/Bratislava")


def rec(id_, price, text="x" * 200):
    return {"id": id_, "source": "nehnutelnosti", "title": "t", "url": "u", "detail_text": text,
            "fp": store.fingerprint(text),
            "eval": {"price": price, "district": "Ružinov", "area": 70}}


def test_price_history_and_removal():
    s = store.empty()
    store.upsert(s, rec("n:1", 289000), "2026-10-01")
    store.upsert(s, rec("n:1", 279000), "2026-10-04")
    assert s["listings"]["n:1"]["price_history"] == [["2026-10-01", 289000], ["2026-10-04", 279000]]
    store.mark_missing(s, set(), "2026-10-07")
    assert s["listings"]["n:1"]["active"]           # one miss is tolerated
    store.mark_missing(s, set(), "2026-10-10")
    assert not s["listings"]["n:1"]["active"]


def test_repost_keeps_first_seen():
    s = store.empty()
    store.upsert(s, rec("n:1", 279000), "2026-10-01")
    store.upsert(s, rec("n:2", 279000, "y" * 200), "2026-10-10")   # same district, m², price
    assert s["listings"]["n:2"]["group"] == "n:1"
    assert store.group_first_seen(s, "n:1") == "2026-10-01"


def test_old_rental_state_is_discarded(tmp_path):
    p = tmp_path / "state.json"
    p.write_text('{"listings": {"x": {}}, "runs": [{"date": "2026-10-01"}], "notified": []}')
    assert store.load(p) == store.empty()


def test_gate():
    at = lambda d, h: datetime(2026, 10, d, h, 5, tzinfo=BA)
    assert should_run(at(26, 16), None, False)[0] is False          # before 17:00
    assert should_run(at(26, 17), None, False)[0] is True           # first run
    assert should_run(at(28, 17), "2026-10-26", False)[0] is False  # only 2 days
    assert should_run(at(29, 17), "2026-10-26", False)[0] is True   # 3 days
    assert should_run(at(29, 18), "2026-10-29", False)[0] is False  # second firing same day
    assert should_run(at(27, 9), "2026-10-26", True)[0] is True     # manual always runs
    assert config.RUN_EVERY_DAYS == 3 and config.RUN_AT_HOUR == 17


def test_matches_split_by_condition():
    from tracker.render import page_section
    assert page_section({"section": "match", "condition": "renovated"}) == "match_full"
    assert page_section({"section": "match", "condition": "new"}) == "match_full"
    assert page_section({"section": "match", "condition": "partial"}) == "match_partial"
    assert page_section({"section": "near", "condition": "partial"}) == "near"
