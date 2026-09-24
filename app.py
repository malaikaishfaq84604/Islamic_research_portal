"""
app.py
------
The Flask web application - the part the user actually sees.

VERY IMPORTANT RULE: this file NEVER touches the internet.
There is no "import requests" anywhere below. Every single piece of
information shown on screen is read out of portal.db, which is why the
portal keeps working with the Wi-Fi switched off.

Run it with:   python app.py
Then open:     http://127.0.0.1:5000
"""

from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, flash,
)

import config
import db
import mapping

# Create the Flask application object.
app = Flask(__name__)

# The secret key lets Flask sign the session cookie that remembers an
# admin login. It comes from config.py.
app.secret_key = config.SECRET_KEY

# By default Flask turns every non-English character in a JSON reply into an
# escape code, so "بِسْمِ" would be sent as "بِ...". That is still
# correct, but switching it off sends the real UTF-8 letters instead, which
# makes the /search reply readable when you open it in a browser - very handy
# when demonstrating the project.
app.json.ensure_ascii = False


# ===========================================================================
# SMALL SHARED HELPERS
# ===========================================================================

def get_language():
    """
    Work out which language the visitor wants: "ur" for Urdu or "en" for
    English. We read it from the ?lang= part of the address. Anything we do
    not recognise falls back to English so the page can never break.
    """
    language = request.args.get("lang", "en")
    if language not in ("ur", "en"):
        language = "en"
    return language


def pick_translation(row, language):
    """
    Given a database row and a language code, return the right translation.
    If the chosen translation is empty we fall back to the other one, so the
    user always sees something rather than a blank card.
    """
    if language == "ur":
        return row["urdu_text"] or row["english_text"] or ""
    return row["english_text"] or row["urdu_text"] or ""


def is_admin_logged_in():
    """Return True if this browser has already typed the admin password."""
    return session.get("is_admin") is True


# ===========================================================================
# SEARCH LOGIC (used by the /search route)
# ===========================================================================

def build_like_pattern(text):
    """
    Turn plain text into a safe SQL LIKE pattern such as "%ruku%".

    Inside a LIKE, two characters already have a special meaning:
        %  means "any number of characters"
        _  means "exactly one character"
    So a user who types just "%" would match EVERY topic, which looks like a
    bug. We put a backslash in front of those characters so LIKE treats them
    as ordinary text. The queries below then say  ESCAPE '\\'  to tell SQLite
    that the backslash is our escape character.

    This is about correct searching, not security - SQL injection is already
    impossible because the pattern is passed as a ? value, never glued into
    the SQL string.
    """
    cleaned = text.strip().lower()
    cleaned = cleaned.replace("\\", "\\\\")   # escape the escape character first
    cleaned = cleaned.replace("%", "\\%")
    cleaned = cleaned.replace("_", "\\_")
    return "%" + cleaned + "%"


def find_matching_topics(canonical_keyword, raw_keyword):
    """
    Find the topic rows that match what the user searched for.

    Three ways a topic can match:
      1. The user typed a general prayer word (namaz / salah / نماز) - then we
         return ALL 8 topics, because the whole prayer is being asked about.
      2. The topic's English name contains the search text.
      3. The topic's Urdu name contains the search text.

    Every value goes into the query through a ? placeholder, so a user typing
    SQL such as  ' OR 1=1--  is treated as ordinary text and simply finds
    nothing. It can never change what the query does.
    """
    # Case 1 - a general word for prayer ("namaz", "salah", "prayer") means
    # "show me the whole prayer", so we return the 8 Namaz topics.
    #
    # We list those 8 by name rather than returning every row, because the
    # database now also holds 26 everyday-life topics. Someone searching
    # "namaz" does not want Hajj, Zakat and Marriage cards as well.
    if mapping.is_general_salah_term(canonical_keyword):
        placeholders = ",".join(["?"] * len(mapping.NAMAZ_TOPIC_NAMES))
        return db.fetch_all(
            "SELECT topic_id, topic_name, urdu_name, description "
            "FROM topics WHERE topic_name IN (" + placeholders + ") "
            "ORDER BY topic_id",
            tuple(mapping.NAMAZ_TOPIC_NAMES),
        )

    # Cases 2 and 3 - a LIKE search on both name columns.
    # The % signs mean "any characters here", so "ruku" finds "Ruku (Bowing)".
    # We build the patterns in PYTHON and pass them as values - the SQL text
    # itself never changes, which is what makes injection impossible.
    #
    # We search with BOTH patterns so either spelling works:
    #   canonical - what mapping.py turned the word into ("rukoo" -> "ruku")
    #   raw       - exactly what the user typed (needed for Urdu script, which
    #               is stored directly in the urdu_name column)
    canonical_pattern = build_like_pattern(canonical_keyword)
    raw_pattern = build_like_pattern(raw_keyword)

    return db.fetch_all(
        "SELECT topic_id, topic_name, urdu_name, description FROM topics "
        "WHERE LOWER(topic_name) LIKE ? ESCAPE '\\' "
        "   OR LOWER(topic_name) LIKE ? ESCAPE '\\' "
        "   OR urdu_name LIKE ? ESCAPE '\\' "
        "   OR urdu_name LIKE ? ESCAPE '\\' "
        "ORDER BY topic_id",
        (canonical_pattern, raw_pattern, canonical_pattern, raw_pattern),
    )


