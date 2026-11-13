"""HTTP-Schicht. Duenn: jede Route uebersetzt nur zwischen Request und
data/pomodoro*.py, die Logik steht dort.
"""

import json
import os
import uuid
from datetime import date, timedelta
from urllib.parse import urlencode

from flask import (Blueprint, Response, g, jsonify, redirect, render_template, request,
                   send_from_directory)

from data import pomodoro as pomo
from data import pomodoro_biotop as biotop
from data import pomodoro_feed as feed
from data import pomodoro_icons as icons
from data import pomodoro_journal as journal
from data import pomodoro_journal_feed as journal_feed
from data import pomodoro_notify as notify
from data import pomodoro_palette as palette_mod
from data import pomodoro_projects as projects
from data import pomodoro_stats as stats
from data import profiles
from data.appconfig import POMO

bp = Blueprint("pomodoro", __name__)


#: Abgefragt von anderen Anwendungen (Merge Requests), ohne Cookie. Hier
#: gilt nie das zuletzt gewaehlte Profil -- sonst saehe das Spiel nach
#: jedem Wechsel in der App fremde Daten. Ohne ?profile= das erste Profil.
FEED_PATHS = ("/api/pomodoro/activity", "/api/pomodoro/journal/feed")

#: Kennung dieses App-Starts. "Beim Start fragen" heisst: einmal je Start,
#: nicht nur ohne Cookie -- der Browser behielte pomo_profile sonst ein Jahr.
BOOT_ID = uuid.uuid4().hex[:12]
BOOT_COOKIE = "pomo_boot"

#: Welches Profil dieser Browser gewaehlt hat. Bis zur Umbenennung hiess
#: das Cookie pomo_user -- es wird noch gelesen und beim ersten Kontakt
#: durch das neue ersetzt, sonst verloere jeder Browser seine Wahl.
PROFILE_COOKIE = "pomo_profile"
OLD_PROFILE_COOKIE = "pomo_user"
PROFILE_COOKIE_AGE = 365 * 24 * 3600


def _set_profile_cookie(response, profile_id):
    response.set_cookie(PROFILE_COOKIE, profile_id, max_age=PROFILE_COOKIE_AGE,
                        samesite="Lax")
    response.delete_cookie(OLD_PROFILE_COOKIE)


def _wants_chooser():
    """Seitenaufruf, der erst die Auswahl "Wer bist du?" braucht?"""
    path = request.path
    if request.method != "GET" or path == "/pomodoro/profiles":
        return False
    if not (path == "/pomodoro" or path.startswith("/pomodoro/")):
        return False
    if path.startswith("/pomodoro/media/"):
        return False
    return (profiles.ask_on_start()
            and request.cookies.get(BOOT_COOKIE) != BOOT_ID)


@bp.before_app_request
def _enter_profile():
    """Jede Anfrage laeuft fuer genau ein Profil (KONZEPT-PROFILE.md, 4)."""
    if request.path in FEED_PATHS:
        if "user" in request.args and "profile" not in request.args:
            # Laut statt still die Daten des Feed-Profils: Ein Abnehmer mit
            # dem alten Parameter zaehlte sonst unbemerkt fuer den Falschen.
            return jsonify({"ok": False, "reason": "Der Parameter ?user= heisst "
                            "jetzt ?profile=."}), 400
        # ?profile= nimmt id oder Namen: ?profile=Lena reicht.
        wanted = request.args.get("profile")
        if wanted:
            found = profiles.find(wanted)
            if not found:
                return jsonify({"ok": False, "reason": "Unbekanntes Profil."}), 404
            profile_id = found["id"]
        else:
            profile_id = profiles.feed_profile_id()
    else:
        if _wants_chooser():
            return redirect("/pomodoro/profiles?" + urlencode({"next": request.full_path.rstrip("?")}))
        chosen = request.cookies.get(PROFILE_COOKIE)
        if not chosen and request.cookies.get(OLD_PROFILE_COOKIE):
            chosen = request.cookies.get(OLD_PROFILE_COOKIE)
            g.pomo_cookie_upgrade = True
        profile_id = profiles.resolve(chosen)
    g.pomo_profile_token = profiles.activate(profile_id)


