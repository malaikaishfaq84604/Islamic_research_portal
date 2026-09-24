"""
ingest.py
---------
THE ONLY FILE IN THIS PROJECT THAT USES THE INTERNET.

Run it once:      python ingest.py

It downloads the whole Quran and two complete Hadith collections, stores them
in portal.db, creates the 8 Namaz topics, and links verses and hadiths to
those topics. After it finishes you can switch your Wi-Fi off forever - the
web app reads only from portal.db.

Everything uses "INSERT OR IGNORE", which means:
  * running this file twice does NOT create duplicates
  * if the download is interrupted half way, just run it again - it picks up
    where it left off because the rows already saved are skipped

Only free, keyless sources are used (see config.py for the exact URLs).
"""

import json
import re
import sys
import time

import requests

import config
import db
import mapping

# ---------------------------------------------------------------------------
# THE 8 TOPICS OF NAMAZ-E-NABWI (peace be upon him)
# These are the case study of the Final Year Project. Each tuple is
# (english name, urdu name, description).
# ---------------------------------------------------------------------------
TOPICS_SEED = [
    ("Niyyah (Intention)", "نیت", "The intention before starting prayer"),
    ("Takbir & Qayam (Standing)", "تکبیر و قیام", "Opening Takbir and the standing posture"),
    ("Qirat (Recitation)", "قرأت", "Recitation of Al-Fatiha and surahs"),
    ("Ruku (Bowing)", "رکوع", "The bowing posture and its supplications"),
    ("Sajdah (Prostration)", "سجدہ", "Prostration and its supplications"),
    ("Tashahhud (Sitting)", "تشہد", "The sitting and testimony"),
    ("Salam (Ending)", "سلام", "Concluding the prayer"),
    ("Sajdah Sahw (Forgetfulness)", "سجدہ سہو", "Prostration of forgetfulness"),
]

# ---------------------------------------------------------------------------
# EVERYDAY-LIFE TOPICS
#
# The 8 topics above are the Namaz-e-Nabwi case study. These 26 widen the
# portal so that ordinary questions - "khana", "zakat", "walidain", "sabr" -
# also land on a proper topic page instead of "No Results Found".
#
# The English name of each topic deliberately contains its canonical keyword
# from mapping.py (canonical "zakat" is inside "Zakat & Charity"), which is how
# one simple LIKE query in app.py finds the right card.
# ---------------------------------------------------------------------------
LIFE_TOPICS_SEED = [
    ("Zakat & Charity", "زکوٰۃ و صدقہ", "Obligatory zakah, voluntary charity and giving"),
    ("Fasting (Sawm)", "روزہ", "Fasting, Ramadan and its rulings"),
    ("Hajj & Umrah", "حج و عمرہ", "The pilgrimage to Makkah and its rites"),
    ("Food & Eating", "کھانا پینا", "Manners of eating and drinking"),
    ("Halal & Haram", "حلال و حرام", "What is lawful and what is forbidden"),
    ("Marriage & Family", "نکاح و خاندان", "Marriage, spouses and family life"),
    ("Parents & Kindness", "والدین", "The rights of parents and kindness to them"),
    ("Children & Upbringing", "اولاد", "Raising children and their rights"),
    ("Knowledge & Learning", "علم", "Seeking knowledge and teaching it"),
    ("Cleanliness & Purity", "طہارت", "Wudu, ghusl and cleanliness"),
    ("Honesty & Truthfulness", "سچائی", "Truthfulness, trust and avoiding lies"),
    ("Patience (Sabr)", "صبر", "Patience in hardship and perseverance"),
    ("Gratitude (Shukr)", "شکر", "Thankfulness to Allah for His blessings"),
    ("Repentance & Forgiveness", "توبہ و مغفرت", "Turning back to Allah and seeking pardon"),
    ("Dua & Remembrance", "دعا و ذکر", "Supplication and the remembrance of Allah"),
    ("Neighbours & Community", "پڑوسی", "Rights of neighbours, guests and hospitality"),
    ("Trade & Business", "تجارت", "Honest earning, buying and selling"),
    ("Justice & Fairness", "عدل و انصاف", "Justice, fairness and opposing oppression"),
    ("Death & the Hereafter", "موت و آخرت", "Death, the grave, Paradise and Hellfire"),
    ("Wealth & Interest (Riba)", "مال و سود", "Wealth, debt and the prohibition of interest"),
    ("Anger & Self-Control", "غصہ", "Restraining anger and controlling oneself"),
    ("Speech & Backbiting", "زبان و غیبت", "Guarding the tongue and avoiding backbiting"),
    ("Health & Illness", "صحت و بیماری", "Health, sickness, treatment and visiting the sick"),
    ("Travel", "سفر", "Rulings and manners of travelling"),
    ("Orphans & the Needy", "یتیم و مسکین", "Caring for orphans, the poor and the needy"),
    ("Modesty & Dress", "حیا و لباس", "Modesty, lowering the gaze and clothing"),
]

# ---------------------------------------------------------------------------
# SAFETY CHECK
# app.py answers a general "namaz" search using mapping.NAMAZ_TOPIC_NAMES.
# If somebody renames a topic here but forgets to rename it there, that search
# would quietly return fewer than 8 cards and nobody would notice. So we
# compare the two lists the moment this file is loaded and stop with a clear
# message if they no longer match.
# ---------------------------------------------------------------------------
_names_here = tuple(name for name, _urdu, _desc in TOPICS_SEED)
if _names_here != mapping.NAMAZ_TOPIC_NAMES:
    raise ValueError(
        "The 8 Namaz topic names in ingest.py no longer match "
        "mapping.NAMAZ_TOPIC_NAMES.\n"
        "  ingest.py : " + str(_names_here) + "\n"
        "  mapping.py: " + str(mapping.NAMAZ_TOPIC_NAMES) + "\n"
        "Make the two lists identical and try again."
    )

