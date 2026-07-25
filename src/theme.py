from __future__ import annotations

from typing import Any


THEME_OPTIONS: dict[str, dict[str, str]] = {
    "midnight_blue": {
        "label": "午夜藍",
        "background": "#0B1324",
        "surface": "#111C33",
        "card": "#16243D",
        "sidebar": "#0F1A2E",
        "primary": "#8FB9D1",
        "secondary": "#6191D3",
        "accent": "#FDB338",
        "danger": "#E86349",
        "success": "#4DB6AC",
        "warning": "#FDB338",
        "text": "#F8F6F6",
        "muted_text": "#C9D4E5",
        "border": "#2F4264",
        "table_header": "#1E3152",
        "chart_grid": "#2F4264",
    },
    "deep_teal": {
        "label": "深海綠",
        "background": "#071C1F",
        "surface": "#0D2A2E",
        "card": "#12363B",
        "sidebar": "#092326",
        "primary": "#7ED6C4",
        "secondary": "#4DB6AC",
        "accent": "#FDB338",
        "danger": "#E86349",
        "success": "#7ED6C4",
        "warning": "#FDB338",
        "text": "#F4FAFA",
        "muted_text": "#B9D7D5",
        "border": "#245257",
        "table_header": "#164247",
        "chart_grid": "#245257",
    },
    "charcoal_orange": {
        "label": "炭黑橘",
        "background": "#0F1115",
        "surface": "#181B22",
        "card": "#20242D",
        "sidebar": "#141820",
        "primary": "#F0F2F3",
        "secondary": "#9CA3AF",
        "accent": "#FDB338",
        "danger": "#E86349",
        "success": "#8FB9D1",
        "warning": "#FDB338",
        "text": "#F5F7FA",
        "muted_text": "#C7CBD1",
        "border": "#343A46",
        "table_header": "#2A303A",
        "chart_grid": "#343A46",
    },
    "navy_gold": {
        "label": "深藍金",
        "background": "#061826",
        "surface": "#092B42",
        "card": "#0E3550",
        "sidebar": "#071F30",
        "primary": "#D6DFEB",
        "secondary": "#8FB9D1",
        "accent": "#FDB338",
        "danger": "#E86349",
        "success": "#6191D3",
        "warning": "#FDB338",
        "text": "#F8F6F6",
        "muted_text": "#C9D4E5",
        "border": "#244A66",
        "table_header": "#123A58",
        "chart_grid": "#244A66",
    },
    "slate_purple": {
        "label": "石板紫",
        "background": "#11111F",
        "surface": "#1A1A2E",
        "card": "#23233B",
        "sidebar": "#161627",
        "primary": "#C7D2FE",
        "secondary": "#A5B4FC",
        "accent": "#FDB338",
        "danger": "#E86349",
        "success": "#8FB9D1",
        "warning": "#FDB338",
        "text": "#F8F6F6",
        "muted_text": "#D1D5DB",
        "border": "#3A3A5A",
        "table_header": "#2C2C48",
        "chart_grid": "#3A3A5A",
    },
}

DEFAULT_THEME_NAME = "midnight_blue"

REQUIRED_THEME_KEYS = {
    "background",
    "surface",
    "card",
    "sidebar",
    "primary",
    "secondary",
    "accent",
    "danger",
    "success",
    "warning",
    "text",
    "muted_text",
    "border",
    "table_header",
    "chart_grid",
}


def _with_legacy_aliases(theme: dict[str, str]) -> dict[str, str]:
    out = dict(theme)
    out.setdefault("normal", out["secondary"])
    out.setdefault("light_blue", out["primary"])
    out.setdefault("pale_blue", out["chart_grid"])
    out.setdefault("card_dark", out["card"])
    out.setdefault("panel", out["card"])
    out.setdefault("panel_strong", out["surface"])
    out.setdefault("surface_soft", out["muted_text"])
    out.setdefault("surface_muted", out["muted_text"])
    out.setdefault("surface_border", out["border"])
    out.setdefault("accent_soft", "rgba(253, 179, 56, 0.16)")
    out.setdefault("warning_soft", "rgba(253, 179, 56, 0.16)")
    success_red, success_green, success_blue = hex_to_rgb(out["success"])
    out.setdefault("success_soft", f"rgba({success_red}, {success_green}, {success_blue}, 0.16)")
    out.setdefault("shadow", "rgba(0, 0, 0, 0.30)")
    return out


def get_theme(theme_name: str | None = None) -> dict[str, str]:
    if not theme_name or theme_name not in THEME_OPTIONS:
        theme_name = DEFAULT_THEME_NAME
    return _with_legacy_aliases(THEME_OPTIONS[theme_name])


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB color, got {hex_color!r}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def relative_luminance(hex_color: str) -> float:
    channels = []
    for channel in hex_to_rgb(hex_color):
        normalized = channel / 255
        channels.append(normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    fg = relative_luminance(foreground)
    bg = relative_luminance(background)
    lighter, darker = max(fg, bg), min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def validate_theme_contrast(theme: dict[str, str]) -> dict[str, Any]:
    pairs = {
        "text_vs_background": ("text", "background", 4.5),
        "text_vs_card": ("text", "card", 4.5),
        "text_vs_surface": ("text", "surface", 4.5),
        "text_vs_sidebar": ("text", "sidebar", 4.5),
        "muted_text_vs_background": ("muted_text", "background", 3.0),
        "muted_text_vs_card": ("muted_text", "card", 3.0),
        "muted_text_vs_surface": ("muted_text", "surface", 3.0),
        "danger_vs_background": ("danger", "background", 3.0),
        "danger_vs_card": ("danger", "card", 3.0),
        "accent_vs_background": ("accent", "background", 3.0),
        "accent_vs_card": ("accent", "card", 3.0),
    }
    checks = {
        name: {"ratio": contrast_ratio(theme[foreground], theme[background]), "minimum": minimum}
        for name, (foreground, background, minimum) in pairs.items()
    }
    for value in checks.values():
        value["passed"] = value["ratio"] >= value["minimum"]
        value["ratio"] = round(value["ratio"], 3)
    return {
        "passed": all(bool(value["passed"]) for value in checks.values()),
        "checks": checks,
    }


def chart_color_sequence(theme: dict[str, str] | None = None) -> list[str]:
    active = theme or THEME
    return [
        active["primary"],
        active["secondary"],
        active["accent"],
        active["success"],
        active["danger"],
    ]


THEME = get_theme(DEFAULT_THEME_NAME)
CHART_COLORS = chart_color_sequence(THEME)
