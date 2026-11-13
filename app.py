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

import sys
import threading
import webbrowser

from flask import Flask, redirect

from data import pomodoro, profiles
from data.appconfig import server_address, server_running
from routes.pomodoro import bp as pomodoro_bp


def create_app():
    app = Flask(__name__)
    # Vorlagen bei jeder Anfrage neu lesen. Ohne das haelt Flask sie im
    # Cache, und eine geaenderte .html braucht einen Serverneustart --
    # bei einer lokalen App ist das den Bruchteil einer Millisekunde nicht wert.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.register_blueprint(pomodoro_bp)
    # Einmalig: bisherige Daten in den Ordner des ersten Profils.
    profiles.migrate()
    # Wessen Daten Merge Requests ohne ?profile= liest -- fest eintragen.
    profiles.ensure_feed_profile()
    # Jedes Profil einmal oeffnen: Schema, Migration und Recovery -- damit
    # auch der Timer eines gerade nicht gewaehlten Profils weiterlaeuft.
    for profile in profiles.all_profiles():
        with profiles.as_profile(profile["id"]):
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


def main():
    args = sys.argv[1:]
    page = "/pomodoro"
    if "--page" in args:
        page = args[args.index("--page") + 1]

    host, port = server_address()
    url = "http://%s:%d%s" % (host, port, page)
    # Vor create_app: Eine zweite Instanz wuerde sonst Daten umziehen,
    # waehrend die erste noch in die alte Datenbank schreibt -- und
    # danach ohnehin am belegten Port scheitern.
    if server_running(host, port):
        print("Pomodoro laeuft schon auf http://%s:%d -- erst beenden." % (host, port))
        sys.exit(1)
    try:
        app = create_app()
    except profiles.MigrationError as exc:
        # Ohne die richtige Ablage nicht starten: Sonst entstuende ein leeres
        # Profil, waehrend die eigentlichen Daten daneben liegen.
        print(exc)
        sys.exit(1)

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
