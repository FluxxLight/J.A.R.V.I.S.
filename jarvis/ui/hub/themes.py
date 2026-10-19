"""Design system do J.A.R.V.I.S. — tokens puros (sem Qt, 100% testável).

Toda decisão visual nasce aqui: temas, tipografia, espaçamentos, raios,
opacidades e o QSS gerado para o HUB. Os widgets Qt apenas consomem.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Tipografia / escala / espaçamento (design tokens)
# ---------------------------------------------------------------------------

FONT_UI = ["Segoe UI", "Inter", "Helvetica Neue", "Arial", "sans-serif"]
FONT_MONO = ["Cascadia Mono", "Consolas", "JetBrains Mono", "monospace"]

FONT_TITLE = 22
FONT_SECTION = 13
FONT_BODY = 11
FONT_SMALL = 9
FONT_MONO_BODY = 10

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 16

PANEL_OPACITY = 0.72        # painéis de vidro sobre o fundo
NUCLEUS_MIN = 220           # diâmetro mínimo do núcleo (px)
NUCLEUS_MAX = 420           # diâmetro máximo do núcleo (px)
PARTICLE_COUNT = 130        # pool fixo de partículas (performance)


# ---------------------------------------------------------------------------
# Temas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Theme:
    id: str            # azul | vermelho | verde | amarelo | cinza
    label: str         # "Azul Reator"
    primary: str       # cor principal (núcleo, HUD, glow, acentos)
    primary_soft: str  # variação translúcida para brilhos
    deep: str          # variação escura para gradientes
    secondary: str     # cor de apoio (textos de destaque, links)
    danger: str        # erros (sempre legível sobre o fundo)
    warning: str
    success: str
    background_top: str = "#04070d"
    background_bottom: str = "#0a1220"
    panel: str = "#0b1420"
    panel_border: str = "#1c2c40"
    text: str = "#e9f2fa"
    text_dim: str = "#8fa3b8"
    text_faint: str = "#54687d"


THEMES: dict[str, Theme] = {
    "azul": Theme(
        id="azul", label="Azul Reator",
        primary="#35c4ff", primary_soft="#35c4ff55", deep="#0a4d80",
        secondary="#7dd8ff", danger="#ff5d5d", warning="#ffc44d",
        success="#3ddc84",
    ),
    "vermelho": Theme(
        id="vermelho", label="Vermelho Alerta",
        primary="#ff4d5e", primary_soft="#ff4d5e55", deep="#7d0f1c",
        secondary="#ff8f98", danger="#ff5d5d", warning="#ffc44d",
        success="#3ddc84",
    ),
    "verde": Theme(
        id="verde", label="Verde Matriz",
        primary="#3dffa0", primary_soft="#3dffa055", deep="#0a5c3a",
        secondary="#8affc4", danger="#ff5d5d", warning="#ffc44d",
        success="#3ddc84",
    ),
    "amarelo": Theme(
        id="amarelo", label="Amarelo Pulso",
        primary="#ffd23d", primary_soft="#ffd23d55", deep="#7a5a06",
        secondary="#ffe38a", danger="#ff5d5d", warning="#ff9d3d",
        success="#3ddc84",
    ),
    "cinza": Theme(
        id="cinza", label="Cinza Fantasma",
        primary="#b9c6d4", primary_soft="#b9c6d455", deep="#49525e",
        secondary="#dde6ef", danger="#ff5d5d", warning="#ffc44d",
        success="#3ddc84",
    ),
}

THEME_ORDER = ("azul", "vermelho", "verde", "amarelo", "cinza")


def get_theme(theme_id: str) -> Theme:
    """Devolve o tema (fallback determinístico para 'azul')."""
    return THEMES.get((theme_id or "").strip().lower(), THEMES["azul"])


def cycle_theme(theme_id: str) -> str:
    """Próximo tema na ordem (para atalho de teclado)."""
    current = get_theme(theme_id).id
    idx = THEME_ORDER.index(current)
    return THEME_ORDER[(idx + 1) % len(THEME_ORDER)]


# ---------------------------------------------------------------------------
# Estados -> apresentação (labels PT-BR + papel de cor)
# ---------------------------------------------------------------------------

STATE_STYLE: dict[str, dict[str, str]] = {
    # role: primary | success | warning | danger | dim
    "STARTING": {"label": "INICIANDO", "role": "primary"},
    "IDLE": {"label": "EM ESPERA", "role": "dim"},
    "LISTENING": {"label": "OUVINDO", "role": "primary"},
    "PROCESSING": {"label": "PROCESSANDO", "role": "primary"},
    "EXECUTING": {"label": "EXECUTANDO", "role": "warning"},
    "SPEAKING": {"label": "FALANDO", "role": "success"},
    "READY": {"label": "PRONTO", "role": "success"},
    "ERROR": {"label": "ERRO", "role": "danger"},
    "SHUTDOWN": {"label": "ENCERRANDO", "role": "dim"},
}


def state_label(state: str) -> str:
    return STATE_STYLE.get(state, {"label": state})["label"]


def role_color(theme: Theme, role: str) -> str:
    return {
        "primary": theme.primary,
        "success": theme.success,
        "warning": theme.warning,
        "danger": theme.danger,
        "dim": theme.text_dim,
    }.get(role, theme.text)


def state_color(theme: Theme, state: str) -> str:
    role = STATE_STYLE.get(state, {"role": "dim"})["role"]
    return role_color(theme, role)


# ---------------------------------------------------------------------------
# Resultado de comando -> feedback (sempre fiel ao EngineResult real)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeedbackView:
    title: str       # ex.: "ABRIR NAVEGADOR"
    status: str      # "CONCLUÍDO" | "ERRO" | "AGUARDANDO CONFIRMAÇÃO" | ...
    role: str        # success | danger | warning | primary | dim
    detail: str


def feedback_for(intent: str, success: bool, executed: bool,
                 needs_confirmation: bool, message: str) -> FeedbackView:
    """Mapeia o resultado REAL do engine para o cartão de feedback do HUB."""
    title = (intent or "—").replace("_", " ") if intent != "UNKNOWN" else "NÃO RECONHECIDO"
    if needs_confirmation:
        return FeedbackView(title, "AGUARDANDO CONFIRMAÇÃO", "warning", message)
    if executed and success:
        return FeedbackView(title, "CONCLUÍDO", "success", message)
    if executed and not success:
        return FeedbackView(title, "ERRO", "danger", message)
    if success:  # ex.: "Cancelado."
        return FeedbackView(title, "CONCLUÍDO", "success", message)
    return FeedbackView(title, "NÃO EXECUTADO", "dim", message)


# ---------------------------------------------------------------------------
# QSS (Qt Style Sheets) gerado a partir do tema
# ---------------------------------------------------------------------------

def _font_stack(names: list[str]) -> str:
    return ", ".join(f'"{n}"' for n in names)


def build_stylesheet(theme: Theme) -> str:
    """Gera o QSS completo do HUB para um tema. Determinístico."""
    ui_font = _font_stack(FONT_UI)
    mono_font = _font_stack(FONT_MONO)
    return f"""
