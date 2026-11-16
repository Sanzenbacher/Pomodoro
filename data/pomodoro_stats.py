"""Pomodoro: Auswertungen und Diagramme.

Getrennt von data/pomodoro.py, weil dieser Teil wachsen wird.

Die Diagramme entstehen serverseitig als Inline-SVG, nach dem Muster von
generate_calendar_svg() in data/git_metrics.py. Kein Chart.js: spart eine
vendorte 200-KB-Datei, und die Diagramme uebernehmen automatisch die
Farbrollen des gerade gewaehlten Projekts.

Die Tagesbildung laeuft in Python und nicht per GROUP BY, weil der Versatz
um day_start_hour zusammen mit der Zeitzonenumrechnung in SQL schwer lesbar
waere. Bei einer lokalen Ein-Personen-Datenbank ist das kein Thema.
"""

import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta

from data import pomodoro as pomo
from data.appconfig import POMO

RANGES = {
    "today": 1,
    "7": 7,
    "30": 30,
    "quarter": 92,
    "all": None,
}


def range_days(key):
    return RANGES.get(str(key), 30)


def _iter_days(first, last):
    current = first
    while current <= last:
        yield current.isoformat()
        current += timedelta(days=1)


def _fetch(range_key="30", project_id=None, tag=None):
    """Alle abgeschlossenen Sitzungen im Zeitraum, schon mit Tagesschluessel."""
    conn = pomo.get_db()
    try:
        sql = ("SELECT s.*, p.label AS project_label, p.color AS project_color"
               " FROM pomo_sessions s LEFT JOIN pomo_projects p ON p.id = s.project_id"
               " WHERE s.ended_at IS NOT NULL")
        args = []
        if project_id:
            sql += " AND s.project_id = ?"
            args.append(project_id)
        rows = [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()

    days = range_days(range_key)
    today = date.fromisoformat(pomo.today())
    cutoff = None if days is None else today - timedelta(days=days - 1)

    out = []
    for row in rows:
        started = pomo.parse(row["started_at"])
        row["day"] = pomo.day_of(started)
        row["hour"] = pomo.local(started).hour
        row["weekday"] = date.fromisoformat(row["day"]).weekday()
        row["minutes"] = round((row["actual_seconds"] or 0) / 60.0, 2)
        # Ueberzeit bleibt in "minutes" enthalten -- eine ueberzogene Sitzung
        # ist ein Pomodoro, aber die Fokusminuten zaehlen voll.
        row["overtime_seconds"] = pomo.overtime_of(row)
        row["overtime_minutes"] = round(row["overtime_seconds"] / 60.0, 2)
        if tag and tag not in (row.get("tags") or ""):
            continue
        if cutoff and date.fromisoformat(row["day"]) < cutoff:
            continue
        out.append(row)
    return out


def _streak(all_work_days):
    """Aufeinanderfolgende Tage mit mindestens einem erledigten Pomodoro."""
    if not all_work_days:
        return 0
    days = set(all_work_days)
    current = date.fromisoformat(pomo.today())
    if current.isoformat() not in days:
        current -= timedelta(days=1)
        if current.isoformat() not in days:
            return 0
    count = 0
    while current.isoformat() in days:
        count += 1
        current -= timedelta(days=1)
    return count


def summary(range_key="30", project_id=None, tag=None):
    rows = _fetch(range_key, project_id, tag)
    work = [r for r in rows if r["kind"] == "work"]
    done = [r for r in work if r["outcome"] == "completed"]
    today_key = pomo.today()

    today_done = [r for r in done if r["day"] == today_key]
    by_day = defaultdict(float)
    count_by_day = defaultdict(int)
    for row in done:
        by_day[row["day"]] += row["minutes"]
        count_by_day[row["day"]] += 1

    # Streak zaehlt ueber die ganze Historie, nicht nur ueber den Filter.
    all_rows = _fetch("all", project_id, tag)
    all_done_days = [r["day"] for r in all_rows
                     if r["kind"] == "work" and r["outcome"] == "completed"]

    interruptions = [r["interruptions"] or 0 for r in work]
    ratings = [r["focus_rating"] for r in done if r["focus_rating"]]

    goal = int(pomo.setting("daily_goal_pomodoros"))
    active_days = len(by_day) or 1

    # Ueberzeit gilt erst ab einer Minute -- ein Klick kurz nach dem Gong
    # ist kein Ueberziehen.
    over = [r for r in done if r["overtime_seconds"] >= pomo.OVERTIME_THRESHOLD]
    over_seconds = sum(r["overtime_seconds"] for r in over)
    reasons = {key: 0 for key in pomo.OVERTIME_REASONS + ("none",)}
    for row in over:
        reasons[row["overtime_reason"] if row["overtime_reason"] in reasons
                else "none"] += 1

    return {
        "pomodoros_today": len(today_done),
        "goal": goal,
        "goal_pct": min(100, round(len(today_done) * 100.0 / goal)) if goal else 0,
        "focus_minutes_today": round(sum(r["minutes"] for r in today_done)),
        "focus_minutes_total": round(sum(r["minutes"] for r in done)),
        "avg_minutes_per_day": round(sum(by_day.values()) / active_days),
        "avg_pomodoros_per_day": round(len(done) / active_days, 1),
        "streak": _streak(all_done_days),
        "completion_rate": round(len(done) * 100.0 / len(work)) if work else 0,
        "avg_interruptions": round(sum(interruptions) / len(work), 2) if work else 0.0,
        "avg_focus_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "rated": len(ratings),
        "done": len(done),
        "sessions": len(work),
        "aborted": len([r for r in work if r["outcome"] == "aborted"]),
        "overtime_sessions": len(over),
        "overtime_share": round(len(over) * 100.0 / len(done)) if done else 0,
        "avg_overtime_seconds": round(over_seconds / len(over)) if over else 0,
        "overtime_minutes_total": round(over_seconds / 60.0),
        "overtime_reasons": reasons,
        "overtime_reason_share": {
            key: round(count * 100.0 / len(over)) if over else 0
            for key, count in reasons.items()},
    }


def discipline(range_key="30", project_id=None):
    rows = _fetch(range_key, project_id)
    work = [r for r in rows if r["kind"] == "work"]
    breaks = [r for r in rows if r["kind"] != "work"]
    skipped = [r for r in breaks if r["outcome"] == "discarded"]
    taken = [r for r in breaks if r["outcome"] == "completed"]
    planned = sum((r["planned_seconds"] or 0) for r in taken) / 60.0
    actual = sum(r["minutes"] for r in taken)
    # Pausendisziplin: Auch eine Pause zaehlt nach dem Ablauf weiter.
    overrun = [r for r in taken if r["overtime_seconds"] >= pomo.OVERTIME_THRESHOLD]
    return {
        "abort_rate": round(len([r for r in work if r["outcome"] == "aborted"])
                            * 100.0 / len(work)) if work else 0,
        "breaks_taken": len(taken),
        "breaks_skipped": len(skipped),
        "skip_rate": round(len(skipped) * 100.0 / len(breaks)) if breaks else 0,
        "break_planned_min": round(planned / len(taken), 1) if taken else 0.0,
        "break_actual_min": round(actual / len(taken), 1) if taken else 0.0,
        "breaks_overrun": len(overrun),
        "break_overrun_rate": round(len(overrun) * 100.0 / len(taken)) if taken else 0,
        "break_overrun_avg_min": round(
            sum(r["overtime_minutes"] for r in overrun) / len(overrun), 1) if overrun else 0.0,
        "avg_interruptions": round(
            sum((r["interruptions"] or 0) for r in work) / len(work), 2) if work else 0.0,
    }


def by_hour(range_key="30", project_id=None):
    rows = [r for r in _fetch(range_key, project_id)
            if r["kind"] == "work" and r["outcome"] == "completed"]
    minutes = [0.0] * 24
    count = [0] * 24
    rating_sum = [0.0] * 24
    rating_n = [0] * 24
    for row in rows:
        minutes[row["hour"]] += row["minutes"]
        count[row["hour"]] += 1
        if row["focus_rating"]:
            rating_sum[row["hour"]] += row["focus_rating"]
            rating_n[row["hour"]] += 1
    avg = [round(rating_sum[h] / rating_n[h], 2) if rating_n[h] else None
           for h in range(24)]
    return {"minutes": [round(m) for m in minutes], "avg_rating": avg,
            "count": count, "rated": rating_n}


def best_window(hours):
    """Bestes Deep-Work-Fenster: hoechstes Volumen mal Fokus-Rating ueber drei
    zusammenhaengende Stunden."""
    minutes, avg = hours["minutes"], hours["avg_rating"]
    if not any(minutes):
        return None
    score = [minutes[h] * ((avg[h] or 3.0) / 5.0) for h in range(24)]
    best, best_sum = 0, -1.0
    for h in range(22):
        window = sum(score[h:h + 3])
        if window > best_sum:
            best_sum, best = window, h
    if best_sum <= 0:
        return None
    return {"from": best, "to": best + 3}


def by_weekday(range_key="30", project_id=None):
    rows = [r for r in _fetch(range_key, project_id)
            if r["kind"] == "work" and r["outcome"] == "completed"]
    minutes = [0.0] * 7
    for row in rows:
        minutes[row["weekday"]] += row["minutes"]
    return [round(m) for m in minutes]


def by_project(range_key="30"):
    rows = [r for r in _fetch(range_key)
            if r["kind"] == "work" and r["outcome"] == "completed"]
    buckets = defaultdict(lambda: {"minutes": 0.0, "count": 0, "label": None,
                                   "color": None, "id": None, "ratings": []})
    for row in rows:
        key = row["project_id"] or 0
        bucket = buckets[key]
        bucket["minutes"] += row["minutes"]
        bucket["count"] += 1
        if row["focus_rating"]:
            bucket["ratings"].append(row["focus_rating"])
        bucket["label"] = row["project_label"] or "Ohne Projekt"
        bucket["color"] = row["project_color"] or "#FF9679"
        bucket["id"] = row["project_id"]
    total = sum(b["minutes"] for b in buckets.values()) or 1
    out = []
    for bucket in buckets.values():
        ratings = bucket.pop("ratings")
        bucket["rated"] = len(ratings)
        bucket["avg_rating"] = round(sum(ratings) / len(ratings), 1) if ratings else None
        bucket["minutes"] = round(bucket["minutes"])
        bucket["share"] = round(bucket["minutes"] * 100.0 / total)
        out.append(bucket)
    return sorted(out, key=lambda b: -b["minutes"])


def _per_project(rows):
    """Sitzungen eines Tages nach Projekt: Minuten, Ueberzeit, Anzahl und
    Fokusbewertung -- fuer Stapelbalken und Tooltips."""
    buckets = {}
    for row in rows:
        key = row["project_id"] or 0
        bucket = buckets.setdefault(key, {
            "id": row["project_id"], "label": row["project_label"] or "Ohne Projekt",
            "minutes": 0.0, "overtime": 0.0, "count": 0, "ratings": []})
        bucket["minutes"] += row["minutes"]
        bucket["overtime"] += row["overtime_minutes"]
        bucket["count"] += 1
        if row["focus_rating"]:
            bucket["ratings"].append(row["focus_rating"])
    out = []
    for bucket in buckets.values():
        ratings = bucket.pop("ratings")
        bucket["minutes"] = round(bucket["minutes"])
        bucket["overtime"] = round(bucket["overtime"])
        bucket["rated"] = len(ratings)
        bucket["avg_rating"] = round(sum(ratings) / len(ratings), 1) if ratings else None
        out.append(bucket)
    return sorted(out, key=lambda b: -b["minutes"])


def daily(range_key="30", project_id=None):
    """Fokusminuten pro Tag, luecklos aufgefuellt -- dazu der Anteil, der
    Ueberzeit war, und die Aufteilung nach Projekt fuer die Stapelbalken."""
    rows = [r for r in _fetch(range_key, project_id)
            if r["kind"] == "work" and r["outcome"] == "completed"]
    rows_by_day = defaultdict(list)
    for row in rows:
        rows_by_day[row["day"]].append(row)
    if not rows_by_day:
        return []
    days = range_days(range_key)
    last = date.fromisoformat(pomo.today())
    first = (min(date.fromisoformat(d) for d in rows_by_day) if days is None
             else last - timedelta(days=days - 1))
    out = []
    for day in _iter_days(first, last):
        day_rows = rows_by_day.get(day, [])
        ratings = [r["focus_rating"] for r in day_rows if r["focus_rating"]]
        out.append({
            "day": day,
            "minutes": round(sum(r["minutes"] for r in day_rows)),
            "overtime": round(sum(r["overtime_minutes"] for r in day_rows)),
            "count": len(day_rows),
            "avg_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
            "projects": _per_project(day_rows),
        })
    return out


def weekly(weeks=8, project_id=None):
    """Fokusminuten je Kalenderwoche (Mo-So), nach Projekt aufgeteilt."""
    rows = [r for r in _fetch("all", project_id)
            if r["kind"] == "work" and r["outcome"] == "completed"]
    today = date.fromisoformat(pomo.today())
    this_monday = today - timedelta(days=today.weekday())
    # Eine Woche mehr rechnen, damit auch die erste gezeigte einen Vergleich hat.
    mondays = [this_monday - timedelta(weeks=n) for n in range(weeks, -1, -1)]
    rows_by_week = defaultdict(list)
    for row in rows:
        day = date.fromisoformat(row["day"])
        rows_by_week[day - timedelta(days=day.weekday())].append(row)
    out = []
    for monday in mondays:
        week_rows = rows_by_week.get(monday, [])
        ratings = [r["focus_rating"] for r in week_rows if r["focus_rating"]]
        out.append({
            "monday": monday.isoformat(),
            "week": monday.isocalendar()[1],
            "current": monday == this_monday,
            "minutes": round(sum(r["minutes"] for r in week_rows)),
            "overtime": round(sum(r["overtime_minutes"] for r in week_rows)),
            "count": len(week_rows),
            "active_days": len({r["day"] for r in week_rows}),
            "avg_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
            "projects": _per_project(week_rows),
            "by_weekday": [round(sum(r["minutes"] for r in week_rows
                                     if r["weekday"] == wd)) for wd in range(7)],
        })
    for prev, week in zip(out, out[1:]):
        # Die laufende Woche fair vergleichen: nur bis zum selben Wochentag.
        upto = today.weekday() + 1 if week["current"] else 7
        week["compare_minutes"] = sum(week["by_weekday"][:upto])
        week["prev_minutes"] = sum(prev["by_weekday"][:upto])
        week["compare_upto"] = WEEKDAYS[upto - 1] if week["current"] else None
        week["delta_pct"] = (round((week["compare_minutes"] - week["prev_minutes"])
                                   * 100.0 / week["prev_minutes"])
                             if week["prev_minutes"] else None)
        week["delta_text"] = delta_text(week)
    return out[1:]


def delta_text(week):
    """"+35 % ggü. Vorwoche (bis Sa)" -- oder leer, wenn es nichts zu vergleichen gibt."""
    if week["delta_pct"] is None:
        return "Vorwoche leer" if week["compare_minutes"] else ""
    sign = "+" if week["delta_pct"] > 0 else ("−" if week["delta_pct"] < 0 else "±")
    text = "%s%d %% ggü. Vorwoche" % (sign, abs(week["delta_pct"]))
    if week["compare_upto"]:
        text += " (jeweils Mo–%s)" % week["compare_upto"]
    return text


def today_timeline():
    """Alle Sitzungen des heutigen Tages mit Lage auf der Tagesachse.

    Die Achse beginnt bei day_start_hour, damit eine Nachtsession nach
    Mitternacht rechts vom Abend liegt und nicht links vom Morgen.
    """
    day = pomo.today()
    start_hour = int(pomo.setting("day_start_hour"))
    origin = pomo.local_midnight(date.fromisoformat(day))
    origin = origin.replace(hour=start_hour)
    current = pomo.local(pomo.now())

    def offset(moment):
        return (pomo.local(moment) - origin).total_seconds() / 3600.0

    out = []
    for row in sorted(pomo.sessions(limit=300, day=day), key=lambda r: r["started_at"]):
        started = pomo.parse(row["started_at"])
        ended = pomo.parse(row["ended_at"]) or current
        out.append({
            "kind": row["kind"],
            "project_id": row["project_id"],
            "label": row["project_label"] or "Ohne Projekt",
            "from": offset(started),
            "to": max(offset(ended), offset(started) + 1 / 60.0),
            "clock": "%s–%s" % (pomo.local(started).strftime("%H:%M"),
                                "läuft" if not row["ended_at"]
                                else pomo.local(ended).strftime("%H:%M")),
            "minutes": round((row["actual_seconds"] or 0) / 60.0),
            "overtime": round(row["overtime_seconds"] / 60.0),
            "outcome": row["outcome"],
            "rating": row["focus_rating"],
            "running": not row["ended_at"],
        })
    done = [s for s in out if s["kind"] == "work" and s["outcome"] == "completed"]
    ratings = [s["rating"] for s in done if s["rating"]]
    return {"day": day, "start_hour": start_hour, "now": offset(current),
            "sessions": out,
            "pomodoros": len(done),
            "minutes": sum(s["minutes"] for s in done),
            "overtime": sum(s["overtime"] for s in done),
            "projects": len({s["project_id"] for s in done}),
            "avg_rating": _num(sum(ratings) / len(ratings)) if ratings else None,
            "unrated": len(done) - len(ratings)}


def calendar(weeks=26, project_id=None):
    """Heatmap-Kalender: ein Wert pro Tag, spaltenweise nach Wochen."""
    rows = [r for r in _fetch("all", project_id)
            if r["kind"] == "work" and r["outcome"] == "completed"]
    rows_by_day = defaultdict(list)
    for row in rows:
        rows_by_day[row["day"]].append(row)
    last = date.fromisoformat(pomo.today())
    last += timedelta(days=(6 - last.weekday()))
    first = last - timedelta(weeks=weeks) + timedelta(days=1)
    first -= timedelta(days=first.weekday())
    return [{"day": day,
             "minutes": round(sum(r["minutes"] for r in rows_by_day.get(day, []))),
             "projects": _per_project(rows_by_day.get(day, []))}
            for day in _iter_days(first, last)]


def trend(range_key="all", project_id=None):
    """Rollender 4-Wochen-Schnitt ueber die Tageswerte."""
    days = daily(range_key, project_id)
    out = []
    for i, entry in enumerate(days):
        window = days[max(0, i - 27):i + 1]
        out.append({"day": entry["day"], "minutes": entry["minutes"],
                    "rolling": round(sum(d["minutes"] for d in window) / len(window))})
    return out


# ---------------------------------------------------------------- SVG

def _esc(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

#: Fuer Sitzungen ohne Projekt (Projekt geloescht) und als Rueckfall.
NO_PROJECT_COLOR = "#8a8494"


def _day_label(day):
    d = date.fromisoformat(day)
    return "%s %s" % (WEEKDAYS[d.weekday()], d.strftime("%d.%m.%Y"))


day_label = _day_label


def _num(value):
    return ("%.1f" % value).replace(".", ",")


def _rating_text(bucket):
    """"Fokus Ø 4,5 / 5" -- mit Hinweis, wenn nicht alles bewertet ist."""
    if not bucket.get("avg_rating"):
        return "Fokus nicht bewertet"
    text = "Fokus Ø %s / 5" % _num(bucket["avg_rating"])
    if bucket["rated"] < bucket["count"]:
        text += " (%d von %d bewertet)" % (bucket["rated"], bucket["count"])
    return text


def _project_line(bucket):
    text = "%s: %d Min · %d Pomodoro%s · %s" % (
        bucket["label"], bucket["minutes"], bucket["count"],
        "" if bucket["count"] == 1 else "s", _rating_text(bucket))
    if bucket.get("overtime"):
        text += " · %d Min Überzeit" % bucket["overtime"]
    return text


def _day_tip(entry, goal_minutes=None):
    """Tooltip fuer einen ganzen Tag: Summe und jedes Projekt einzeln."""
    if not entry["minutes"]:
        return "%s: nichts geloggt" % _day_label(entry["day"])
    head = "%s · %d Min gesamt" % (_day_label(entry["day"]), entry["minutes"])
    if goal_minutes:
        head += (" · Tagesziel erreicht" if entry["minutes"] >= goal_minutes
                 else " · %d Min bis zum Tagesziel" % (goal_minutes - entry["minutes"]))
    lines = [head]
    lines += [_project_line(b) for b in entry["projects"]]
    return "\n".join(lines)


def _color_of(bucket, colors):
    return (colors or {}).get(bucket["id"]) or NO_PROJECT_COLOR


def legend(days, colors):
    """Projekte, die im Diagramm vorkommen, mit ihrer Farbe."""
    seen = {}
    for entry in days:
        for bucket in entry.get("projects", []):
            seen.setdefault(bucket["id"] or 0, {
                "label": bucket["label"], "color": _color_of(bucket, colors)})
    return [seen[k] for k in sorted(seen)]


def _ramp(palette, steps=5):
    """Farbtreppe vom Grund zur Leitfarbe -- dieselbe Logik wie im Mockup."""
    from data import pomodoro_palette as pal
    bg = palette["bg"]
    return [pal.mix(bg, palette["ink"], 0.10),
            pal.mix(bg, palette["a3"], 0.50),
            pal.mix(bg, palette["a4"], 0.75),
            pal.mix(bg, palette["a1"], 0.90),
            palette["a2"]][:steps]


def calendar_svg(cells, palette, cell=13, gap=3, link=None):
    if not cells:
        return ""
    ramp = _ramp(palette)
    peak = max(c["minutes"] for c in cells) or 1
    columns = (len(cells) + 6) // 7
    width = columns * (cell + gap)
    height = 7 * (cell + gap)
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'role="img" aria-label="Fokusminuten pro Tag">' % (width, height, height)]
    for index, entry in enumerate(cells):
        column, row = divmod(index, 7)
        value = entry["minutes"]
        level = 0 if not value else min(4, 1 + int(value / peak * 3.99))
        column_start = len(parts)
        parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s">'
            '<title>%s</title></rect>'
            % (column * (cell + gap), row * (cell + gap), cell, cell,
               ramp[level], _esc(_day_tip(entry) if "projects" in entry
                                 else "%s: %d Min" % (entry["day"], value))))
        _linked(parts, column_start, link and value and link(entry["day"]))
    parts.append("</svg>")
    return "".join(parts)


