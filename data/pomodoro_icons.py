"""Projekt-Icons.

Das Projektbild ist fuer die Farben da (meist ein Screenshot) und taugt als
kleines Vorschaubild wenig. Deshalb hat jedes Projekt zusaetzlich ein Icon:
ein kleines SVG aus der Bibliothek unten, eingefaerbt mit der Palette des
Projekts. Ohne gewaehltes Icon wird es aus dem Namen geraten, sonst gibt es
ein Monogramm.

Farben im SVG:
    --ib  Kachelgrund   (palette.bg)
    --i1  Hauptakzent   (palette.a1)
    --i2  Zweitakzent   (palette.a2)
    --i3  Schrift/Hell  (palette.ink)
    --i4  dritter Akzent (palette.a3)
"""

import re
from html import escape

from markupsafe import Markup

I1, I2, I3, I4 = "var(--i1)", "var(--i2)", "var(--i3)", "var(--i4)"
BG = "var(--ib)"

# key -> (Titel, SVG-Inhalt im 48er-Raster)
ICONS = {
    "tomato": ("Tomate", f"""
      <circle cx="24" cy="27" r="14" fill="{I1}"/>
      <ellipse cx="18.5" cy="22" rx="3.5" ry="2.2" fill="{I3}" opacity=".35" transform="rotate(-35 18.5 22)"/>
      <path d="M24 14 l-7 -2 l4 4 l-6 2 l7 1 l2 4 l2 -4 l7 -1 l-6 -2 l4 -4z" fill="{I2}"/>
      <path d="M24 15 q1 -5 4 -7" stroke="{I2}" stroke-width="2" fill="none" stroke-linecap="round"/>"""),

    "teamviewer": ("Fernwartung", f"""
      <rect x="6" y="6" width="36" height="36" rx="9" fill="{I1}"/>
      <circle cx="24" cy="24" r="13" fill="{I3}"/>
      <path d="M13.5 24 l6.5 -5.5 v3.4 h8 v-3.4 l6.5 5.5 l-6.5 5.5 v-3.4 h-8 v3.4z" fill="{I1}"/>"""),

    "guitar": ("Gitarre", f"""
      <g transform="translate(24 24) rotate(40) scale(.97) translate(-24 -24)">
        <rect x="20.5" y="1" width="7" height="8" rx="2" fill="{I3}"/>
        <circle cx="19" cy="3.5" r="1.3" fill="{I3}"/><circle cx="19" cy="7" r="1.3" fill="{I3}"/>
        <circle cx="29" cy="3.5" r="1.3" fill="{I3}"/><circle cx="29" cy="7" r="1.3" fill="{I3}"/>
        <rect x="22.4" y="8" width="3.2" height="21" fill="{I2}"/>
        <path d="M22.4 12h3.2M22.4 15.5h3.2M22.4 19h3.2M22.4 22.5h3.2M22.4 26h3.2" stroke="{BG}" stroke-width=".6"/>
        <path d="M24 26.5 c-4.5 0 -9.5 -1.2 -10.6 2.8 c-.9 3.2 2.2 4.4 1.2 7.4 c-1.1 3.2 -2.4 6.2 2 8.2
                 c3.2 1.5 5.2 -.2 7.4 -.2 s4.2 1.7 7.4 .2 c4.4 -2 3.1 -5 2 -8.2 c-1 -3 2.1 -4.2 1.2 -7.4
                 c-1.1 -4 -6.1 -2.8 -10.6 -2.8z" fill="{I1}"/>
        <rect x="19.5" y="31" width="9" height="2.2" rx="1" fill="{I3}"/>
        <rect x="19.5" y="35" width="9" height="2.2" rx="1" fill="{I3}"/>
        <rect x="20.5" y="39.5" width="7" height="1.8" rx=".6" fill="{I2}"/>
        <path d="M23 5v35M25 5v35" stroke="{I3}" stroke-width=".35" opacity=".7"/>
      </g>"""),

    "rocket": ("Rakete", f"""
      <path d="M5 36 q5 -3 9 0 M3 41 q6 -3 11 0 M9 31 q4 -2 7 0" stroke="{I2}" stroke-width="1.8" fill="none" stroke-linecap="round" opacity=".8"/>
      <g transform="rotate(45 26 22)">
        <path d="M21.5 34 h9 l-1.6 6 l-2.9 5 l-2.9 -5z" fill="{I4}"/>
        <path d="M23.5 34 h5 l-.9 4 l-1.6 3 l-1.6 -3z" fill="{I3}" opacity=".85"/>
        <path d="M19 26 l-5.5 8 v4.5 l5.5 -3.5z M33 26 l5.5 8 v4.5 l-5.5 -3.5z" fill="{I1}"/>
        <path d="M26 3 c5.5 4.5 7.5 12 7.5 19.5 v12 h-15 v-12 c0 -7.5 2 -15 7.5 -19.5z" fill="{I3}"/>
        <path d="M26 3 c3 2.5 5 6.5 6.2 10.5 h-12.4 c1.2 -4 3.2 -8 6.2 -10.5z" fill="{I1}"/>
        <circle cx="26" cy="20" r="3.6" fill="{BG}" stroke="{I2}" stroke-width="1.6"/>
        <rect x="23.5" y="34.5" width="5" height="1.5" fill="{I1}"/>
      </g>"""),

    "swarm": ("Schwarm", f"""
      <path d="M8 34 c6 8 22 8 28 -2 c5 -9 -3 -18 -11 -15 c-6 2 -5 10 1 10" stroke="{I2}" stroke-width="1.2" fill="none" stroke-dasharray="1.5 3" stroke-linecap="round"/>
      <g fill="{I1}">
        <circle cx="26" cy="27" r="5" opacity=".22"/><circle cx="26" cy="27" r="2.2"/>
        <circle cx="36" cy="15" r="6" opacity=".22"/><circle cx="36" cy="15" r="2.6"/>
        <circle cx="13" cy="14" r="4" opacity=".22"/><circle cx="13" cy="14" r="1.7"/>
        <circle cx="10" cy="35" r="3.6" opacity=".22"/><circle cx="10" cy="35" r="1.5"/>
        <circle cx="38" cy="34" r="4" opacity=".22"/><circle cx="38" cy="34" r="1.7"/>
      </g>
      <g fill="{I3}">
        <circle cx="22" cy="10" r="1.1"/><circle cx="20" cy="40" r="1"/><circle cx="42" cy="24" r=".9"/><circle cx="6" cy="24" r=".9"/>
      </g>"""),

    "tax": ("Steuer & Ablage", f"""
      <path d="M5 13 a2 2 0 0 1 2 -2 h10 l3 3.5 h21 a2 2 0 0 1 2 2 v22 a2 2 0 0 1 -2 2 h-34 a2 2 0 0 1 -2 -2z" fill="{I2}"/>
      <rect x="12" y="6" width="22" height="26" rx="1.5" fill="{I3}" transform="rotate(-6 23 19)"/>
      <g transform="rotate(-6 23 19)" fill="{I1}">
        <circle cx="18.5" cy="13.5" r="2.4"/><circle cx="27.5" cy="22.5" r="2.4"/>
        <path d="M28.5 11 l1.6 1.6 l-12.6 12.6 l-1.6 -1.6z"/>
      </g>
      <path d="M4 21 a2 2 0 0 1 2 -2 h36 a2 2 0 0 1 2 2 l-2 17.5 a2 2 0 0 1 -2 1.8 h-32 a2 2 0 0 1 -2 -1.8z" fill="{I1}"/>
      <rect x="18" y="26" width="12" height="3" rx="1.5" fill="{I3}" opacity=".7"/>"""),

    "code": ("Code", f"""
      <rect x="4" y="8" width="40" height="32" rx="4" fill="{I2}" opacity=".25"/>
      <rect x="4" y="8" width="40" height="6" rx="3" fill="{I2}"/>
      <circle cx="8.5" cy="11" r="1.1" fill="{BG}"/><circle cx="12" cy="11" r="1.1" fill="{BG}"/>
      <path d="M17 21 l-6 6 l6 6 M31 21 l6 6 l-6 6" stroke="{I1}" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M27 19 l-6 16" stroke="{I3}" stroke-width="2.6" stroke-linecap="round"/>"""),

    "gamepad": ("Spiel", f"""
      <path d="M14 15 h20 c5.5 0 8.5 5 9.5 12 c1 7 -1 11 -4.5 11 c-3 0 -4.5 -3.5 -7 -6 h-16 c-2.5 2.5 -4 6 -7 6 c-3.5 0 -5.5 -4 -4.5 -11 c1 -7 4 -12 9.5 -12z" fill="{I1}"/>
      <path d="M12.5 22v8M8.5 26h8" stroke="{I3}" stroke-width="2.8" stroke-linecap="round"/>
      <circle cx="33" cy="23" r="2.1" fill="{I2}"/><circle cx="37.5" cy="27" r="2.1" fill="{I3}"/>
      <circle cx="28.5" cy="27" r="2.1" fill="{I3}"/><circle cx="33" cy="31" r="2.1" fill="{I2}"/>"""),

    "book": ("Buch", f"""
      <path d="M24 12 c-5 -3.5 -12 -4 -19 -2.5 v28 c7 -1.5 14 -1 19 2.5z" fill="{I1}"/>
      <path d="M24 12 c5 -3.5 12 -4 19 -2.5 v28 c-7 -1.5 -14 -1 -19 2.5z" fill="{I2}"/>
      <path d="M9 16 c4 -.8 8 -.5 11 1 M9 21 c4 -.8 8 -.5 11 1 M9 26 c4 -.8 8 -.5 11 1 M28 17 c3 -1.5 7 -1.8 11 -1 M28 22 c3 -1.5 7 -1.8 11 -1" stroke="{I3}" stroke-width="1.3" fill="none" opacity=".75" stroke-linecap="round"/>
      <path d="M33 8 v12 l3 -2.5 l3 2.5 v-12z" fill="{I4}"/>"""),

    "pen": ("Schreiben", f"""
      <path d="M8 42 c8 -2 14 -1 20 0 s10 1 13 -1" stroke="{I2}" stroke-width="1.8" fill="none" stroke-linecap="round"/>
      <g transform="rotate(45 24 22)">
        <rect x="20" y="2" width="8" height="30" rx="1.5" fill="{I1}"/>
        <rect x="20" y="6" width="8" height="3" fill="{I3}" opacity=".6"/>
        <path d="M20 32 h8 l-4 9z" fill="{I3}"/>
        <path d="M23 38.5 h2 l-1 2.5z" fill="{I2}"/>
      </g>"""),

    "music": ("Musik", f"""
      <path d="M18 34 V12 l20 -5 v22" stroke="{I3}" stroke-width="2.6" fill="none" stroke-linejoin="round"/>
      <path d="M18 12 l20 -5 v5.5 l-20 5z" fill="{I3}"/>
      <ellipse cx="13.5" cy="35" rx="5.5" ry="4.2" fill="{I1}" transform="rotate(-20 13.5 35)"/>
      <ellipse cx="33.5" cy="30" rx="5.5" ry="4.2" fill="{I2}" transform="rotate(-20 33.5 30)"/>"""),

    "art": ("Kunst", f"""
      <path d="M24 6 c10 0 19 7 19 16 c0 6 -5 8 -9 7 c-3 -.8 -5 1 -4 4 c1.2 3.5 -1 8 -6 8 c-10 0 -19 -7 -19 -17 s9 -18 19 -18z" fill="{I3}"/>
      <circle cx="14" cy="21" r="3.3" fill="{I1}"/><circle cx="20" cy="13" r="3.3" fill="{I2}"/>
      <circle cx="30" cy="13" r="3.3" fill="{I4}"/><circle cx="14.5" cy="31" r="3.3" fill="{I2}"/>
      <circle cx="35" cy="20" r="3" fill="{I1}"/>"""),

    "chart": ("Zahlen", f"""
      <rect x="8" y="26" width="7" height="14" rx="1.5" fill="{I2}"/>
      <rect x="20" y="18" width="7" height="22" rx="1.5" fill="{I1}"/>
      <rect x="32" y="10" width="7" height="30" rx="1.5" fill="{I4}"/>
      <path d="M6 42 h37" stroke="{I3}" stroke-width="2" stroke-linecap="round"/>
      <path d="M9 20 l12 -7 l6 3 l12 -9" stroke="{I3}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>"""),

    "leaf": ("Natur", f"""
      <path d="M40 7 c-20 0 -31 9 -31 22 c0 4 1.5 7.5 3.5 10 c15 0 27.5 -9 27.5 -32z" fill="{I1}"/>
      <path d="M8 43 c5 -10 13 -19 25 -28" stroke="{I3}" stroke-width="2" fill="none" stroke-linecap="round"/>
      <path d="M17 31 l-2 -8 M23 25 l-1.5 -9 M22 31 l8 1" stroke="{I3}" stroke-width="1.3" stroke-linecap="round" opacity=".7"/>"""),

    "home": ("Haushalt", f"""
      <path d="M6 23 l18 -15 l18 15" stroke="{I1}" stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M11 21 v19 h26 v-19 l-13 -10.5z" fill="{I2}"/>
      <rect x="20" y="28" width="8" height="12" rx="1" fill="{I3}"/>
      <rect x="31" y="9" width="4" height="8" fill="{I1}"/>"""),

    "work": ("Arbeit", f"""
      <path d="M18 13 v-3 a2 2 0 0 1 2 -2 h8 a2 2 0 0 1 2 2 v3" stroke="{I3}" stroke-width="2.5" fill="none"/>
      <rect x="5" y="13" width="38" height="27" rx="3.5" fill="{I1}"/>
      <path d="M5 23 h38" stroke="{BG}" stroke-width="1.5" opacity=".5"/>
      <rect x="20.5" y="20" width="7" height="6" rx="1.2" fill="{I3}"/>"""),

    "sport": ("Sport", f"""
      <rect x="15" y="22.5" width="18" height="3" fill="{I3}"/>
      <rect x="8" y="13" width="6" height="22" rx="2" fill="{I1}"/>
      <rect x="34" y="13" width="6" height="22" rx="2" fill="{I1}"/>
      <rect x="3" y="17" width="4.5" height="14" rx="1.5" fill="{I2}"/>
      <rect x="40.5" y="17" width="4.5" height="14" rx="1.5" fill="{I2}"/>"""),

    "camera": ("Foto & Video", f"""
      <path d="M16 12 l3 -4 h10 l3 4z" fill="{I2}"/>
      <rect x="4" y="12" width="40" height="27" rx="4" fill="{I1}"/>
      <circle cx="24" cy="25.5" r="9" fill="{I3}"/>
      <circle cx="24" cy="25.5" r="5.5" fill="{I2}"/>
      <circle cx="22" cy="23.5" r="1.6" fill="{I3}" opacity=".8"/>
      <rect x="35" y="15.5" width="5" height="3" rx="1" fill="{I3}"/>"""),

    "mail": ("Kommunikation", f"""
      <rect x="5" y="11" width="38" height="26" rx="3.5" fill="{I1}"/>
      <path d="M7 14 l17 13 l17 -13" stroke="{I3}" stroke-width="2.5" fill="none" stroke-linejoin="round"/>
      <circle cx="40" cy="12" r="5" fill="{I4}"/>"""),
}

