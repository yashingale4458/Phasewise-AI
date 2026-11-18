"""PhaseWise AI dashboard design system.

Presentation only. Every component renders values the service has already
established; no business rule lives here.

Design system principles:
- Dual themes: Deep dark mode (#0D1117) with electric-green brand (#00C896) and
  glassmorphism surfaces; Light mode (#F4F7F5) with forest-green brand (#0B6B57).
- Typography: Outfit (700, 800) for display/headings, Inter (400, 500, 600) for
  interface body, JetBrains Mono for code and numerical data.
- Interactive glow: Animated gradient border glow on stat cards, color-matched neon
  glow on badges, smooth CSS transitions everywhere.
- Inline SVGs (Lucide geometry, 24px grid, 1.75 stroke). No emoji in system components.
- Every piece of text that reaches HTML goes through escape().
"""

from __future__ import annotations

import html
import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import streamlit as st

from config import config


# ---------------------------------------------------------------------------
# Theme state helper
# ---------------------------------------------------------------------------

def _is_dark_mode() -> bool:
    """Always use the light theme for a consistent, production-ready UI."""
    return False


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

# Light mode palette: name -> (background, foreground, border)
TONES_LIGHT: dict[str, tuple[str, str, str]] = {
    "green": ("#EDF6F1", "#156B45", "#CFE6D9"),
    "red": ("#FCEFED", "#A12A1F", "#F3D2CD"),
    "orange": ("#FCF3E8", "#924A10", "#F1DCC2"),
    "yellow": ("#FBF6E2", "#6B5304", "#EEE2B4"),
    "blue": ("#EDF3FB", "#1F4E8C", "#D3E0F2"),
    "violet": ("#F3EFFA", "#5934A0", "#DFD5F1"),
    "gray": ("#F3F4F2", "#4A5451", "#E3E6E2"),
    "grey": ("#F3F4F2", "#4A5451", "#E3E6E2"),
    "primary": ("#E9F2EE", "#0B6B57", "#CDE1D9"),
}

# Dark mode palette: high-contrast neon accents against glass surfaces
TONES_DARK: dict[str, tuple[str, str, str]] = {
    "green": ("rgba(0, 200, 150, 0.14)", "#00E5AC", "rgba(0, 200, 150, 0.32)"),
    "red": ("rgba(255, 99, 99, 0.14)", "#FF7B72", "rgba(255, 99, 99, 0.32)"),
    "orange": ("rgba(255, 166, 0, 0.14)", "#FFA657", "rgba(255, 166, 0, 0.32)"),
    "yellow": ("rgba(242, 204, 96, 0.14)", "#F2CC60", "rgba(242, 204, 96, 0.32)"),
    "blue": ("rgba(88, 166, 255, 0.14)", "#79C0FF", "rgba(88, 166, 255, 0.32)"),
    "violet": ("rgba(188, 140, 255, 0.14)", "#D2A8FF", "rgba(188, 140, 255, 0.32)"),
    "gray": ("rgba(255, 255, 255, 0.06)", "#8B949E", "rgba(255, 255, 255, 0.12)"),
    "grey": ("rgba(255, 255, 255, 0.06)", "#8B949E", "rgba(255, 255, 255, 0.12)"),
    "primary": ("rgba(0, 200, 150, 0.16)", "#00C896", "rgba(0, 200, 150, 0.38)"),
}


class _DynamicTones(dict):
    """Dictionary that dynamically resolves color tokens based on the active theme."""

    def __getitem__(self, key: str) -> tuple[str, str, str]:
        tones = TONES_DARK if _is_dark_mode() else TONES_LIGHT
        return tones.get(key, tones["gray"])

    def get(self, key: str, default: Any = None) -> Any:
        tones = TONES_DARK if _is_dark_mode() else TONES_LIGHT
        if key in tones:
            return tones[key]
        return tones["gray"] if default is None else default

    def __iter__(self):
        tones = TONES_DARK if _is_dark_mode() else TONES_LIGHT
        return iter(tones)

    def __len__(self) -> int:
        return len(TONES_DARK)

    def items(self):
        tones = TONES_DARK if _is_dark_mode() else TONES_LIGHT
        return tones.items()

    def values(self):
        tones = TONES_DARK if _is_dark_mode() else TONES_LIGHT
        return tones.values()

    def keys(self):
        tones = TONES_DARK if _is_dark_mode() else TONES_LIGHT
        return tones.keys()


# Backward-compatible global dictionary that works seamlessly in both themes
TONES: dict[str, tuple[str, str, str]] = _DynamicTones(TONES_DARK)

_STAT_ACCENT_TONES = {
    "pw-accent": "primary",
    "pw-accent-amber": "orange",
    "pw-accent-red": "red",
    "pw-accent-violet": "violet",
}

_CALLOUTS = {
    "info": ("gray", "info"),
    "success": ("green", "circle-check"),
    "warning": ("orange", "alert-triangle"),
    "error": ("red", "alert-circle"),
}

# Lucide icon geometry (ISC licence), 24 x 24 grid.
ICON_PATHS: dict[str, str] = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    "zap": '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "flag": '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>',
    "alert-triangle": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
                      '<path d="M12 9v4"/><path d="M12 17h.01"/>',
    "alert-circle": '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "circle-check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "layers": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 '
             '6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>'
           '<path d="M15 2v2M9 2v2M15 20v2M9 20v2M2 15h2M2 9h2M20 15h2M20 9h2"/>',
    "hash": '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
}


