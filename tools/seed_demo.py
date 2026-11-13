"""Beispieldaten zum Anschauen: drei Projekte und ein halbes Jahr Sitzungen.

    python tools/seed_demo.py          anlegen
    python tools/seed_demo.py --clear  alles wieder entfernen

Erzeugt nur, was die Statistikseite braucht -- echte Sitzungen entstehen
ueber den Timer. Die Zufallszahlen haengen an einem festen Startwert, damit
zweimal Saeen dasselbe Bild ergibt.
"""

import os
import random
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import pomodoro as pomo

DEMO_PROJECTS = [
    ("Rocketz Flying in the Wind", "#FF9679", 0.52),
    ("Lumina-Schwarm", "#57D9F2", 0.24),
    ("Steuer & Ablage", "#9B968A", 0.24),
]

# Wann wird gearbeitet: Gewicht je Stunde, Nachmittag deutlich staerker.
HOUR_WEIGHTS = [0, 0, 0, 0, 0, 0, 1, 2, 5, 9, 12, 13, 6, 5, 11, 15, 14, 10, 6, 4, 3, 2, 1, 0]


def clear():
    """Beispieldaten entfernen.

    Vorsicht mit den Projekten: Die Demonamen sind absichtlich echte
    Projektnamen, also kann ein Projekt mit demselben Namen inzwischen dem
    Nutzer gehoeren. Deshalb werden Sitzungen immer geloescht, das Projekt
    selbst aber nur, wenn nichts von Hand daran haengt -- kein Bild, keine
    eigene Palette, keine festgehaltenen Farben.
    """
    conn = pomo.get_db()
    try:
        rows = conn.execute(
            "SELECT id, label, image_path, seeds_json, palette_locked"
            " FROM pomo_projects WHERE label IN (%s)"
            % ", ".join("?" * len(DEMO_PROJECTS)),
            [p[0] for p in DEMO_PROJECTS]).fetchall()

        removed, kept, sessions = 0, [], 0
        for row in rows:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM pomo_sessions WHERE project_id = ?",
                (row["id"],)).fetchone()["n"]
            conn.execute("DELETE FROM pomo_events WHERE session_id IN"
                         " (SELECT id FROM pomo_sessions WHERE project_id = ?)",
                         (row["id"],))
            conn.execute("DELETE FROM pomo_sessions WHERE project_id = ?", (row["id"],))
            sessions += count

            touched = row["image_path"] or row["seeds_json"] or row["palette_locked"]
            if touched:
                kept.append(row["label"])
            else:
                conn.execute("DELETE FROM pomo_projects WHERE id = ?", (row["id"],))
                removed += 1
        conn.commit()

        print("%d Sitzungen und %d Demoprojekte entfernt." % (sessions, removed))
        for label in kept:
            print("  behalten: %s -- hat ein Bild oder eigene Farben." % label)
    finally:
        conn.close()


def seed():
    random.seed(20260920)
    pomo.init_db()

    existing = {p["label"]: p["id"] for p in pomo.projects(include_archived=True)}
    project_ids = []
    for label, color, share in DEMO_PROJECTS:
        pid = existing.get(label) or pomo.create_project(label, color)
        project_ids.append((pid, share))

    conn = pomo.get_db()
    rows = []
    try:
        last = date.fromisoformat(pomo.today())
        for offset in range(182):
            day = last - timedelta(days=offset)
            if day.weekday() >= 5 and random.random() < 0.72:
                continue
            if random.random() < 0.14:
                continue

            count = random.choice([2, 3, 3, 4, 4, 5, 6, 7])
            hours = random.choices(range(24), weights=HOUR_WEIGHTS, k=count)
            for index, hour in enumerate(sorted(hours)):
                roll = random.random()
                pid = project_ids[0][0]
                threshold = 0.0
                for candidate, share in project_ids:
                    threshold += share
                    if roll <= threshold:
                        pid = candidate
                        break

                minute = random.choice([0, 5, 12, 18, 25, 31, 44, 52])
                started = datetime.combine(day, time(hour, minute)).astimezone()
                planned = 25 * 60
                aborted = random.random() < 0.11
                actual = random.randint(300, 1400) if aborted else planned
                interruptions = random.choices([0, 0, 0, 1, 1, 2, 3],
                                               k=1)[0]
                rating = None if aborted else random.choices(
                    [3, 4, 4, 5, 5, 5] if 14 <= hour <= 17 else [2, 3, 3, 4, 4, 5],
                    k=1)[0]

                session_id = uuid.uuid4().hex[:12]
                rows.append((
                    session_id, pid, 1, "work", None, None, planned,
                    pomo.iso(started.astimezone(timezone.utc)),
                    pomo.iso((started + timedelta(seconds=actual)).astimezone(timezone.utc)),
                    actual, random.randint(0, 180), interruptions,
                    "aborted" if aborted else "completed", rating, None, None))

                if not aborted and index < count - 1:
                    skipped = random.random() < 0.23
                    break_kind = "long_break" if (index + 1) % 4 == 0 else "short_break"
                    break_planned = (15 if break_kind == "long_break" else 5) * 60
                    break_start = started + timedelta(seconds=actual + 20)
                    break_actual = 0 if skipped else int(
                        break_planned * random.uniform(0.7, 1.35))
                    rows.append((
                        uuid.uuid4().hex[:12], pid, 1, break_kind, None, None,
                        break_planned,
                        pomo.iso(break_start.astimezone(timezone.utc)),
                        pomo.iso((break_start + timedelta(seconds=break_actual))
                                 .astimezone(timezone.utc)),
                        break_actual, 0, 0,
                        "discarded" if skipped else "completed", None, None, None))

        conn.executemany(
            "INSERT INTO pomo_sessions (id, project_id, preset_id, kind, target_kind,"
            " target_id, planned_seconds, started_at, ended_at, actual_seconds,"
            " paused_seconds, interruptions, outcome, focus_rating, note, tags)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        conn.commit()
    finally:
        conn.close()
    print("%d Sitzungen fuer %d Projekte angelegt." % (len(rows), len(project_ids)))


if __name__ == "__main__":
    import argparse

    from data import profiles

    # argparse statt sys.argv: Ein unbekannter Schalter (etwa das alte
    # --user) bricht ab, statt still beim ersten Profil zu landen.
    parser = argparse.ArgumentParser(description="Beispieldaten anlegen oder entfernen.")
    parser.add_argument("--clear", action="store_true", help="Beispieldaten entfernen")
    parser.add_argument("--profile", help="id oder Name (ohne: das erste Profil, "
                                          "KONZEPT-PROFILE.md, 7)")
    args = parser.parse_args()
    profile = profiles.find(args.profile) if args.profile else profiles.get(profiles.default_id())
    if not profile:
        sys.exit("Unbekanntes Profil: %s" % args.profile)
    with profiles.as_profile(profile["id"]):
        if args.clear:
            clear()
        else:
            seed()