# How many free-text results to send back. Without a cap, a common word like
# "eat" would return thousands of cards and make the page enormous.
MAX_FREE_TEXT_VERSES = 25
MAX_FREE_TEXT_HADITHS = 30


def search_verses_by_text(search_words):
    """
    Look for the given words INSIDE the text of the Qur'an itself.

    This is what makes the portal answer questions we never curated a topic
    for. If somebody types "honey" or "camel", there is no topic card, but
    these verses still come back.

    We look in the English translation AND the Urdu translation, so the search
    works whichever language the user typed in.

    One "(english LIKE ? OR urdu LIKE ?)" pair is built per word, joined with
    OR. The words themselves are ALWAYS passed as ? values, so this stays
    injection-proof - only the number of placeholders changes, never the SQL.
    """
    if not search_words:
        return []

    conditions = []
    values = []
    for word in search_words:
        pattern = build_like_pattern(word)
        conditions.append("(english_text LIKE ? ESCAPE '\\' "
                          "OR urdu_text LIKE ? ESCAPE '\\')")
        values.append(pattern)
        values.append(pattern)

    # Add the row limit as the final ? value.
    values.append(MAX_FREE_TEXT_VERSES)

    return db.fetch_all(
        "SELECT surah_no, surah_name, ayah_no, arabic_text, urdu_text, english_text "
        "FROM quran WHERE " + " OR ".join(conditions) + " "
        "ORDER BY surah_no, ayah_no LIMIT ?",
        tuple(values),
    )


def search_hadiths_by_text(search_words):
    """
    The same free-text search, but over the Hadith collections.

    Sahih and Hasan narrations are shown first (ORDER BY puts grade 'Sahih'
    and 'Hasan' before the rest), so the strongest evidence is at the top.
    """
    if not search_words:
        return []

    conditions = []
    values = []
    for word in search_words:
        pattern = build_like_pattern(word)
        conditions.append("(english_text LIKE ? ESCAPE '\\' "
                          "OR urdu_text LIKE ? ESCAPE '\\')")
        values.append(pattern)
        values.append(pattern)

    values.append(MAX_FREE_TEXT_HADITHS)

    return db.fetch_all(
        "SELECT hadith_id, book_name, hadith_no, arabic_text, urdu_text, "
        "       english_text, grade "
        "FROM hadith WHERE " + " OR ".join(conditions) + " "
        "ORDER BY CASE grade WHEN 'Sahih' THEN 1 WHEN 'Hasan' THEN 2 "
        "                    WHEN \"Da'if\" THEN 3 ELSE 4 END, "
        "         book_name, CAST(hadith_no AS INTEGER) "
        "LIMIT ?",
        tuple(values),
    )


def count_hadiths_for_topic(topic_id):
    """Count how many hadiths are linked to one topic."""
    row = db.fetch_one(
        "SELECT COUNT(*) AS total FROM hadith_topics WHERE topic_id = ?",
        (topic_id,),
    )
    return row["total"] if row else 0


