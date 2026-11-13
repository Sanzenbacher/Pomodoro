"""Projektbilder und ihre Paletten.

Die Extraktion laeuft im Browser (static/js/pomodoro_palette.js): Dort
liegen die Pixel ohnehin schon, Canvas kann sie lesen, und damit bleibt es
bei den Abhaengigkeiten aus dem Hauptkonzept -- kein Pillow, kein NumPy.

Der Browser schickt drei Dinge: das Originalbild, zwei fertig gerechnete
Verkleinerungen und die gefundenen Farbtoene ("Seeds"). Die Ableitung der
neun Rollen macht der Server, damit die Regeln an genau einer Stelle stehen.

Siehe KONZEPT-PROJEKTFARBEN.md, Abschnitt 2 und 7.
"""

import base64
import hashlib
import json
import os
import re

from data import pomodoro as pomo
from data import pomodoro_icons as icons
from data import pomodoro_palette as palette
from data import profiles
from data.appconfig import POMO

MAX_BYTES = 8 * 1024 * 1024
ALLOWED = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}

_DATA_URL = re.compile(r"^data:(image/[a-z+]+);base64,(.+)$", re.I | re.S)


def image_dir():
    """Projektbilder des aktuellen Profils (KONZEPT-PROFILE.md, 3)."""
    return profiles.paths()["images"]


def _ensure_dir():
    os.makedirs(image_dir(), exist_ok=True)


def _decode_data_url(value):
    match = _DATA_URL.match(value or "")
    if not match:
        return None, None
    return match.group(1).lower(), base64.b64decode(match.group(2))


def image_files(project_id):
    _ensure_dir()
    found = {}
    for suffix in ("", "_veil", "_thumb"):
        for ext in ("png", "jpg", "webp"):
            name = "%s%s.%s" % (project_id, suffix, ext)
            if os.path.exists(os.path.join(image_dir(), name)):
                found[suffix or "full"] = name
                break
    return found


def has_image(project_row):
    return bool(project_row.get("image_path"))


def save_image(project_id, blob, mime, seeds, thumb_url=None, veil_url=None):
    """Bild und Seeds ablegen, Palette neu rechnen.

    blob       Originalbytes
    seeds      {bg_hue, bg_chroma, acc_hue, acc_chroma, alt_hue, low_chroma}
    thumb_url  data:-URL der 160-px-Miniatur (vom Browser gerechnet)
    veil_url   data:-URL des 1280-px-Schleiers
    """
    if len(blob) > MAX_BYTES:
        raise ValueError("Das Bild ist groesser als 8 MB.")
    ext = ALLOWED.get((mime or "").lower())
    if not ext:
        raise ValueError("Nur PNG, JPG oder WEBP.")

    _ensure_dir()
    remove_image(project_id, keep_palette=True)

    name = "%s.%s" % (project_id, ext)
    with open(os.path.join(image_dir(), name), "wb") as handle:
        handle.write(blob)

    for suffix, data_url in (("_thumb", thumb_url), ("_veil", veil_url)):
        mime2, data = _decode_data_url(data_url) if data_url else (None, None)
        if data:
            ext2 = ALLOWED.get(mime2, "png")
            with open(os.path.join(image_dir(), "%s%s.%s" % (project_id, suffix, ext2)),
                      "wb") as handle:
                handle.write(data)

    pomo.update_project(project_id, {
        "image_path": name,
        "image_hash": hashlib.sha256(blob).hexdigest()[:16],
        "seeds_json": json.dumps(seeds),
    })
    return recompute(project_id)


def remove_image(project_id, keep_palette=False):
    _ensure_dir()
    for name in os.listdir(image_dir()):
        if name.split(".")[0].split("_")[0] == str(project_id):
            try:
                os.remove(os.path.join(image_dir(), name))
            except OSError:
                pass
    if not keep_palette:
        pomo.update_project(project_id, {"image_path": None, "image_hash": None,
                                         "seeds_json": None})
        return recompute(project_id)
    return None


# ---------------------------------------------------------------- Palette


def seeds_of(project_row):
    """Seeds aus dem Bild, sonst aus der Leitfarbe, sonst aus dem Thema."""
    raw = project_row.get("seeds_json")
    if raw:
        try:
            return json.loads(raw)
        except ValueError:
            pass
    if project_row.get("color"):
        return palette.seeds_from_color(project_row["color"])
    return palette.seeds_from_theme()


def overrides_of(project_row):
    raw = project_row.get("palette_json")
    if not raw:
        return {}
    try:
        return (json.loads(raw) or {}).get("_overrides", {}) or {}
    except ValueError:
        return {}


def resolve(project_row):
    """Die neun Farbrollen fuer ein Projekt.

    Ist die Palette festgehalten, wird nichts neu gerechnet -- sonst wuerde
    eine Aenderung an den Ableitungsregeln von Hand gesetzte Farben
    ueberschreiben.
    """
    if not POMO.get("project_colors", True) or not project_row:
        return palette.default_palette()

    if project_row.get("palette_locked") and project_row.get("palette_json"):
        try:
            stored = json.loads(project_row["palette_json"])
            if all(role in stored for role in palette.ROLES):
                return stored
        except ValueError:
            pass

    return palette.derive(
        seeds_of(project_row),
        hue_shift=project_row.get("hue_shift") or 0,
        chroma_scale=project_row.get("chroma_scale") or 1.0,
        overrides=overrides_of(project_row))