@bp.after_app_request
def _upgrade_profile_cookie(response):
    """Altes pomo_user einmal durch pomo_profile ersetzen."""
    if g.pop("pomo_cookie_upgrade", False):
        _set_profile_cookie(response, profiles.current())
    return response


@bp.teardown_app_request
def _leave_profile(_exc):
    token = g.pop("pomo_profile_token", None)
    if token is not None:
        profiles.deactivate(token)


@bp.app_context_processor
def _profile_helpers():
    return {"current_profile": profiles.get(profiles.current()),
            "all_profiles": profiles.all_profiles()}


@bp.app_context_processor
def _icon_helpers():
    return {"project_icon": icons.for_project, "icon_svg": icons.svg,
            "ICONS": icons.ICONS}


REASON_LABELS = {"flow": "Im Flow", "unnoticed": "Nicht bemerkt",
                 "finishing": "Musste fertig werden"}


def _current_project():
    """Das Projekt, dessen Farben gerade gelten: das der laufenden Sitzung,
    sonst das zuletzt gewaehlte, sonst das Standardprojekt."""
    state = pomo.get_state()
    if state["session"] and state["session"]["project_id"]:
        row = pomo.project(state["session"]["project_id"])
        if row:
            return row
    wanted = request.args.get("project", type=int) or request.cookies.get("pomo_project")
    try:
        row = pomo.project(int(wanted)) if wanted else None
    except (TypeError, ValueError):
        row = None
    # Eine reine Journal-Kategorie hat im Timer nichts verloren.
    if row and not row.get("use_timer", 1):
        row = None
    return row or pomo.project()


def _page_context():
    row = _current_project()
    view = projects.view(row) if row else None
    return {
        "project": view,
        "projects": [projects.view(p) for p in pomo.projects()],
        "presets": pomo.presets(),
        "state": pomo.get_state(),
        "palette": view["palette"] if view else None,
        "palette_css": palette_mod.css_vars(view["palette"] if view else
                                            palette_mod.default_palette()),
        "font": view["font"] if view else "Cormorant Garamond",
        "config": POMO,
        "settings": pomo.settings(),
        # Hintergrund jeder Seite: der laufende Monat. Die Biotop-Seite
        # zeichnet ihn selbst gross und setzt das wieder auf None.
        "biotop_bg": biotop.month(),
    }


# ---------------------------------------------------------------- Seiten


@bp.route("/pomodoro")
def page():
    context = _page_context()
    context["active"] = "timer"
    context["summary"] = stats.summary("today", context["project"]["id"]
                                       if context["project"] else None)
    hours = stats.by_hour("30")
    context["hours_svg"] = stats.hours_svg(hours, context["palette"])
    context["best_window"] = stats.best_window(hours)
    context["calendar_svg"] = stats.calendar_svg(
        stats.calendar(18), context["palette"],
        link=lambda day: "/pomodoro/stats?range=all&day=%s#sitzungen" % day)
    # Heute und die letzten Wochen ueber alle Projekte -- die Kennzahlen oben
    # gelten fuer das gewaehlte Projekt, diese Uebersicht fuer den ganzen Tag.
    colors = projects.stats_colors()
    timeline = stats.today_timeline()
    weeks = stats.weekly(8)
    context["today"] = timeline
    context["timeline_svg"] = stats.timeline_svg(timeline, context["palette"], colors)
    context["weekly_svg"] = stats.weekly_svg(
        weeks, context["palette"], colors, height=96,
        link=lambda monday: "/pomodoro/stats?range=all&week=%s#sitzungen" % monday)
    context["this_week"] = weeks[-1]
    context["rating_legend"] = stats.rating_legend(context["palette"])
    context["weekly_legend"] = stats.legend(weeks, colors)
    return render_template("pomodoro.html", **context)