# Short nicknames so the tables below stay readable.
NIYYAH = "Niyyah (Intention)"
TAKBIR = "Takbir & Qayam (Standing)"
QIRAT = "Qirat (Recitation)"
RUKU = "Ruku (Bowing)"
SAJDAH = "Sajdah (Prostration)"
TASHAHHUD = "Tashahhud (Sitting)"
SALAM = "Salam (Ending)"
SAHW = "Sajdah Sahw (Forgetfulness)"

# "ALL" is a shortcut meaning "link this ayah to every one of the 8 topics".
ALL = "ALL"

# ---------------------------------------------------------------------------
# QURAN -> TOPIC LINKS  (hand-picked, hard-coded on purpose)
# Each entry is (surah_no, ayah_no, list_of_topics).
#
# Verses that command the prayer in GENERAL are tagged with ALL, so every one
# of the 8 topic pages opens with a "Divine Command" section. Verses that name
# a specific posture are tagged only to that posture.
#
# These were chosen by reading the verses - this is the "scholar curation"
# step of the project and is deliberately small and reviewable.
# ---------------------------------------------------------------------------
QURAN_TOPIC_LINKS = [
    (2, 43, [ALL, RUKU]),        # "...and bow with those who bow"
    (2, 45, [ALL]),              # "seek help through patience and prayer"
    (2, 110, [ALL]),             # "and establish prayer and give zakah"
    (2, 238, [ALL, TAKBIR]),     # "...and stand before Allah devoutly obedient"
    (4, 43, [NIYYAH, QIRAT]),    # "...until you know what you are saying"
    (4, 103, [ALL, SALAM]),      # "when you have completed the prayer, remember Allah"
    (5, 6, [NIYYAH, TAKBIR]),    # the verse of wudu - the preparation for prayer
    (11, 114, [ALL]),            # "establish prayer at the two ends of the day"
    (17, 78, [QIRAT, TAKBIR]),   # "...indeed, the recitation of dawn is ever witnessed"
    (17, 79, [QIRAT, TAKBIR]),   # "and from the night, pray with it as additional worship"
    (20, 14, [ALL]),             # "establish prayer for My remembrance"
    (22, 77, [RUKU, SAJDAH]),    # "bow and prostrate" - commands BOTH postures
    (23, 1, [ALL]),              # "successful indeed are the believers"
    (23, 2, [ALL]),              # "those who during their prayer are humbly submissive"
    (29, 45, [ALL, QIRAT]),      # "recite what has been revealed... and establish prayer"
    (48, 29, [RUKU, SAJDAH]),    # "you see them bowing and prostrating"
    (62, 9, [ALL]),              # "when the prayer is called on Friday, hasten"
    (70, 34, [ALL]),             # "and those who guard their prayer"
    (87, 14, [NIYYAH, TAKBIR]),  # "successful is he who purifies himself"
    (87, 15, [NIYYAH, TAKBIR]),  # "and mentions the name of his Lord and prays"
    (96, 19, [SAJDAH]),          # "but prostrate and draw near to Allah"
]

# ---------------------------------------------------------------------------
# HADITH -> TOPIC KEYWORDS
# We lower-case the English text of every hadith and check whether it contains
# any of these words. If it does, we link that hadith to that topic.
#
# This is a simple, honest keyword pass - not perfect. Bukhari and Muslim are
# prayer-heavy collections so words like "bow" are safe enough. Anything the
# keyword pass gets wrong can be fixed by hand on the /admin page.
# ---------------------------------------------------------------------------
HADITH_TOPIC_KEYWORDS = {
    NIYYAH: ["intention", "actions are by"],
    TAKBIR: ["takbir", "allahu akbar", "raised his hands", "standing in prayer"],
    QIRAT: ["fatiha", "recite", "recitation"],
    RUKU: ["bow", "ruku", "bowing"],
    SAJDAH: ["prostrat", "sujud", "sajdah", "forehead on the ground"],
    TASHAHHUD: ["tashahhud", "at-tahiyyat", "sitting in prayer"],
    SALAM: ["taslim", "salam to end", "right and left"],
    SAHW: ["forgetfulness", "sahw", "forgot in prayer", "added or omitted"],
}