def rating_color(avg, palette):
    """Farbe fuer eine Durchschnittsbewertung -- dieselbe Stufung ueberall,
    siehe rating_legend(). Ohne Bewertung: gedaempftes Grau."""
    if avg is None:
        return palette["muted"], 0.45
    if avg >= 4:
        # a3 ist die "erledigt"-Farbe. Nur wenn sie im Farbton zu nah an der
        # Warnfarbe liegt, die Leitfarbe nehmen -- gut und schlecht muessen
        # auf einen Blick unterscheidbar sein.
        from data import pomodoro_palette as pal
        good = palette["a3"]
        if pal.hue_distance(pal.hex_to_lch(good)[2], pal.hex_to_lch(palette["warn"])[2]) < 40:
            good = palette["a1"]
        return good, 1.0
    if avg >= 3:
        return palette["a4"], 1.0
    return palette["warn"], 1.0


def rating_legend(palette):
    return [{"label": label, "color": rating_color(avg, palette)[0],
             "opacity": rating_color(avg, palette)[1]}
            for label, avg in (("Ø FOKUS 4–5", 4), ("3–4", 3), ("UNTER 3", 1),
                               ("NICHT BEWERTET", None))]


def hours_svg(hours, palette, height=92):
    """Hoehe = Fokusminuten, Farbe = durchschnittliche Fokusbewertung.
    So sieht man, ob viel Zeit auch gute Zeit war."""
    minutes = hours["minutes"]
    peak = max(minutes) or 1
    width, gap = 24 * 14, 3
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'role="img" aria-label="Fokus nach Tageszeit">' % (width, height, height)]
    for hour, value in enumerate(minutes):
        bar = max(3, round(value / peak * (height - 4)))
        avg = hours["avg_rating"][hour]
        if not value:
            fill, opacity = palette["line"], 1.0
            tip = "%02d Uhr: nichts" % hour
        else:
            fill, opacity = rating_color(avg, palette)
            tip = "%02d Uhr: %d Min · %s" % (hour, value, _rating_text({
                "avg_rating": avg, "rated": hours["rated"][hour],
                "count": hours["count"][hour]}))
        parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s"%s>'
            '<title>%s</title></rect>'
            % (hour * 14, height - bar, 14 - gap, bar, fill,
               ' opacity="%.2f"' % opacity if opacity < 1 else "", _esc(tip)))
    parts.append("</svg>")
    return "".join(parts)