def _tone(name: str) -> tuple[str, str, str]:
    """Return (background, foreground, border) for a named color tone in current mode."""
    tones = TONES_DARK if _is_dark_mode() else TONES_LIGHT
    return tones.get(name, tones["gray"])


def _glow(name: str) -> str:
    """Return color-matched soft neon glow (box-shadow) for badges and accents."""
    dark = _is_dark_mode()
    if dark:
        glows = {
            "green": "0 0 10px rgba(0, 200, 150, 0.35), inset 0 0 4px rgba(0, 200, 150, 0.15)",
            "primary": "0 0 10px rgba(0, 200, 150, 0.35), inset 0 0 4px rgba(0, 200, 150, 0.15)",
            "red": "0 0 10px rgba(255, 99, 99, 0.35), inset 0 0 4px rgba(255, 99, 99, 0.15)",
            "orange": "0 0 10px rgba(255, 166, 0, 0.35), inset 0 0 4px rgba(255, 166, 0, 0.15)",
            "yellow": "0 0 10px rgba(242, 204, 96, 0.35), inset 0 0 4px rgba(242, 204, 96, 0.15)",
            "blue": "0 0 10px rgba(88, 166, 255, 0.35), inset 0 0 4px rgba(88, 166, 255, 0.15)",
            "violet": "0 0 10px rgba(188, 140, 255, 0.35), inset 0 0 4px rgba(188, 140, 255, 0.15)",
            "gray": "0 0 6px rgba(255, 255, 255, 0.08)",
            "grey": "0 0 6px rgba(255, 255, 255, 0.08)",
        }
    else:
        glows = {
            "green": "0 1px 3px rgba(21, 107, 69, 0.12)",
            "primary": "0 1px 3px rgba(11, 107, 87, 0.12)",
            "red": "0 1px 3px rgba(161, 42, 31, 0.12)",
            "orange": "0 1px 3px rgba(146, 74, 16, 0.12)",
            "yellow": "0 1px 3px rgba(107, 83, 4, 0.12)",
            "blue": "0 1px 3px rgba(31, 78, 140, 0.12)",
            "violet": "0 1px 3px rgba(89, 52, 160, 0.12)",
            "gray": "0 1px 2px rgba(16, 24, 22, 0.04)",
            "grey": "0 1px 2px rgba(16, 24, 22, 0.04)",
        }
    return glows.get(name, glows["gray"])


# ---------------------------------------------------------------------------
# CSS Generator
# ---------------------------------------------------------------------------

def _build_theme_css(dark: bool = False) -> str:
    """Generate a single, polished light theme for the whole app."""
    # Active root CSS variables
    root_vars = """
  --pw-ink: #16201D;
  --pw-ink-2: #3A4643;
  --pw-muted: #6A7471;
  --pw-faint: #9AA29F;

  --pw-canvas: #F4F7F5;
  --pw-surface: #FFFFFF;
  --pw-surface-solid: #FFFFFF;
  --pw-subtle: #EEF2EF;
  --pw-table-hover: #F8FAF9;

  --pw-line: #E2E6E2;
  --pw-line-strong: #D0D6D1;

  --pw-brand: #0B6B57;
  --pw-brand-hover: #084F40;
  --pw-brand-subtle: #E6F3EE;
  --pw-brand-glow: 0 0 12px rgba(11, 107, 87, 0.2);

  --pw-radius-sm: 6px;
  --pw-radius: 10px;
  --pw-radius-lg: 12px;
  --pw-shadow: 0 1px 3px rgba(16, 24, 22, 0.05), 0 4px 12px rgba(16, 24, 22, 0.03);
  --pw-glass-blur: none;
  --pw-sidebar-bg: #FFFFFF;
  --pw-btn-primary-text: #FFFFFF;
"""

    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@600;700;800&display=swap');

:root {{
{root_vars}
  --pw-font: "Inter", ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --pw-font-heading: "Outfit", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --pw-font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}}

/* ---------- Smooth transitions & base reset ---------- */
*, *::before, *::after {{
  box-sizing: border-box;
  transition: background-color 0.22s ease, border-color 0.22s ease, color 0.22s ease, box-shadow 0.22s ease;
}}

html, body, .stApp, .stMarkdown, input, textarea, select, button {{
  font-family: var(--pw-font);
  font-feature-settings: "cv11", "ss01";
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}}

.stApp {{
  background: var(--pw-canvas) !important;
  color: var(--pw-ink) !important;
}}

.block-container {{
  max-width: 1320px;
  padding-top: 2.1rem;
  padding-bottom: 5rem;
}}

header[data-testid="stHeader"] {{
  background: transparent !important;
}}

.stAppDeployButton, footer {{
  display: none !important;
}}

p {{
  color: var(--pw-ink-2);
}}

/* ---------- Headings ---------- */
h1, h2, h3, h4, .pw-title, .pw-section-title, .pw-form-title, .pw-stat-value {{
  font-family: var(--pw-font-heading);
}}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {{
  background: var(--pw-sidebar-bg) !important;
  border-right: 1px solid var(--pw-line) !important;
  width: 320px !important;
  min-width: 280px !important;
}}

section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
  width: 100%;
  overflow-wrap: anywhere;
}}

section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] .stHeader {{
  overflow-wrap: anywhere;
}}

[data-testid="stSidebarNav"] {{
  padding-top: 12px;
}}

