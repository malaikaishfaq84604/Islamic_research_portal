"""
dev.py
------
A DEVELOPMENT-ONLY launcher, used while we are working on the look of the
portal (the templates in templates/ and the styling in static/style.css).

It is NOT a replacement for app.py / run.bat. Those stay exactly as they are
and remain the way the finished project is demonstrated and marked.

What this file adds on top of "python app.py":

  1. AUTO-RELOAD - save a .html or .py file and the server restarts itself.
     Save a .css file and a refresh in the browser shows it straight away,
     because caching is switched off (see point 3).

  2. A FIXED PORT OF ITS OWN (5050) - app.py politely hops to 5001, 5002 ...
     if 5000 is busy, which is right for a demo but annoying while developing,
     because the address in the browser keeps changing. Here we insist on one
     port and say clearly if it is taken.

     5050 is deliberately NOT 5000, so this development server can run at the
     same time as the ordinary portal (run.bat / python app.py) without the
     two fighting over the same port. Port 5000 stays free for the demo.

  3. NO CACHING of style.css - browsers hold on to stylesheets very
     stubbornly. SEND_FILE_MAX_AGE_DEFAULT = 0 tells the browser "always ask
     me again", so a CSS change is visible on the very next refresh instead
     of after a hard reload.

  4. FULL ERROR PAGES - debug mode replaces the calm 500.html page with the
     real Python traceback, so a mistake in a template points straight at the
     offending line.

Run it with:   python dev.py
Then open:     http://127.0.0.1:5050

To use a different port:   python dev.py 5060

Press CTRL+C in the window to stop it.
"""

import os
import sys

import config

# Import the SAME app object that app.py builds, so the routes, the database
# access and the templates are all identical to the real thing. Only the way
# it is started differs.
from app import app, is_port_already_used

import db


# The port we insist on. Kept separate from config.PORT so that changing it
# here for development can never affect how the finished project runs, and so
# the real portal can keep port 5000 to itself.
DEFAULT_DEV_PORT = 5050
DEV_HOST = config.HOST


def read_port_from_command_line():
    """
    Allow "python dev.py 5060" to override the port. Anything that is not a
    sensible number is ignored with a note, rather than crashing.
    """
    if len(sys.argv) < 2:
        return DEFAULT_DEV_PORT

    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Ignoring '" + sys.argv[1] + "' - that is not a port number. "
              "Using " + str(DEFAULT_DEV_PORT) + ".")
        return DEFAULT_DEV_PORT

    if not (1024 <= port <= 65535):
        print("Ignoring " + str(port) + " - please pick a port between 1024 "
              "and 65535. Using " + str(DEFAULT_DEV_PORT) + ".")
        return DEFAULT_DEV_PORT

    return port


def is_the_reloader_child():
    """
    True when we are the process the auto-reloader restarted, rather than the
    one the user launched.

    WHY THIS MATTERS: with the reloader on, dev.py runs TWICE. The first
    process opens the socket and then watches for file changes; the second is
    the one actually serving pages. Werkzeug marks that second process by
    setting WERKZEUG_RUN_MAIN in its environment.

    Without this check the second process runs the "is the port free?" test
    below, finds the FIRST process already listening on it, and exits with
    "port already in use" - the server shutting itself down on startup every
    single time. The startup banner and the port test therefore belong to the
    launching process only.
    """
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def main():
    DEV_PORT = read_port_from_command_line()

    # Everything from here to app.run() is first-launch-only work: the checks
    # and the banner. The reloader's child skips straight to serving.
    if is_the_reloader_child():
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.run(host=DEV_HOST, port=DEV_PORT, debug=True, use_reloader=True)
        return

    # Same safety net as app.py: make sure the tables exist before serving.
    db.create_schema()

    if db.count_rows("quran") == 0:
        print("!" * 68)
        print("WARNING: the database is empty, so pages will look bare.")
        print("Run this once (it needs the internet):   python ingest.py")
        print("!" * 68)

    # Unlike app.py we do NOT hop to another port. While styling a page we
    # want the address in the browser to stay the same every single time.
    if is_port_already_used(DEV_HOST, DEV_PORT):
        print("=" * 68)
        print("PORT " + str(DEV_PORT) + " IS ALREADY IN USE.")
        print("")
        print("Another copy of this development server is probably still")
        print("running. Close that window (or press CTRL+C in it), or start")
        print("this one on a different port:")
        print("")
        print("    python dev.py " + str(DEV_PORT + 1))
        print("=" * 68)
        raise SystemExit(1)

    # Point 3 from the notes above: never let the browser cache style.css.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # TEMPLATES_AUTO_RELOAD makes Jinja re-read a template on every request.
    # debug=True normally does this already, but setting it explicitly means
    # the behaviour does not depend on Flask's defaults.
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    address = "http://" + DEV_HOST + ":" + str(DEV_PORT)

    print("=" * 68)
    print("ISLAMIC RESEARCH PORTAL - DEVELOPMENT MODE")
    print("")
    print("  Open:        " + address)
    print("  Topic page:  " + address + "/topic/1")
    print("  Urdu:        " + address + "/?lang=ur")
    print("  Admin:       " + address + "/admin")
    print("")
    print("  Edits to templates/ and static/ appear on the next refresh.")
    print("  Press CTRL+C to stop.")
    print("=" * 68)

    # use_reloader=True is what restarts the server when a file is saved.
    app.run(host=DEV_HOST, port=DEV_PORT, debug=True, use_reloader=True)


if __name__ == "__main__":
    main()
