"""Farbableitung fuer das Pomodoro-Modul.

Die eine Regel: Aus dem Bild (oder aus einer von Hand gewaehlten Leitfarbe)
kommt fast nur der FARBTON. Helligkeit und Saettigung setzt das Thema.
Siehe KONZEPT-PROJEKTFARBEN.md, Abschnitt 1 und 2.

Die Ableitung steht bewusst hier und nicht im Browser-JS: Der Browser liest
nur die Pixel und schickt die gefundenen Farbtoene ("Seeds") her. Damit gibt
es genau eine Stelle, an der die Regeln stehen, und Projekte ohne Bild
bekommen ueber dieselbe Funktion eine Palette aus ihrer Leitfarbe.

Keine Abhaengigkeiten ausser der stdlib.
"""

import math


def _srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def rgb_to_oklab(r, g, b):
    lr, lg, lb = _srgb_to_lin(r / 255), _srgb_to_lin(g / 255), _srgb_to_lin(b / 255)
    l = (0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb) ** (1 / 3)
    m = (0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb) ** (1 / 3)
    s = (0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb) ** (1 / 3)
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def oklab_to_rgb(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        _lin_to_srgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
        _lin_to_srgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
        _lin_to_srgb(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s),
    )


def _in_gamut(rgb):
    return all(-0.001 <= c <= 1.001 for c in rgb)


def lch_to_hex(L, C, h):
    """OKLCH nach #rrggbb.

    Liegt die Farbe ausserhalb von sRGB, wird die Saettigung gesenkt bis sie
    passt. Helligkeit und Farbton bleiben, weil die beiden die Lesbarkeit
    tragen.
    """
    rad = math.radians(h)
    c = C
    rgb = oklab_to_rgb(L, math.cos(rad) * c, math.sin(rad) * c)
    for _ in range(40):
        if _in_gamut(rgb):
            break
        c = max(0.0, c - 0.005)
        rgb = oklab_to_rgb(L, math.cos(rad) * c, math.sin(rad) * c)
    return "#" + "".join("%02x" % round(max(0.0, min(1.0, v)) * 255) for v in rgb)


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def hex_to_lch(value):
    L, a, b = rgb_to_oklab(*hex_to_rgb(value))
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def mix(hex_a, hex_b, t):
    """Mischung in OKLab. In sRGB gemischte Zwischentoene werden matschig."""
    la, aa, ba = rgb_to_oklab(*hex_to_rgb(hex_a))
    lb, ab, bb = rgb_to_oklab(*hex_to_rgb(hex_b))
    L = la + (lb - la) * t
    a = aa + (ab - aa) * t
    b = ba + (bb - ba) * t
    return lch_to_hex(L, math.hypot(a, b), math.degrees(math.atan2(b, a)))