[data-testid="stSidebarNavLink"] svg {{
  color: var(--pw-muted);
  transition: color 0.2s ease;
}}

[data-testid="stSidebarNavLink"] {{
  border-radius: var(--pw-radius-sm);
  margin: 2px 10px;
  padding: 7px 12px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}}

[data-testid="stSidebarNavLink"]:hover {{
  background: var(--pw-subtle) !important;
  border-color: var(--pw-line);
}}

[data-testid="stSidebarNavLink"][aria-current="page"] {{
  background: var(--pw-brand-subtle) !important;
  border-color: rgba(0, 200, 150, 0.25);
}}

[data-testid="stSidebarNavLink"][aria-current="page"] span {{
  color: var(--pw-brand) !important;
  font-weight: 600;
}}

[data-testid="stSidebarNavLink"][aria-current="page"] svg {{
  color: var(--pw-brand) !important;
}}

/* ---------- Page header & sections ---------- */
.pw-header {{
  padding: 4px 0 22px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--pw-line);
}}

.pw-eyebrow {{
  color: var(--pw-brand);
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 6px;
}}

.pw-title {{
  color: var(--pw-ink);
  font-size: 28px;
  font-weight: 750;
  letter-spacing: -0.025em;
  line-height: 1.2;
}}

.pw-subtitle {{
  color: var(--pw-muted);
  font-size: 14.5px;
  line-height: 1.55;
  margin-top: 6px;
  max-width: 780px;
}}

.pw-runtime-status {{
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--pw-muted);
  font-size: 11.5px;
  margin: 14px 10px 4px;
}}

.pw-runtime-status span {{
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
  box-shadow: 0 0 6px currentColor;
}}

.pw-runtime-status small {{
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: .75;
  margin-left: auto;
  max-width: 110px;
}}

.pw-section {{
  margin: 28px 0 12px;
}}

.pw-section-title {{
  color: var(--pw-ink);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
}}

.pw-section-caption {{
  color: var(--pw-muted);
  font-size: 13px;
  margin-top: 2px;
  line-height: 1.5;
}}

.pw-subheading {{
  color: var(--pw-ink-2);
  font-size: 13px;
  font-weight: 600;
  margin: 18px 0 8px;
}}

/* ---------- Text utilities ---------- */
.pw-strong {{ color: var(--pw-ink); font-weight: 600; }}
.pw-text {{ color: var(--pw-ink-2); }}
.pw-muted {{ color: var(--pw-muted); }}
.pw-mono {{ font-family: var(--pw-font-mono); font-size: 12.5px; }}
.pw-num {{ font-variant-numeric: tabular-nums; }}
.pw-icon {{ flex: none; display: inline-block; vertical-align: middle; }}

/* ---------- Badges with neon glow ---------- */
.pw-row {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 4px 0 8px;
}}

.pw-row-meta {{
  color: var(--pw-muted);
  font-size: 13px;
  margin-left: 4px;
}}

.pw-badge {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 24px;
  padding: 0 10px;
  border: 1px solid;
  border-radius: var(--pw-radius-sm);
  font-size: 12px;
  font-weight: 550;
  line-height: 1;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  cursor: default;
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), filter 0.2s ease, box-shadow 0.2s ease;
}}

.pw-badge:hover {{
  transform: translateY(-1px);
  filter: brightness(1.1);
}}

/* ---------- Stat cards with animated gradient hover glow ---------- */
.pw-stat {{
  display: flex;
  flex-direction: column;
  min-height: 118px;
  height: 100%;
  padding: 16px 18px;
  background: var(--pw-surface);
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
  border: 1px solid var(--pw-line);
  border-radius: var(--pw-radius-lg);
  box-shadow: var(--pw-shadow);
  position: relative;
  overflow: hidden;
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s ease;
}}

.pw-stat::before {{
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--pw-brand), transparent);
  transition: left 0.6s ease;
}}

.pw-stat:hover {{
  transform: translateY(-3px);
  border-color: rgba(0, 200, 150, 0.45);
  box-shadow: 0 8px 30px rgba(0, 200, 150, 0.16), 0 0 20px rgba(0, 200, 150, 0.22);
}}

.pw-stat:hover::before {{
  left: 100%;
}}

.pw-stat-label {{
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--pw-muted);
  font-size: 13px;
  font-weight: 500;
  min-height: 36px;
}}

.pw-stat-icon {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--pw-radius-sm);
}}

.pw-stat-value {{
  color: var(--pw-ink);
  font-size: 30px;
  font-weight: 750;
  letter-spacing: -0.03em;
  line-height: 1.1;
  margin-top: 10px;
  font-variant-numeric: tabular-nums;
}}

.pw-stat-hint {{
  color: var(--pw-muted);
  font-size: 12.5px;
  line-height: 1.45;
  margin-top: auto;
  padding-top: 10px;
}}

/* ---------- Key / value grid ---------- */
.pw-kv {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 14px 24px;
  margin: 4px 0 0;
  padding: 16px 20px;
  background: var(--pw-surface);
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
  border: 1px solid var(--pw-line);
  border-radius: var(--pw-radius-lg);
  box-shadow: var(--pw-shadow);
}}

.pw-kv dt {{
  color: var(--pw-muted);
  font-size: 12px;
  font-weight: 500;
  margin: 0 0 3px;
}}

.pw-kv dd {{
  color: var(--pw-ink);
  font-size: 14px;
  margin: 0;
  line-height: 1.45;
  word-break: break-word;
}}