def get_verses_for_topics(topic_ids):
    """
    Collect every Quranic verse linked to any of the given topic ids,
    with no duplicates, sorted in Quran order (surah then ayah).

    Because the number of topic ids changes from search to search, we build
    exactly the right number of ? placeholders - one per id - and still pass
    the ids as values. There is no user text in the SQL string at all.
    """
    if not topic_ids:
        return []

    # ["?", "?", "?"] joined together -> "?,?,?"
    placeholders = ",".join(["?"] * len(topic_ids))

    return db.fetch_all(
        "SELECT DISTINCT q.quran_id, q.surah_no, q.surah_name, q.ayah_no, "
        "       q.arabic_text, q.urdu_text, q.english_text "
        "FROM quran q "
        "JOIN quran_topics qt ON qt.quran_id = q.quran_id "
        "WHERE qt.topic_id IN (" + placeholders + ") "
        "ORDER BY q.surah_no, q.ayah_no",
        tuple(topic_ids),
    )


# ===========================================================================
# PUBLIC ROUTES (read-only - they only ever run SELECT statements)
# ===========================================================================

@app.route("/")
def home():
    """
    The dashboard. Shows the navbar, the big search box and an empty results
    area. The results are filled in later by JavaScript calling /search.
    """
    return render_template("index.html", lang=get_language())


@app.route("/search")
def search():
    """
    The AJAX endpoint the search box calls. It returns JSON, not HTML, so the
    page can update without reloading.

    Query parameters:
        q    - what the user typed (for example "namaz", "khana" or "نماز")
        lang - "ur" or "en"

    THE SEARCH WORKS IN TWO STEPS:

      STEP 1 - CURATED. Is there a topic for this word? If yes, send back the
               topic cards and the verses linked to them. This is the good,
               organised answer.

      STEP 2 - FREE TEXT. If no topic matched, search the actual text of the
               Qur'an and the Hadith for the word instead. This is what lets
               the portal answer something like "honey" or "camel" that nobody
               ever made a topic for.

    It always returns HTTP 200. A word that is genuinely nowhere in the portal
    gives empty lists, which the JavaScript shows as a friendly
    "No Results Found" card.
    """
    raw_keyword = request.args.get("q", "")
    language = get_language()

    # Nothing typed? Return empty results immediately - no database work.
    if not raw_keyword.strip():
        return jsonify({"verses": [], "topics": [], "hadiths": []})

    # Turn "Namaz" / "نماز" / "salat" into the single word "salah",
    # or "khana" / "کھانا" into "food".
    canonical_keyword = mapping.normalize(raw_keyword)

    # ----- STEP 1: the curated answer ---------------------------------------
    topic_rows = find_matching_topics(canonical_keyword, raw_keyword)

    # Build the topic cards, each with its hadith count.
    topics_output = []
    topic_ids = []
    for row in topic_rows:
        topic_ids.append(row["topic_id"])
        topics_output.append({
            "topic_id": row["topic_id"],
            "topic_name": row["topic_name"],
            "urdu_name": row["urdu_name"],
            "hadith_count": count_hadiths_for_topic(row["topic_id"]),
        })

    # Build the verse cards from every matched topic.
    verses_output = []
    for row in get_verses_for_topics(topic_ids):
        verses_output.append({
            "surah_no": row["surah_no"],
            "surah_name": row["surah_name"],
            "ayah_no": row["ayah_no"],
            "arabic": row["arabic_text"],
            "translation": pick_translation(row, language),
        })

    hadiths_output = []

    # ----- STEP 2: the free-text fallback -----------------------------------
    # Only runs when the curated step found no topic at all. If a topic did
    # match, its own page already holds the ahadith, so we keep the dashboard
    # clean instead of piling more cards on.
    if not topics_output:
        # "zakat" -> ["zakah", "zakat", "charity", ...] so we catch the
        # spellings the translators actually used. We also always include
        # exactly what the user typed, which is what makes an Urdu-script
        # search match the Urdu translation.
        search_words = mapping.get_search_variants(canonical_keyword)
        if raw_keyword.strip().lower() not in search_words:
            search_words = search_words + [raw_keyword.strip().lower()]

        for row in search_verses_by_text(search_words):
            verses_output.append({
                "surah_no": row["surah_no"],
                "surah_name": row["surah_name"],
                "ayah_no": row["ayah_no"],
                "arabic": row["arabic_text"],
                "translation": pick_translation(row, language),
            })

        for row in search_hadiths_by_text(search_words):
            hadiths_output.append({
                "hadith_id": row["hadith_id"],
                "book_name": row["book_name"],
                "hadith_no": row["hadith_no"],
                "arabic": row["arabic_text"],
                "translation": pick_translation(row, language),
                "grade": row["grade"],
            })

    return jsonify({
        "verses": verses_output,
        "topics": topics_output,
        "hadiths": hadiths_output,
    })


