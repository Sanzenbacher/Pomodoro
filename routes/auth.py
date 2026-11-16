"""HTTP-Schicht fuer Konten (KONZEPT-ACCOUNTS.md, 6 und 7).

Nur im gehosteten Betrieb registriert. Duenn wie routes/pomodoro.py: Die
Regeln stehen in data/accounts.py.

Die Seiten (/login, /reset ...) sind bewusst schlicht -- die eigentliche
Oberflaeche folgt im Frontend-Konzept. Sie rufen nur die API unten auf.
"""

import io
import json
import os
import tempfile
import zipfile
from datetime import datetime
from urllib.parse import urlsplit

from flask import Blueprint, g, jsonify, render_template, request, send_file

from data import accounts, db, profiles
from data import pomodoro as pomo
from data.appconfig import ACCOUNTS

bp = Blueprint("auth", __name__)

SECURE = bool(ACCOUNTS.get("cookie_secure", True))
#: __Host- verlangt Secure, Path=/ und keine Domain (OWASP Session Mgmt).
SESSION_COOKIE = "__Host-pomo_session" if SECURE else "pomo_session"

PUBLIC_PAGES = ("/login", "/register", "/forgot", "/reset", "/verify",
                "/verify-email-change")

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


# ---------------------------------------------------------------- Schutz


@bp.before_app_request
def _check_origin():
    """CSRF: Jede schreibende Anfrage muss von der eigenen Seite kommen.
    SameSite=Lax haelt das meiste ab; Origin (sonst Referer) gegen den Host
    pruefen schliesst den Rest. Bildupload ist multipart -- deshalb diese
    Pruefung statt "nur JSON"."""
    if request.method in SAFE_METHODS:
        return None
    source = request.headers.get("Origin") or request.headers.get("Referer")
    expected = request.host_url.rstrip("/")
    if source:
        parts = urlsplit(source)
        if "%s://%s" % (parts.scheme, parts.netloc) == expected:
            return None
    return jsonify({"ok": False, "reason": "Anfrage von fremder Seite abgewiesen."}), 403


def session_token():
    return request.cookies.get(SESSION_COOKIE)


def set_session_cookie(response, token):
    response.set_cookie(SESSION_COOKIE, token,
                        max_age=int(ACCOUNTS.get("session_max_days") or 30) * 86400,
                        secure=SECURE, httponly=True, samesite="Lax", path="/")


def clear_session_cookie(response):
    response.delete_cookie(SESSION_COOKIE, path="/", secure=SECURE, httponly=True,
                           samesite="Lax")


def _data():
    return request.get_json(silent=True) or {}


def _ip():
    return request.remote_addr


def _account():
    """Angemeldetes Konto -- gesetzt von routes/pomodoro._enter_profile oder
    hier aus dem Cookie (die /api/auth-Routen laufen ohne Profil)."""
    account_id = g.get("account_id")
    if account_id:
        return account_id
    account_id = accounts.session_account(session_token())
    g.account_id = account_id
    return account_id


def _needs_login():
    return jsonify({"ok": False, "reason": "Bitte anmelden."}), 401


# ---------------------------------------------------------------- Seiten


def _page(mode):
    return render_template("auth.html", mode=mode, min_password=accounts.MIN_PASSWORD)


@bp.route("/login")
def login_page():
    return _page("login")


@bp.route("/register")
def register_page():
    return _page("register")


@bp.route("/forgot")
def forgot_page():
    return _page("forgot")


@bp.route("/reset")
def reset_page():
    return _page("reset")


@bp.route("/verify")
def verify_page():
    return _page("verify")


@bp.route("/verify-email-change")
def verify_email_change_page():
    return _page("verify-email-change")


# ---------------------------------------------------------------- Anmeldung


@bp.route("/api/auth/register", methods=["POST"])
def api_register():
    data = _data()
    try:
        accounts.register(data.get("email"), data.get("password"),
                          profile_name=data.get("profile_name") or "Ich",
                          tz=data.get("timezone"))
    except accounts.PolicyError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    # Gleiche Antwort, ob es die Adresse schon gibt oder nicht.
    return jsonify({"ok": True, "message": "Fast geschafft: Bitte bestätige deine "
                    "Adresse über den Link in der Mail, die wir gerade geschickt haben."})


@bp.route("/api/auth/verify", methods=["POST"])
def api_verify():
    ok = accounts.verify_email(_data().get("token"))
    if not ok:
        return jsonify({"ok": False, "reason": "Der Link ist ungültig oder abgelaufen."}), 400
    return jsonify({"ok": True})


@bp.route("/api/auth/login", methods=["POST"])
def api_login():
    data = _data()
    try:
        account_id, token = accounts.login(data.get("email"), data.get("password"), _ip())
    except accounts.AuthError as error:
        return jsonify({"ok": False, "reason": str(error)}), 401
    # Neue Sitzung bei jedem Login, die alte (falls da) faellt weg.
    accounts.logout(session_token())
    response = jsonify({"ok": True})
    set_session_cookie(response, token)
    return response


@bp.route("/api/auth/logout", methods=["POST"])
def api_logout():
    accounts.logout(session_token())
    response = jsonify({"ok": True})
    clear_session_cookie(response)
    return response


@bp.route("/api/auth/password/forgot", methods=["POST"])
def api_forgot():
    accounts.request_reset(_data().get("email"), _ip())
    return jsonify({"ok": True, "message": "Wenn es zu dieser Adresse ein Konto gibt, "
                    "ist gleich eine Mail mit einem Link unterwegs."})