#: Erraten aus dem Projektnamen -- erstes Muster gewinnt.
GUESS = (
    (r"teamviewer|fernwartung|remote", "teamviewer"),
    (r"gitar|guitar|bass", "guitar"),
    (r"rocket|rakete", "rocket"),
    (r"schwarm|swarm|lumina|gl[uü]hw", "swarm"),
    (r"steuer|ablage|finanz|tax|buchhalt|rechnung", "tax"),
    (r"ohne projekt", "tomato"),
    (r"code|dev|program|software|python|web", "code"),
    (r"spiel|game|unreal|unity", "gamepad"),
    (r"buch|book|lesen|lern|studi|kurs", "book"),
    (r"schreib|text|blog|roman|write", "pen"),
    (r"musik|music|klavier|piano|song|gesang", "music"),
    (r"kunst|art|mal|zeichn|design", "art"),
    (r"zahl|statistik|analyse|chart|report", "chart"),
    (r"garten|natur|pflanz|biotop", "leaf"),
    (r"haus|wohnung|putz|home|haushalt", "home"),
    (r"arbeit|job|b[uü]ro|work|meeting", "work"),
    (r"sport|training|fitness|gym|lauf", "sport"),
    (r"foto|photo|video|film", "camera"),
    (r"mail|brief|nachricht|kommunik", "mail"),
)