* {{ font-family: {ui_font}; }}
QMainWindow, QDialog, QWidget#root {{
    background-color: {theme.background_top};
    color: {theme.text};
}}
QLabel {{ color: {theme.text}; }}
QFrame#panel {{
    background-color: rgba(11, 20, 32, 225);
    border: 1px solid {theme.panel_border};
    border-radius: {RADIUS_MD}px;
}}
QFrame#panelAccent {{
    background-color: rgba(11, 20, 32, 235);
    border: 1px solid {theme.primary};
    border-radius: {RADIUS_MD}px;
}}
QLabel#title {{
    color: {theme.text}; font-size: {FONT_TITLE}px; font-weight: 800;
    letter-spacing: 3px;
}}
QLabel#subtitle {{
    color: {theme.secondary}; font-size: {FONT_SMALL}px; font-weight: 600;
    letter-spacing: 4px;
}}
QLabel#section {{
    color: {theme.primary}; font-size: {FONT_SECTION}px; font-weight: 700;
    letter-spacing: 2px;
}}
QLabel#body {{ color: {theme.text}; font-size: {FONT_BODY}px; }}
QLabel#dim {{ color: {theme.text_dim}; font-size: {FONT_SMALL}px; }}
QLabel#mono {{
    font-family: {mono_font}; font-size: {FONT_MONO_BODY}px;
    color: {theme.secondary};
}}
QLabel#stateBadge {{
    font-size: {FONT_SECTION}px; font-weight: 800; letter-spacing: 2px;
    padding: {SPACE_XS}px {SPACE_MD}px;
    border-radius: {RADIUS_SM}px;
}}
QPushButton {{
    background-color: #12202f; color: {theme.text};
    border: 1px solid {theme.panel_border};
    border-radius: {RADIUS_SM}px; padding: {SPACE_SM}px {SPACE_MD}px;
    font-size: {FONT_BODY}px; font-weight: 600;
}}
QPushButton:hover {{ border-color: {theme.primary}; color: {theme.secondary}; }}
QPushButton:pressed {{ background-color: {theme.deep}; }}
QPushButton:disabled {{ color: {theme.text_faint}; border-color: {theme.panel_border}; }}
QPushButton#primary {{
    background-color: {theme.deep}; border: 1px solid {theme.primary};
    color: #ffffff; font-weight: 700;
}}
QPushButton#primary:hover {{ background-color: {theme.primary}; color: #04121c; }}
QPushButton#danger {{
    background-color: #3a0d12; border: 1px solid {theme.danger};
    color: #ffd7d7; font-weight: 700;
}}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background-color: #0a1320; color: {theme.text};
    border: 1px solid {theme.panel_border};
    border-radius: {RADIUS_SM}px; padding: {SPACE_SM}px;
    font-size: {FONT_BODY}px; selection-background-color: {theme.deep};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {theme.primary}; }}