@bp.route("/pomodoro/stats")
def stats_page():
    context = _page_context()
    context["active"] = "stats"
    range_key = request.args.get("range", "30")
    project_id = request.args.get("project", type=int)
    palette = context["palette"]

    hours = stats.by_hour(range_key, project_id)
    colors = projects.stats_colors()
    days = stats.daily(range_key, project_id)
    weeks = stats.weekly(12, project_id)
    # Das Tagesziel gilt fuer alle Projekte zusammen -- im Projektfilter
    # waere die Linie irrefuehrend.
    goal_minutes = (None if project_id else
                    int(pomo.setting("daily_goal_pomodoros")) * pomo.preset()["work_min"])

    # Klick auf einen Balken: Sitzungstabelle auf Tag oder Woche einschraenken.
    base = "?range=%s%s" % (range_key, "&project=%d" % project_id if project_id else "")
    sel_day = request.args.get("day")
    sel_week = request.args.get("week")
    filter_days, filter_label = None, None
    try:
        if sel_day:
            date.fromisoformat(sel_day)
            filter_days = {sel_day}
            filter_label = stats.day_label(sel_day)
        elif sel_week:
            monday = date.fromisoformat(sel_week)
            filter_days = {(monday + timedelta(days=n)).isoformat() for n in range(7)}
            filter_label = "KW %d · %s – %s" % (
                monday.isocalendar()[1], monday.strftime("%d.%m."),
                (monday + timedelta(days=6)).strftime("%d.%m.%Y"))
    except ValueError:
        filter_days = None
    if filter_days:
        rows = [r for r in pomo.sessions(limit=100000, project_id=project_id)
                if pomo.day_of(pomo.parse(r["started_at"])) in filter_days]
    else:
        rows = pomo.sessions(limit=120, project_id=project_id)
    for row in rows:
        # In der Datenbank steht UTC; die Tabelle zeigt Ortszeit wie die Diagramme.
        local = pomo.parse(row["started_at"]).astimezone()
        row["local_start"] = local.strftime("%H:%M · %d.%m.%Y")
    breakdown = stats.by_project(range_key)
    for bucket in breakdown:
        bucket["color"] = colors.get(bucket["id"]) or stats.NO_PROJECT_COLOR
    # Filter: alles aus dem Timer, dazu jede Kategorie mit Sitzungen im
    # Zeitraum -- auch archivierte oder inzwischen nur noch im Journal.
    filter_projects = list(context["projects"])
    listed = {p["id"] for p in filter_projects}
    extra = {b["id"] for b in breakdown if b["id"]} | ({project_id} if project_id else set())
    for row in pomo.projects(include_archived=True, use=None):
        if row["id"] in extra - listed:
            filter_projects.append(projects.view(row))
    context.update({
        "filter_projects": filter_projects,
        "range_key": range_key,
        "filter_project": project_id,
        "summary": stats.summary(range_key, project_id),
        "discipline": stats.discipline(range_key, project_id),
        "hours_svg": stats.hours_svg(hours, palette, height=132),
        "best_window": stats.best_window(hours),
        "weekday_svg": stats.weekday_svg(stats.by_weekday(range_key, project_id), palette),
        "calendar_svg": stats.calendar_svg(
            stats.calendar(26, project_id), palette,
            link=lambda day: "%s&day=%s#sitzungen" % (base, day)),
        "trend_svg": stats.trend_svg(stats.trend(range_key, project_id), palette),
        "focus_bars_svg": stats.focus_bars_svg(
            days, palette, colors, goal_minutes=goal_minutes, selected=sel_day,
            link=lambda day: "%s&day=%s#sitzungen" % (base, day)),
        "goal_minutes": goal_minutes,
        "this_week": weeks[-1],
        "rating_legend": stats.rating_legend(palette),
        "filter_label": filter_label,
        "filter_clear": base + "#sitzungen",
        "focus_legend": stats.legend(days, colors),
        "weekly_svg": stats.weekly_svg(
            weeks, palette, colors,
            link=lambda monday: "%s&week=%s#sitzungen" % (base, monday)),
        "reason_labels": REASON_LABELS,
        "breakdown": breakdown,
        "breakdown_svg": stats.breakdown_svg(breakdown, palette, colors),
        "rows": rows,
    })
    return render_template("pomodoro_stats.html", **context)