/* ---------- Callouts & empty states ---------- */
.pw-callout {{
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 16px;
  margin: 10px 0;
  border: 1px solid;
  border-radius: var(--pw-radius);
  font-size: 14px;
  line-height: 1.5;
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
}}

.pw-callout .pw-icon {{
  margin-top: 2px;
}}

.pw-callout-title {{
  color: var(--pw-ink);
  font-weight: 600;
  margin-bottom: 2px;
}}

.pw-callout-body {{
  color: var(--pw-ink-2);
}}

.pw-empty {{
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 48px 24px;
  margin: 8px 0;
  background: var(--pw-surface);
  border: 1px dashed var(--pw-line-strong);
  border-radius: var(--pw-radius-lg);
}}

.pw-empty-icon {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--pw-radius);
  background: var(--pw-subtle);
  color: var(--pw-muted);
}}

.pw-empty-title {{
  color: var(--pw-ink);
  font-size: 16px;
  font-weight: 600;
  margin-top: 14px;
}}

.pw-empty-body {{
  color: var(--pw-muted);
  font-size: 13.5px;
  margin-top: 4px;
  max-width: 440px;
  line-height: 1.5;
}}

/* ---------- Tables: sticky header & hover row highlight ---------- */
.pw-table-wrap {{
  width: 100%;
  overflow-x: auto;
  max-height: 600px;
  background: var(--pw-surface);
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
  border: 1px solid var(--pw-line);
  border-radius: var(--pw-radius-lg);
  box-shadow: var(--pw-shadow);
  position: relative;
}}

table.pw-table {{
  width: 100%;
  min-width: 620px;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 14px;
}}

table.pw-table thead {{
  position: sticky;
  top: 0;
  z-index: 10;
}}

table.pw-table th {{
  padding: 12px 16px;
  background: var(--pw-subtle);
  color: var(--pw-muted);
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  text-align: left;
  white-space: nowrap;
  border-bottom: 1px solid var(--pw-line);
  position: sticky;
  top: 0;
  z-index: 10;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}}

table.pw-table td {{
  padding: 13px 16px;
  color: var(--pw-ink);
  line-height: 1.5;
  vertical-align: top;
  border-top: 1px solid var(--pw-line);
  transition: background 0.15s ease;
}}

table.pw-table tbody tr:first-child td {{
  border-top: none;
}}

table.pw-table tbody tr {{
  transition: background-color 0.15s ease;
}}

table.pw-table tbody tr:hover {{
  background: var(--pw-table-hover);
}}

/* ---------- Documents & sentences ---------- */
.pw-doc-head {{
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--pw-muted);
  margin-bottom: 4px;
}}

.pw-doc-title {{
  color: var(--pw-ink);
  font-size: 14.5px;
  font-weight: 600;
}}

.pw-doc-count {{
  margin-left: auto;
  color: var(--pw-muted);
  font-size: 12.5px;
}}

.pw-sentence {{
  padding: 14px 16px;
  margin: 8px 0;
  background: var(--pw-surface);
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
  border: 1px solid var(--pw-line);
  border-left: 3px solid var(--pw-line-strong);
  border-radius: var(--pw-radius);
}}

.pw-sentence.pw-flagged {{
  background: rgba(255, 99, 99, 0.08);
  border-color: rgba(255, 99, 99, 0.28);
  border-left-color: #FF6B6B;
}}

.pw-sentence-top {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}}

.pw-sentence-text {{
  color: var(--pw-ink);
  font-size: 14px;
  line-height: 1.6;
}}

.pw-sentence-meta {{
  color: var(--pw-muted);
  font-size: 12.5px;
  margin-top: 8px;
  line-height: 1.45;
}}

/* ---------- Notices ---------- */
.pw-notice {{
  padding: 14px 18px;
  background: var(--pw-surface);
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
  border: 1px solid var(--pw-line);
  border-radius: var(--pw-radius);
  color: var(--pw-ink);
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
}}

/* ---------- Brand mark ---------- */
.pw-brandmark {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--pw-brand);
  color: var(--pw-btn-primary-text);
  border-radius: 9px;
  box-shadow: 0 0 12px rgba(0, 200, 150, 0.35);
}}

.pw-signin-brand {{
  display: flex;
  align-items: center;
  gap: 13px;
  margin-bottom: 30px;
}}

.pw-signin-name {{
  color: var(--pw-ink);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
}}

.pw-signin-sub {{
  color: var(--pw-muted);
  font-size: 13px;
  margin-top: 2px;
}}

.pw-form-title {{
  color: var(--pw-ink);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.025em;
}}

.pw-form-caption {{
  color: var(--pw-muted);
  font-size: 14px;
  margin: 4px 0 8px;
}}

.pw-footnote {{
  color: var(--pw-faint);
  font-size: 12.5px;
  line-height: 1.5;
  text-align: center;
  margin-top: 20px;
}}

/* ---------- Chat bubbles & assistant cards ---------- */
.pw-chat-turn {{
  margin-bottom: 18px;
}}

.pw-chat-user {{
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  align-items: flex-end;
  margin: 10px 0;
}}