def weekday_svg(minutes, palette, height=92):
    peak = max(minutes) or 1
    names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    width = 7 * 46
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'role="img" aria-label="Verteilung nach Wochentag">'
             % (width, height + 16, height + 16)]
    for index, value in enumerate(minutes):
        bar = max(3, round(value / peak * (height - 4)))
        parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s">'
            '<title>%s: %d Min</title></rect>'
            % (index * 46, height - bar, 38, bar,
               palette["a2"] if value == peak else palette["a4"], names[index], value))
        parts.append(
            '<text x="%d" y="%d" fill="%s" font-size="10" text-anchor="middle" '
            'letter-spacing="1.5">%s</text>'
            % (index * 46 + 19, height + 12, palette["muted"], names[index]))
    parts.append("</svg>")
    return "".join(parts)


def trend_svg(points, palette, height=140):
    if len(points) < 2:
        return ""
    width = 640
    peak = max(max(p["minutes"] for p in points),
               max(p["rolling"] for p in points)) or 1
    step = width / (len(points) - 1)

    def path(key):
        return " ".join(
            "%s%.1f %.1f" % ("M" if i == 0 else "L", i * step,
                             height - (p[key] / peak) * (height - 8))
            for i, p in enumerate(points))

    return (
        '<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img" '
        'aria-label="Fokusminuten im Verlauf">'
        '<path d="%s" fill="none" stroke="%s" stroke-width="1.5" opacity="0.45"/>'
        '<path d="%s" fill="none" stroke="%s" stroke-width="2.5" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
        % (width, height, height, path("minutes"), palette["a4"],
           path("rolling"), palette["a1"]))