@bp.route("/pomodoro/journal")
def journal_page():
    context = _page_context()
    context["active"] = "journal"
    days = max(1, request.args.get("days", 14, type=int))
    timeline = journal.timeline(days)
    for bucket in timeline["days"]:
        bucket["label"] = stats.day_label(bucket["day"])
    context["timeline"] = timeline
    # Icons fuer Chips und Tagesverlauf: Aktivitaeten sind Kategorien wie
    # Projekte und sehen deshalb genauso aus (KONZEPT-PROJEKTE-AKTIVITAETEN.md).
    views = {p["id"]: projects.view(p) for p in pomo.projects(include_archived=True, use=None)}
    context["category_views"] = views
    activities = journal.activities()
    for activity in activities:
        activity["icon"] = str(icons.for_project(views.get(activity["id"]), 18, "picon chip-icon"))
    context["activities"] = activities
    context["feelings"] = journal.feelings()
    return render_template("pomodoro_journal.html", **context)


@bp.route("/pomodoro/biotop")
def biotop_page():
    context = _page_context()
    context["active"] = "biotop"
    context["biotop_bg"] = None
    context["gallery"] = biotop.gallery()
    context["targets"] = biotop.targets()
    return render_template("pomodoro_biotop.html", **context)


#: Umschalter ueber der Liste auf der Projektseite: Schluessel -> use fuer
#: pomo.projects(). Siehe KONZEPT-PROJEKTE-AKTIVITAETEN.md, Abschnitt 5.
CATEGORY_FILTERS = {"all": None, "timer": "timer", "journal": "journal"}


def _use_payload(data, before=None):
    """use_timer/use_journal aus einer Anfrage. Beide aus geht nicht -- zum
    Ausblenden gibt es Archivieren. ValueError mit Satz fuer die Oberflaeche."""
    fields = {}
    for key in ("use_timer", "use_journal"):
        if key in data:
            fields[key] = 1 if data[key] else 0
    if fields:
        merged = {"use_timer": 1, "use_journal": 0, **(before or {}), **fields}
        if not merged["use_timer"] and not merged["use_journal"]:
            raise ValueError("Timer oder Journal — eins von beiden bleibt an. "
                             "Zum Ausblenden archivieren.")
    return fields


@bp.route("/pomodoro/projects")
def projects_page():
    """Projekte & Aktivitaeten: eine Liste fuer alle Kategorien, egal ob im
    Timer, im Journal oder in beiden. Bearbeitet werden kann jede, auch eine,
    die der Timer nicht kennt -- deshalb waehlt die Seite selbst aus."""
    context = _page_context()
    context["active"] = "projects"
    shown = request.args.get("filter")
    shown = shown if shown in CATEGORY_FILTERS else "all"
    rows = pomo.projects(use=CATEGORY_FILTERS[shown])
    categories = [projects.view(p) for p in rows]

    wanted = request.args.get("project", type=int)
    row = pomo.project(wanted) if wanted else None
    if row is None and context["project"] and not any(
            c["id"] == context["project"]["id"] for c in categories):
        row = rows[0] if rows else None
    if row is not None and (not context["project"] or row["id"] != context["project"]["id"]):
        view = projects.view(row)
        context.update({"project": view, "palette": view["palette"], "font": view["font"],
                        "palette_css": palette_mod.css_vars(view["palette"])})
    elif not rows:
        context["project"] = None

    plants = None
    if context["project"]:
        target = next((t for t in biotop.targets() if t["id"] == context["project"]["id"]), None)
        plants = target["plants"] if target else None
    everything = pomo.projects(use=None)
    context.update({
        "categories": categories,
        "filter": shown,
        "filter_counts": {"all": len(everything),
                          "timer": sum(1 for p in everything if p["use_timer"]),
                          "journal": sum(1 for p in everything if p["use_journal"])},
        "plants": plants,
        "collisions": projects.collide(),
    })
    return render_template("pomodoro_projects.html", **context)


@bp.route("/pomodoro/settings")
def settings_page():
    context = _page_context()
    context["active"] = "settings"
    context["settings"] = pomo.settings()
    context["profile_colors"] = profiles.COLORS
    context["ask_on_start"] = profiles.ask_on_start_setting()
    context["spec"] = pomo.SETTING_SPEC
    context["summary"] = stats.summary("today")
    return render_template("pomodoro_settings.html", **context)


@bp.route("/pomodoro/media/<path:name>")
def media(name):
    """Projektbilder liegen ausserhalb von static/, damit storage/ die
    einzige Stelle mit Nutzerdaten bleibt."""
    return send_from_directory(projects.image_dir(), name, max_age=0)