def recompute(project_id, overrides=None):
    row = pomo.project(project_id)
    if not row:
        return palette.default_palette()
    if overrides is not None:
        stored = {"_overrides": overrides}
        pomo.update_project(project_id, {"palette_json": json.dumps(stored)})
        row = pomo.project(project_id)
    result = resolve(row)
    keep = overrides_of(row)
    payload = dict(result)
    payload["_overrides"] = keep
    pomo.update_project(project_id, {"palette_json": json.dumps(payload)})
    return result


def font_of(project_row, pal=None):
    """Gesetzte Schrift schlaegt den Vorschlag. In den Pixeln steht keine
    Schrift -- siehe KONZEPT-PROJEKTFARBEN.md, Abschnitt 4."""
    if project_row and project_row.get("display_font"):
        return project_row["display_font"]
    return palette.font_suggestion(pal or resolve(project_row or {}))


def view(project_row):
    """Alles, was eine Seite ueber ein Projekt wissen muss."""
    pal = resolve(project_row)
    files = image_files(project_row["id"]) if project_row else {}
    return {
        "id": project_row["id"],
        "label": project_row["label"],
        "color": project_row["color"],
        "stats_color": project_row.get("stats_color"),
        "stats_color_auto": stats_colors().get(project_row["id"]),
        "archived": bool(project_row["archived"]),
        "is_default": bool(project_row["is_default"]),
        "has_image": bool(files.get("full")),
        "image": files.get("full"),
        "thumb": files.get("_thumb") or files.get("full"),
        "veil": files.get("_veil") or files.get("full"),
        "palette": pal,
        "font": font_of(project_row, pal),
        "icon": icons.resolve(project_row),
        "icon_set": project_row.get("icon"),
        "hue_shift": project_row["hue_shift"],
        "chroma_scale": project_row["chroma_scale"],
        "palette_locked": bool(project_row["palette_locked"]),
        "overrides": overrides_of(project_row),
        "sessions": pomo.project_session_count(project_row["id"]),
        "entries": pomo.project_entry_count(project_row["id"]),
        "use_timer": bool(project_row.get("use_timer", 1)),
        "use_journal": bool(project_row.get("use_journal", 0)),
    }


def collide(project_id=None):
    """Projekte, deren Leitfarbton weniger als 25 Grad auseinanderliegt.

    Zwei gleich aussehende Projekte nehmen der ganzen Idee den Sinn,
    siehe KONZEPT-PROJEKTFARBEN.md, Abschnitt 9.
    """
    # Alle Kategorien: Projekte und Aktivitaeten stehen gemeinsam in
    # Biotop-Legende und Timeline.
    rows = pomo.projects(use=None)
    hues = []
    for row in rows:
        pal = resolve(row)
        hues.append((row["id"], row["label"], pal.get("_meta", {}).get("acc_hue", 0)))
    out = []
    for i, (pid, label, hue) in enumerate(hues):
        for other_id, other_label, other_hue in hues[i + 1:]:
            if palette.hue_distance(hue, other_hue) < 25:
                out.append({"a": label, "b": other_label,
                            "a_id": pid, "b_id": other_id})
    if project_id:
        out = [c for c in out if project_id in (c["a_id"], c["b_id"])]
    return out


# ---------------------------------------------------------------- Statistik

#: Unter diesem Abstand gilt ein Farbton in der Statistik als "schon vergeben".
STATS_MIN_HUE_GAP = 45


def stats_colors():
    """Eine Farbe je Projekt fuer die Diagramme, {project_id: "#rrggbb"}.

    Von Hand gesetzte Farben (stats_color) gelten unveraendert. Alle anderen
    Projekte starten beim Farbton ihrer Leitfarbe -- damit bleibt die
    Verbindung zum Projekt erkennbar. Liegt der zu nah an einem schon
    vergebenen, wird der Farbton genommen, der von allen vergebenen am
    weitesten weg ist. Helligkeit und Saettigung sind fest, damit alle Balken
    gleich kraeftig wirken und keiner nur durch Helligkeit auffaellt.

    Zugeteilt wird ueber alle Projekte (auch archivierte) in fester
    Reihenfolge, damit sich eine Farbe nicht aendert, nur weil man im
    Zeitraumfilter blaettert.
    """
    rows = sorted(pomo.projects(include_archived=True, use=None), key=lambda r: r["id"])
    out, used = {}, []
    for row in rows:
        if row.get("stats_color"):
            out[row["id"]] = row["stats_color"]
            used.append(palette.hex_to_lch(row["stats_color"])[2])
    for row in rows:
        if row["id"] in out:
            continue
        wanted = resolve(row).get("_meta", {}).get("acc_hue", 0) % 360
        if used and min(palette.hue_distance(wanted, h) for h in used) < STATS_MIN_HUE_GAP:
            wanted = max(range(0, 360, 5), key=lambda h: (
                min(palette.hue_distance(h, u) for u in used),
                -palette.hue_distance(h, wanted)))
        used.append(wanted)
        out[row["id"]] = palette.lch_to_hex(palette._lift_for_hue(0.74, wanted), 0.14, wanted)
    return out