def focus_bars_svg(days, palette, colors=None, height=140, limit=42,
                   goal_minutes=None, link=None, selected=None):
    """Fokus pro Tag als Stapelbalken, ein Abschnitt je Projekt in dessen
    Statistikfarbe. Die Ueberzeit steckt blass oben im jeweiligen Abschnitt --
    so bleibt sichtbar, welches Projekt ueberzogen hat.

    Jeder Abschnitt hat einen eigenen Tooltip (Projekt, Minuten, Pomodoros,
    Fokusbewertung, Ueberzeit); die leere Flaeche ueber dem Balken zeigt den
    ganzen Tag.
    """
    days = days[-limit:]
    if not days:
        return ""
    # Bei "Heute" oder "7 Tage" nicht einen Balken auf volle Breite ziehen:
    # links mit leeren Tagen auf zwei Wochen auffuellen.
    days = [{"day": "", "minutes": 0, "overtime": 0, "projects": []}] * max(0, 14 - len(days)) + days
    # Das Tagesziel soll immer im Bild sein, auch an schwachen Tagen.
    peak = max([d["minutes"] for d in days] + [goal_minutes or 0]) or 1
    slot = 16
    width = len(days) * slot
    scale = (height - 4) / float(peak)
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'preserveAspectRatio="none" role="img" '
             'aria-label="Fokus pro Tag nach Projekt">' % (width, height, height)]
    for index, entry in enumerate(days):
        column_start = len(parts)
        x = index * slot + 2
        if entry["day"] and entry["day"] == selected:
            parts.append('<rect x="%d" y="0" width="%d" height="%d" fill="%s" opacity="0.08" '
                         'pointer-events="none"></rect>'
                         % (index * slot, slot, height, palette["ink"]))
        if entry["day"]:
            # Unsichtbare Trefferflaeche ueber die ganze Spalte fuer den Tagestooltip.
            parts.append('<rect x="%d" y="0" width="%d" height="%d" fill="transparent">'
                         '<title>%s</title></rect>'
                         % (index * slot, slot, height, _esc(_day_tip(entry, goal_minutes))))
        if not entry["minutes"]:
            parts.append('<rect x="%d" y="%d" width="%d" height="2" rx="1" fill="%s"%s></rect>'
                         % (x, height - 2, slot - 4, palette["line"],
                            ' pointer-events="none"' if entry["day"] else ""))
            continue
        # Feste Reihenfolge nach Projekt, damit ein Projekt jeden Tag an
        # derselben Stelle im Stapel liegt.
        bottom = height
        stack = sorted(entry["projects"], key=lambda b: b["id"] or 0)
        for n, bucket in enumerate(stack):
            seg = bucket["minutes"] * scale
            # Rundung am Ende ausgleichen, damit der Stapel genau die Tageshoehe hat.
            top_y = (height - round(entry["minutes"] * scale) if n == len(stack) - 1
                     else round(bottom - seg))
            seg_h = bottom - top_y
            if seg_h <= 0:
                continue
            over_h = min(seg_h, round(min(bucket["overtime"], bucket["minutes"]) * scale))
            color = _color_of(bucket, colors)
            tip = _esc("%s\n%s" % (_day_label(entry["day"]), _project_line(bucket)))
            if seg_h - over_h > 0:
                parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s">'
                             '<title>%s</title></rect>'
                             % (x, top_y + over_h, slot - 4, seg_h - over_h, color, tip))
            if over_h:
                parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" '
                             'opacity="0.45"><title>%s</title></rect>'
                             % (x, top_y, slot - 4, over_h, color, tip))
            bottom = top_y
        _linked(parts, column_start, link and entry["minutes"] and link(entry["day"]))
    if goal_minutes:
        y = round(height - goal_minutes * scale)
        parts.append('<line x1="0" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1" '
                     'stroke-dasharray="4 4" vector-effect="non-scaling-stroke" '
                     'pointer-events="none"></line>' % (y, width, y, palette["ink"]))
    parts.append("</svg>")
    return "".join(parts)


