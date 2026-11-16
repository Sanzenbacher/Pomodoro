"""Erinnerung beim Ablauf -- drei Ebenen mit unterschiedlicher Reichweite.

    1 Ton     winsound aus der stdlib        immer, auch minimiert
    2 Toast   windows-toasts, sonst PowerShell   auch im Hintergrund
    3 Fenster pywebview restore + Overlay    wenn die App laeuft

Der Ton laeuft getrennt ueber die stdlib. Er ist die eigentliche Erinnerung
und darf nie an einer optionalen Abhaengigkeit haengen. Alles ist per
config.yaml abschaltbar, und jede Ebene faellt still aus, wenn sie nicht
kann. Siehe KONZEPT.md, Abschnitt 3.
"""

import os
import subprocess
import sys
import threading

from data import profiles
from data.appconfig import POMO, ROOT, hosted

NOTIFY = POMO["notify"]

_toaster = None
_toaster_tried = False

#: Wird von der Oberflaeche abgeholt (Ebene 3) und dann geleert -- je
#: Profil, damit eine Nachfrage nur bei dem ankommt, dem sie gehoert.
_pending = {}
_pending_lock = threading.Lock()

LABELS = {
    "work": "Arbeitsphase",
    "short_break": "Kurze Pause",
    "long_break": "Lange Pause",
}


# ---------------------------------------------------------------- Ebene 1


def play_sound():
    # Gehostet klingelte der Server, nicht der Rechner der Familie.
    if hosted() or not NOTIFY.get("sound"):
        return False
    try:
        import winsound
    except ImportError:
        return False
    path = os.path.join(ROOT, NOTIFY.get("sound_file") or "")
    try:
        if os.path.exists(path):
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- Ebene 2


def _get_toaster():
    """windows-toasts ist optional. Fehlt es, faellt alles auf PowerShell
    zurueck, und wenn auch das nicht geht, bleibt der Ton."""
    global _toaster, _toaster_tried
    if _toaster_tried:
        return _toaster
    _toaster_tried = True
    try:
        from windows_toasts import WindowsToaster
        _toaster = WindowsToaster("GameDev Tools")
    except Exception:
        _toaster = None
    return _toaster


def _toast_powershell(title, body):
    """Fallback ohne Abhaengigkeit: rund 300 ms Prozessstart, Absender heisst
    Windows PowerShell, keine Rueckmeldung -- reicht als Notnagel."""
    if sys.platform != "win32":
        return False
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,"
        " ContentType=WindowsRuntime] > $null;"
        "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);"
        "$n=$t.GetElementsByTagName('text');"
        "$n.Item(0).AppendChild($t.CreateTextNode('%s')) > $null;"
        "$n.Item(1).AppendChild($t.CreateTextNode('%s')) > $null;"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        "'GameDev Tools').Show([Windows.UI.Notifications.ToastNotification]::new($t))"
    ) % (title.replace("'", " "), body.replace("'", " "))
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


def _named(title):
    """Mit mehr als einem Profil: "Lena · Arbeitsphase fertig"."""
    try:
        if len(profiles.all_profiles()) > 1:
            profile = profiles.get(profiles.current())
            if profile:
                return "%s · %s" % (profile["name"], title)
    except Exception:
        pass
    return title


def _toast(title, body):
    """Toast im Hintergrund; den Namen vorher holen -- der Thread hat
    keinen Profil-Kontext."""
    threading.Thread(target=show_toast, args=(_named(title), body),
                     daemon=True).start()


def show_toast(title, body):
    if hosted() or not NOTIFY.get("toast"):
        return False
    toaster = _get_toaster()
    if toaster is not None:
        try:
            from windows_toasts import Toast
            notification = Toast()
            notification.text_fields = [title, body]
            toaster.show_toast(notification)
            return True
        except Exception:
            pass
    return _toast_powershell(title, body)


# ---------------------------------------------------------------- Ebene 3


def raise_window():
    """Bei minimiertem Fenster hilft ein DOM-Overlay gar nichts -- erst muss
    das Fenster wieder da sein."""
    if hosted() or not NOTIFY.get("raise_window"):
        return False
    try:
        import webview
        if webview.windows:
            webview.windows[0].restore()
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------- Bescheid


def announce(payload):
    """Ruft die Ebenen. Keine darf die anderen aufhalten.

    Das Ende einer Arbeitsphase unterbricht nicht: Wer im Flow ist, schaut
    nicht auf die Uhr, und die zaehlt ohnehin als Ueberzeit weiter. Deshalb
    dort nur Ton und Toast -- kein Fenster nach vorn, kein Overlay, nichts
    zu bestaetigen. Nur das Pausenende holt einen zurueck an den Tisch.
    """
    kind = payload.get("kind", "work")
    label = LABELS.get(kind, kind)
    work = kind == "work"

    title = "%s fertig" % label
    body = payload.get("body") or (
        "Fokuszeit vorbei — die Uhr läuft weiter." if work
        else "Pause vorbei — die Uhr läuft weiter.")

    play_sound()
    _toast(title, body)
    if not work:
        raise_window()

    _push({"title": title, "body": body, "kind": kind,
           "session_id": payload.get("session_id"), "quiet": work})


# ---------------------------------------------------------------- Ueberzeit


def _context(payload):
    return payload.get("project") or LABELS.get(payload.get("kind"), "")


def overtime_reminder(payload):
    """Dezente Erinnerung waehrend der Ueberzeit: nur Toast, kein Ton --
    der Ton gehoert dem Ablauf. In der Oberflaeche ein kleiner Hinweis,
    kein Overlay."""
    minutes = payload.get("minutes") or 0
    if payload.get("kind") == "work":
        title = "Seit %d Minuten in Überzeit" % minutes
    else:
        title = "Pause seit %d Minuten überzogen" % minutes
    body = "%s · die Uhr läuft weiter." % _context(payload)
    _toast(title, body)
    _push({"title": title, "body": body, "kind": payload.get("kind"),
           "session_id": payload.get("session_id"), "quiet": True})


def overtime_capped(payload):
    """Obergrenze erreicht: Die Uhr steht, beim naechsten Blick kommt die
    Nachfrage. Deshalb auch hier nur ein Toast."""
    title = "Überzeit angehalten"
    body = "%s · %d Minuten über der Zeit. Wie viel davon war Arbeit?" % (
        _context(payload), payload.get("cap_minutes") or 0)
    _toast(title, body)
    _push({"title": title, "body": body, "kind": payload.get("kind"),
           "session_id": payload.get("session_id"), "quiet": True})


def _push(alert):
    with _pending_lock:
        _pending.setdefault(profiles.current_key(), []).append(alert)


def take_pending():
    """Die Seite fragt beim Pollen nach und bekommt jeden Alarm genau einmal
    -- nur die des aktuellen Profils."""
    with _pending_lock:
        return _pending.pop(profiles.current_key(), [])