# ---------------------------------------------------------------- Timer


@bp.route("/api/pomodoro/state")
def api_state():
    state = pomo.get_state()
    state["alerts"] = notify.take_pending()
    if state["session"] and state["session"]["project_id"]:
        row = pomo.project(state["session"]["project_id"])
        if row:
            pal = projects.resolve(row)
            state["project"] = {"id": row["id"], "label": row["label"],
                                "a1": pal["a1"], "a2": pal["a2"]}
    return jsonify(state)


@bp.route("/api/pomodoro/start", methods=["POST"])
def api_start():
    data = request.get_json(silent=True) or {}
    return jsonify(pomo.start(
        kind=data.get("kind", "work"),
        project_id=data.get("project_id"),
        preset_id=data.get("preset_id"),
        target_kind=data.get("target_kind"),
        target_id=data.get("target_id")))


@bp.route("/api/pomodoro/pause", methods=["POST"])
def api_pause():
    return jsonify(pomo.pause())


@bp.route("/api/pomodoro/resume", methods=["POST"])
def api_resume():
    return jsonify(pomo.resume())


@bp.route("/api/pomodoro/abort", methods=["POST"])
def api_abort():
    return jsonify(pomo.abort())


@bp.route("/api/pomodoro/complete", methods=["POST"])
def api_complete():
    return jsonify(pomo.complete())


@bp.route("/api/pomodoro/skip", methods=["POST"])
def api_skip():
    return jsonify(pomo.skip())


@bp.route("/api/pomodoro/interrupt", methods=["POST"])
def api_interrupt():
    return jsonify(pomo.interrupt())


@bp.route("/api/pomodoro/annotate", methods=["POST"])
def api_annotate():
    data = request.get_json(silent=True) or {}
    return jsonify(pomo.annotate(data.get("session_id"),
                                 data.get("focus_rating"),
                                 data.get("note"),
                                 data.get("tags"),
                                 data.get("overtime_reason")))


@bp.route("/api/pomodoro/recover", methods=["POST"])
def api_recover():
    data = request.get_json(silent=True) or {}
    return jsonify(pomo.recover_decide(data.get("mode", "discarded"),
                                       data.get("until")))


# ---------------------------------------------------------------- Projekte


@bp.route("/api/pomodoro/projects")
def api_projects():
    """?use=timer|journal filtert, ohne use kommen alle Kategorien."""
    use = request.args.get("use")
    return jsonify([projects.view(p) for p in
                    pomo.projects(include_archived=request.args.get("all") == "1",
                                  use=use if use in ("timer", "journal") else None)])


@bp.route("/api/pomodoro/projects", methods=["POST"])
def api_project_create():
    data = request.get_json(silent=True) or {}
    label = (data.get("label") or "").strip()
    if not label:
        return jsonify({"ok": False, "reason": "Name fehlt."}), 400
    try:
        use = _use_payload(data)
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    project_id = pomo.create_project(label, data.get("color"), **use)
    projects.recompute(project_id)
    return jsonify({"ok": True, "project": projects.view(pomo.project(project_id))})


@bp.route("/api/pomodoro/projects/<int:project_id>", methods=["POST"])
def api_project_update(project_id):
    data = request.get_json(silent=True) or {}
    row = pomo.project(project_id)
    if not row or row["id"] != project_id:
        return jsonify({"ok": False, "reason": "Diese Kategorie gibt es nicht mehr."}), 404
    fields = {k: v for k, v in data.items()
              if k in ("label", "color", "archived", "is_default", "display_font",
                       "hue_shift", "chroma_scale", "palette_locked", "stats_color",
                       "icon")}
    try:
        fields.update(_use_payload(data, {k: row[k] for k in ("use_timer", "use_journal")}))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    if row["is_default"] and fields.get("use_timer") == 0:
        return jsonify({"ok": False, "reason": "Das Standardprojekt bleibt im Timer."}), 400
    pomo.update_project(project_id, fields)
    if "overrides" in data:
        projects.recompute(project_id, data["overrides"])
    else:
        projects.recompute(project_id)
    return jsonify({"ok": True, "project": projects.view(pomo.project(project_id))})