def _linked(parts, start, href):
    """Alles ab parts[start] in einen Link packen -- ein Klick auf die Spalte
    filtert die Sitzungstabelle."""
    if href:
        parts.insert(start, '<a href="%s" style="cursor: pointer;">' % _esc(href))
        parts.append("</a>")


def weekly_svg(weeks, palette, colors=None, height=120, link=None):
    """Wochenbalken, nach Projekt gestapelt wie focus_bars_svg; darunter die KW."""
    if not weeks:
        return ""
    peak = max(w["minutes"] for w in weeks) or 1
    slot = 40
    label_h = 16
    width = len(weeks) * slot
    scale = (height - 4) / float(peak)
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img" '
             'aria-label="Fokus pro Woche nach Projekt">'
             % (width, height + label_h, height + label_h)]
    for index, week in enumerate(weeks):
        column_start = len(parts)
        x = index * slot + 5
        monday = date.fromisoformat(week["monday"])
        head = "KW %d · %s – %s" % (week["week"], monday.strftime("%d.%m."),
                                     (monday + timedelta(days=6)).strftime("%d.%m.%Y"))
        if week["minutes"]:
            lines = ["%s · %d Min an %d Tag%s%s" % (
                head, week["minutes"], week["active_days"],
                "" if week["active_days"] == 1 else "en",
                " (laufende Woche)" if week["current"] else "")]
            if week.get("delta_text"):
                lines.append(week["delta_text"])
            lines += [_project_line(b) for b in week["projects"]]
            tip = "\n".join(lines)
        else:
            tip = "%s: nichts geloggt" % head
        parts.append('<rect x="%d" y="0" width="%d" height="%d" fill="transparent">'
                     '<title>%s</title></rect>' % (index * slot, slot, height, _esc(tip)))
        parts.append('<text x="%d" y="%d" fill="%s" font-size="10" text-anchor="middle" '
                     'letter-spacing="1" pointer-events="none">%d</text>'
                     % (index * slot + slot // 2, height + 12,
                        palette["a2"] if week["current"] else palette["muted"], week["week"]))
        if not week["minutes"]:
            parts.append('<rect x="%d" y="%d" width="%d" height="2" rx="1" fill="%s" '
                         'pointer-events="none"></rect>'
                         % (x, height - 2, slot - 10, palette["line"]))
            continue
        bottom = height
        stack = sorted(week["projects"], key=lambda b: b["id"] or 0)
        for n, bucket in enumerate(stack):
            top_y = (height - round(week["minutes"] * scale) if n == len(stack) - 1
                     else round(bottom - bucket["minutes"] * scale))
            if bottom - top_y <= 0:
                continue
            parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"%s>'
                         '<title>%s</title></rect>'
                         % (x, top_y, slot - 10, bottom - top_y, _color_of(bucket, colors),
                            # Die laufende Woche ist noch nicht fertig -- etwas blasser.
                            ' opacity="0.7"' if week["current"] else "",
                            _esc("%s\n%s" % (head, _project_line(bucket)))))
            bottom = top_y
        _linked(parts, column_start, link and link(week["monday"]))
    parts.append("</svg>")
    return "".join(parts)