@app.route("/topic/<int:topic_id>")
def topic_detail(topic_id):
    """
    The detail page for one topic, for example /topic/4 for Ruku.

    Shows ONLY the ahadith linked to this topic ("Prophetic Implementation"),
    each with its grade badge.

    WHY THERE ARE NO QUR'ANIC VERSES ON THIS PAGE
    --------------------------------------------
    This page used to repeat the "Divine Command" verses above the ahadith.
    That was a mistake in the journey through the site: the search results
    page has ALREADY shown those verses, on its Qur'an tab, before the reader
    clicked a topic card. Showing them again meant the reader had to scroll
    past the very same verses a second time to reach the ahadith - which are
    the whole reason they clicked the card.

    So a topic page now answers exactly one question: "how did the Prophet
    do this?" The verses stay one click away on the search page.

    A happy side effect is that the page no longer runs the verse query or
    renders those tall Arabic cards, which makes it markedly cheaper to serve
    - and this is the busiest page on the site.

    Query parameters:
        lang  - "ur" or "en"
        grade - "all" (default) or "sahih_hasan" to hide weaker hadiths

    A topic id that does not exist shows the friendly 404 page, not a crash.
    """
    language = get_language()
    grade_filter = request.args.get("grade", "all")

    # The word the visitor searched for before clicking this topic card, if
    # they arrived that way. It is passed straight back to the template so the
    # "Back to Search" link can rebuild the search they came from, rather than
    # returning them to an empty box. Purely for navigation - it is never used
    # in a query.
    search_query = request.args.get("q", "")

    topic = db.fetch_one(
        "SELECT topic_id, topic_name, urdu_name, description "
        "FROM topics WHERE topic_id = ?",
        (topic_id,),
    )

    # No such topic -> show the friendly 404 page with a 404 status code.
    if topic is None:
        return render_template("404.html", lang=language), 404

    # --- the hadiths for this topic ---
    # The filter is done here on the server, which keeps the JavaScript simple
    # and means the behaviour can be tested with pytest.
    if grade_filter == "sahih_hasan":
        hadith_rows = db.fetch_all(
            "SELECT h.hadith_id, h.book_name, h.hadith_no, h.arabic_text, "
            "       h.urdu_text, h.english_text, h.grade "
            "FROM hadith h "
            "JOIN hadith_topics ht ON ht.hadith_id = h.hadith_id "
            "WHERE ht.topic_id = ? AND h.grade IN (?, ?) "
            "ORDER BY h.book_name, CAST(h.hadith_no AS INTEGER)",
            (topic_id, "Sahih", "Hasan"),
        )
    else:
        hadith_rows = db.fetch_all(
            "SELECT h.hadith_id, h.book_name, h.hadith_no, h.arabic_text, "
            "       h.urdu_text, h.english_text, h.grade "
            "FROM hadith h "
            "JOIN hadith_topics ht ON ht.hadith_id = h.hadith_id "
            "WHERE ht.topic_id = ? "
            "ORDER BY h.book_name, CAST(h.hadith_no AS INTEGER)",
            (topic_id,),
        )

    hadiths = []
    for row in hadith_rows:
        hadiths.append({
            "hadith_id": row["hadith_id"],
            "book_name": row["book_name"],
            "hadith_no": row["hadith_no"],
            "arabic": row["arabic_text"],
            "translation": pick_translation(row, language),
            "grade": row["grade"],
        })

    return render_template(
        "topic.html",
        topic=topic,
        hadiths=hadiths,
        lang=language,
        grade_filter=grade_filter,
        search_query=search_query,
    )


# ===========================================================================
# ADMIN ROUTES (password protected - these are the only ones that write)
# ===========================================================================