@bp.route("/api/pomodoro/projects/<int:project_id>", methods=["DELETE"])
def api_project_delete(project_id):
    hard = request.args.get("hard") == "1"
    result = pomo.delete_project(project_id, hard=hard)
    if result.get("action") == "deleted":
        projects.remove_image(project_id, keep_palette=True)
    return jsonify(result)


@bp.route("/api/pomodoro/projects/<int:project_id>/image", methods=["POST"])
def api_project_image(project_id):
    """Der Browser schickt Bild, Miniaturen und die gefundenen Farbtoene
    in einem Rutsch. Siehe static/js/pomodoro_palette.js."""
    upload = request.files.get("image")
    if not upload:
        return jsonify({"ok": False, "reason": "Kein Bild dabei."}), 400
    try:
        seeds = json.loads(request.form.get("seeds") or "{}")
        palette = projects.save_image(
            project_id, upload.read(), upload.mimetype, seeds,
            thumb_url=request.form.get("thumb"),
            veil_url=request.form.get("veil"))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "palette": palette,
                    "project": projects.view(pomo.project(project_id)),
                    "collisions": projects.collide(project_id)})


@bp.route("/api/pomodoro/projects/<int:project_id>/image", methods=["DELETE"])
def api_project_image_delete(project_id):
    projects.remove_image(project_id)
    return jsonify({"ok": True, "project": projects.view(pomo.project(project_id))})


@bp.route("/api/pomodoro/projects/<int:project_id>/palette", methods=["POST"])
def api_project_palette(project_id):
    """Vorschau fuer die Regler: rechnet, ohne zu speichern."""
    data = request.get_json(silent=True) or {}
    row = pomo.project(project_id)
    if not row:
        return jsonify({"ok": False}), 404
    from data import pomodoro_palette as palette_mod
    result = palette_mod.derive(
        projects.seeds_of(row),
        hue_shift=data.get("hue_shift", row["hue_shift"]),
        chroma_scale=data.get("chroma_scale", row["chroma_scale"]),
        overrides=data.get("overrides") or projects.overrides_of(row))
    return jsonify({"ok": True, "palette": result,
                    "font": data.get("display_font") or row["display_font"]
                    or palette_mod.font_suggestion(result)})


# ---------------------------------------------------------------- Presets


@bp.route("/api/pomodoro/settings")
def api_settings():
    return jsonify(pomo.settings())


@bp.route("/api/pomodoro/settings", methods=["POST"])
def api_settings_save():
    data = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "settings": pomo.save_settings(data),
                    "all": pomo.settings()})


@bp.route("/api/pomodoro/presets")
def api_presets():
    return jsonify(pomo.presets())


@bp.route("/api/pomodoro/presets", methods=["POST"])
def api_preset_create():
    data = request.get_json(silent=True) or {}
    preset_id = pomo.save_preset(data)
    return jsonify({"ok": True, "id": preset_id, "presets": pomo.presets()})


@bp.route("/api/pomodoro/presets/<int:preset_id>", methods=["POST"])
def api_preset_update(preset_id):
    data = request.get_json(silent=True) or {}
    pomo.save_preset(data, preset_id)
    return jsonify({"ok": True, "presets": pomo.presets()})


@bp.route("/api/pomodoro/presets/<int:preset_id>", methods=["DELETE"])
def api_preset_delete(preset_id):
    try:
        return jsonify({"ok": pomo.delete_preset(preset_id)})
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400


# ---------------------------------------------------------------- Sitzungen


@bp.route("/api/pomodoro/sessions")
def api_sessions():
    return jsonify(pomo.sessions(
        limit=request.args.get("limit", 200, type=int),
        project_id=request.args.get("project", type=int),
        day=request.args.get("day")))


@bp.route("/api/pomodoro/sessions", methods=["POST"])
def api_session_create():
    """Nachtrag fuer Arbeit ausserhalb der App."""
    data = request.get_json(silent=True) or {}
    try:
        session_id = pomo.add_manual_session(
            data.get("project_id"), data.get("kind", "work"),
            data["started_at"], data.get("minutes", 25), data.get("note"))
    except (KeyError, TypeError, ValueError) as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "id": session_id})