# ---------------------------------------------------------------------------
# KEYWORDS FOR THE 26 EVERYDAY-LIFE TOPICS
#
# These are used to tag BOTH Qur'anic verses AND hadiths, by looking for the
# words inside the ENGLISH translation. Using the same table for both keeps
# the code short and means a topic behaves consistently in both sections.
#
# WHY THE VERSES ARE TAGGED BY KEYWORD RATHER THAN BY HAND:
# The 8 Namaz topics use a hand-picked list of verse references (see
# QURAN_TOPIC_LINKS above), because that is the graded case study of the
# project. For these 26 broader topics a hand-picked list would mean inventing
# hundreds of references from memory, and a wrong reference in a Qur'anic
# citation is a serious error. Matching on words that genuinely appear in the
# translation is verifiable: you can always read the verse and check.
#
# The matching is deliberately simple and will sometimes be too generous. The
# /admin page exists so a knowledgeable person can correct it.
# ---------------------------------------------------------------------------
LIFE_TOPIC_KEYWORDS = {
    "Zakat & Charity": ["zakah", "zakat", "charity", "alms", "sadaqah",
                        "spend in the way", "give in charity"],
    "Fasting (Sawm)": ["fasting", "fasts", "ramadan", "sawm", "break the fast"],
    "Hajj & Umrah": ["hajj", "pilgrimage", "umrah", "kaaba", "ka'bah",
                     "sacred house", "tawaf", "ihram", "arafat"],
    "Food & Eating": ["eat", "ate", "eating", "food", "drink", "meal",
                      "hungry", "hunger", "dates", "bread", "milk"],
    "Halal & Haram": ["lawful", "unlawful", "forbidden", "prohibited",
                      "wine", "intoxicant", "swine", "pork", "carrion"],
    "Marriage & Family": ["marriage", "marry", "married", "wife", "wives",
                          "husband", "divorce", "dowry", "mahr"],
    "Parents & Kindness": ["parents", "his mother", "your mother",
                           "his father", "your father", "kindness to parents"],
    "Children & Upbringing": ["children", "child", "his son", "daughter",
                              "offspring", "orphan child"],
    "Knowledge & Learning": ["knowledge", "learn", "learned", "teach",
                             "taught", "wisdom", "scholar"],
    "Cleanliness & Purity": ["ablution", "wudu", "ghusl", "purify",
                             "purification", "clean", "miswak", "impurity"],
    "Honesty & Truthfulness": ["truthful", "truthfulness", "honest",
                               "tells a lie", "lying", "falsehood",
                               "trustworthy", "betray"],
    "Patience (Sabr)": ["patience", "patient", "patiently", "persevere",
                        "steadfast", "endure"],
    "Gratitude (Shukr)": ["grateful", "gratitude", "thankful",
                          "give thanks", "praise be to allah"],
    "Repentance & Forgiveness": ["repent", "repentance", "forgive",
                                 "forgiveness", "pardon", "seek refuge",
                                 "his sins"],
    "Dua & Remembrance": ["supplication", "supplicate", "invoke",
                          "remembrance of allah", "call upon", "dua"],
    "Neighbours & Community": ["neighbour", "neighbor", "his guest",
                               "hospitality", "brotherhood"],
    "Trade & Business": ["trade", "business", "buying", "selling", "sells",
                         "market", "earn", "wages", "transaction"],
    "Justice & Fairness": ["justice", "with justice", "oppress",
                           "oppression", "wrongdoing", "witness", "judge"],
    "Death & the Hereafter": ["death", "dies", "died", "grave", "hereafter",
                              "paradise", "hellfire", "resurrection",
                              "day of judgement", "funeral"],
    "Wealth & Interest (Riba)": ["interest", "usury", "riba", "wealth",
                                 "debt", "loan", "borrow", "property"],
    "Anger & Self-Control": ["anger", "angry", "restrain", "rage"],
    "Speech & Backbiting": ["his tongue", "the tongue", "backbit", "slander",
                            "speaks", "speak good", "remain silent"],
    "Health & Illness": ["illness", "sick", "disease", "cure", "healing",
                         "medicine", "remedy", "visit the sick"],
    "Travel": ["travel", "traveller", "traveler", "journey", "wayfarer",
               "migration", "emigrat"],
    "Orphans & the Needy": ["orphan", "the poor", "needy", "beggar",
                            "poverty", "destitute"],
    "Modesty & Dress": ["modesty", "modest", "veil", "garment", "clothing",
                        "lower their gaze", "adornment", "shyness"],
}

# ---------------------------------------------------------------------------
# The 114 surah names, used only when we fall back to the CDN source (that
# source gives the verse text but not the surah names).
# ---------------------------------------------------------------------------
SURAH_NAMES = [
    "Al-Faatiha", "Al-Baqara", "Aal-i-Imraan", "An-Nisaa", "Al-Maaida",
    "Al-An'aam", "Al-A'raaf", "Al-Anfaal", "At-Tawba", "Yunus",
    "Hud", "Yusuf", "Ar-Ra'd", "Ibrahim", "Al-Hijr",
    "An-Nahl", "Al-Israa", "Al-Kahf", "Maryam", "Taa-Haa",
    "Al-Anbiyaa", "Al-Hajj", "Al-Muminoon", "An-Noor", "Al-Furqaan",
    "Ash-Shu'araa", "An-Naml", "Al-Qasas", "Al-Ankaboot", "Ar-Room",
    "Luqman", "As-Sajda", "Al-Ahzaab", "Saba", "Faatir",
    "Yaseen", "As-Saaffaat", "Saad", "Az-Zumar", "Ghafir",
    "Fussilat", "Ash-Shura", "Az-Zukhruf", "Ad-Dukhaan", "Al-Jaathiya",
    "Al-Ahqaf", "Muhammad", "Al-Fath", "Al-Hujuraat", "Qaaf",
    "Adh-Dhaariyat", "At-Tur", "An-Najm", "Al-Qamar", "Ar-Rahmaan",
    "Al-Waaqia", "Al-Hadid", "Al-Mujaadila", "Al-Hashr", "Al-Mumtahana",
    "As-Saff", "Al-Jumu'a", "Al-Munaafiqoon", "At-Taghaabun", "At-Talaaq",
    "At-Tahrim", "Al-Mulk", "Al-Qalam", "Al-Haaqqa", "Al-Ma'aarij",
    "Nooh", "Al-Jinn", "Al-Muzzammil", "Al-Muddaththir", "Al-Qiyaama",
    "Al-Insaan", "Al-Mursalaat", "An-Naba", "An-Naazi'aat", "Abasa",
    "At-Takwir", "Al-Infitaar", "Al-Mutaffifin", "Al-Inshiqaaq", "Al-Burooj",
    "At-Taariq", "Al-A'laa", "Al-Ghaashiya", "Al-Fajr", "Al-Balad",
    "Ash-Shams", "Al-Lail", "Ad-Dhuhaa", "Ash-Sharh", "At-Tin",
    "Al-Alaq", "Al-Qadr", "Al-Bayyina", "Az-Zalzala", "Al-Aadiyaat",
    "Al-Qaari'a", "At-Takaathur", "Al-Asr", "Al-Humaza", "Al-Fil",
    "Quraish", "Al-Maa'un", "Al-Kawthar", "Al-Kaafiroon", "An-Nasr",
    "Al-Masad", "Al-Ikhlaas", "Al-Falaq", "An-Naas",
]


