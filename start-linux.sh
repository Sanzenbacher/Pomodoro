#!/bin/sh
# ===========================================================================
#  Pomodoro starten (Linux).
#
#  Gegenstueck zu start-windows.bat. Argumente werden durchgereicht:
#      ./start-linux.sh --window
#      ./start-linux.sh --page /pomodoro/stats
#      ./start-linux.sh --no-browser
#
#  Das Skript sucht Python, ergaenzt fehlende Abhaengigkeiten und merkt,
#  wenn der Server schon laeuft -- dann oeffnet es nur den Browser.
#
#  Unterschied zu Windows: Viele Distributionen sperren "pip install" in
#  das System-Python (PEP 668, "externally-managed-environment"). Klappt
#  die Installation dort nicht, legt das Skript eine .venv im Projekt an
#  und nutzt kuenftig diese.
# ===========================================================================

cd "$(dirname "$(readlink -f "$0")")" || exit 1

# Bei einem Fehler kurz warten, sonst ist die Meldung weg, bevor man sie
# lesen kann -- aber nur, wenn jemand am Terminal sitzt.
pause() {
    if [ -t 0 ]; then
        printf '  Weiter mit Enter ... '
        read -r _
    fi
}

echo
echo "  Pomodoro"
echo "  --------"
echo

# -- 1. Python finden -------------------------------------------------------
#     Eine vorhandene .venv hat Vorrang -- dort liegen die Abhaengigkeiten.
PY=""
if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
elif command -v python >/dev/null 2>&1 \
     && python -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >/dev/null 2>&1; then
    PY="python"
fi
if [ -z "$PY" ]; then
    echo "  Python 3 wurde nicht gefunden."
    echo
    echo "  Installieren ueber den Paketmanager, zum Beispiel:"
    echo "      sudo apt install python3 python3-venv     (Debian/Ubuntu)"
    echo "      sudo dnf install python3                  (Fedora)"
    echo "      sudo pacman -S python                     (Arch)"
    echo
    pause
    exit 1
fi

# -- 2. Abhaengigkeiten pruefen ---------------------------------------------
if ! "$PY" -c "import flask, yaml" >/dev/null 2>&1; then
    echo "  Flask oder PyYAML fehlen. Installiere ..."
    echo
    if ! "$PY" -m pip install --disable-pip-version-check --quiet --user Flask PyYAML >/dev/null 2>&1; then
        # System-Python gesperrt oder pip fehlt: eigene Umgebung anlegen.
        echo "  System-Python laesst keine Installation zu -- lege .venv an ..."
        # Eine kaputte .venv von einem frueheren Versuch nicht weiterbenutzen:
        # neu anlegen, und zwar mit dem System-Python, nicht aus ihr heraus.
        BASE_PY="$PY"
        if [ "$PY" = ".venv/bin/python" ]; then
            BASE_PY=$(command -v python3 || command -v python)
        fi
        rm -rf .venv
        if ! "$BASE_PY" -m venv .venv \
           || ! .venv/bin/python -m pip install --disable-pip-version-check --quiet Flask PyYAML; then
            # Halb angelegte .venv entfernen, sonst nimmt der naechste Start sie.
            rm -rf .venv
            echo
            echo "  Installation fehlgeschlagen. Von Hand:"
            echo "      sudo apt install python3-venv      (falls venv fehlt)"
            echo "      python3 -m venv .venv"
            echo "      .venv/bin/python -m pip install Flask PyYAML"
            echo
            pause
            exit 1
        fi
        PY=".venv/bin/python"
    fi
    echo "  Fertig."
    echo
fi

# -- 3. Adresse aus config.yaml lesen ---------------------------------------
HOST="127.0.0.1"
PORT="5333"
ADDR=$("$PY" -c "from data.appconfig import CONFIG as c; print(c['server']['host'], c['server']['port'])" 2>/dev/null)
if [ -n "$ADDR" ]; then
    HOST=${ADDR% *}
    PORT=${ADDR#* }
fi

# -- 4. Laeuft schon einer? --------------------------------------------------
#     Ohne diese Pruefung endet ein zweiter Start in einem haesslichen
#     "address already in use" statt im Timer.
if "$PY" -c "import socket,sys; s=socket.socket(); s.settimeout(0.5); sys.exit(0 if s.connect_ex(('$HOST', $PORT))==0 else 1)" >/dev/null 2>&1; then
    echo "  Der Server laeuft bereits auf Port $PORT."
    echo "  Oeffne nur den Browser ..."
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://$HOST:$PORT/pomodoro" >/dev/null 2>&1 &
    else
        "$PY" -m webbrowser "http://$HOST:$PORT/pomodoro" >/dev/null 2>&1 &
    fi
    sleep 2
    exit 0
fi

# -- 5. Los -----------------------------------------------------------------
echo "  Adresse:  http://$HOST:$PORT/pomodoro"
echo "  Beenden:  Strg + C"
echo

"$PY" app.py "$@"
rc=$?

# 130 = mit Strg + C beendet, das ist kein Fehler.
if [ "$rc" -ne 0 ] && [ "$rc" -ne 130 ]; then
    echo
    echo "  Der Server hat sich mit einem Fehler beendet (siehe oben)."
    echo
    pause
fi
exit "$rc"