def timeline_svg(timeline, palette, colors=None, height=34):
    """Der heutige Tag als Zeitleiste: Arbeitsphasen als Bloecke in der
    Projektfarbe, Pausen als duenne Linie, jetzt als senkrechter Strich."""
    sessions = timeline["sessions"]
    first = min([s["from"] for s in sessions] + [timeline["now"]])
    last = max([s["to"] for s in sessions] + [timeline["now"]])
    # Mindestens acht Stunden zeigen, damit ein einzelner Pomodoro nicht die
    # ganze Breite fuellt; auf volle Stunden runden.
    lo = max(0, int(first))
    hi = min(24, max(int(last) + 1, lo + 8))
    span = float(hi - lo)
    width = 336
    axis_h = 14

    def px(hours):
        return (hours - lo) / span * width

    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img" '
             'aria-label="Sitzungen heute">' % (width, height + axis_h, height + axis_h)]
    parts.append('<rect x="0" y="%d" width="%d" height="1" fill="%s"></rect>'
                 % (height - 1, width, palette["line"]))
    step = 1 if span <= 8 else (2 if span <= 14 else 3)
    for h in range(lo, hi + 1, step):
        x = px(h)
        clock = (h + timeline["start_hour"]) % 24
        parts.append('<rect x="%.1f" y="%d" width="1" height="4" fill="%s"></rect>'
                     % (min(x, width - 1), height - 1, palette["line"]))
        parts.append('<text x="%.1f" y="%d" fill="%s" font-size="9.5" text-anchor="%s">%02d</text>'
                     % (x, height + axis_h - 1, palette["muted"],
                        "start" if h == lo else ("end" if h == hi else "middle"), clock))
    for entry in sessions:
        x = px(entry["from"])
        w = max(2.0, px(entry["to"]) - x)
        if entry["kind"] != "work":
            tip = "%s · %s · %d Min" % (
                entry["clock"], "Lange Pause" if entry["kind"] == "long_break" else "Pause",
                entry["minutes"])
            parts.append('<rect x="%.1f" y="%d" width="%.1f" height="3" rx="1.5" fill="%s">'
                         '<title>%s</title></rect>'
                         % (x, height - 9, w, palette["muted"], _esc(tip)))
            continue
        color = (colors or {}).get(entry["project_id"]) or NO_PROJECT_COLOR
        bits = [entry["clock"], entry["label"]]
        if entry["running"]:
            bits.append("läuft gerade")
        else:
            bits.append("%d Min" % entry["minutes"])
            bits.append("Fokus %d / 5" % entry["rating"] if entry["rating"] else "nicht bewertet")
            if entry["overtime"]:
                bits.append("+%d Min Überzeit" % entry["overtime"])
            bits.append({"completed": "erledigt", "aborted": "abgebrochen",
                         "discarded": "verworfen"}.get(entry["outcome"], "offen"))
        faded = entry["running"] or entry["outcome"] != "completed"
        parts.append('<rect x="%.1f" y="4" width="%.1f" height="%d" rx="2" fill="%s"%s>'
                     '<title>%s</title></rect>'
                     % (x, w, height - 10, color, ' opacity="0.45"' if faded else "",
                        _esc(" · ".join(bits))))
    parts.append('<rect x="%.1f" y="0" width="1.5" height="%d" fill="%s" pointer-events="none">'
                 '</rect>' % (min(px(timeline["now"]), width - 1.5), height, palette["a2"]))
    parts.append("</svg>")
    return "".join(parts)