.pw-chat-user-bubble {{
  background: linear-gradient(135deg, #00C896 0%, #009E77 100%);
  color: #061B14;
  font-weight: 500;
  border-radius: 20px 20px 4px 20px;
  padding: 11px 18px;
  max-width: 72%;
  font-size: 14px;
  line-height: 1.55;
  box-shadow: 0 4px 14px rgba(0, 200, 150, 0.28);
}}

.pw-chat-assistant {{
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin: 10px 0;
}}

.pw-chat-avatar {{
  width: 36px;
  height: 36px;
  border-radius: 11px;
  background: linear-gradient(135deg, #00C896, #008765);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #051912;
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 0 12px rgba(0, 200, 150, 0.4);
}}

.pw-chat-assistant-bubble {{
  background: var(--pw-surface);
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
  border: 1px solid var(--pw-line);
  border-radius: 4px 20px 20px 20px;
  padding: 16px 20px;
  max-width: 76%;
  font-size: 14px;
  line-height: 1.65;
  box-shadow: var(--pw-shadow);
}}

.pw-chat-assistant-bubble p {{
  margin: 0 0 8px;
  color: var(--pw-ink);
}}

.pw-chat-assistant-bubble p:last-child {{
  margin-bottom: 0;
}}

.pw-chat-assistant-bubble strong {{
  color: var(--pw-ink);
  font-weight: 600;
}}

.pw-chat-assistant-bubble code {{
  font-family: var(--pw-font-mono);
  font-size: 12.5px;
  background: var(--pw-subtle);
  border-radius: 4px;
  padding: 2px 6px;
  color: var(--pw-brand);
}}

div[data-testid="stChatMessage"] {{
  background: var(--pw-surface);
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
  border: 1px solid var(--pw-line);
  border-radius: var(--pw-radius-lg);
  padding: 14px 18px;
  box-shadow: var(--pw-shadow);
}}

/* ---------- SHAP explanation cards ---------- */
.pw-shap-panel {{
  background: rgba(11, 107, 87, 0.02);
  border: 1px solid var(--pw-line);
  border-radius: 14px;
  padding: 14px 16px 12px;
  margin-top: 4px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
}}

.pw-shap-row {{
  display: grid;
  grid-template-columns: minmax(150px, 190px) minmax(180px, 1fr) 72px 92px;
  align-items: center;
  gap: 10px;
  min-height: 38px;
  padding: 7px 0;
  border-bottom: 1px solid rgba(11, 107, 87, 0.06);
}}

.pw-shap-row:last-child {{
  border-bottom: none;
}}

.pw-shap-name {{
  color: var(--pw-ink-2);
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

.pw-shap-bar-wrap {{
  position: relative;
  width: 100%;
  height: 12px;
  border-radius: 999px;
  background: rgba(16, 24, 22, 0.06);
  overflow: hidden;
  border: 1px solid rgba(16, 24, 22, 0.03);
}}

.pw-shap-bar {{
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 999px;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.25);
}}

.pw-shap-amount {{
  font-family: var(--pw-font-mono);
  font-size: 11.5px;
  font-weight: 600;
  text-align: right;
}}

.pw-shap-actual {{
  color: var(--pw-muted);
  font-size: 11px;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

@media (max-width: 780px) {{
  .pw-shap-row {{
    grid-template-columns: minmax(120px, 150px) minmax(120px, 1fr) 60px 72px;
    gap: 8px;
  }}
}}

/* ---------- API Health Sidebar Panel ---------- */
.pw-api-health-panel {{
  background: linear-gradient(180deg, #ffffff 0%, #f9fbfa 100%);
  border: 1px solid var(--pw-line);
  border-radius: 12px;
  padding: 12px 12px 10px;
  margin: 10px 0 14px;
  box-shadow: 0 6px 18px rgba(11, 107, 87, 0.04), inset 0 1px 0 rgba(255,255,255,0.8);
}}

.pw-api-health-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--pw-line);
  gap: 8px;
}}

.pw-api-health-title {{
  font-size: 11.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--pw-ink);
}}

.pw-api-health-badge {{
  font-size: 10.5px;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--pw-brand-subtle);
  color: var(--pw-brand);
  border: 1px solid rgba(11, 107, 87, 0.18);
  font-weight: 700;
  white-space: nowrap;
}}

.pw-api-keys-list {{
  display: flex;
  flex-direction: column;
  gap: 6px;
}}

.pw-api-key-row {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  border-radius: 8px;
  min-height: 28px;
  background: rgba(15, 23, 42, 0.01);
  border: 1px solid transparent;
}}

.pw-api-key-row:hover {{
  background: rgba(11, 107, 87, 0.03);
  border-color: rgba(11, 107, 87, 0.08);
}}

.pw-api-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-block;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.65);
}}

.pw-api-key-name {{
  color: var(--pw-ink-2);
  font-family: var(--pw-font-mono);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}}

.pw-api-key-meta {{
  margin-left: auto;
  color: var(--pw-muted);
  font-size: 10.5px;
  white-space: nowrap;
  opacity: 0.9;
}}

/* ---------- Streamlit UI refinements ---------- */
.stTabs [data-baseweb="tab-list"] {{
  gap: 20px;
  border-bottom: 1px solid var(--pw-line);
  background: transparent;
}}

.stTabs [data-baseweb="tab"] {{
  padding: 10px 4px;
  font-size: 14px;
  font-weight: 500;
  color: var(--pw-muted);
  border-bottom: 2px solid transparent;
}}

.stTabs [data-baseweb="tab"]:hover {{
  color: var(--pw-ink);
}}

.stTabs [aria-selected="true"] {{
  color: var(--pw-brand) !important;
  border-bottom: 2px solid var(--pw-brand) !important;
  font-weight: 600;
}}

