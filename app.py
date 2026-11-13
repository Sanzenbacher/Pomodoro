"""Pomodoro -- eigenstaendige Fassung.

Das Modul ist so geschnitten, dass es als 13. Feature-Modul nach
GameDevTools wandern kann: routes/, data/, templates/, static/ liegen dort
genauso. Beim Umzug sind vier Stellen anzupassen, alles andere wandert
unveraendert mit:

    1  Blueprint in app.py registrieren, dazu pomodoro.init_db()
    2  Sidebar-Link unter Development
    3  Metriken in helpers._gather_all_metrics() fuer Overview
    4  static/css/pomodoro.css auf die Variablen aus theme.css setzen

Start:
    python app.py                 Server, Browser selbst oeffnen
    python app.py --window        eigenes Fenster via pywebview
    python app.py --page /pomodoro/stats
"""

import socket
import sys
import threading
import webbrowser

from flask import Flask, redirect

from data import pomodoro, users
from data.appconfig import CONFIG
from routes.pomodoro import bp as pomodoro_bp


def create_app():
    app = Flask(__name__)
    # Vorlagen bei jeder Anfrage neu lesen. Ohne das haelt Flask sie im
    # Cache, und eine geaenderte .html braucht einen Serverneustart --
    # bei einer lokalen App ist das den Bruchteil einer Millisekunde nicht wert.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.register_blueprint(pomodoro_bp)
    # Einmalig: bisherige Daten in den Ordner des ersten Benutzers.
    users.migrate()
    # Wessen Daten Merge Requests ohne ?user= liest -- fest eintragen.
    users.ensure_feed_user()
    # Jeden Benutzer einmal oeffnen: Schema, Migration und Recovery -- damit
    # auch der Timer eines gerade nicht gewaehlten Benutzers weiterlaeuft.
    for user in users.all_users():
        with users.as_user(user["id"]):
            pomodoro.init_db()

    @app.route("/")
    def index():
        return redirect("/pomodoro")

    @app.after_request
    def no_cache(response):
        # Lokale App: nie aus dem Cache, sonst sieht man alte Paletten.
        response.headers["Cache-Control"] = "no-store"
        return response

    return app


def _port_busy(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((host, port)) == 0


def main():
    args = sys.argv[1:]
    page = "/pomodoro"
    if "--page" in args:
        page = args[args.index("--page") + 1]

    host = CONFIG["server"]["host"]
    port = int(CONFIG["server"]["port"])
    url = "http://%s:%d%s" % (host, port, page)
    # Vor create_app: Eine zweite Instanz wuerde sonst Daten umziehen,
    # waehrend die erste noch in die alte Datenbank schreibt -- und
    # danach ohnehin am belegten Port scheitern.
    if _port_busy(host, port):
        print("Pomodoro laeuft schon auf http://%s:%d -- erst beenden." % (host, port))
        sys.exit(1)
    app = create_app()

    if "--window" in args:
        try:
            import webview
        except ImportError:
            print("pywebview fehlt -- starte stattdessen im Browser.")
        else:
            threading.Thread(
                target=lambda: app.run(host=host, port=port, debug=False,
                                       use_reloader=False),
                daemon=True).start()
            webview.create_window("GameDev Tools -- Pomodoro", url,
                                  width=1360, height=920)
            webview.start()
            return

    if "--no-browser" not in args:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print("Pomodoro laeuft auf %s" % url)
    app.run(host=host, port=port, debug="--debug" in args, use_reloader=False)


if __name__ == "__main__":
    main()
