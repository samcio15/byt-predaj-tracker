"""All tunable settings live here. Edit this file, not the code."""

# ---- Price rules (EUR, purchase price) --------------------------------------
PRICE_MIN = 210_000          # below this = suspicious, dropped
PRICE_MAX = 280_000          # main list
NEAR_MISS_MAX = 290_000      # near-miss section: PRICE_MAX < price <= this

# ---- Flat rules -------------------------------------------------------------
ROOMS = (3, 3.5)             # 3-room and 3,5-room flats
MIN_AREA = 60                # m²
MIN_FLOOR = 2                # 2. poschodie and higher (prízemie / zvýšené prízemie = 0)
# Cellar is shown as a column only, never used to filter.
STALE_DAYS = 45             # listed this long -> marked "negotiable" on the page

# ---- Schedule (checked by tracker.gate, see .github/workflows/track.yml) ----
RUN_EVERY_DAYS = 3
RUN_AT_HOUR = 17             # local time, Europe/Bratislava

# ---- Districts --------------------------------------------------------------
# Regexes run on lowercase text with diacritics removed.
DISTRICTS = {
    "Petržalka":   [r"petrzal\w*", r"\bovsist\w*"],
    "Ružinov":     [r"ruzinov\w*", r"\bprievoz\w*", r"\btrnavk\w*", r"\bstrkovc\w*|\bstrkovec",
                    r"\bostredk\w*", r"\bposen\w*", r"\bmlynske nivy"],
    "Karlova Ves": [r"karlov\w* ves\w*", r"karlovej vsi", r"\bdlhe diely|\bdlhych dieloch"],
    "Nové Mesto":  [r"\bnov(e|om|eho|ym) mest(o|e|a|u|om)\b(?! nad)", r"\bkolib\w*", r"\bkramar\w*",
                    r"\bkuchajd\w*", r"\bpasienk\w*", r"jurajov\w* dvor\w*"],
    "Rača":        [r"\brac(a|i|e|u|ou)\b", r"\bkrasnan\w*"],
}

# ---- Source -----------------------------------------------------------------
# 3-room category, plus the 4-room category because sellers often file
# 3,5-room flats there (only listings that say "3,5" are kept from it).
LIST_URLS = [
    ("https://www.nehnutelnosti.sk/vysledky/3-izbove-byty/bratislava/predaj", 3),
    ("https://www.nehnutelnosti.sk/vysledky/4-izbove-byty/bratislava/predaj", 4),
]
MAX_PAGES = 60

# ---- Politeness -------------------------------------------------------------
REQUEST_DELAY = (2.0, 4.5)   # random pause between requests, seconds
TIMEOUT = 25
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

# A listing is marked removed after it is missing this many successful runs in a row.
REMOVED_AFTER_MISSES = 2

# Bump when parsing changes, so stored listings get their detail page re-read once.
PARSER_VERSION = 1
STATE_KIND = "sale-3room"    # a state file of another kind (e.g. the old rental one) is discarded