# ===========================================================================
# SMALL HELPERS
# ===========================================================================

def clean_text(value):
    """
    Tidy up a piece of text that came from the internet.

    Some sources put an invisible "byte order mark" (﻿) at the front of
    the very first verse. It is not part of the Quran, it is a file marker,
    so we remove it. We also trim spaces from both ends.

    We do NOT touch anything else - every Arabic diacritic (harakat) is left
    exactly as received, because losing even one is unacceptable for sacred text.
    """
    if value is None:
        return None
    return str(value).replace("﻿", "").strip()


def download_json(url, description):
    """
    Download one URL and return the parsed JSON.

    Tries up to config.MAX_RETRIES times. After each failure it waits longer
    than the time before ("exponential backoff": 2s, then 4s, then 8s) so we
    do not hammer a server that is having a bad day.

    Returns None if every attempt failed - the caller decides what to do.
    """
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()   # turns a 404 / 500 into an exception
            # Force UTF-8 so Arabic and Urdu decode correctly on every machine.
            response.encoding = "utf-8"
            return response.json()
        except Exception as error:
            wait_seconds = 2 ** attempt
            print("   ! attempt " + str(attempt) + "/" + str(config.MAX_RETRIES)
                  + " failed for " + description + " (" + type(error).__name__ + ")")
            if attempt < config.MAX_RETRIES:
                print("     retrying in " + str(wait_seconds) + "s ...")
                time.sleep(wait_seconds)
    print("   X gave up on " + description)
    return None


def normalize_grade(grades_list, book_name):
    """
    Turn the messy "grades" list from the API into ONE simple word.

    The API gives something like:
        [{"name": "Al-Albani", "grade": "Sahih"}, ...]
    and quite often gives an empty list [].

    Our rules, checked in this order:
      1. any grade text contains "sahih"                 -> "Sahih"
      2. otherwise contains "hasan"                      -> "Hasan"
      3. otherwise contains "da'if" / "daif" / "weak"    -> "Da'if"
      4. list is empty AND book is Bukhari or Muslim     -> "Sahih"
         JUSTIFICATION: Sahih al-Bukhari and Sahih Muslim are accepted as
         authentic (sahih) in their entirety by scholarly consensus (ijma'),
         so an unlabelled hadith from these two books is graded Sahih.
      5. anything else                                   -> "Unknown"
    """
    # Join every grade string into one lower-case blob so we only search once.
    #
    # We read ONLY the "grade" value, never the "name" value. The name is the
    # scholar who gave the grade (Al-Albani, Zubair Ali Zai, ...), and some
    # scholars are actually called Hasan - reading the name would then grade
    # the hadith "Hasan" purely because of who assessed it.
    joined = ""
    if grades_list:
        for entry in grades_list:
            if isinstance(entry, dict):
                joined = joined + " " + str(entry.get("grade", ""))
            else:
                joined = joined + " " + str(entry)
    joined = joined.lower()

    if "sahih" in joined:
        return "Sahih"
    if "hasan" in joined:
        return "Hasan"
    if "da'if" in joined or "daif" in joined or "weak" in joined:
        return "Da'if"

    # Rule 4 - the consensus default described above.
    if not grades_list and book_name in ("Sahih Bukhari", "Sahih Muslim"):
        return "Sahih"

    return "Unknown"


def build_keyword_matcher(keywords):
    """
    Turn a topic's list of keywords into ONE compiled regular expression that
    matches any of them at the START of a word.

    WHY THIS IS NEEDED - a bug worth explaining in the viva:
    The obvious way to check a keyword is  if "eat" in text.  That is wrong,
    because "eat" also sits inside gr-EAT, d-EAT-h and def-EAT. Worse, "ate"
    sits inside n-arr-ATE-d, and EVERY hadith begins with "Narrated ...". That
    one mistake tagged 15,439 of the 20,427 hadiths as being about food.

    The fix is \\b, the "word boundary" marker. \\beat matches the START of a
    word only, so it still finds eat / eats / eating / eaten (we deliberately
    allow endings), but no longer finds great or defeat.

    Allowing the ending is on purpose: the keyword "prostrat" is meant to catch
    prostrate, prostrating and prostration all at once.

    All of a topic's keywords go into one pattern joined by | ("or"), so we
    test each hadith once per topic instead of once per keyword - which keeps
    the tagging fast even over 20,000 hadiths.
    """
    # re.escape makes characters like ( ) ' safe inside a pattern.
    escaped = [re.escape(word) for word in keywords]
    pattern = r"\b(?:" + "|".join(escaped) + r")"
    return re.compile(pattern, re.IGNORECASE)