@app.route("/admin", methods=["GET", "POST"])
def admin():
    """
    The admin page.

    Not logged in  -> shows a password box.
    Logged in      -> shows the row counts, data-refresh buttons, a form to
                      add a topic, and a form to attach or detach a hadith
                      to/from a topic (manual curation).

    Every action below is triggered by a POST with a hidden "action" field, so
    one route can handle all of them and the code stays in one place.
    """
    language = get_language()

    if request.method == "POST":
        action = request.form.get("action", "login")

        # ----- 1. logging in -------------------------------------------------
        if action == "login":
            typed_password = request.form.get("password", "")
            if typed_password == config.ADMIN_PASSWORD:
                session["is_admin"] = True
                flash("Welcome, admin.", "success")
            else:
                flash("Wrong password. Please try again.", "danger")
            return redirect(url_for("admin", lang=language))

        # Everything past this point needs a login.
        if not is_admin_logged_in():
            flash("Please log in first.", "warning")
            return redirect(url_for("admin", lang=language))

        # ----- 2. re-download the Quran -------------------------------------
        if action == "refresh_quran":
            # ingest is imported HERE, inside the function, not at the top of
            # the file. That keeps "import requests" out of the public app:
            # the network code is only loaded when an admin asks for it.
            try:
                import ingest
                total = ingest.ingest_quran()
                ingest.tag_quran_topics()
                flash("Quran data refreshed. The database now holds "
                      + str(total) + " ayahs.", "success")
            except Exception as error:
                flash("Quran refresh failed: " + type(error).__name__
                      + " - " + str(error), "danger")
            return redirect(url_for("admin", lang=language))

        # ----- 3. re-download the Hadith collections -------------------------
        if action == "refresh_hadith":
            try:
                import ingest
                total = ingest.ingest_hadith()
                ingest.tag_hadith_topics()
                flash("Hadith data refreshed. The database now holds "
                      + str(total) + " hadiths.", "success")
            except Exception as error:
                flash("Hadith refresh failed: " + type(error).__name__
                      + " - " + str(error), "danger")
            return redirect(url_for("admin", lang=language))

        # ----- 4. add a new topic --------------------------------------------
        if action == "add_topic":
            topic_name = request.form.get("topic_name", "").strip()
            urdu_name = request.form.get("urdu_name", "").strip()
            description = request.form.get("description", "").strip()

            if not topic_name:
                flash("The English topic name cannot be empty.", "warning")
            else:
                changed = db.execute(
                    "INSERT OR IGNORE INTO topics (topic_name, urdu_name, description) "
                    "VALUES (?, ?, ?)",
                    (topic_name, urdu_name, description),
                )
                if changed:
                    flash("Topic '" + topic_name + "' added.", "success")
                else:
                    flash("A topic called '" + topic_name
                          + "' already exists.", "warning")
            return redirect(url_for("admin", lang=language))

        # ----- 5. attach or detach one hadith to/from a topic -----------------
        if action in ("attach_hadith", "detach_hadith"):
            book_name = request.form.get("book_name", "").strip()
            hadith_no = request.form.get("hadith_no", "").strip()
            topic_id_text = request.form.get("topic_id", "").strip()

            # The topic id arrives as text from the form, so check it really
            # is a number before we use it.
            if not topic_id_text.isdigit():
                flash("Please choose a topic.", "warning")
                return redirect(url_for("admin", lang=language))

            topic_id = int(topic_id_text)

            hadith_row = db.fetch_one(
                "SELECT hadith_id FROM hadith WHERE book_name = ? AND hadith_no = ?",
                (book_name, hadith_no),
            )

            if hadith_row is None:
                flash("No hadith number " + hadith_no + " found in "
                      + book_name + ".", "warning")
            elif action == "attach_hadith":
                db.execute(
                    "INSERT OR IGNORE INTO hadith_topics (hadith_id, topic_id) "
                    "VALUES (?, ?)",
                    (hadith_row["hadith_id"], topic_id),
                )
                flash("Hadith " + hadith_no + " attached to the topic.", "success")
            else:
                db.execute(
                    "DELETE FROM hadith_topics WHERE hadith_id = ? AND topic_id = ?",
                    (hadith_row["hadith_id"], topic_id),
                )
                flash("Hadith " + hadith_no + " detached from the topic.", "success")

            return redirect(url_for("admin", lang=language))

        # An unknown action - just go back to the admin page.
        return redirect(url_for("admin", lang=language))

    # ----- GET request ------------------------------------------------------
    if not is_admin_logged_in():
        # Show only the password form.
        return render_template("admin.html", logged_in=False, lang=language)

    # Logged in: gather the numbers for the dashboard.
    counts = {
        "quran": db.count_rows("quran"),
        "hadith": db.count_rows("hadith"),
        "topics": db.count_rows("topics"),
        "quran_topics": db.count_rows("quran_topics"),
        "hadith_topics": db.count_rows("hadith_topics"),
    }

    all_topics = db.fetch_all(
        "SELECT topic_id, topic_name, urdu_name FROM topics ORDER BY topic_id"
    )

    # The distinct book names, so the curation form can offer a dropdown.
    book_rows = db.fetch_all(
        "SELECT DISTINCT book_name FROM hadith ORDER BY book_name"
    )
    book_names = [row["book_name"] for row in book_rows]

    return render_template(
        "admin.html",
        logged_in=True,
        counts=counts,
        all_topics=all_topics,
        book_names=book_names,
        lang=language,
    )