def breakdown_svg(buckets, palette, colors=None, height=14):
    """Gestapelter Balken ueber alle Projekte, in den Statistikfarben."""
    total = sum(b["minutes"] for b in buckets) or 1
    parts = ['<svg viewBox="0 0 100 %d" width="100%%" height="%d" '
             'preserveAspectRatio="none" role="img" aria-label="Anteil je Projekt">'
             % (height, height)]
    offset = 0.0
    for bucket in buckets:
        share = bucket["minutes"] * 100.0 / total
        parts.append('<rect x="%.2f" y="0" width="%.2f" height="%d" fill="%s">'
                     '<title>%s</title></rect>'
                     % (offset, share, height, _color_of(bucket, colors),
                        _esc("%s · %d %%" % (_project_line(bucket), bucket["share"]))))
        offset += share
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------- Export


def csv_export(range_key="all", project_id=None):
    rows = _fetch(range_key, project_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(["id", "tag", "start", "ende", "projekt", "phase", "geplant_min",
                     "tatsaechlich_min", "pausiert_s", "stoerungen", "ergebnis",
                     "fokus", "ziel", "notiz", "tags", "overtime_seconds",
                     "overtime_reason"])
    for row in sorted(rows, key=lambda r: r["started_at"]):
        writer.writerow([
            row["id"], row["day"], row["started_at"], row["ended_at"],
            row["project_label"] or "", row["kind"],
            round((row["planned_seconds"] or 0) / 60.0, 1), row["minutes"],
            row["paused_seconds"], row["interruptions"], row["outcome"] or "",
            row["focus_rating"] or "", row["target_id"] or "",
            (row["note"] or "").replace("\n", " "), row["tags"] or "",
            row["overtime_seconds"], row["overtime_reason"] or ""])
    return buffer.getvalue()
