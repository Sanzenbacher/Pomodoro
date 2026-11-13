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
from data import users
from data.appconfig import POMO

bp = Blueprint("pomodoro", __name__)


#: Abgefragt von anderen Anwendungen (Merge Requests), ohne Cookie. Hier
#: gilt nie der zuletzt gewaehlte Benutzer -- sonst saehe das Spiel nach
#: jedem Wechsel in der App fremde Daten. Ohne ?user= der erste Benutzer.
FEED_PATHS = ("/api/pomodoro/activity", "/api/pomodoro/journal/feed")

#: Kennung dieses App-Starts. "Beim Start fragen" heisst: einmal je Start,
#: nicht nur ohne Cookie -- der Browser behielte pomo_user sonst ein Jahr.
BOOT_ID = uuid.uuid4().hex[:12]
BOOT_COOKIE = "pomo_boot"


def _wants_chooser():
    """Seitenaufruf, der erst die Auswahl "Wer bist du?" braucht?"""
    path = request.path
    if request.method != "GET" or path == "/pomodoro/users":
        return False
    if not (path == "/pomodoro" or path.startswith("/pomodoro/")):
        return False
    if path.startswith("/pomodoro/media/"):
        return False
    return (users.ask_on_start()
            and request.cookies.get(BOOT_COOKIE) != BOOT_ID)


@bp.before_app_request
def _enter_user():
    """Jede Anfrage laeuft fuer genau einen Benutzer (KONZEPT-BENUTZER.md, 4)."""
    if request.path in FEED_PATHS:
        # ?user= nimmt id oder Namen: ?user=Lena reicht.
        wanted = request.args.get("user")
        if wanted:
            found = users.find(wanted)
            if not found:
                return jsonify({"ok": False, "reason": "Unbekannter Benutzer."}), 404
            user_id = found["id"]
        else:
            user_id = users.feed_user_id()
    else:
        if _wants_chooser():
            return redirect("/pomodoro/users?" + urlencode({"next": request.full_path.rstrip("?")}))
        user_id = users.resolve(request.cookies.get("pomo_user"))
    g.pomo_user_token = users.activate(user_id)


@bp.teardown_app_request
def _leave_user(_exc):
    token = g.pop("pomo_user_token", None)
    if token is not None:
        users.deactivate(token)


@bp.app_context_processor
def _user_helpers():
    return {"current_user": users.get(users.current()),
            "all_users": users.all_users()}


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
    context["user_colors"] = users.COLORS
    context["ask_on_start"] = users._registry().get("ask_on_start", False)
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


def _with_user(payload):
    """Feeds sagen, wessen Daten sie liefern (zusaetzliches Feld, der
    Vertrag activity/1 bleibt sonst unveraendert)."""
    user = users.get(users.current()) or {}
    payload.setdefault("meta", {})["user"] = {"id": user.get("id"),
                                              "name": user.get("name")}
    return payload


# ---------------------------------------------------------------- Benutzer


def _user_row(user):
    with users.as_user(user["id"]):
        summary = pomo.user_summary()
    return dict(user, **summary)


@bp.route("/api/pomodoro/users")
def api_users():
    """Alle Benutzer mit laufendem Timer je Benutzer."""
    return jsonify({"current": users.current(), "feed_user": users.feed_user_id(),
                    "users": [_user_row(u) for u in users.all_users()]})


@bp.route("/api/pomodoro/users", methods=["POST"])
def api_user_create():
    data = request.get_json(silent=True) or {}
    try:
        user = users.create(data.get("name"), data.get("color"))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    if data.get("copy_settings", True):
        source = users.current()
        with users.as_user(user["id"]):
            pomo.copy_settings_from(source)
    return jsonify({"ok": True, "user": _user_row(user)})


@bp.route("/api/pomodoro/users/<user_id>", methods=["POST"])
def api_user_update(user_id):
    data = request.get_json(silent=True) or {}
    try:
        user = users.update(user_id, data.get("name"), data.get("color"))
    except KeyError:
        return jsonify({"ok": False, "reason": "Unbekannter Benutzer."}), 404
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "user": user})