def get_topic_ids(connection):
    """
    Read the topics table and return a dictionary:
        {"Ruku (Bowing)": 4, "Sajdah (Prostration)": 5, ...}
    so the tagging code can turn a topic name into its id quickly.
    """
    topic_ids = {}
    for row in connection.execute("SELECT topic_id, topic_name FROM topics"):
        topic_ids[row["topic_name"]] = row["topic_id"]
    return topic_ids


# ===========================================================================
# STEP 1 - TOPICS
# ===========================================================================

def seed_topics():
    """
    Insert the 8 Namaz topics AND the 26 everyday-life topics.
    INSERT OR IGNORE means running this again changes nothing, because
    topic_name is UNIQUE.
    """
    print("\n[1/5] Seeding topics ...")
    connection = db.get_connection()
    try:
        # The + joins the two lists into one, so we only write the loop once.
        for topic_name, urdu_name, description in TOPICS_SEED + LIFE_TOPICS_SEED:
            connection.execute(
                "INSERT OR IGNORE INTO topics (topic_name, urdu_name, description) "
                "VALUES (?, ?, ?)",
                (topic_name, urdu_name, description),
            )
        connection.commit()
        total = connection.execute("SELECT COUNT(*) AS c FROM topics").fetchone()["c"]
        print("      " + str(len(TOPICS_SEED)) + " Namaz topics + "
              + str(len(LIFE_TOPICS_SEED)) + " everyday-life topics")
        print("      topics in database: " + str(total))
    finally:
        connection.close()


# ===========================================================================
# STEP 2 - QURAN
# ===========================================================================

def get_stored_surah_numbers():
    """
    Return the set of surah numbers that are already saved in the database.

    Each surah is written and committed as one complete unit, so if a surah
    appears here at all, every one of its ayahs is present. This is what makes
    re-running ingest.py fast: finished surahs are simply skipped.
    """
    stored = set()
    for row in db.fetch_all("SELECT DISTINCT surah_no FROM quran"):
        stored.add(row["surah_no"])
    return stored


def ingest_quran_from_alquran_cloud(surah_numbers):
    """
    Download the listed surahs from AlQuran.cloud, one surah at a time.

    Each request returns THREE editions at once (Arabic, Urdu, English), so we
    only need one request per surah instead of three.

    surah_numbers - the list of surahs to fetch (usually the ones we do not
                    have yet, not always all 114)

    Returns the number of surahs that were downloaded successfully.
    """
    print("      source: AlQuran.cloud (primary)")
    successful_surahs = 0
    connection = db.get_connection()
    try:
        for surah_no in surah_numbers:
            url = config.QURAN_API_URL.format(surah=surah_no)
            payload = download_json(url, "surah " + str(surah_no))

            if payload is None or "data" not in payload:
                print("      Surah " + str(surah_no) + "/114  X skipped")
                continue

            editions = payload["data"]
            if len(editions) < 3:
                print("      Surah " + str(surah_no) + "/114  X incomplete data")
                continue

            # The three editions come back in the order we asked for them.
            arabic_edition, urdu_edition, english_edition = editions[0], editions[1], editions[2]
            surah_name = arabic_edition.get("englishName", "")

            # Walk the three ayah lists side by side using their position.
            for index in range(len(arabic_edition["ayahs"])):
                arabic_ayah = arabic_edition["ayahs"][index]
                ayah_no = arabic_ayah["numberInSurah"]

                arabic_text = clean_text(arabic_ayah["text"])
                urdu_text = clean_text(urdu_edition["ayahs"][index]["text"])
                english_text = clean_text(english_edition["ayahs"][index]["text"])

                connection.execute(
                    "INSERT OR IGNORE INTO quran "
                    "(surah_no, surah_name, ayah_no, arabic_text, urdu_text, english_text) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (surah_no, surah_name, ayah_no, arabic_text, urdu_text, english_text),
                )

            # Commit the whole surah in one go, so a surah is either fully
            # saved or not saved at all - never half saved.
            connection.commit()
            successful_surahs = successful_surahs + 1
            print("      Surah " + str(surah_no) + "/114 " + surah_name + " OK")

            # Be a polite guest on somebody else's free server.
            time.sleep(config.POLITE_DELAY)
    finally:
        connection.close()

    return successful_surahs


