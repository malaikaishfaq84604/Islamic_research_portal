"""
mapping.py
----------
This file solves TWO problems.

PROBLEM 1 - people spell the same Islamic term in many different ways.
    A user might type "Namaz", "namaaz", "salat", "salah", "prayer" or "نماز".
    All six mean the same thing. SEMANTIC_MAP turns any of them into ONE
    canonical word, so the rest of the program only has to understand one.

PROBLEM 2 - the canonical word is not always the word used in the English
    translation of the Qur'an.
    Someone searching "zakat" finds nothing by text, because the Sahih
    International translation spells it "zakah". SEARCH_VARIANTS fixes this by
    giving each canonical word a small list of spellings to actually look for
    in the text.

Both are plain Python dictionaries - no AI, no machine learning, just lookup
tables. Simple enough to explain in a viva, and they work completely offline.
"""

# ===========================================================================
# 1. THE SYNONYM TABLE:  what the user typed  ->  our canonical word
# ---------------------------------------------------------------------------
# Keys are written in lower case (normalize() lower-cases the input first).
# Urdu keys are written in Urdu script.
#
# IMPORTANT DESIGN NOTE: each canonical word on the right is also a word that
# appears in the matching topic's English name (canonical "zakat" matches the
# topic "Zakat & Charity"). That is what lets one simple LIKE query in app.py
# find the right topic card without any extra configuration.
# ===========================================================================
SEMANTIC_MAP = {

    # ---------------------------------------------------------------- SALAH
    "نماز": "salah", "نماز نبوی": "salah", "صلاۃ": "salah",
    "namaz": "salah", "namaaz": "salah", "namaz e nabwi": "salah",
    "namaz-e-nabwi": "salah", "salat": "salah", "salaat": "salah",
    "salah": "salah", "prayer": "salah", "prayers": "salah",
    "worship": "salah",

    # --------------------------------------------- THE 8 PARTS OF THE PRAYER
    "نیت": "niyyah", "niyat": "niyyah", "niyyah": "niyyah",
    "niyah": "niyyah", "neeyat": "niyyah", "intention": "niyyah",

    "تکبیر": "takbir", "takbir": "takbir", "takbeer": "takbir",
    "takbir e tahrima": "takbir", "allahu akbar": "takbir",

    "قیام": "qayam", "qayam": "qayam", "qiyam": "qayam",
    "qiyaam": "qayam", "standing": "qayam",

    "قرأت": "qirat", "قرات": "qirat", "qirat": "qirat", "qiraat": "qirat",
    "qirah": "qirat", "recitation": "qirat", "recite": "qirat",
    "fatiha": "qirat", "surah fatiha": "qirat",

    "رکوع": "ruku", "ruku": "ruku", "rukoo": "ruku", "rukuh": "ruku",
    "rukooh": "ruku", "bowing": "ruku", "bow": "ruku",

    "سجدہ": "sajdah", "سجود": "sajdah", "sajda": "sajdah",
    "sajdah": "sajdah", "sajood": "sajdah", "sujood": "sajdah",
    "sujud": "sajdah", "prostration": "sajdah", "prostrate": "sajdah",

    "تشہد": "tashahhud", "tashahud": "tashahhud", "tashahhud": "tashahhud",
    "attahiyat": "tashahhud", "at-tahiyyat": "tashahhud",
    "sitting": "tashahhud",

    "سلام": "salam", "salam": "salam", "salaam": "salam",
    "taslim": "salam", "ending prayer": "salam",

    "سجدہ سہو": "sajdah sahw", "sajda sahw": "sajdah sahw",
    "sajdah sahw": "sajdah sahw", "sahw": "sajdah sahw",
    "forgetfulness": "sajdah sahw", "forgot": "sajdah sahw",

    # ------------------------------------------------------- ZAKAT & CHARITY
    "زکوٰۃ": "zakat", "زکوة": "zakat", "زکات": "zakat", "صدقہ": "zakat",
    "خیرات": "zakat", "zakat": "zakat", "zakah": "zakat", "zakaat": "zakat",
    "sadqa": "zakat", "sadaqah": "zakat", "khairat": "zakat",
    "charity": "zakat", "alms": "zakat", "donation": "zakat",
    "giving": "zakat",

    # --------------------------------------------------------------- FASTING
    "روزہ": "fasting", "روزے": "fasting", "رمضان": "fasting",
    "roza": "fasting", "rozay": "fasting", "sawm": "fasting",
    "saum": "fasting", "ramadan": "fasting", "ramzan": "fasting",
    "fast": "fasting", "fasting": "fasting", "iftar": "fasting",
    "sehri": "fasting",

    # ---------------------------------------------------------- HAJJ & UMRAH
    "حج": "hajj", "عمرہ": "hajj", "کعبہ": "hajj",
    "hajj": "hajj", "haj": "hajj", "umrah": "hajj", "umra": "hajj",
    "pilgrimage": "hajj", "kaaba": "hajj", "makkah": "hajj",
    "mecca": "hajj", "tawaf": "hajj",

    # ---------------------------------------------------------- FOOD! EATING
    "کھانا": "food", "کھانے": "food", "پینا": "food", "غذا": "food",
    "khana": "food", "khaana": "food", "peena": "food", "taam": "food",
    "food": "food", "eating": "food", "eat": "food", "drink": "food",
    "drinking": "food", "meal": "food", "hunger": "food",

    # ---------------------------------------------------------- HALAL! HARAM
    "حلال": "halal", "حرام": "halal", "شراب": "halal",
    "halal": "halal", "haram": "halal", "haraam": "halal",
    "lawful": "halal", "unlawful": "halal", "forbidden": "halal",
    "permissible": "halal", "sharab": "halal", "alcohol": "halal",
    "wine": "halal", "intoxicant": "halal", "pork": "halal",

    # ------------------------------------------------------ MARRIAGE! FAMILY
    "نکاح": "marriage", "شادی": "marriage", "بیوی": "marriage",
    "شوہر": "marriage", "طلاق": "marriage",
    "nikah": "marriage", "nikkah": "marriage", "shadi": "marriage",
    "marriage": "marriage", "marry": "marriage", "wedding": "marriage",
    "wife": "marriage", "husband": "marriage", "spouse": "marriage",
    "biwi": "marriage", "shohar": "marriage", "talaq": "marriage",
    "divorce": "marriage", "family": "marriage",

    # -------------------------------------------------------------- PARENTS
    "والدین": "parents", "ماں": "parents", "باپ": "parents",
    "ماں باپ": "parents",
    "walidain": "parents", "maa": "parents", "baap": "parents",
    "ammi": "parents", "abbu": "parents", "parents": "parents",
    "parent": "parents", "mother": "parents", "father": "parents",
    "mom": "parents", "dad": "parents",

    # -------------------------------------------------------------- CHILDREN
    "اولاد": "children", "بچے": "children", "بچہ": "children",
    "aulad": "children", "bachay": "children", "bacha": "children",
    "children": "children", "child": "children", "son": "children",
    "daughter": "children", "kids": "children", "upbringing": "children",

    # ------------------------------------------------------------- KNOWLEDGE
    "علم": "knowledge", "تعلیم": "knowledge", "پڑھائی": "knowledge",
    "ilm": "knowledge", "taleem": "knowledge", "parhai": "knowledge",
    "knowledge": "knowledge", "learning": "knowledge", "study": "knowledge",
    "education": "knowledge", "teach": "knowledge", "scholar": "knowledge",
    "wisdom": "knowledge",

    # ----------------------------------------------------------- CLEANLINESS
    "طہارت": "cleanliness", "پاکی": "cleanliness", "وضو": "cleanliness",
    "غسل": "cleanliness", "صفائی": "cleanliness",
    "taharat": "cleanliness", "paki": "cleanliness", "wudu": "cleanliness",
    "wuzu": "cleanliness", "ablution": "cleanliness", "ghusl": "cleanliness",
    "safai": "cleanliness", "cleanliness": "cleanliness",
    "clean": "cleanliness", "purity": "cleanliness", "pure": "cleanliness",
    "miswak": "cleanliness",

    # --------------------------------------------------------------- HONESTY
    "سچائی": "honesty", "سچ": "honesty", "جھوٹ": "honesty",
    "امانت": "honesty", "دیانت": "honesty",
    "sach": "honesty", "sachai": "honesty", "jhoot": "honesty",
    "amanat": "honesty", "honesty": "honesty", "honest": "honesty",
    "truth": "honesty", "truthful": "honesty", "lie": "honesty",
    "lying": "honesty", "trust": "honesty", "trustworthy": "honesty",

    # -------------------------------------------------------------- PATIENCE
    "صبر": "patience", "sabr": "patience", "saber": "patience",
    "patience": "patience", "patient": "patience",
    "perseverance": "patience", "endurance": "patience",
    "hardship": "patience", "difficulty": "patience", "trial": "patience",

    # ------------------------------------------------------------- GRATITUDE
    "شکر": "gratitude", "الحمدللہ": "gratitude",
    "shukr": "gratitude", "shukar": "gratitude", "alhamdulillah": "gratitude",
    "gratitude": "gratitude", "grateful": "gratitude",
    "thankful": "gratitude", "thanks": "gratitude", "blessing": "gratitude",

    # ------------------------------------------------------------ REPENTANCE
    "توبہ": "repentance", "استغفار": "repentance", "معافی": "repentance",
    "گناہ": "repentance",
    "tauba": "repentance", "tawba": "repentance",
    "istighfar": "repentance", "maafi": "repentance", "gunah": "repentance",
    "repentance": "repentance", "repent": "repentance", "sin": "repentance",
    "forgiveness": "repentance", "forgive": "repentance",
    "mercy": "repentance",

    # ------------------------------------------------------ DUA! REMEMBRANCE
    "دعا": "dua", "ذکر": "dua", "تسبیح": "dua",
    "dua": "dua", "duaa": "dua", "zikr": "dua", "dhikr": "dua",
    "tasbeeh": "dua", "supplication": "dua", "remembrance": "dua",
    "invocation": "dua",

    # ------------------------------------------------------------- NEIGHBOUR
    "پڑوسی": "neighbours", "ہمسایہ": "neighbours",
    "parosi": "neighbours", "hamsaya": "neighbours",
    "neighbour": "neighbours", "neighbours": "neighbours",
    "neighbor": "neighbours", "neighbors": "neighbours",
    "community": "neighbours", "guest": "neighbours",
    "hospitality": "neighbours",

    # ------------------------------------------------------- TRADE! BUSINESS
    "تجارت": "trade", "کاروبار": "trade", "خرید": "trade",
    "tijarat": "trade", "karobar": "trade", "trade": "trade",
    "business": "trade", "trading": "trade", "buy": "trade",
    "sell": "trade", "selling": "trade", "market": "trade",
    "earning": "trade", "livelihood": "trade", "work": "trade",

    # --------------------------------------------------------------- JUSTICE
    "عدل": "justice", "انصاف": "justice", "ظلم": "justice",
    "adl": "justice", "insaf": "justice", "zulm": "justice",
    "justice": "justice", "just": "justice", "fair": "justice",
    "fairness": "justice", "oppression": "justice", "injustice": "justice",
    "rights": "justice",

    # ---------------------------------------------------- DEATH! REAFTERLIFE
    "موت": "death", "آخرت": "death", "قیامت": "death", "جنت": "death",
    "جہنم": "death", "قبر": "death",
    "maut": "death", "akhirat": "death", "qayamat": "death",
    "jannat": "death", "jahannam": "death", "qabr": "death",
    "death": "death", "die": "death", "grave": "death",
    "hereafter": "death", "paradise": "death", "hell": "death",
    "resurrection": "death", "judgement": "death", "funeral": "death",

    # ------------------------------------------------------- WEALTH! INTEREST
    "سود": "riba", "مال": "riba", "دولت": "riba", "قرض": "riba",
    "sood": "riba", "riba": "riba", "maal": "riba", "daulat": "riba",
    "qarz": "riba", "interest": "riba", "usury": "riba",
    "wealth": "riba", "money": "riba", "rich": "riba", "debt": "riba",
    "loan": "riba",

    # ----------------------------------------------------------------- ANGER
    "غصہ": "anger", "ghussa": "anger", "gussa": "anger",
    "anger": "anger", "angry": "anger", "rage": "anger",
    "self control": "anger", "temper": "anger",

    # -------------------------------------------------------- SPEECH! TONGUE
    "زبان": "speech", "غیبت": "speech", "چغلی": "speech",
    "zaban": "speech", "gheebat": "speech", "ghibah": "speech",
    "chugli": "speech", "speech": "speech", "tongue": "speech",
    "backbiting": "speech", "gossip": "speech", "slander": "speech",
    "words": "speech", "silence": "speech",

    # ---------------------------------------------------------------- HEALTH
    "صحت": "health", "بیماری": "health", "علاج": "health",
    "sehat": "health", "bimari": "health", "ilaj": "health",
    "health": "health", "healthy": "health", "illness": "health",
    "sick": "health", "sickness": "health", "disease": "health",
    "medicine": "health", "cure": "health", "healing": "health",

    # ---------------------------------------------------------------- TRAVEL
    "سفر": "travel", "safar": "travel", "travel": "travel",
    "travelling": "travel", "traveler": "travel", "journey": "travel",
    "migration": "travel", "hijrah": "travel",

    # -------------------------------------------------------- ORPHANS! NEEDY
    "یتیم": "orphans", "مسکین": "orphans", "غریب": "orphans",
    "yateem": "orphans", "miskeen": "orphans", "ghareeb": "orphans",
    "orphan": "orphans", "orphans": "orphans", "poor": "orphans",
    "needy": "orphans", "beggar": "orphans", "poverty": "orphans",

    # -------------------------------------------------------- MODESTY! DRESS
    "حیا": "modesty", "پردہ": "modesty", "لباس": "modesty",
    "حجاب": "modesty",
    "haya": "modesty", "parda": "modesty", "libas": "modesty",
    "hijab": "modesty", "modesty": "modesty", "modest": "modesty",
    "veil": "modesty", "dress": "modesty", "clothing": "modesty",
    "shame": "modesty",
}


