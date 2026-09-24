"""
db.py
-----
Everything to do with the SQLite database lives here.

We use Python's BUILT-IN sqlite3 module - no SQLAlchemy, no ORM. That means
every query is plain SQL that the student can read out loud and explain.

SECURITY RULE FOLLOWED EVERYWHERE IN THIS PROJECT:
    Values are NEVER glued into the SQL string with f-strings or +.
    They are always passed as a separate tuple and marked with a ? in the SQL.
    SQLite then treats them as *data*, never as *commands*, which is what
    stops SQL-injection attacks.

    GOOD:  cur.execute("SELECT * FROM quran WHERE surah_no = ?", (n,))
    BAD :  cur.execute("SELECT * FROM quran WHERE surah_no = " + str(n))
"""

import sqlite3

import config

# ---------------------------------------------------------------------------
# THE SCHEMA
# One long string containing every CREATE statement. "IF NOT EXISTS" means
# running this twice is completely safe - nothing is deleted or duplicated.
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS quran (
    quran_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    surah_no     INTEGER NOT NULL,
    surah_name   TEXT,
    ayah_no      INTEGER NOT NULL,
    arabic_text  TEXT NOT NULL,
    urdu_text    TEXT,
    english_text TEXT,
    UNIQUE(surah_no, ayah_no)
);

CREATE TABLE IF NOT EXISTS hadith (
    hadith_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    book_name    TEXT NOT NULL,
    hadith_no    TEXT NOT NULL,
    arabic_text  TEXT,
    urdu_text    TEXT,
    english_text TEXT,
    grade        TEXT DEFAULT 'Unknown',
    UNIQUE(book_name, hadith_no)
);

CREATE TABLE IF NOT EXISTS topics (
    topic_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_name  TEXT NOT NULL UNIQUE,
    urdu_name   TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS quran_topics (
    quran_id INTEGER REFERENCES quran(quran_id),
    topic_id INTEGER REFERENCES topics(topic_id),
    UNIQUE(quran_id, topic_id)
);

CREATE TABLE IF NOT EXISTS hadith_topics (
    hadith_id INTEGER REFERENCES hadith(hadith_id),
    topic_id  INTEGER REFERENCES topics(topic_id),
    UNIQUE(hadith_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_hadith_grade ON hadith(grade);
CREATE INDEX IF NOT EXISTS idx_ht_topic ON hadith_topics(topic_id);
CREATE INDEX IF NOT EXISTS idx_qt_topic ON quran_topics(topic_id);
"""


def get_connection(db_path=None):
    """
    Open a connection to the SQLite database file and hand it back.

    Two important settings are applied to every connection:
      1. row_factory = sqlite3.Row  -> rows behave like dictionaries, so we can
         write row["arabic_text"] instead of the confusing row[4].
      2. text_factory = str         -> SQLite already stores text as UTF-8, and
         Python decodes it back to a str. This guarantees Arabic diacritics
         come back exactly as they went in (no character loss).

    If db_path is not given we use the path from config.py. The tests pass in a
    temporary file path here so they never touch the real portal.db.
    """
    if db_path is None:
        db_path = config.DB_PATH

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.text_factory = str
    # Turn on foreign key checking (SQLite has it switched off by default).
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_schema(db_path=None):
    """
    Create every table and index if they do not already exist.
    Safe to call as many times as you like.
    """
    connection = get_connection(db_path)
    try:
        # executescript runs several SQL statements separated by semicolons.
        connection.executescript(SCHEMA_SQL)
        connection.commit()
    finally:
        # "finally" guarantees the connection closes even if an error happened.
        connection.close()


def fetch_all(sql, params=(), db_path=None):
    """
    Run a SELECT that may return many rows and give back a list of rows.

    sql     - the SQL text, using ? for every value
    params  - a tuple of the values that replace the ? marks
    """
    connection = get_connection(db_path)
    try:
        cursor = connection.execute(sql, params)
        return cursor.fetchall()
    finally:
        connection.close()


def fetch_one(sql, params=(), db_path=None):
    """
    Run a SELECT that returns at most one row.
    Returns that single row, or None when nothing matched.
    """
    connection = get_connection(db_path)
    try:
        cursor = connection.execute(sql, params)
        return cursor.fetchone()
    finally:
        connection.close()


def execute(sql, params=(), db_path=None):
    """
    Run one INSERT / UPDATE / DELETE statement and save the change.
    Returns how many rows were affected (useful for "did the delete work?").

    NOTE: the public website never calls this - only ingest.py and the
    password-protected admin pages do. Public pages are read-only by design.
    """
    connection = get_connection(db_path)
    try:
        cursor = connection.execute(sql, params)
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()


def count_rows(table_name, db_path=None):
    """
    Count the rows in one table and return the number.

    The table name cannot be a ? placeholder (SQLite only allows ? for VALUES,
    not for table names), so we protect ourselves with a whitelist: if the name
    is not one of our five known tables we refuse to build the query at all.
    This keeps the "no untrusted text in SQL" rule intact.
    """
    allowed_tables = ("quran", "hadith", "topics", "quran_topics", "hadith_topics")
    if table_name not in allowed_tables:
        raise ValueError("Unknown table name: " + str(table_name))

    row = fetch_one("SELECT COUNT(*) AS total FROM " + table_name, (), db_path)
    return row["total"] if row else 0