def ingest_quran_from_cdn_fallback():
    """
    Backup plan: download the WHOLE Quran in three files from the jsDelivr CDN.

    Each file looks like:
        {"quran": [{"chapter": 1, "verse": 1, "text": "..."}, ...]}

    We build a lookup keyed by (chapter, verse) for Urdu and English, then walk
    the Arabic list and write one row per ayah.

    Returns how many ayah rows we managed to insert, or 0 on total failure.
    """
    print("      source: jsDelivr CDN (fallback)")

    arabic_payload = download_json(config.QURAN_FALLBACK_URLS["arabic"], "fallback Arabic Quran")
    urdu_payload = download_json(config.QURAN_FALLBACK_URLS["urdu"], "fallback Urdu Quran")
    english_payload = download_json(config.QURAN_FALLBACK_URLS["english"], "fallback English Quran")

    if not arabic_payload:
        print("      X fallback Arabic download failed - cannot continue")
        return 0

    def build_lookup(payload):
        """Turn a fallback payload into {(chapter, verse): text}."""
        lookup = {}
        if not payload:
            return lookup
        for verse in payload.get("quran", []):
            lookup[(verse["chapter"], verse["verse"])] = clean_text(verse["text"])
        return lookup

    urdu_lookup = build_lookup(urdu_payload)
    english_lookup = build_lookup(english_payload)

    inserted = 0
    connection = db.get_connection()
    try:
        for verse in arabic_payload.get("quran", []):
            surah_no = verse["chapter"]
            ayah_no = verse["verse"]
            surah_name = SURAH_NAMES[surah_no - 1] if 1 <= surah_no <= 114 else ""

            connection.execute(
                "INSERT OR IGNORE INTO quran "
                "(surah_no, surah_name, ayah_no, arabic_text, urdu_text, english_text) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    surah_no,
                    surah_name,
                    ayah_no,
                    clean_text(verse["text"]),
                    urdu_lookup.get((surah_no, ayah_no)),
                    english_lookup.get((surah_no, ayah_no)),
                ),
            )
            inserted = inserted + 1

        connection.commit()
    finally:
        connection.close()

    print("      fallback processed " + str(inserted) + " ayahs")
    return inserted


def get_missing_surah_numbers():
    """
    Work out which of the 114 surahs are still not in the database.
    Returns a sorted list, empty when the Quran is complete.
    """
    stored = get_stored_surah_numbers()
    return [n for n in range(1, config.TOTAL_SURAHS + 1) if n not in stored]


def ingest_quran():
    """
    Fill the quran table, in three passes, so a dropped connection can never
    leave the Quran permanently incomplete:

      PASS 1  Download every surah we do not already have.
              (Surahs already saved are skipped, so a re-run is quick.)

      PASS 2  REPAIR. A short network glitch can make one or two surahs fail
              even after their 3 retries. So we simply look at what is still
              missing and try those few again.

      PASS 3  FALLBACK. If anything is STILL missing, we switch to the
              jsDelivr CDN, which serves the whole Quran in one file. Because
              every insert is INSERT OR IGNORE, this only fills the gaps and
              never touches the verses we already have.

    The source actually used is printed at each step.
    """
    print("\n[2/5] Downloading the Quran (114 surahs, 6236 ayahs) ...")

    # ----- PASS 1 -----------------------------------------------------------
    already_have = get_stored_surah_numbers()
    if already_have:
        print("      " + str(len(already_have))
              + " surah(s) are already saved and will be skipped.")

    to_download = get_missing_surah_numbers()
    if to_download:
        try:
            ingest_quran_from_alquran_cloud(to_download)
        except Exception as error:
            print("      ! primary source crashed: "
                  + type(error).__name__ + " - " + str(error))
    else:
        print("      Nothing to download - the Quran is already complete.")

    # ----- PASS 2: repair whatever failed -----------------------------------
    missing = get_missing_surah_numbers()
    if missing:
        print("\n      REPAIR PASS: " + str(len(missing))
              + " surah(s) failed and will be retried: " + str(missing))
        try:
            ingest_quran_from_alquran_cloud(missing)
        except Exception as error:
            print("      ! repair pass crashed: "
                  + type(error).__name__ + " - " + str(error))

    # ----- PASS 3: fall back to the CDN for anything still missing ----------
    missing = get_missing_surah_numbers()
    if missing:
        print("\n      Still missing " + str(len(missing)) + " surah(s): "
              + str(missing))
        print("      Switching to the fallback source to fill the gaps ...")
        try:
            ingest_quran_from_cdn_fallback()
        except Exception as error:
            print("      ! fallback source crashed: "
                  + type(error).__name__ + " - " + str(error))

    # ----- report -----------------------------------------------------------
    total = db.count_rows("quran")
    missing = get_missing_surah_numbers()

    if missing:
        print("      WARNING - these surahs are still missing: " + str(missing))
        print("      Check your internet connection and run this file again.")
    print("      DONE - quran table now holds " + str(total) + " ayahs"
          + (" (complete)" if total == 6236 else ""))
    return total


# ===========================================================================
# STEP 3 - HADITH
# ===========================================================================

def build_hadith_lookup(payload):
    """
    Turn one downloaded collection into a dictionary keyed by hadith number:
        {"735": {"text": "...", "grades": [...]}, ...}

    We store the key as TEXT because a few hadith numbers are not whole
    numbers (for example "1.1"), and text works for every case.
    """
    lookup = {}
    if not payload:
        return lookup
    for hadith in payload.get("hadiths", []):
        number = str(hadith.get("hadithnumber", "")).strip()
        if number:
            lookup[number] = hadith
    return lookup