# ===========================================================================
# 2. SEARCH VARIANTS:  canonical word  ->  spellings to look for in the TEXT
# ---------------------------------------------------------------------------
# The canonical word is not always the word the translator used. Searching the
# text for "zakat" finds nothing, because Sahih International writes "zakah".
#
# So for every canonical word we keep a short list of spellings to search for.
# app.py looks for ALL of them, which greatly improves what the user finds.
#
# A canonical word that is not listed here simply searches for itself.
# ===========================================================================
SEARCH_VARIANTS = {
    "salah": ["prayer", "salah"],
    "niyyah": ["intention"],
    "takbir": ["takbir", "allahu akbar"],
    "qayam": ["standing", "stood"],
    "qirat": ["recite", "recitation", "fatihah", "fatiha"],
    "ruku": ["bow", "ruku"],
    "sajdah": ["prostrat", "sujud"],
    "tashahhud": ["tashahhud", "tahiyyat"],
    "salam": ["salam", "taslim"],
    "sajdah sahw": ["forgetfulness", "sahw", "forgot"],

    "zakat": ["zakah", "zakat", "charity", "alms", "sadaqah"],
    "fasting": ["fast", "fasting", "ramadan", "sawm"],
    "hajj": ["hajj", "pilgrimage", "umrah", "kaaba", "mecca", "makkah"],
    "food": ["food", "eat", "ate", "drink", "meal", "hungry", "hunger"],
    "halal": ["lawful", "unlawful", "forbidden", "wine", "intoxicant",
              "swine", "pork", "halal", "haram"],
    "marriage": ["marriage", "marry", "married", "wife", "wives", "husband",
                 "divorce", "nikah"],
    "parents": ["parents", "mother", "father", "kindness to parents"],
    "children": ["children", "child", "son", "daughter", "offspring"],
    "knowledge": ["knowledge", "learn", "teach", "wisdom", "scholar",
                  "seek knowledge"],
    "cleanliness": ["purify", "purification", "clean", "ablution", "wudu",
                    "ghusl", "pure"],
    "honesty": ["truth", "truthful", "honest", "lie", "lying", "trust"],
    "patience": ["patience", "patient", "persevere", "steadfast"],
    "gratitude": ["grateful", "thankful", "gratitude", "thanks", "blessing"],
    "repentance": ["repent", "forgive", "forgiveness", "mercy", "sin"],
    "dua": ["supplication", "invoke", "remembrance", "dua", "call upon"],
    "neighbours": ["neighbour", "neighbor", "guest", "hospitality"],
    "trade": ["trade", "business", "sell", "buy", "earn", "wage", "market"],
    "justice": ["justice", "just", "oppress", "wrongdoing", "fair"],
    "death": ["death", "die", "died", "grave", "hereafter", "paradise",
              "hellfire", "resurrection"],
    "riba": ["interest", "usury", "riba", "wealth", "debt", "loan"],
    "anger": ["anger", "angry", "rage", "restrain"],
    "speech": ["tongue", "backbit", "slander", "speech", "speak", "silent"],
    "health": ["illness", "sick", "disease", "cure", "heal", "medicine",
               "health"],
    "travel": ["travel", "journey", "migrat", "wayfarer"],
    "orphans": ["orphan", "poor", "needy", "beggar"],
    "modesty": ["modest", "veil", "garment", "clothing", "lower their gaze",
                "shame"],
}