@bp.route("/api/pomodoro/users/<user_id>", methods=["DELETE"])
def api_user_delete(user_id):
    if user_id == users.current():
        return jsonify({"ok": False, "reason": "Der aktive Benutzer kann nicht "
                        "geloescht werden -- erst wechseln."}), 400
    if not users.get(user_id):
        return jsonify({"ok": False, "reason": "Unbekannter Benutzer."}), 404
    if len(users.all_users()) <= 1:
        return jsonify({"ok": False, "reason": "Der letzte Benutzer kann nicht "
                        "geloescht werden."}), 400
    if user_id == users.feed_user_id():
        return jsonify({"ok": False, "reason": "Merge Requests liest die Daten "
                        "dieses Benutzers -- er kann nicht geloescht werden."}), 400
    pomo.forget_user(user_id)
    try:
        moved = users.remove(user_id)
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "moved_to": moved})


@bp.route("/api/pomodoro/users/settings", methods=["POST"])
def api_users_settings():
    data = request.get_json(silent=True) or {}
    try:
        flag = users.set_ask_on_start(bool(data.get("ask_on_start")))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    return jsonify({"ok": True, "ask_on_start": flag})


def _safe_next(target):
    """Nur Ziele innerhalb der App -- kein offener Redirect."""
    target = target or "/pomodoro"
    if not target.startswith("/pomodoro") or target.startswith("/pomodoro/users"):
        return "/pomodoro"
    return target


@bp.route("/pomodoro/users")
def users_page():
    """Auswahl "Wer bist du?" (KONZEPT-BENUTZER.md, 6). Ohne Biotop und
    Mini-Timer -- noch steht nicht fest, wessen."""
    return render_template(
        "pomodoro_users.html",
        users_rows=[_user_row(u) for u in users.all_users()],
        current_id=users.current(),
        next_url=_safe_next(request.args.get("next")),
        palette_css=palette_mod.css_vars(palette_mod.default_palette()),
        user_colors=users.COLORS)


@bp.route("/api/pomodoro/user/switch", methods=["POST"])
def api_user_switch():
    data = request.get_json(silent=True) or {}
    user_id = data.get("id")
    try:
        users.remember(user_id)
    except KeyError:
        return jsonify({"ok": False, "reason": "Unbekannter Benutzer."}), 404
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400
    with users.as_user(user_id):
        running = pomo.get_state()["state"] != "idle"
    previous = users.current()
    with users.as_user(previous):
        left_running = pomo.get_state()["state"] in ("running", "paused")
    response = jsonify({"ok": True, "user": users.get(user_id),
                        "running": running,
                        "left_running": left_running and previous != user_id})
    response.set_cookie("pomo_user", user_id, max_age=365 * 24 * 3600,
                        samesite="Lax")
    # Fuer diesen App-Start ist die Frage "Wer bist du?" beantwortet.
    response.set_cookie(BOOT_COOKIE, BOOT_ID, samesite="Lax")
    # Projekt-ids gelten nur in der Datenbank eines Benutzers.
    response.delete_cookie("pomo_project")
    return response


@bp.route("/api/pomodoro/activity")
def api_activity():
    """Activity Feed v1 fuer andere Anwendungen, siehe data/pomodoro_feed.py."""
    try:
        return jsonify(_with_user(feed.read(since=request.args.get("since"),
                                 start=request.args.get("start"),
                                 limit=request.args.get("limit", type=int))))
    except ValueError as error:
        return jsonify({"ok": False, "reason": str(error)}), 400


@bp.route("/api/pomodoro/journal/feed")
def api_journal_feed():
    """Activity Feed v1 fuer Aktivitaeten, siehe data/pomodoro_journal_feed.py."""
    try:
        return jsonify(_with_user(journal_feed.read(since=request.args.get("since"),
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