@bp.route("/api/pomodoro/sessions/<session_id>", methods=["POST"])
def api_session_update(session_id):
    return jsonify({"ok": pomo.update_session(session_id,
                                              request.get_json(silent=True) or {})})


@bp.route("/api/pomodoro/sessions/<session_id>", methods=["DELETE"])
def api_session_delete(session_id):
    return jsonify({"ok": pomo.delete_session(session_id)})


# ---------------------------------------------------------------- Journal


@bp.route("/api/pomodoro/journal")
def api_journal():
    return jsonify(journal.entries())


@bp.route("/api/pomodoro/journal", methods=["POST"])
def api_journal_create():
    try:
        return jsonify({"ok": True,
                        "id": journal.add(request.get_json(silent=True) or {})})
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)})


@bp.route("/api/pomodoro/journal/<entry_id>", methods=["POST"])
def api_journal_update(entry_id):
    try:
        return jsonify({"ok": journal.update(entry_id,
                                             request.get_json(silent=True) or {})})
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)})


@bp.route("/api/pomodoro/journal/<entry_id>", methods=["DELETE"])
def api_journal_delete(entry_id):
    return jsonify({"ok": journal.delete(entry_id)})


# ---------------------------------------------------------------- Biotop


@bp.route("/api/pomodoro/biotop")
def api_biotop():
    """Ein Monat zum Zeichnen, ohne ?month der laufende."""
    try:
        return jsonify(biotop.month(request.args.get("month")))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400


@bp.route("/api/pomodoro/biotop/theme", methods=["POST"])
def api_biotop_theme():
    data = request.get_json(silent=True) or {}
    try:
        biotop.set_theme(data.get("month") or biotop.current_month(), data.get("theme"))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)})
    return jsonify({"ok": True, "month": biotop.month()})


@bp.route("/api/pomodoro/biotop/map", methods=["POST"])
def api_biotop_map():
    data = request.get_json(silent=True) or {}
    try:
        biotop.set_plant(data.get("kind"), data.get("id"), data.get("theme"), data.get("plant"))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)})
    return jsonify({"ok": True, "targets": biotop.targets()})


# ---------------------------------------------------------------- Feed


def _with_profile(payload):
    """Feeds sagen, wessen Daten sie liefern (zusaetzliches Feld, der
    Vertrag activity/1 bleibt sonst unveraendert)."""
    profile = profiles.get(profiles.current()) or {}
    payload.setdefault("meta", {})["profile"] = {"id": profile.get("id"),
                                                 "name": profile.get("name")}
    return payload


# ---------------------------------------------------------------- Profil


def _profile_row(profile):
    with profiles.as_profile(profile["id"]):
        summary = pomo.profile_summary()
    return dict(profile, **summary)


@bp.route("/api/pomodoro/profiles")
def api_profiles():
    """Alle Profile mit laufendem Timer je Profil."""
    return jsonify({"current": profiles.current(), "feed_profile": profiles.feed_profile_id(),
                    "profiles": [_profile_row(u) for u in profiles.all_profiles()]})


@bp.route("/api/pomodoro/profiles", methods=["POST"])
def api_profile_create():
    data = request.get_json(silent=True) or {}
    try:
        profile = profiles.create(data.get("name"), data.get("color"))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    if data.get("copy_settings", True):
        source = profiles.current()
        with profiles.as_profile(profile["id"]):
            pomo.copy_settings_from(source)
    return jsonify({"ok": True, "profile": _profile_row(profile)})


@bp.route("/api/pomodoro/profiles/<profile_id>", methods=["POST"])
def api_profile_update(profile_id):
    data = request.get_json(silent=True) or {}
    try:
        profile = profiles.update(profile_id, data.get("name"), data.get("color"))
    except KeyError:
        return jsonify({"ok": False, "reason": "Unbekanntes Profil."}), 404
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "profile": profile})