div[data-testid="stForm"] {{
  padding: 22px;
  background: var(--pw-surface);
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
  border: 1px solid var(--pw-line);
  border-radius: var(--pw-radius-lg);
  box-shadow: var(--pw-shadow);
}}

div[data-testid="stVerticalBlockBorderWrapper"] {{
  border-color: var(--pw-line) !important;
  border-radius: var(--pw-radius-lg) !important;
}}

div[data-testid="stExpander"] details {{
  background: var(--pw-surface);
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
  border: 1px solid var(--pw-line);
  border-radius: var(--pw-radius-lg);
}}

div[data-testid="stExpander"] summary {{
  font-size: 14px;
  font-weight: 500;
  color: var(--pw-ink);
}}

/* Buttons */
.stButton > button, .stFormSubmitButton > button {{
  min-height: 38px;
  border-radius: 8px;
  font-weight: 550;
  font-size: 14px;
  box-shadow: none;
}}

.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"],
button[data-testid^="stBaseButton-primary"] {{
  background: var(--pw-brand) !important;
  border: 1px solid var(--pw-brand) !important;
  color: var(--pw-btn-primary-text) !important;
  -webkit-text-fill-color: var(--pw-btn-primary-text) !important;
  box-shadow: var(--pw-brand-glow) !important;
}}

.stButton > button[kind="primary"] *, .stFormSubmitButton > button[kind="primary"] *,
button[data-testid^="stBaseButton-primary"] * {{
  color: var(--pw-btn-primary-text) !important;
  fill: var(--pw-btn-primary-text) !important;
  -webkit-text-fill-color: var(--pw-btn-primary-text) !important;
}}

.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover,
button[data-testid^="stBaseButton-primary"]:hover {{
  background: var(--pw-brand-hover) !important;
  border-color: var(--pw-brand-hover) !important;
  transform: translateY(-1px);
}}

.stButton > button[kind="secondary"], .stFormSubmitButton > button[kind="secondary"] {{
  background: var(--pw-surface) !important;
  border: 1px solid var(--pw-line-strong) !important;
  color: var(--pw-ink) !important;
}}

.stButton > button[kind="secondary"] *, .stFormSubmitButton > button[kind="secondary"] * {{
  color: var(--pw-ink) !important;
}}

.stButton > button[kind="secondary"]:hover, .stFormSubmitButton > button[kind="secondary"]:hover {{
  border-color: var(--pw-brand) !important;
  color: var(--pw-brand) !important;
}}

.stButton > button:disabled, .stFormSubmitButton > button:disabled {{
  opacity: .5;
  cursor: not-allowed;
}}

[data-testid="stWidgetLabel"] p {{
  color: var(--pw-ink-2);
  font-size: 13px;
  font-weight: 500;
}}

[data-testid="stDataFrame"] {{
  border: 1px solid var(--pw-line);
  border-radius: var(--pw-radius-lg);
  overflow: hidden;
  background: var(--pw-surface);
}}

.stSegmentedControl {{
  background: var(--pw-surface);
  border-radius: var(--pw-radius);
  padding: 3px;
}}

.stSegmentedControl [aria-checked="true"] {{
  background: var(--pw-brand-subtle);
  color: var(--pw-brand);
}}

.stProgress > div > div > div > div {{
  background: var(--pw-brand);
}}

button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible, a:focus-visible {{
  outline: 2px solid var(--pw-brand) !important;
  outline-offset: 2px !important;
}}

/* Sign-in shell */
.st-key-pw_signin_shell {{
  max-width: 500px;
  margin: 0 auto;
  padding: 36px 40px 30px;
  background: var(--pw-surface);
  backdrop-filter: var(--pw-glass-blur);
  -webkit-backdrop-filter: var(--pw-glass-blur);
  border: 1px solid var(--pw-line);
  border-radius: 18px;
  box-shadow: 0 18px 48px rgba(0, 0, 0, .28);
}}

.stHorizontalBlock:has(.st-key-pw_signin_shell) {{
  justify-content: center;
}}

.stHorizontalBlock:has(.st-key-pw_signin_shell) > .stColumn:not(:has(.st-key-pw_signin_shell)) {{
  display: none;
}}

.stHorizontalBlock:has(.st-key-pw_signin_shell) > .stColumn:has(.st-key-pw_signin_shell) {{
  flex: 0 1 500px !important;
  width: min(500px, 100%) !important;
}}

.st-key-pw_signin_shell div[data-testid="stForm"] {{
  padding: 0;
  background: transparent;
  border: 0;
  box-shadow: none;
  backdrop-filter: none;
}}

.st-key-pw_signin_shell .stTextInput input {{
  min-height: 48px;
  border-radius: 9px;
  background: var(--pw-subtle);
  border-color: var(--pw-line-strong);
  color: var(--pw-ink);
}}

.st-key-pw_signin_shell [data-testid="stFormSubmitButton"] button {{
  min-height: 48px;
  margin-top: 8px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: .01em;
}}

/* Media queries */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }}
}}

@media (max-width: 768px) {{
  .block-container {{ padding: 1.25rem 1rem 3rem; }}
  .pw-title {{ font-size: 22px; }}
  .pw-stat-value {{ font-size: 24px; }}
  .pw-doc-count {{ margin-left: 0; }}
}}