@bp.route("/api/auth/password/reset", methods=["POST"])
def api_reset():
    data = _data()
    try:
        accounts.reset_password(data.get("token"), data.get("password"))
    except accounts.PolicyError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    except accounts.AuthError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    response = jsonify({"ok": True, "message": "Neues Passwort gesetzt. Bitte neu anmelden."})
    clear_session_cookie(response)
    return response


# ---------------------------------------------------------------- Konto


@bp.route("/api/auth/me")
def api_me():
    account_id = _account()
    if not account_id:
        return _needs_login()
    info = accounts.account_info(account_id)
    with profiles.as_account(account_id):
        count = len(profiles.all_profiles())
    return jsonify({"ok": True, "account": {
        "id": info["id"], "email": info["email"], "timezone": info["timezone"],
        "created_at": info["created_at"], "profiles": count,
        "max_profiles": profiles.max_profiles()}})


@bp.route("/api/auth/password/change", methods=["POST"])
def api_password_change():
    account_id = _account()
    if not account_id:
        return _needs_login()
    data = _data()
    try:
        accounts.change_password(account_id, data.get("old"), data.get("new"),
                                 keep_token=session_token())
    except (accounts.AuthError, accounts.PolicyError) as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True})


@bp.route("/api/auth/email/change", methods=["POST"])
def api_email_change():
    account_id = _account()
    if not account_id:
        return _needs_login()
    data = _data()
    try:
        accounts.request_email_change(account_id, data.get("password"),
                                      data.get("new_email"))
    except (accounts.AuthError, accounts.PolicyError) as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "message": "Bitte bestätige die neue Adresse über den "
                    "Link in der Mail."})


@bp.route("/api/auth/email/confirm", methods=["POST"])
def api_email_confirm():
    if not accounts.confirm_email_change(_data().get("token")):
        return jsonify({"ok": False, "reason": "Der Link ist ungültig oder abgelaufen."}), 400
    return jsonify({"ok": True})


@bp.route("/api/auth/timezone", methods=["POST"])
def api_timezone():
    account_id = _account()
    if not account_id:
        return _needs_login()
    try:
        name = accounts.set_timezone(account_id, _data().get("timezone"))
    except accounts.PolicyError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "timezone": name})


@bp.route("/api/auth/account", methods=["DELETE"])
def api_delete_account():
    account_id = _account()
    if not account_id:
        return _needs_login()
    password = _data().get("password")
    try:
        accounts.require_password(account_id, password)
    except accounts.AuthError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    # Erst die Timer aller Profile anhalten -- danach ist der Schluessel weg.
    with profiles.as_account(account_id):
        for profile in profiles.all_profiles():
            pomo.forget_profile(profile["id"])
    accounts.delete_account(account_id, password)
    response = jsonify({"ok": True})
    clear_session_cookie(response)
    return response


# ---------------------------------------------------------------- API-Tokens


@bp.route("/api/auth/tokens")
def api_tokens():
    account_id = _account()
    if not account_id:
        return _needs_login()
    return jsonify({"ok": True, "tokens": accounts.list_api_tokens(account_id)})


@bp.route("/api/auth/tokens", methods=["POST"])
def api_token_create():
    account_id = _account()
    if not account_id:
        return _needs_login()
    data = _data()
    try:
        created = accounts.create_api_token(account_id, data.get("password"),
                                            data.get("profile_id"), data.get("label"))
    except (accounts.AuthError, accounts.PolicyError) as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "token": created,
                    "hint": "Das Token wird nur jetzt angezeigt -- bitte sicher ablegen."})


@bp.route("/api/auth/tokens/<token_id>", methods=["DELETE"])
def api_token_revoke(token_id):
    account_id = _account()
    if not account_id:
        return _needs_login()
    if not accounts.revoke_api_token(account_id, token_id):
        return jsonify({"ok": False, "reason": "Unbekanntes Token."}), 404
    return jsonify({"ok": True})


# ---------------------------------------------------------------- Export


@bp.route("/api/auth/export")
def api_export():
    """Alle eigenen Daten entschluesselt als ZIP (Datenportabilitaet)."""
    account_id = _account()
    if not account_id:
        return _needs_login()
    buffer = io.BytesIO()
    with profiles.as_account(account_id), \
            tempfile.TemporaryDirectory(prefix="pomodoro-export-") as tmp, \
            zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        registry = profiles._registry()
        archive.writestr("profiles.json", json.dumps(registry, ensure_ascii=False, indent=2))
        for profile in registry["profiles"]:
            with profiles.as_profile(profile["id"]):
                where = profiles.paths()
                if os.path.exists(where["db"]):
                    plain = os.path.join(tmp, profile["id"] + ".db")
                    db.decrypt_copy(where["db"], plain, profiles.db_key())
                    archive.write(plain, "profiles/%s/pomodoro.db" % profile["id"])
                if os.path.isdir(where["images"]):
                    for name in sorted(os.listdir(where["images"])):
                        full = os.path.join(where["images"], name)
                        if os.path.isfile(full) and not name.endswith(".tmp"):
                            archive.writestr("profiles/%s/projects/%s" % (profile["id"], name),
                                             profiles.read_file(full))
    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True,
                     download_name="pomodoro-export-%s.zip"
                     % datetime.now().strftime("%Y%m%d-%H%M%S"))