QComboBox QAbstractItemView {{
    background-color: #0a1320; color: {theme.text};
    selection-background-color: {theme.deep};
    border: 1px solid {theme.primary};
}}
QListWidget {{
    background-color: #0a1320; color: {theme.text};
    border: 1px solid {theme.panel_border};
    border-radius: {RADIUS_SM}px; font-size: {FONT_BODY}px;
}}
QListWidget::item {{ padding: {SPACE_XS}px; }}
QListWidget::item:selected {{
    background-color: {theme.deep}; color: #ffffff;
    border-left: 3px solid {theme.primary};
}}
QCheckBox, QRadioButton {{ color: {theme.text}; font-size: {FONT_BODY}px; spacing: {SPACE_SM}px; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid {theme.panel_border}; background: #0a1320;
}}
QCheckBox::indicator:checked {{
    background-color: {theme.primary}; border-color: {theme.primary};
}}
QSlider::groove:horizontal {{
    height: 4px; background: {theme.panel_border}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px; height: 14px; margin: -6px 0;
    border-radius: 7px; background: {theme.primary};
}}
QTabWidget::pane {{ border: 1px solid {theme.panel_border}; border-radius: {RADIUS_MD}px; }}
QTabBar::tab {{
    background: #0d1624; color: {theme.text_dim};
    padding: {SPACE_SM}px {SPACE_LG}px; margin-right: 2px;
    border-top-left-radius: {RADIUS_SM}px; border-top-right-radius: {RADIUS_SM}px;
    font-weight: 600;
}}
QTabBar::tab:selected {{ background: {theme.deep}; color: #ffffff; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {theme.panel_border}; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {theme.primary}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px; background: none; border: none;
}}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {theme.panel_border}; border-radius: 5px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {theme.primary}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px; background: none; border: none;
}}
QToolTip {{
    background-color: #0d1624; color: {theme.text};
    border: 1px solid {theme.primary}; padding: {SPACE_XS}px;
}}
QMenuBar {{ background: transparent; color: {theme.text_dim}; }}
QMenuBar::item:selected {{ background: {theme.deep}; color: #fff; }}
QMenu {{
    background-color: #0d1624; color: {theme.text};
    border: 1px solid {theme.panel_border};
}}
QMenu::item:selected {{ background-color: {theme.deep}; color: #fff; }}
QSplitter::handle {{ background: {theme.panel_border}; }}
QProgressBar {{
    background: #0a1320; border: 1px solid {theme.panel_border};
    border-radius: 4px; text-align: center; color: {theme.text_dim};
    height: 10px; font-size: {FONT_SMALL}px;
}}
QProgressBar::chunk {{ background-color: {theme.primary}; border-radius: 3px; }}
QGroupBox {{
    color: {theme.primary}; font-weight: 700; font-size: {FONT_BODY}px;
    border: 1px solid {theme.panel_border};
    border-radius: {RADIUS_MD}px; margin-top: {SPACE_LG}px;
    padding-top: {SPACE_SM}px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: {SPACE_MD}px; padding: 0 4px; }}
"""