def ingest_one_collection(collection):
    """
    Download and store ONE hadith collection (for example Sahih Bukhari).

    Three files are downloaded - Arabic, Urdu and English - and then joined
    together by hadith number, so one database row holds all three languages.

    Returns how many rows were written for this collection.
    """
    book_name = collection["book_name"]
    print("\n      --- " + book_name + " ---")

    english_payload = download_json(
        config.HADITH_BASE_URL + collection["english"], book_name + " (English)")
    arabic_payload = download_json(
        config.HADITH_BASE_URL + collection["arabic"], book_name + " (Arabic)")
    urdu_payload = download_json(
        config.HADITH_BASE_URL + collection["urdu"], book_name + " (Urdu)")

    if not english_payload and not arabic_payload:
        print("      X could not download " + book_name + " - skipping it")
        return 0

    english_lookup = build_hadith_lookup(english_payload)
    arabic_lookup = build_hadith_lookup(arabic_payload)
    urdu_lookup = build_hadith_lookup(urdu_payload)

    print("      downloaded: " + str(len(arabic_lookup)) + " Arabic, "
          + str(len(urdu_lookup)) + " Urdu, " + str(len(english_lookup)) + " English")

    # Collect every hadith number that appears in ANY language, so we never
    # lose a hadith just because one translation is missing it.
    all_numbers = set(english_lookup.keys()) | set(arabic_lookup.keys()) | set(urdu_lookup.keys())

    written = 0
    connection = db.get_connection()
    try:
        for number in all_numbers:
            english_entry = english_lookup.get(number, {})
            arabic_entry = arabic_lookup.get(number, {})
            urdu_entry = urdu_lookup.get(number, {})

            # The grade information is most complete in the English edition;
            # if it is missing there we try the Arabic one.
            grades_list = english_entry.get("grades") or arabic_entry.get("grades") or []
            grade = normalize_grade(grades_list, book_name)

            connection.execute(
                "INSERT OR IGNORE INTO hadith "
                "(book_name, hadith_no, arabic_text, urdu_text, english_text, grade) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    book_name,
                    number,
                    clean_text(arabic_entry.get("text")),
                    clean_text(urdu_entry.get("text")),
                    clean_text(english_entry.get("text")),
                    grade,
                ),
            )
            written = written + 1

        connection.commit()
    finally:
        connection.close()

    print("      stored " + str(written) + " hadiths from " + book_name)
    return written


def ingest_hadith():
    """
    Fill the hadith table with every collection listed in config.py
    (Sahih Bukhari and Sahih Muslim - about 15,000 hadiths in total).
    """
    print("\n[3/5] Downloading Hadith collections ...")

    for collection in config.HADITH_COLLECTIONS:
        try:
            ingest_one_collection(collection)
        except Exception as error:
            print("      ! " + collection["book_name"] + " failed: "
                  + type(error).__name__ + " - " + str(error))

    total = db.count_rows("hadith")
    print("\n      DONE - hadith table now holds " + str(total) + " hadiths")
    return total


# ===========================================================================
# STEP 4 - LINK QURAN VERSES TO TOPICS
# ===========================================================================

def tag_quran_topics():
    """
    Create the rows in quran_topics using the hand-picked QURAN_TOPIC_LINKS
    table at the top of this file.
    """
    print("\n[4/5] Linking Quranic verses to topics ...")

    # Wipe the old links first and build them again from scratch.
    #
    # WHY: every insert below is INSERT OR IGNORE, which can only ADD links,
    # never remove one. So if a keyword is later corrected, the links it
    # wrongly created before would stay in the database forever. Clearing
    # first means the tagging rules in this file are always the single source
    # of truth.
    #
    # NOTE FOR THE ADMIN: this also clears links you attached by hand on the
    # /admin page, so re-do any manual corrections after a full re-ingest.
    db.execute("DELETE FROM quran_topics")

    connection = db.get_connection()
    try:
        topic_ids = get_topic_ids(connection)
        every_topic_name = [name for name, _urdu, _desc in TOPICS_SEED]
        links_made = 0
        missing_verses = 0

        for surah_no, ayah_no, topic_names in QURAN_TOPIC_LINKS:
            # Find the database id of this ayah.
            row = connection.execute(
                "SELECT quran_id FROM quran WHERE surah_no = ? AND ayah_no = ?",
                (surah_no, ayah_no),
            ).fetchone()

            if row is None:
                missing_verses = missing_verses + 1
                print("      ! verse " + str(surah_no) + ":" + str(ayah_no)
                      + " is not in the database yet - skipped")
                continue

            # Expand the "ALL" shortcut into the 8 real topic names.
            expanded = []
            for name in topic_names:
                if name == ALL:
                    expanded.extend(every_topic_name)
                else:
                    expanded.append(name)

            for topic_name in expanded:
                topic_id = topic_ids.get(topic_name)
                if topic_id is None:
                    continue
                connection.execute(
                    "INSERT OR IGNORE INTO quran_topics (quran_id, topic_id) VALUES (?, ?)",
                    (row["quran_id"], topic_id),
                )
                links_made = links_made + 1

        connection.commit()
        hand_picked_total = connection.execute(
            "SELECT COUNT(*) AS c FROM quran_topics").fetchone()["c"]
        print("      hand-picked verse links: " + str(hand_picked_total)
              + " (missing verses: " + str(missing_verses) + ")")
    finally:
        connection.close()

    # Now the keyword pass for the 26 everyday-life topics.
    tag_quran_by_keyword()

    total = db.count_rows("quran_topics")
    print("      verse-to-topic links in database: " + str(total))
    return total


