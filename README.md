# Bratislava 3-room flats for sale tracker

Every 3 days at 17:00 (Bratislava time) it reads nehnutelnosti.sk, keeps the
3- and 3,5-room flats for sale in Petržalka, Ružinov, Karlova Ves, Nové Mesto
and Rača, and records how long each one has been listed and every price change.
Results go to a sortable web page; new matches and price drops go to Telegram.

| Section | Rule |
|---|---|
| Matches | 210 000 – 280 000 €, every rule confirmed |
| Near misses | 280 000 – 290 000 € |
| Needs a manual check | price fits, but floor, balcony, condition, size or price is not stated |
| Recently removed | disappeared in the last 60 days (probably sold) |
| Excluded | failed a rule, with the reason |

Rules: 3 or 3,5 rooms, at least 60 m², balcony (loggia/terrace counts),
2nd floor or higher (prízemie, zvýšené/vyvýšené prízemie and 1st floor are excluded),
not in original condition (pôvodný stav). Below 210 000 € is dropped as suspicious.
Cellar is shown as a column, not used as a filter.

3,5-room flats are often filed by sellers in the 4-room category, so the tracker
also reads that category and keeps only listings that say "3,5".

## Negotiation signals

- **Listed**: days since the tracker first saw the flat. After 45 days it's marked "negotiable".
- **Price drops**: total drop and every step (e.g. 289k → 279k → 269k).
- **Recently removed**: how long comparable flats lasted before selling.

Days listed starts counting when the tracker first sees a listing; the portal
doesn't publish the original listing date.

## Schedule

GitHub schedules run in UTC only, so the workflow fires daily at 15:00 and
16:00 UTC, and `tracker/gate.py` lets through only the first firing at or
after 17:00 Bratislava time, once 3 days have passed. Skipped days take a few
seconds and change nothing. The **Run workflow** button always runs immediately.

## Tuning

All rules are in `tracker/config.py`: price range, size, floor, rooms, districts,
schedule. After editing, the next run re-evaluates all stored listings.

## Local test

```
pip install -r requirements.txt
python -m pytest -q
python -m tracker.main --offline tests/fixtures --no-alerts   # uses saved pages
```