@bp.route("/api/pomodoro/profiles/<profile_id>", methods=["DELETE"])
def api_profile_delete(profile_id):
    if profile_id == profiles.current():
        return jsonify({"ok": False, "reason": "Das aktive Profil kann nicht "
                        "geloescht werden -- erst wechseln."}), 400
    if not profiles.get(profile_id):
        return jsonify({"ok": False, "reason": "Unbekanntes Profil."}), 404
    if len(profiles.all_profiles()) <= 1:
        return jsonify({"ok": False, "reason": "Das letzte Profil kann nicht "
                        "geloescht werden."}), 400
    if profile_id == profiles.feed_profile_id():
        return jsonify({"ok": False, "reason": "Merge Requests liest die Daten "
                        "dieses Profils -- es kann nicht geloescht werden."}), 400
    pomo.forget_profile(profile_id)
    try:
        moved = profiles.remove(profile_id)
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "moved_to": moved})


@bp.route("/api/pomodoro/profiles/settings", methods=["POST"])
def api_profiles_settings():
    data = request.get_json(silent=True) or {}
    try:
        flag = profiles.set_ask_on_start(bool(data.get("ask_on_start")))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "ask_on_start": flag})


def _safe_next(target):
    """Nur Ziele innerhalb der App -- kein offener Redirect."""
    target = target or "/pomodoro"
    if not target.startswith("/pomodoro") or target.startswith("/pomodoro/profiles"):
        return "/pomodoro"
    return target


@bp.route("/pomodoro/profiles")
def profiles_page():
    """Auswahl "Wer bist du?" (KONZEPT-PROFILE.md, 6). Ohne Biotop und
    Mini-Timer -- noch steht nicht fest, wessen."""
    return render_template(
        "pomodoro_profiles.html",
        profiles_rows=[_profile_row(u) for u in profiles.all_profiles()],
        current_id=profiles.current(),
        next_url=_safe_next(request.args.get("next")),
        palette_css=palette_mod.css_vars(palette_mod.default_palette()),
        profile_colors=profiles.COLORS)


@bp.route("/api/pomodoro/profile/switch", methods=["POST"])
def api_profile_switch():
    data = request.get_json(silent=True) or {}
    profile_id = data.get("id")
    try:
        profiles.remember(profile_id)
    except KeyError:
        return jsonify({"ok": False, "reason": "Unbekanntes Profil."}), 404
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    with profiles.as_profile(profile_id):
        running = pomo.get_state()["state"] != "idle"
    previous = profiles.current()
    with profiles.as_profile(previous):
        left_running = pomo.get_state()["state"] in ("running", "paused")
    response = jsonify({"ok": True, "profile": profiles.get(profile_id),
                        "running": running,
                        "left_running": left_running and previous != profile_id})
    _set_profile_cookie(response, profile_id)
    # Fuer diesen App-Start ist die Frage "Wer bist du?" beantwortet.
    response.set_cookie(BOOT_COOKIE, BOOT_ID, samesite="Lax")
    # Projekt-ids gelten nur in der Datenbank eines Profils.
    response.delete_cookie("pomo_project")
    return response


@bp.route("/api/pomodoro/activity")
def api_activity():
    """Activity Feed v1 fuer andere Anwendungen, siehe data/pomodoro_feed.py."""
    try:
        return jsonify(_with_profile(feed.read(since=request.args.get("since"),
                                 start=request.args.get("start"),
                                 limit=request.args.get("limit", type=int))))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400


@bp.route("/api/pomodoro/journal/feed")
def api_journal_feed():
    """Activity Feed v1 fuer Aktivitaeten, siehe data/pomodoro_journal_feed.py."""
    try:
        return jsonify(_with_profile(journal_feed.read(since=request.args.get("since"),
                                         start=request.args.get("start"),
                                         limit=request.args.get("limit", type=int))))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400


@bp.route("/api/pomodoro/stats")
def api_stats():
    range_key = request.args.get("range", "30")
    project_id = request.args.get("project", type=int)
    hours = stats.by_hour(range_key, project_id)
    return jsonify({
        "summary": stats.summary(range_key, project_id),
        "discipline": stats.discipline(range_key, project_id),
        "hours": hours,
        "best_window": stats.best_window(hours),
        "weekday": stats.by_weekday(range_key, project_id),
        "projects": stats.by_project(range_key),
        "daily": stats.daily(range_key, project_id),
    })


@bp.route("/api/pomodoro/export.csv")
def api_export():
    payload = stats.csv_export(request.args.get("range", "all"),
                               request.args.get("project", type=int))
    return Response(
        payload.encode("utf-8-sig"),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=pomodoro.csv"})
