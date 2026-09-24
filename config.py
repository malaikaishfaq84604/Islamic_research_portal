"""
config.py
---------
All the settings for the Islamic Research Portal live in this one file.
Keeping settings here (instead of scattered through the code) means the
student only has to edit ONE file to change the admin password or the
database location.

Nothing here talks to the internet or the database - these are just values.
"""

import os

# ---------------------------------------------------------------------------
# BASE_DIR is the folder that this config.py file sits in.
# os.path.abspath(__file__) -> full path of this file
# os.path.dirname(...)      -> the folder that contains it
# We build every other path from BASE_DIR so the app works no matter which
# folder the user runs "python app.py" from (important on Windows).
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Full path to the SQLite database file. os.path.join builds the path using
# the correct separator for the operating system ("\" on Windows, "/" on Linux).
DB_PATH = os.path.join(BASE_DIR, "portal.db")

# ===========================================================================
# THE TWO SECRETS: THE ADMIN PASSWORD AND THE SECRET KEY
#
# WHY THIS IS NOT SIMPLY TWO STRINGS ANY MORE
# -------------------------------------------
# On your own laptop it does not matter that the password is written here in
# plain sight - nobody else can reach 127.0.0.1. The moment the portal is put
# on the internet that changes completely:
#
#   * anyone who reads this file (it is in the project folder, and in the
#     GitHub repository if you use one) can log into /admin and add, attach
#     or detach whatever they like;
#   * worse, SECRET_KEY is what Flask uses to SIGN the "I am the admin"
#     cookie. Somebody who knows it does not even need the password - they
#     can forge the cookie and walk straight in.
#
# HOW IT WORKS NOW
# ----------------
# Both values are read from ENVIRONMENT VARIABLES - settings stored on the
# server itself rather than inside the code, so they are never written in a
# file and never uploaded anywhere.
#
#   PORTAL_ADMIN_PASSWORD   the password /admin asks for
#   PORTAL_SECRET_KEY       the long random string that signs the cookie
#
# If they are NOT set, the old built-in values are used, so running the
# project on your own machine (run.bat, python app.py, python dev.py) carries
# on working exactly as before with nothing to configure.
#
# But if the portal is running on a real web host AND the built-in values are
# still in use, it refuses to start at all - see the check at the bottom of
# this file. A portal that stops with a clear message is far better than one
# that quietly serves an admin page secured by a password printed in the
# source code.
# ===========================================================================

# The built-in values, used for local development only.
DEFAULT_ADMIN_PASSWORD = "changeme123"
DEFAULT_SECRET_KEY = "islamic-research-portal-fyp-secret-key"


def _read_setting(variable_name, fallback):
    """
    Read one environment variable, falling back to the built-in value.

    A variable that exists but is empty or is nothing but spaces counts as
    "not set", because an empty password is not a password.
    """
    value = os.environ.get(variable_name, "").strip()
    return value if value else fallback