@app.route("/admin/logout")
def admin_logout():
    """Forget the admin login and go back to the password form."""
    session.pop("is_admin", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("admin"))


# ===========================================================================
# ERROR PAGES - the user must never see a stack trace
# ===========================================================================

@app.errorhandler(404)
def page_not_found(error):
    """Shown when an address does not exist, for example /topic/99999."""
    return render_template("404.html", lang=get_language()), 404


@app.errorhandler(500)
def internal_server_error(error):
    """
    Shown if something unexpected goes wrong inside the app. The visitor
    gets a calm message instead of a red Python error page.
    """
    return render_template("500.html", lang=get_language()), 500


# ===========================================================================
# STARTING THE SERVER
# ===========================================================================

def is_port_already_used(host, port):
    """
    Return True if some other program is already listening on this port.

    We simply try to CONNECT to the address, the same way a browser would.
    connect_ex() gives back 0 when the connection succeeded, which can only
    happen if something is already there answering.

    This is a connection to your OWN computer (127.0.0.1), not the internet,
    so it still works perfectly with the Wi-Fi switched off.

    WHY THIS CHECK EXISTS:
    On Windows, two programs are allowed to claim the same port. The second
    one prints "Running on ..." as if all is well, but the browser keeps
    talking to the FIRST program. You then see somebody else's website and
    have no idea why. Checking first turns that silent, confusing failure
    into a clear message.
    """
    import socket   # only used here, for a check against your own computer

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.5)
    try:
        return probe.connect_ex((host, port)) == 0
    finally:
        probe.close()


def find_free_port(host, first_port, how_many_to_try=20):
    """
    Start at first_port and return the first port that nothing else is using.
    Returns None if every port in the range is busy.
    """
    for port in range(first_port, first_port + how_many_to_try):
        if not is_port_already_used(host, port):
            return port
    return None


if __name__ == "__main__":
    # Make sure the tables exist, so a brand-new copy of the project does not
    # crash if somebody runs app.py before ingest.py.
    db.create_schema()

    # Warn if the database is empty - the commonest beginner mistake is
    # running app.py before ingest.py.
    if db.count_rows("quran") == 0:
        print("!" * 60)
        print("WARNING: the database is empty.")
        print("Run this first (it needs the internet, once):")
        print("    python ingest.py")
        print("!" * 60)

    # Pick a port that is actually free.
    chosen_port = config.PORT
    if is_port_already_used(config.HOST, config.PORT):
        print("Port " + str(config.PORT) + " is already being used by another "
              "program on this computer.")
        chosen_port = find_free_port(config.HOST, config.PORT + 1)

        if chosen_port is None:
            print("Could not find a free port. Please close the other program "
                  "and try again.")
            raise SystemExit(1)

        print("Using port " + str(chosen_port) + " instead.")

    address = "http://" + config.HOST + ":" + str(chosen_port)

    print("=" * 60)
    print("ISLAMIC RESEARCH PORTAL is starting ...")
    print("Open this address in your browser:  " + address)
    print("Press CTRL+C in this window to stop the server.")
    print("=" * 60)

    # debug=False so visitors never see a stack trace.
    app.run(host=config.HOST, port=chosen_port, debug=False)