def tag_quran_by_keyword():
    """
    Link Qur'anic verses to the everyday-life topics by looking for each
    topic's keywords inside the ENGLISH translation of the verse.

    Exactly the same idea as the hadith tagging - read the text, lower-case
    it, and if it contains one of the topic's words, make the link.
    """
    print("      keyword-tagging verses to the everyday-life topics ...")

    connection = db.get_connection()
    try:
        topic_ids = get_topic_ids(connection)
        per_topic_counts = {}

        # Build each topic's matcher once, before the loop over the verses.
        matchers = {}
        for topic_name, keywords in LIFE_TOPIC_KEYWORDS.items():
            matchers[topic_name] = build_keyword_matcher(keywords)

        rows = connection.execute(
            "SELECT quran_id, english_text FROM quran WHERE english_text IS NOT NULL"
        ).fetchall()

        for row in rows:
            text = row["english_text"]

            for topic_name, matcher in matchers.items():
                topic_id = topic_ids.get(topic_name)
                if topic_id is None:
                    continue

                # Does this verse contain ANY keyword for this topic?
                if matcher.search(text):
                    connection.execute(
                        "INSERT OR IGNORE INTO quran_topics (quran_id, topic_id) "
                        "VALUES (?, ?)",
                        (row["quran_id"], topic_id),
                    )
                    per_topic_counts[topic_name] = \
                        per_topic_counts.get(topic_name, 0) + 1

        connection.commit()

        print("      per-topic verse counts:")
        for topic_name, _urdu, _desc in LIFE_TOPICS_SEED:
            print("        " + topic_name.ljust(28)
                  + str(per_topic_counts.get(topic_name, 0)))
    finally:
        connection.close()


# ===========================================================================
# STEP 5 - LINK HADITHS TO TOPICS
# ===========================================================================

def tag_hadith_topics():
    """
    Read every hadith's English text, lower-case it, and link it to a topic
    whenever the text contains one of that topic's keywords.

    This runs entirely offline against the database - no internet needed.
    """
    print("\n[5/5] Auto-tagging hadiths to topics by keyword ...")

    # Same reasoning as in tag_quran_topics(): clear the old links so the
    # keyword tables in this file are the single source of truth.
    db.execute("DELETE FROM hadith_topics")

    connection = db.get_connection()
    try:
        topic_ids = get_topic_ids(connection)

        # One combined table: the 8 Namaz topics plus the 26 life topics.
        # {**a, **b} makes a new dictionary containing the entries of both.
        all_keywords = {**HADITH_TOPIC_KEYWORDS, **LIFE_TOPIC_KEYWORDS}

        # Build each topic's matcher once, before the loop over the hadiths.
        matchers = {}
        for topic_name, keywords in all_keywords.items():
            matchers[topic_name] = build_keyword_matcher(keywords)

        # Count how many hadiths each topic picked up, for the report at the end.
        per_topic_counts = {}
        for topic_name in topic_ids:
            per_topic_counts[topic_name] = 0

        rows = connection.execute(
            "SELECT hadith_id, english_text FROM hadith WHERE english_text IS NOT NULL"
        ).fetchall()

        for row in rows:
            text = row["english_text"]

            for topic_name, matcher in matchers.items():
                topic_id = topic_ids.get(topic_name)
                if topic_id is None:
                    continue

                # Does the hadith text contain ANY keyword for this topic?
                if matcher.search(text):
                    connection.execute(
                        "INSERT OR IGNORE INTO hadith_topics (hadith_id, topic_id) "
                        "VALUES (?, ?)",
                        (row["hadith_id"], topic_id),
                    )
                    per_topic_counts[topic_name] = per_topic_counts[topic_name] + 1

        connection.commit()

        print("      per-topic hadith counts:")
        for topic_name, _urdu, _desc in TOPICS_SEED + LIFE_TOPICS_SEED:
            print("        " + topic_name.ljust(30)
                  + str(per_topic_counts.get(topic_name, 0)))

        total = connection.execute(
            "SELECT COUNT(*) AS c FROM hadith_topics").fetchone()["c"]
        print("      hadith-to-topic links in database: " + str(total))
        return total
    finally:
        connection.close()


# ===========================================================================
# THE MAIN PROGRAM
# ===========================================================================

def print_summary():
    """Print the final row counts so the student can screenshot them."""
    print("\n" + "=" * 60)
    print("FINAL DATABASE SUMMARY")
    print("=" * 60)
    print("  Quran ayahs        : " + str(db.count_rows("quran")))
    print("  Hadiths            : " + str(db.count_rows("hadith")))
    print("  Topics             : " + str(db.count_rows("topics")))
    print("  Verse-topic links  : " + str(db.count_rows("quran_topics")))
    print("  Hadith-topic links : " + str(db.count_rows("hadith_topics")))
    print("  Database file      : " + config.DB_PATH)
    print("=" * 60)
    print("You can now switch the internet OFF and run:  python app.py")


def main():
    """
    Run the whole ingestion in order:
      schema -> topics -> quran -> hadith -> verse tagging -> hadith tagging
    """
    print("=" * 60)
    print("ISLAMIC RESEARCH PORTAL - DATA INGESTION")
    print("This needs the internet ONCE. It takes a few minutes.")
    print("Safe to stop and re-run: nothing gets duplicated.")
    print("=" * 60)

    print("\n[0/5] Creating database tables (if they do not exist) ...")
    db.create_schema()
    print("      schema ready at " + config.DB_PATH)

    seed_topics()
    ingest_quran()
    ingest_hadith()
    tag_quran_topics()
    tag_hadith_topics()
    print_summary()


# This "if" means: only run main() when the file is executed directly
# (python ingest.py). If another file imports ingest.py, nothing runs.
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # The student pressed Ctrl+C. Exit politely instead of showing a
        # frightening red stack trace.
        print("\n\nInterrupted by user. Everything downloaded so far is saved.")
        print("Just run 'python ingest.py' again to continue.")
        sys.exit(1)