ADMIN_PASSWORD = _read_setting("PORTAL_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
SECRET_KEY = _read_setting("PORTAL_SECRET_KEY", DEFAULT_SECRET_KEY)

# Are we still using the values printed in this file?
USING_DEFAULT_PASSWORD = (ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD)
USING_DEFAULT_SECRET_KEY = (SECRET_KEY == DEFAULT_SECRET_KEY)

# ---------------------------------------------------------------------------
# ARE WE ON A REAL WEB HOST, OR ON A LAPTOP?
#
# PythonAnywhere sets PYTHONANYWHERE_DOMAIN for every process it runs, so its
# presence is a reliable sign that the portal is reachable from the internet.
# PORTAL_ENV=production lets you say so manually on any other host.
# ---------------------------------------------------------------------------
ON_PYTHONANYWHERE = bool(os.environ.get("PYTHONANYWHERE_DOMAIN"))
IS_PRODUCTION = (
    ON_PYTHONANYWHERE
    or os.environ.get("PORTAL_ENV", "").strip().lower() == "production"
)

# ---------------------------------------------------------------------------
# WHICH ADDRESS THE WEBSITE RUNS ON
# 127.0.0.1 means "this computer only" - nobody else on the network can reach
# it, which is exactly what we want for a college project.
# If port 5000 is already taken, app.py automatically tries 5001, 5002, ...
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 5000

# ---------------------------------------------------------------------------
# QURAN DATA SOURCE (AlQuran.cloud - free, no API key needed)
# {surah} is replaced with the surah number (1 to 114) before the request.
# The three "editions" we ask for are:
#   quran-uthmani -> Arabic text with full diacritics (harakat)
#   ur.jalandhry  -> Urdu translation by Fateh Muhammad Jalandhry
#   en.sahih      -> English translation (Sahih International)
# ---------------------------------------------------------------------------
QURAN_API_URL = (
    "https://api.alquran.cloud/v1/surah/{surah}/editions/"
    "quran-uthmani,ur.jalandhry,en.sahih"
)

# There are exactly 114 surahs in the Quran.
TOTAL_SURAHS = 114

# ---------------------------------------------------------------------------
# QURAN FALLBACK SOURCE (fawazahmed0 quran-api on the jsDelivr CDN)
# Used automatically if AlQuran.cloud is unreachable. Each URL returns the
# WHOLE Quran in one file, so we only need three downloads.
#
# NOTE ON EDITION NAMES (checked against .../quran-api@1/editions.json):
#   * The Urdu slug is "urd-fatehmuhammadja", NOT "urd-fatehmuhammadjala".
#     This CDN cuts every slug to 19 characters.
#   * There is no "eng-sahih" edition on this CDN. The Sahih International
#     translation is published there under its translator's name,
#     "eng-ummmuhammad" (Umm Muhammad), so we use that - it is the same text.
# ---------------------------------------------------------------------------
QURAN_FALLBACK_URLS = {
    "arabic": "https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1/editions/ara-quranuthmanihaf.json",
    "urdu": "https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1/editions/urd-fatehmuhammadja.json",
    "english": "https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1/editions/eng-ummmuhammad.json",
}

# ---------------------------------------------------------------------------
# HADITH DATA SOURCE (fawazahmed0 hadith-api on the jsDelivr CDN)
# Free, no key, no rate limit. Each URL returns one whole collection in one
# JSON file. We download the same collection three times (Arabic / Urdu /
# English) and then join the rows together using the hadith number.
# ---------------------------------------------------------------------------
HADITH_BASE_URL = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/"

# The list of collections we ingest. "book_name" is what we show on screen.
HADITH_COLLECTIONS = [
    {
        "book_name": "Sahih Bukhari",
        "arabic": "ara-bukhari.json",
        "urdu": "urd-bukhari.json",
        "english": "eng-bukhari.json",
    },
    {
        "book_name": "Sahih Muslim",
        "arabic": "ara-muslim.json",
        "urdu": "urd-muslim.json",
        "english": "eng-muslim.json",
    },

    # -----------------------------------------------------------------------
    # WHY SUNAN ABU DAWUD IS HERE
    #
    # Bukhari and Muslim are graded Sahih in their entirety by scholarly
    # consensus, and the API returns an empty "grades" list for every one of
    # their ~15,000 hadiths. So with only those two books, EVERY row in the
    # database is "Sahih" - which means every grade badge is the same colour
    # and the "Show only Sahih & Hasan" filter has nothing to hide.
    #
    # Sunan Abu Dawud is graded hadith by hadith (roughly 3,900 Sahih,
    # 580 Hasan and 730 Da'if), so adding it makes the grading feature real
    # and demonstrable instead of decorative.
    #
    # To leave it out, simply delete this block and re-run ingest.py.
    # -----------------------------------------------------------------------
    {
        "book_name": "Sunan Abu Dawud",
        "arabic": "ara-abudawud.json",
        "urdu": "urd-abudawud.json",
        "english": "eng-abudawud.json",
    },
]

# If a listed edition file is missing, ingest.py checks this index file to
# find the correct (renamed) slug instead of failing silently.
HADITH_EDITIONS_INDEX = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions.json"

# ---------------------------------------------------------------------------
# NETWORK BEHAVIOUR (only used by ingest.py, never by the web app)
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 60      # give up on a single request after 60 seconds
MAX_RETRIES = 3           # try each download up to 3 times
POLITE_DELAY = 0.3        # seconds to wait between surah requests (be polite)


# ===========================================================================
# THE SAFETY CATCH
#
# This runs the moment config.py is imported, which happens before the web
# app can serve a single page. If the portal is on a real web host and either
# secret is still the value printed in this file, we stop everything here.
#
# Raising an exception looks dramatic, but the alternative is worse: a live
# admin page whose password anybody can read in the source code. Failing
# loudly at start-up is noticed and fixed in minutes; failing silently is
# noticed only after somebody has emptied your topic table.
#
# On your own laptop IS_PRODUCTION is False, so none of this ever fires and
# the project behaves exactly as it always has.
# ===========================================================================

def _describe_missing_settings():
    """Build the list of things the person deploying still has to set."""
    missing = []
    if USING_DEFAULT_PASSWORD:
        missing.append("PORTAL_ADMIN_PASSWORD")
    if USING_DEFAULT_SECRET_KEY:
        missing.append("PORTAL_SECRET_KEY")
    return missing


if IS_PRODUCTION:
    _missing = _describe_missing_settings()
    if _missing:
        # The message is built as a LIST OF LINES and then joined. Writing it
        # as one long run of quoted strings is a trap: Python glues adjacent
        # string literals together before it applies "*", so a line like
        #     "\n" "=" * 70
        # quietly becomes ("\n=") * 70 - seventy separate lines each holding a
        # single "=" - instead of one line of seventy "=" characters.
        _rule = "=" * 70
        _lines = [
            "",
            _rule,
            "REFUSING TO START: this portal is running on a web host but is",
            "still using the example secrets printed inside config.py.",
            "",
            "Anyone who can read config.py could log into /admin, and a known",
            "SECRET_KEY lets an attacker forge the admin cookie without even",
            "needing the password.",
            "",
            "Still to set: " + ", ".join(_missing),
            "",
            "Set them as environment variables on the host, then reload the",
            "web app. DEPLOY.md explains exactly where to put them.",
            "",
            "To generate a strong secret key, run:",
            '    python -c "import secrets; print(secrets.token_hex(32))"',
            _rule,
        ]
        raise RuntimeError("\n".join(_lines))