def guess(label):
    text = (label or "").lower()
    for pattern, key in GUESS:
        if re.search(pattern, text):
            return key
    return None


def resolve(project_row):
    """Gewaehltes Icon, sonst geraten, sonst None (= Monogramm)."""
    chosen = (project_row or {}).get("icon")
    if chosen in ICONS:
        return chosen
    if chosen == "letter":
        return None
    return guess((project_row or {}).get("label"))


def _monogram(label):
    letter = escape(((label or "?").strip() or "?")[0].upper())
    return (f'<text x="24" y="25" text-anchor="middle" dominant-baseline="central" '
            f'font-family="var(--pomo-display), Georgia, serif" font-size="27" '
            f'fill="{I1}">{letter}</text>')


def svg(key, label="", palette=None, size=48, cls="picon"):
    """Fertige Kachel als SVG-Markup."""
    pal = palette or {}
    style = "--ib:%s;--i1:%s;--i2:%s;--i3:%s;--i4:%s" % (
        pal.get("bg", "#151020"), pal.get("a1", "#ff9679"), pal.get("a2", "#f7c35a"),
        pal.get("ink", "#f4ece4"), pal.get("a3", "#c58cff"))
    body = ICONS[key][1] if key in ICONS else _monogram(label)
    return Markup(
        f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 48 48" '
        f'style="{style}" role="img" aria-label="{escape(label or "")}">'
        f'<rect width="48" height="48" rx="9" fill="{BG}"/>{body}</svg>')


def for_project(view, size=48, cls="picon"):
    """Icon fuer ein Projekt aus projects.view()."""
    if not view:
        return svg("tomato", "", None, size, cls)
    return svg(view.get("icon"), view.get("label"), view.get("palette"), size, cls)