</style>"""

# ---------------------------------------------------------------------------
# Public UI helpers used across the dashboard
# ---------------------------------------------------------------------------

def inject_theme() -> None:
    """Inject the single light theme CSS into the page."""
    st.markdown(_build_theme_css(dark=False), unsafe_allow_html=True)


def escape(value: Any) -> str:
    """Escape HTML-sensitive text before inserting it into markup."""
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def _svg_icon(path: str, size: int = 18, color: str | None = None, classes: str = "") -> str:
    """Build a small inline SVG icon for use inside HTML fragments."""
    stroke = f' stroke="{color}"' if color else ' stroke="currentColor"'
    return (
        f'<svg class="{classes}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none"{stroke} stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
        f'{path}</svg>'
    )


def icon(name: str, size: int = 18, color: str | None = None) -> str:
    """Return the requested Lucide icon as inline SVG."""
    path = ICON_PATHS.get(name, ICON_PATHS["help"])
    return _svg_icon(path, size=size, color=color)


def brand_mark(size: int = 30) -> str:
    """Return the PhaseWise brand mark."""
    return (
        f'<div class="pw-brandmark" style="width:{size}px;height:{size}px;">'
        f'{icon("zap", max(12, size - 12), color="#FFFFFF")}</div>'
    )


def mono(value: Any) -> str:
    """Render a monospace label."""
    return f'<span class="pw-mono pw-num">{escape(value)}</span>'


def muted(value: Any) -> str:
    """Render a muted text snippet."""
    return f'<span class="pw-muted">{escape(value)}</span>'


def strong(value: Any) -> str:
    """Render a strong text snippet."""
    return f'<span class="pw-strong">{escape(value)}</span>'


def chat_type_colour(question_type: str | None) -> str:
    """Return badge tone for a chat question type."""
    type_name = (question_type or "CHAT").upper()
    palette = {
        "CHAT": "gray",
        "STANDARD": "green",
        "RULE": "blue",
        "REVIEW": "violet",
        "EVIDENCE": "orange",
        "RISK": "red",
    }
    return palette.get(type_name, "gray")


def badge_html(text: Any, tone: str = "gray", icon_name: str | None = None) -> str:
    """Return a styled badge with optional icon."""
    tone_name = tone if tone in TONES else "gray"
    bg, fg, border = _tone(tone_name)
    icon = f'{icon(icon_name, 12, fg)} ' if icon_name else ""
    return (
        f'<span class="pw-badge" style="background:{bg};color:{fg};border-color:{border};">'
        f'{icon}{escape(text)}</span>'
    )


def result_colour(result: str | None) -> str:
    """Return badge tone for a requirement result."""
    result_name = (result or "").strip().lower()
    if result_name in {"pass", "met", "ok", "yes", "true", "clear", "approved"}:
        return "green"
    if result_name in {"fail", "not met", "not", "no", "false", "rejected"}:
        return "red"
    if result_name in {"borderline", "review", "warning", "unclear"}:
        return "orange"
    return "gray"


def decision_colour(decision: str | None) -> str:
    """Return badge tone for a review decision."""
    decision_name = (decision or "").strip().lower()
    if decision_name in {"approve", "accept", "approved"}:
        return "green"
    if decision_name in {"return", "revise", "review"}:
        return "orange"
    if decision_name in {"refer", "reject", "refuse", "decline"}:
        return "red"
    return "gray"


def status_colour(status: str | None) -> str:
    """Return badge tone for generic status values."""
    status_name = (status or "").strip().lower()
    if status_name in {"healthy", "live", "ok", "pass", "completed"}:
        return "green"
    if status_name in {"warning", "cooldown", "pending", "review"}:
        return "orange"
    if status_name in {"failed", "error", "down", "blocked"}:
        return "red"
    return "gray"


def band_colour(band: str | None) -> str:
    """Return badge tone for a likelihood band."""
    band_name = (band or "").strip().lower()
    if band_name in {"high", "high risk", "critical"}:
        return "red"
    if band_name in {"medium", "moderate", "amber"}:
        return "orange"
    if band_name in {"low", "low risk", "green"}:
        return "green"
    return "gray"


def answer_label(column: str | None) -> str:
    """Turn a backend field name into a user-readable label."""
    if not column:
        return ""
    return column.replace("_", " ").title()


def format_amps(value: Any) -> str:
    """Format AMPS values in a stable display form."""
    if value in (None, ""):
        return "—"
    try:
        amount = float(value)
        return f"{amount:g}"
    except (TypeError, ValueError):
        return str(value)


def delay_badge(review: Mapping[str, Any]) -> str:
    """Return a small delay indication for a review."""
    value = review.get("delay_expected")
    if value is None:
        return badge_html("No plan", "gray")
    return badge_html("Delay expected" if value else "On time", "green" if not value else "orange")


def spacer(height: int = 8) -> None:
    """Add vertical spacing."""
    st.markdown(f'<div style="height:{height}px"></div>', unsafe_allow_html=True)


def section(title: str, subtitle: str | None = None) -> None:
    """Render a section heading with optional caption."""
    subtitle_html = f'<div class="pw-section-caption">{escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        '<div class="pw-section">'
        f'<div class="pw-section-title">{escape(title)}</div>'
        f'{subtitle_html}'
        '</div>',
        unsafe_allow_html=True,
    )


def subheading(title: str) -> None:
    """Render a smaller subheading inside a section."""
    st.markdown(f'<div class="pw-subheading">{escape(title)}</div>', unsafe_allow_html=True)


def page_header(title: str, subtitle: str | None = None) -> None:
    """Render the page header with optional subtitle."""
    subtitle_html = f'<div class="pw-subtitle">{escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        '<div class="pw-header">'
        f'<div class="pw-eyebrow">{escape(title)}</div>'
        f'<div class="pw-title">{escape(title)}</div>'
        f'{subtitle_html}'
        '</div>',
        unsafe_allow_html=True,
    )


def empty_state(title: str, body: str, icon_name: str = "inbox") -> None:
    """Render an empty-state panel."""
    st.markdown(
        f'<div class="pw-empty">'
        f'<div class="pw-empty-icon">{icon(icon_name, 18)}</div>'
        f'<div class="pw-empty-title">{escape(title)}</div>'
        f'<div class="pw-empty-body">{escape(body)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def notice_box(text: Any) -> None:
    """Render a neutral panel for informational text or instructions."""
    st.markdown(f'<div class="pw-notice">{escape(text)}</div>', unsafe_allow_html=True)


def callout(message: Any, tone: str = "info", title: str | None = None) -> None:
    """Render a compact callout."""
    tone_name = tone if tone in _CALLOUTS else "info"
    bg, icon_name = _CALLOUTS[tone_name]
    bg_color, fg, border = _tone(bg)
    title_html = f'<div class="pw-callout-title">{escape(title or "Note")}</div>' if title else ""
    body_html = f'<div class="pw-callout-body">{escape(message)}</div>'
    st.markdown(
        f'<div class="pw-callout" style="background:{bg_color};border-color:{border};">'
        f'{icon(icon_name, 16, fg)}'
        f'<div>{title_html}{body_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def stat_row(items: Sequence[Mapping[str, Any]]) -> None:
    """Render a row of dashboard stat cards with consistent sizing."""
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        label = item.get("label", "")
        value = item.get("value", "")
        hint = item.get("hint_html", "")
        accent = item.get("accent", "pw-accent")
        tone_name = item.get("tone") or accent
        if tone_name == "green":
            bg, fg, border = _tone("green")
        elif tone_name == "red":
            bg, fg, border = _tone("red")
        elif tone_name == "orange":
            bg, fg, border = _tone("orange")
        elif tone_name == "yellow":
            bg, fg, border = _tone("yellow")
        elif tone_name == "blue":
            bg, fg, border = _tone("blue")
        elif tone_name == "violet":
            bg, fg, border = _tone("violet")
        else:
            bg, fg, border = _tone("primary")

        with col:
            st.markdown(
                '<div class="pw-stat" style="background:linear-gradient(180deg,#ffffff 0%, #fcfdfd 100%);">'
                f'<div class="pw-stat-label"><span class="pw-stat-icon" style="background:{bg};color:{fg};border:1px solid {border};">{icon(item.get("icon", "activity"), 16, fg)}</span>{escape(label)}</div>'
                f'<div class="pw-stat-value">{escape(value)}</div>'
                f'<div class="pw-stat-hint>{hint}</div>'
                '</div>',
                unsafe_allow_html=True,
            )


def badge_row(items: Sequence[tuple[str, str]], meta: str | None = None) -> None:
    """Render a horizontal list of badges."""
    if not items:
        return
    rendered = "".join(badge_html(label, tone) for label, tone in items)
    block = f'<div class="pw-row">{rendered}</div>'
    if meta:
        block += f'<div class="pw-row-meta">{escape(meta)}</div>'
    st.markdown(block, unsafe_allow_html=True)


def html_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    """Render a simple HTML table with consistent styling."""
    if not rows:
        return
    header_html = "".join(f"<th>{escape(h)}</th>" for h in headers)
    row_html = []
    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        row_html.append(f"<tr>{cells}</tr>")
    st.markdown(
        '<div class="pw-table-wrap"><table class="pw-table"><thead><tr>'
        f'{header_html}</tr></thead><tbody>{"".join(row_html)}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def key_values(items: Sequence[tuple[str, Any]]) -> None:
    """Render a key-value definition list."""
    if not items:
        return
    html = "<dl class=\"pw-kv\">"
    for key, value in items:
        html += f"<dt>{escape(key)}</dt><dd>{value}</dd>"
    html += "</dl>"
    st.markdown(html, unsafe_allow_html=True)


def sentence_card(sentence: str, badges: str, meta: str, flagged: bool = False) -> None:
    """Render a sentence evidence card."""
    extra = " pw-flagged" if flagged else ""
    st.markdown(
        f'<div class="pw-sentence{extra}"><div class="pw-sentence-top">{badges}</div>'
        f'<div class="pw-sentence-text">{escape(sentence)}</div>'
        f'<div class="pw-sentence-meta">{escape(meta)}</div></div>',
        unsafe_allow_html=True,
    )


__all__ = [
    "_build_theme_css", "_CALLOUTS", "_is_dark_mode", "_tone", "_glow", "ICON_PATHS", "TONES",
    "TONES_LIGHT", "TONES_DARK", "inject_theme", "escape", "icon", "brand_mark", "mono", "muted",
    "strong", "chat_type_colour", "badge_html", "result_colour", "decision_colour", "status_colour",
    "band_colour", "answer_label", "format_amps", "delay_badge", "spacer", "section", "subheading",
    "page_header", "empty_state", "notice_box", "callout", "stat_row", "badge_row", "html_table",
    "key_values", "sentence_card",
]