# ---------------------------------------------------------------------------
# GENERAL PRAYER TERMS
# If the user searches one of these they are asking about the prayer as a
# whole, so the portal shows all 8 Namaz topic cards. app.py checks this list.
# ---------------------------------------------------------------------------
GENERAL_SALAH_KEYWORDS = ("salah",)

# ---------------------------------------------------------------------------
# THE 8 TOPICS OF THE NAMAZ CASE STUDY, in the order they occur in the prayer.
#
# app.py uses this list to answer a general "namaz" search with exactly these
# 8 cards. Without it, "namaz" would return all 34 topics in the database -
# including Hajj, Zakat and Marriage - which is not what the user asked for.
#
# These names must stay identical to the first 8 entries of TOPICS_SEED in
# ingest.py; that file checks it on startup and complains if they drift apart.
# ---------------------------------------------------------------------------
NAMAZ_TOPIC_NAMES = (
    "Niyyah (Intention)",
    "Takbir & Qayam (Standing)",
    "Qirat (Recitation)",
    "Ruku (Bowing)",
    "Sajdah (Prostration)",
    "Tashahhud (Sitting)",
    "Salam (Ending)",
    "Sajdah Sahw (Forgetfulness)",
)


def normalize(keyword):
    """
    Turn whatever the user typed into our canonical keyword.

    Steps:
      1. If nothing was typed, return an empty string.
      2. Remove spaces at the start/end and make it lower case.
      3. Look it up in SEMANTIC_MAP.
      4. If it is in the table, return the canonical word ("namaz" -> "salah").
         If it is NOT in the table, return what the user typed unchanged, so a
         normal text search can still be attempted ("xyz" -> "xyz").
    """
    if not keyword:
        return ""

    cleaned = keyword.strip().lower()

    # dict.get(key, default) returns the default when the key is missing.
    return SEMANTIC_MAP.get(cleaned, cleaned)


def get_search_variants(canonical_keyword):
    """
    Return the list of spellings to look for inside the Qur'an and Hadith text.

    "zakat" -> ["zakah", "zakat", "charity", "alms", "sadaqah"]
    "camel" -> ["camel"]   (not in the table, so it searches for itself)
    """
    if not canonical_keyword:
        return []

    return SEARCH_VARIANTS.get(canonical_keyword, [canonical_keyword])


def is_general_salah_term(canonical_keyword):
    """
    Return True when the canonical keyword means "the prayer in general"
    (rather than one specific posture such as Ruku).
    """
    return canonical_keyword in GENERAL_SALAH_KEYWORDS