def _rel_lum(rgb):
    r, g, b = (_srgb_to_lin(c / 255) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(hex_a, hex_b):
    la, lb = _rel_lum(hex_to_rgb(hex_a)), _rel_lum(hex_to_rgb(hex_b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _ensure(L, C, h, bg_hex, target):
    """Hebt die Helligkeit an, bis der Kontrast zum Grund das Ziel erreicht.

    Das ist die Stelle, die garantiert, dass auch ein unpassendes Bild eine
    benutzbare Oberflaeche ergibt.
    """
    for _ in range(90):
        value = lch_to_hex(L, C, h)
        if contrast(value, bg_hex) >= target:
            return value
        L += 0.01
        if L > 0.99:
            return lch_to_hex(0.99, C, h)
    return lch_to_hex(L, C, h)


def _lift_for_hue(L, h):
    """Gelb und Gelbgruen sind bei mittlerer Helligkeit schmutzig.

    Derselbe L-Wert wirkt je nach Farbton anders, deshalb bekommt jeder
    Farbton eine eigene Untergrenze.
    """
    h = h % 360
    if 80 <= h <= 140:
        floor = 0.87
    elif (55 <= h < 80) or (140 < h <= 170):
        floor = 0.80
    else:
        floor = 0.74
    return max(L, floor)


def hue_distance(a, b):
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


LOW_CHROMA = 0.035
ROLES = ("bg", "surface", "ink", "muted", "line", "a1", "a2", "a3", "a4", "warn")

# Variante 08 "Sinnlich & Kuenstlerisch" ist der Stand ohne Bild.
THEME_BG = "#151020"
THEME_ACCENT = "#FF9679"
THEME_ALT = "#7BD6BE"

#: Abstand Grund zu Leitfarbe, abgelesen an Variante 08.
BG_OFFSET = -96


def seeds_from_theme():
    _, bg_c, bg_h = hex_to_lch(THEME_BG)
    _, ac_c, ac_h = hex_to_lch(THEME_ACCENT)
    _, _, alt_h = hex_to_lch(THEME_ALT)
    return {"bg_hue": bg_h, "bg_chroma": bg_c,
            "acc_hue": ac_h, "acc_chroma": ac_c,
            "alt_hue": alt_h, "low_chroma": False}


def seeds_from_color(color_hex):
    """Palette aus einer von Hand gewaehlten Leitfarbe.

    Der billige Weg ohne Bild, siehe KONZEPT-PROJEKTFARBEN.md Abschnitt 10.
    """
    _, c, h = hex_to_lch(color_hex)
    # Der Grund uebernimmt den Farbton NICHT: Grund und Akzent im selben Ton
    # ergeben eine monochrome, tote Oberflaeche. Der Abstand ist der aus
    # Variante 08 (Koralle auf Aubergine).
    return {"bg_hue": h + BG_OFFSET, "bg_chroma": 0.03,
            "acc_hue": h, "acc_chroma": c,
            "alt_hue": h + 135, "low_chroma": c < LOW_CHROMA}


def derive(seeds, hue_shift=0, chroma_scale=1.0, overrides=None):
    """Zehn Farbrollen aus den Seeds.

    seeds         aus dem Bild (Browser) oder aus einer Leitfarbe
    hue_shift     Regler der Verwaltung, -60..+60 Grad
    chroma_scale  Regler der Verwaltung, 0.6..1.5, wirkt nur auf die Akzente
    overrides     {rolle: "#rrggbb"} fuer gesperrte Rollen
    """
    shift = float(hue_shift or 0)
    cs = float(chroma_scale) if chroma_scale else 1.0

    bg_h = seeds["bg_hue"] + shift
    bg_c = min(seeds.get("bg_chroma", 0.0), 0.045)
    bg = lch_to_hex(0.155, bg_c, bg_h)

    acc_h = seeds["acc_hue"] + shift
    acc_c = max(min(seeds.get("acc_chroma", 0.12), 0.17), 0.115) * cs
    alt_h = seeds.get("alt_hue", seeds["acc_hue"] + 135) + shift
    neutral_c = min(bg_c, 0.022)

    out = {
        "bg": bg,
        "surface": lch_to_hex(0.205, bg_c * 0.9, bg_h),
        "ink": _ensure(0.945, neutral_c, bg_h, bg, 7.0),
        "muted": _ensure(0.70, neutral_c, bg_h, bg, 4.5),
        "a1": _ensure(_lift_for_hue(0.76, acc_h), acc_c, acc_h, bg, 4.5),
        "a2": _ensure(_lift_for_hue(0.82, acc_h + 28), acc_c * 0.95, acc_h + 28, bg, 4.5),
        "a3": _ensure(_lift_for_hue(0.79, alt_h), 0.125 * cs, alt_h, bg, 4.5),
        "a4": _ensure(_lift_for_hue(0.72, acc_h - 85), 0.135 * cs, acc_h - 85, bg, 4.5),
        # Die Warnfarbe bleibt in jedem Projekt rot. Eine Abbruchschaltflaeche,
        # die mal rot und mal tuerkis ist, ist kein Design, sondern ein Fehler.
        "warn": _ensure(0.70, 0.16, 18, bg, 4.5),
    }
    out["line"] = mix(out["bg"], out["ink"], 0.18)

    for role, value in (overrides or {}).items():
        if role in ROLES and value:
            out[role] = value

    out["_meta"] = {
        "acc_hue": round(acc_h % 360, 1),
        "low_chroma": bool(seeds.get("low_chroma")),
        "contrast": {
            "ink_on_bg": round(contrast(out["ink"], out["bg"]), 2),
            "muted_on_bg": round(contrast(out["muted"], out["bg"]), 2),
            "a1_on_bg": round(contrast(out["a1"], out["bg"]), 2),
        },
    }
    return out


def default_palette():
    return derive(seeds_from_theme())


def css_vars(palette, prefix="--pomo"):
    """Die Farbwerte als CSS-Block fuer die Jinja-Vorlage.

    Serverseitig gerendert, nicht per JS nachgesetzt: Die Navigation macht
    Vollreloads, sonst blitzt bei jedem Seitenwechsel das Standardthema auf.
    """
    return "\n".join("  %s-%s: %s;" % (prefix, r, palette[r])
                     for r in ROLES if r in palette)


def font_suggestion(palette):
    """Vorschlag, mehr nicht. In den Pixeln steht keine Schrift,
    siehe KONZEPT-PROJEKTFARBEN.md Abschnitt 4."""
    meta = palette.get("_meta", {})
    if meta.get("low_chroma"):
        return "Playfair Display"
    hue = meta.get("acc_hue", 30)
    return "Cormorant Garamond" if (hue < 100 or hue > 330) else "Spectral"


if __name__ == "__main__":
    pal = default_palette()
    for key in ROLES:
        print("%-8s %s" % (key, pal[key]))
    print("meta     %s" % (pal["_meta"],))
    print("schrift  %s" % font_suggestion(pal))
