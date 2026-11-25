"""
ALX2.0 — PySide6 UI.

Dark blue + black glass theme with:
  - real rounded cards (border-radius)
  - drop-shadow glow (QGraphicsDropShadowEffect)
  - animated pill toggles (custom QWidget with QPropertyAnimation)
  - smooth hover transitions on cards + buttons
  - acrylic / mica background on Windows 11 (best-effort via DWM)
  - four tabs: CORE / INSTANT BUILDS / HUMANIZE / ADVANCED
  - mb4/mb5 capture through the raw-input listener (thread-safe via signals)

Backend (engine, hotkeys, humanizer, raw_input, keyboard_hook, input_backend,
config, stealth) is unchanged — only gui.py and main.py were rewritten.
"""
from __future__ import annotations
import os
import sys
import platform

from PySide6.QtCore import (
    Qt, QEvent, QObject, QPoint, QPointF, QPropertyAnimation,
    QEasingCurve, QRect, QRectF, QSize, QTimer, Signal, Property,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QIcon, QLinearGradient,
    QPainter, QPainterPath, QPen, QPixmap, QCursor,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QGraphicsDropShadowEffect,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QPushButton, QScrollArea, QSizePolicy,
    QSpacerItem, QStackedWidget, QSplitter, QTabBar, QTabWidget,
    QVBoxLayout, QWidget, QAbstractItemView,
)


# ---------- palette: dark blue + black ----------
BG       = "#02050C"
BG2      = "#060B17"
PANEL    = "#0C1426"
PANEL_HI = "#122038"
PANEL_LO = "#070C18"
BORDER   = "#1A2A4D"
BORDER_HI= "#2E4A80"
ACC      = "#5B8FD4"      # primary blue
ACC_HI   = "#9FC2F0"      # bright blue (active)
ACC_SOFT = "#2E4A80"      # dim blue
OFF_BLUE = "#3A4A66"
TXT      = "#E8EEF8"
TXT2     = "#9BAAC6"
DIM      = "#4A5B7A"

# translucent variants for glass panels (rgba-style for QSS)
def rgba(hex_or_rgb, alpha):
    if isinstance(hex_or_rgb, str):
        c = QColor(hex_or_rgb)
        return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"
    r, g, b = hex_or_rgb
    return f"rgba({r}, {g}, {b}, {alpha})"


# ---------- global stylesheet ----------
QSS = f"""
QWidget {{
    color: {TXT};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 10pt;
    background: transparent;
}}

QMainWindow, #Root {{
    background-color: {BG};
}}

QLabel {{ background: transparent; }}
#Brand {{ color: {ACC}; font-size: 20pt; font-weight: 700; letter-spacing: 2px; }}
#BrandSub {{ color: {TXT2}; font-size: 20pt; font-weight: 700; }}
#CardTitle {{ color: {TXT}; font-size: 12pt; font-weight: 700; }}
#CardSub {{ color: {TXT2}; font-size: 8pt; }}
#SectionHint {{ color: {TXT2}; font-size: 8pt; }}
#RowLabel {{ color: {TXT2}; font-size: 9pt; }}
#Status {{ color: {TXT}; font-size: 13pt; font-weight: 700; letter-spacing: 1px; }}
#StatusDim {{ color: {DIM}; font-size: 13pt; font-weight: 700; letter-spacing: 1px; }}

/* ---------- tab bar ---------- */
QTabWidget::pane {{
    border: none;
    background: transparent;
    top: -1px;
}}
QTabBar {{
    background: transparent;
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background: transparent;
    color: {DIM};
    padding: 10px 20px;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 1.5px;
    border: none;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    color: {ACC_HI};
    border-bottom: 2px solid {ACC};
}}
QTabBar::tab:hover:!selected {{
    color: {TXT2};
}}

/* ---------- glass card ---------- */
#GlassCard {{
    background-color: {rgba(PANEL, 0.88)};
    border: 1px solid {rgba(BORDER_HI, 0.55)};
    border-radius: 14px;
}}
#GlassCard[hover="true"] {{
    background-color: {rgba(PANEL_HI, 0.92)};
    border: 1px solid {rgba(ACC, 0.7)};
}}

/* ---------- entry ---------- */
QLineEdit {{
    background-color: {rgba(BG2, 0.9)};
    color: {TXT};
    border: 1px solid {rgba(BORDER, 0.9)};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {ACC_SOFT};
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 10pt;
}}
QLineEdit:focus {{
    border: 1px solid {ACC};
    background-color: {rgba(BG2, 1.0)};
}}
QLineEdit:hover {{ border: 1px solid {rgba(BORDER_HI, 1.0)}; }}

/* ---------- combo ---------- */
QComboBox {{
    background-color: {rgba(BG2, 0.9)};
    color: {TXT};
    border: 1px solid {rgba(BORDER, 0.9)};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 16px;
}}
QComboBox:hover  {{ border: 1px solid {rgba(BORDER_HI, 1.0)}; }}
QComboBox:focus  {{ border: 1px solid {ACC}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {ACC};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {PANEL};
    color: {TXT};
    border: 1px solid {BORDER_HI};
    border-radius: 6px;
    selection-background-color: {ACC_SOFT};
    outline: none;
    padding: 4px;
}}

/* ---------- buttons ---------- */
QPushButton#Primary, QPushButton#Danger, QPushButton#Ghost {{
    padding: 10px 22px;
    border-radius: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    font-size: 9pt;
}}
QPushButton#Primary {{
    background-color: {rgba(ACC_SOFT, 0.5)};
    color: {ACC_HI};
    border: 1px solid {rgba(ACC, 0.7)};
}}
QPushButton#Primary:hover {{
    background-color: {rgba(ACC, 0.25)};
    color: {TXT};
    border: 1px solid {ACC_HI};
}}
QPushButton#Primary:pressed {{
    background-color: {rgba(ACC_SOFT, 0.9)};
}}
QPushButton#Danger {{
    background-color: {rgba(PANEL_LO, 0.9)};
    color: {TXT2};
    border: 1px solid {rgba(BORDER, 1.0)};
}}
QPushButton#Danger:hover {{
    background-color: {rgba(PANEL_HI, 1.0)};
    color: {TXT};
    border: 1px solid {rgba(BORDER_HI, 1.0)};
}}
QPushButton#Ghost {{
    background: transparent;
    color: {TXT2};
    border: 1px solid {rgba(BORDER, 0.6)};
}}
QPushButton#Ghost:hover {{
    color: {TXT};
    border: 1px solid {rgba(BORDER_HI, 1.0)};
}}

/* ---------- scrollbar ---------- */
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px 2px 2px 2px;
}}
QScrollBar::handle:vertical {{
    background: {rgba(BORDER_HI, 0.7)};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {rgba(ACC, 0.9)};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent; border: none; height: 0;
}}
"""


# ============================================================
# custom widgets
# ============================================================
class GlassCard(QFrame):
    """Rounded card with drop-shadow glow; shadow intensifies on hover."""
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.setProperty("hover", False)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(28)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(14, 26, 51, 180))
        self.setGraphicsEffect(self._shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 20)
        layout.setSpacing(6)

        if title:
            t = QLabel(title); t.setObjectName("CardTitle")
            layout.addWidget(t)
        if subtitle:
            s = QLabel(subtitle); s.setObjectName("CardSub")
            s.setWordWrap(True)
            layout.addWidget(s)
            layout.addSpacing(6)

        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 2, 0, 0)
        self._body.setSpacing(8)
        layout.addLayout(self._body)

        self._anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def body(self) -> QVBoxLayout:
        return self._body

    def addRow(self, widget):
        self._body.addWidget(widget)

    def addLayoutRow(self, lay):
        self._body.addLayout(lay)

    def enterEvent(self, _e):
        self.setProperty("hover", True)
        self.style().unpolish(self); self.style().polish(self)
        self._anim.stop()
        self._anim.setEndValue(42)
        self._shadow.setColor(QColor(91, 143, 212, 170))
        self._anim.start()

    def leaveEvent(self, _e):
        self.setProperty("hover", False)
        self.style().unpolish(self); self.style().polish(self)
        self._anim.stop()
        self._anim.setEndValue(28)
        self._shadow.setColor(QColor(14, 26, 51, 180))
        self._anim.start()


class PillToggle(QWidget):
    """Animated iOS-style switch, blue-on when active."""
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self._pos = 1.0 if self._checked else 0.0
        self.setFixedSize(52, 28)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"pos_frac", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool):
        v = bool(v)
        if v == self._checked: return
        self._checked = v
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if v else 0.0)
        self._anim.start()

    # expose a float property to animate
    def _get_pos(self): return self._pos
    def _set_pos(self, v):
        self._pos = float(v); self.update()
    pos_frac = Property(float, _get_pos, _set_pos)

    def mousePressEvent(self, _e):
        self.setChecked(not self._checked)
        self.toggled.emit(self._checked)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        rad = h / 2

        # blend between off/on colors based on self._pos
        def mix(c1, c2, t):
            r = c1.red()   + (c2.red()   - c1.red())   * t
            g = c1.green() + (c2.green() - c1.green()) * t
            b = c1.blue()  + (c2.blue()  - c1.blue())  * t
            a = c1.alpha() + (c2.alpha() - c1.alpha()) * t
            return QColor(int(r), int(g), int(b), int(a))

        off_bg  = QColor(PANEL_LO); off_bg.setAlpha(230)
        on_bg   = QColor(ACC_SOFT); on_bg.setAlpha(255)
        off_bor = QColor(BORDER)
        on_bor  = QColor(ACC)
        off_knb = QColor(OFF_BLUE)
        on_knb  = QColor(ACC_HI)

        bg = mix(off_bg, on_bg, self._pos)
        bor = mix(off_bor, on_bor, self._pos)
        knb = mix(off_knb, on_knb, self._pos)

        # glow halo when on
        if self._pos > 0.05:
            halo = QColor(ACC)
            halo.setAlpha(int(70 * self._pos))
            p.setBrush(halo); p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(-2, -2, w + 4, h + 4), rad + 2, rad + 2)

        # track
        p.setBrush(bg); p.setPen(QPen(bor, 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), rad, rad)

        # knob
        kw = h - 6
        kx = 3 + (w - kw - 6) * self._pos
        p.setBrush(knb); p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(kx, 3, kw, kw))


class CaptureEdit(QLineEdit):
    """QLineEdit that registers itself as a mb4/mb5 capture target on focus."""
    focus_in  = Signal(object)
    focus_out = Signal(object)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.focus_in.emit(self)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.focus_out.emit(self)


class StatusDot(QWidget):
    """Breathing blue dot; brightness pulses while the engine is holding."""
    def __init__(self, size: int = 18, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._size = size
        self._color = QColor(OFF_BLUE)
        self._halo = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)
        self._pulse = False
        self._t = 0.0

    def setMode(self, mode: str):
        """mode: 'off' | 'ready' | 'holding' | 'paused'"""
        self._pulse = (mode == "holding")
        if mode == "off":      self._color = QColor(OFF_BLUE)
        elif mode == "ready":  self._color = QColor(ACC)
        elif mode == "paused": self._color = QColor(ACC_SOFT)
        else:                  self._color = QColor(ACC_HI)
        self.update()

    def _tick(self):
        if self._pulse:
            import math
            self._t += 0.12
            self._halo = 0.5 + 0.5 * math.sin(self._t)
        else:
            self._halo = 0.0
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self._size
        # halo
        if self._halo > 0:
            h = QColor(self._color); h.setAlpha(int(100 * self._halo))
            p.setBrush(h); p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(0, 0, s, s))
        # body
        p.setBrush(self._color); p.setPen(Qt.NoPen)
        pad = 3
        p.drawEllipse(QRectF(pad, pad, s - 2 * pad, s - 2 * pad))


def _resource_path(name: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        p = os.path.join(sys._MEIPASS, name)
        if os.path.exists(p): return p
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


# ============================================================
# windows 11 acrylic / mica hack
# ============================================================
def _enable_windows_acrylic(hwnd: int):
    """Best-effort DWM acrylic/mica on Windows 11. Silently no-ops otherwise."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        from ctypes import c_int, byref, sizeof
        dwm = ctypes.windll.dwmapi
        # DWMWA_SYSTEMBACKDROP_TYPE = 38, DWMSBT_MAINWINDOW = 2 (Mica),
        # DWMSBT_TRANSIENTWINDOW = 3 (Acrylic)
        backdrop = c_int(2)
        try:
            dwm.DwmSetWindowAttribute(hwnd, 38, byref(backdrop), sizeof(backdrop))
        except Exception:
            pass
        # dark title bar
        dark = c_int(1)
        try:
            dwm.DwmSetWindowAttribute(hwnd, 20, byref(dark), sizeof(dark))
        except Exception:
            pass
    except Exception:
        pass


# ============================================================
# main application window
# ============================================================
class App(QMainWindow):
    """ALX2.0 PySide6 main window.

    `App` keeps the same constructor signature as the old tk version
    (cfg, engine, router, on_exit, window_title, listener=...) so main.py
    needs minimal changes. `run()` kicks off the QApplication event loop.
    """
    _capture_signal = Signal(str)

    def __init__(self, cfg, engine, router, on_exit, window_title,
                 listener=None, custom_macros=None, **_kw):
        super().__init__()
        self.cfg = cfg
        self.engine = engine
        self.router = router
        self.on_exit = on_exit
        self.listener = listener
        self.macros = custom_macros
        self._capture_target: CaptureEdit | None = None

        self.setWindowTitle(window_title)
        self.setMinimumSize(900, 720)
        self.resize(980, 860)

        try:
            ico = _resource_path("icon.ico")
            if os.path.exists(ico):
                self.setWindowIcon(QIcon(ico))
        except Exception:
            pass

        # root container with the global stylesheet
        root = QWidget(); root.setObjectName("Root")
        self.setCentralWidget(root)
        root.setStyleSheet(QSS)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())
        outer.addWidget(self._build_tabs(), 1)
        outer.addWidget(self._build_footer())

        # thread-safe capture bridge
        self._capture_signal.connect(self._apply_capture)
        self.router.set_capture_cb(self._on_capture)

        # status polling (engine runs on its own threads)
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(120)
        # wire engine state-change -> our refresh
        self.engine.on_state_change = lambda: QTimer.singleShot(0, self._refresh_status)

        # apply acrylic/mica after show
        QTimer.singleShot(50, lambda: _enable_windows_acrylic(int(self.winId())))

        self._refresh_status()

    # --------------- header ---------------
    def _build_header(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(64)
        lay = QHBoxLayout(w); lay.setContentsMargins(24, 14, 24, 10); lay.setSpacing(0)
        a = QLabel("ALX"); a.setObjectName("Brand")
        b = QLabel("2.0"); b.setObjectName("BrandSub")
        lay.addWidget(a); lay.addWidget(b); lay.addStretch(1)
        self.hdr_dot = StatusDot(12)
        self.hdr_lbl = QLabel("OFF"); self.hdr_lbl.setObjectName("StatusDim")
        self.hdr_lbl.setStyleSheet(f"font-size: 10pt;")
        lay.addWidget(self.hdr_lbl)
        lay.addSpacing(8)
        lay.addWidget(self.hdr_dot)
        return w

    # --------------- tabs ---------------
    def _build_tabs(self) -> QWidget:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._scrollable(self._build_core()),    "CORE")
        self.tabs.addTab(self._scrollable(self._build_builds()),  "INSTANT BUILDS")
        self.tabs.addTab(self._build_builder_tab(),               "BUILDER")
        self.tabs.addTab(self._scrollable(self._build_humanize()),"HUMANIZE")
        self.tabs.addTab(self._scrollable(self._build_advanced()),"ADVANCED")
        return self.tabs

    def _scrollable(self, inner: QWidget) -> QWidget:
        sa = QScrollArea()
        sa.setWidget(inner)
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        return sa

    # --------------- helpers to build rows ---------------
    def _hrow(self, label: str, widget: QWidget, suffix: str = "") -> QHBoxLayout:
        h = QHBoxLayout(); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(10)
        l = QLabel(label); l.setObjectName("RowLabel"); l.setFixedWidth(140)
        h.addWidget(l); h.addWidget(widget)
        if suffix:
            s = QLabel(suffix); s.setObjectName("RowLabel"); h.addWidget(s)
        h.addStretch(1)
        return h

    def _toggle_row(self, text: str, checked: bool, on_change) -> QHBoxLayout:
        h = QHBoxLayout(); h.setContentsMargins(0, 2, 0, 2); h.setSpacing(12)
        tog = PillToggle(checked)
        tog.toggled.connect(lambda v: on_change(bool(v)))
        l = QLabel(text); l.setStyleSheet(f"color: {TXT};")
        h.addWidget(tog); h.addWidget(l); h.addStretch(1)
        return h

    def _edit(self, initial, on_change, numeric=False, floatv=False,
              capture_tag=None, width: int = 150) -> CaptureEdit:
        e = CaptureEdit(str(initial))
        e.setFixedWidth(width)
        def _cb():
            raw = e.text()
            if numeric:
                try: raw = int(raw) if raw != "" else 0
                except ValueError: raw = 0
            elif floatv:
                try: raw = float(raw) if raw != "" else 0.0
                except ValueError: raw = 0.0
            on_change(raw)
        e.textChanged.connect(lambda _t: _cb())
        if capture_tag is not None:
            e._alx_capture = capture_tag
            e.focus_in.connect(self._set_capture)
            e.focus_out.connect(self._clear_capture)
        return e

    def _combo(self, values, current, on_change, width: int = 150) -> QComboBox:
        c = QComboBox(); c.addItems(values); c.setCurrentText(str(current))
        c.setFixedWidth(width)
        c.currentTextChanged.connect(lambda t: on_change(t))
        return c

    # --------------- CORE tab ---------------
    def _build_core(self) -> QWidget:
        page = QWidget(); L = QVBoxLayout(page)
        L.setContentsMargins(24, 18, 24, 18); L.setSpacing(14)

        # macro toggle card
        c = GlassCard("Macro",
            "Turn the whole system on or off. F8 toggles anywhere, F9 exits.")
        row = QHBoxLayout()
        self.lbl_main = QLabel("MACRO IS ON" if self.engine.enabled else "MACRO IS OFF")
        self.lbl_main.setObjectName("Status" if self.engine.enabled else "StatusDim")
        row.addWidget(self.lbl_main); row.addStretch(1)
        btn = QPushButton("TOGGLE  (F8)"); btn.setObjectName("Primary")
        btn.clicked.connect(self._toggle_engine)
        row.addWidget(btn)
        c.addLayoutRow(row)
        L.addWidget(c)

        # edit hold
        slot = self.cfg.slot(0)
        c = GlassCard("Edit Hold  (drag edit)",
            "Hold the edit key; after the settle delay it auto-clicks to confirm.\n"
            "Release the key to release the edit.")
        c.addLayoutRow(self._toggle_row("Enable edit hold", slot.get("on", True),
            lambda v: (self.cfg.set_slot_field(0, "on", v), self.router.rebuild())))
        c.addLayoutRow(self._hrow("Edit key",
            self._edit(slot.get("key", "f"), capture_tag="slot0_key",
                on_change=lambda v: (self.cfg.set_slot_field(0, "key", v), self.router.rebuild()))))
        c.addLayoutRow(self._hrow("Reset key",
            self._edit(slot.get("pause", "c"), capture_tag="slot0_pause",
                on_change=lambda v: (self.cfg.set_slot_field(0, "pause", v), self.router.rebuild()))))
        c.addLayoutRow(self._hrow("Settle",
            self._edit(slot.get("settle", 80), numeric=True, width=90,
                on_change=lambda v: self.cfg.set_slot_field(0, "settle", int(v or 0))),
            suffix="ms"))
        L.addWidget(c)

        # build binds
        c = GlassCard("Build Binds",
            "Your in-game piece keys. Used by the post-build trigger.")
        binds = self.cfg.build_binds() or {}
        role_order = ["wall", "floor", "ramp", "roof", "trap", "pickaxe", "edit"]
        for extra in binds.keys():
            if extra not in role_order: role_order.append(extra)
        grid = QGridLayout(); grid.setHorizontalSpacing(24); grid.setVerticalSpacing(6)
        for idx, role in enumerate(role_order):
            col, r = idx % 2, idx // 2
            lbl = QLabel(role.capitalize()); lbl.setObjectName("RowLabel")
            lbl.setFixedWidth(80)
            edit = self._edit(binds.get(role, ""), capture_tag=f"bind_{role}",
                width=100,
                on_change=lambda v, rn=role: (self.cfg.set_build_bind(rn, str(v)),
                                               self.router.rebuild()))
            cell = QHBoxLayout(); cell.addWidget(lbl); cell.addWidget(edit)
            wrap = QWidget(); wrap.setLayout(cell)
            grid.addWidget(wrap, r, col)
        c.addLayoutRow(grid)
        L.addWidget(c)

        # post key
        main = self.cfg.main()
        c = GlassCard("Post Key  (optional)",
            "Automatically press a key after you edit or build.")
        c.addLayoutRow(self._toggle_row("Enable post key", main.get("postEnabled", True),
            lambda v: (self.cfg.set_main("postEnabled", v), self.router.rebuild())))
        c.addLayoutRow(self._hrow("Fires on",
            self._combo(["edit", "build", "both"], main.get("postTrigger", "build"),
                lambda t: (self.cfg.set_main("postTrigger", t), self.router.rebuild()))))
        c.addLayoutRow(self._hrow("Post key",
            self._edit(main.get("postKey", ""), capture_tag="post_key",
                on_change=lambda v: (self.cfg.set_main("postKey", v), self.router.rebuild()))))
        c.addLayoutRow(self._hrow("Delay",
            self._edit(main.get("postDelay", 0), numeric=True, width=90,
                on_change=lambda v: self.cfg.set_main("postDelay", int(v or 0))),
            suffix="ms"))
        L.addWidget(c)

        L.addStretch(1)
        return page

    # --------------- INSTANT BUILDS tab (B1-B4 slots) ---------------
    def _build_builds(self) -> QWidget:
        page = QWidget(); L = QVBoxLayout(page)
        L.setContentsMargins(24, 18, 24, 18); L.setSpacing(14)

        intro = QLabel(
            "Four hold-to-remap slots. Set a KEY you'll press, a PAUSE key to cancel,\n"
            "and a SETTLE delay before the auto-click fires.")
        intro.setObjectName("SectionHint")
        intro.setWordWrap(True)
        L.addWidget(intro)

        for i in range(1, 5):
            s = self.cfg.slot(i)
            c = GlassCard(f"Build {i}", "")
            c.addLayoutRow(self._toggle_row("Enable this slot", s.get("on", False),
                lambda v, idx=i: (self.cfg.set_slot_field(idx, "on", v),
                                  self.router.rebuild())))
            c.addLayoutRow(self._hrow("Key",
                self._edit(s.get("key", ""), capture_tag=f"slot{i}_key",
                    on_change=lambda v, idx=i: (self.cfg.set_slot_field(idx, "key", v),
                                                self.router.rebuild()))))
            c.addLayoutRow(self._hrow("Pause key",
                self._edit(s.get("pause", ""), capture_tag=f"slot{i}_pause",
                    on_change=lambda v, idx=i: (self.cfg.set_slot_field(idx, "pause", v),
                                                self.router.rebuild()))))
            c.addLayoutRow(self._hrow("Settle",
                self._edit(s.get("settle", 50), numeric=True, width=90,
                    on_change=lambda v, idx=i: self.cfg.set_slot_field(idx, "settle", int(v or 0))),
                suffix="ms"))
            L.addWidget(c)

        L.addStretch(1)
        return page

    # --------------- HUMANIZE tab ---------------
    def _build_humanize(self) -> QWidget:
        page = QWidget(); L = QVBoxLayout(page)
        L.setContentsMargins(24, 18, 24, 18); L.setSpacing(14)

        h = self.cfg.humanize()
        c = GlassCard("Humanize",
            "Adds small random variations so the macro isn't frame-perfect.")
        c.addLayoutRow(self._toggle_row("Enable humanizer", h.get("enabled", True),
            lambda v: self.cfg.set_humanize("enabled", v)))

        rows = (
            ("settle_jitter_ms",     "Settle jitter",    True,  False),
            ("hold_jitter_ms",       "Hold jitter",      True,  False),
            ("post_delay_jitter_ms", "Post-key jitter",  True,  False),
            ("microjitter_ms",       "Microjitter",      True,  False),
            ("miss_chance_pct",      "Miss chance %",    False, True),
            ("warmup_presses",       "Warmup presses",   True,  False),
            ("warmup_slowdown_ms",   "Warmup slowdown",  True,  False),
        )
        for field, label, numeric, floatv in rows:
            c.addLayoutRow(self._hrow(label,
                self._edit(h.get(field, 0), numeric=numeric, floatv=floatv, width=120,
                    on_change=lambda v, f=field: self.cfg.set_humanize(f, v))))
        c.addLayoutRow(self._hrow("Distribution",
            self._combo(["normal", "uniform"], h.get("distribution", "normal"),
                lambda t: self.cfg.set_humanize("distribution", t))))
        L.addWidget(c)
        L.addStretch(1)
        return page

    # --------------- ADVANCED tab ---------------
    def _build_advanced(self) -> QWidget:
        page = QWidget(); L = QVBoxLayout(page)
        L.setContentsMargins(24, 18, 24, 18); L.setSpacing(14)
        main = self.cfg.main()

        c = GlassCard("Input Backend", "auto picks the best. Restart to change.")
        c.addLayoutRow(self._hrow("Backend",
            self._combo(["auto", "interception", "sendinput"], self.cfg.backend_name(),
                lambda t: (self.cfg.data.__setitem__("backend", t), self.cfg.save()))))
        c.addLayoutRow(self._hrow("Click button",
            self._combo(["LButton", "RButton"], main.get("selectButton", "LButton"),
                lambda t: (self.cfg.set_main("selectButton", t), self.router.rebuild()))))
        L.addWidget(c)

        c = GlassCard("Fast-Tap Rescue",
            "Rescues fast-tap edits where the settle timer would miss. Leave ON.")
        c.addLayoutRow(self._toggle_row("Enable rescue",
            main.get("fastTapRescueHook", True),
            lambda v: (self.cfg.set_main("fastTapRescueHook", v), self.router.rebuild())))
        c.addLayoutRow(self._hrow("Rescue gap",
            self._edit(main.get("hookRescueGapMs", 3), numeric=True, width=90,
                on_change=lambda v: self.cfg.set_main("hookRescueGapMs", int(v or 0))),
            suffix="ms"))
        L.addWidget(c)

        c = GlassCard("Stealth", "Window appearance; doesn't affect gameplay.")
        st = self.cfg.stealth()
        c.addLayoutRow(self._hrow("Window title",
            self._edit(st.get("window_title", "ALX2.0"), width=200,
                on_change=lambda v: self.cfg.set_stealth("window_title", v))))
        c.addLayoutRow(self._toggle_row("Hide console (compiled builds)",
            st.get("hide_console", True),
            lambda v: self.cfg.set_stealth("hide_console", v)))
        L.addWidget(c)

        c = GlassCard("Hotkeys", "")
        hk = self.cfg.hotkeys()
        c.addLayoutRow(self._hrow("Toggle hotkey",
            self._edit(hk.get("toggle", "f8"), capture_tag="hk_toggle",
                on_change=lambda v: (hk.__setitem__("toggle", v), self.cfg.save(), self.router.rebuild()))))
        c.addLayoutRow(self._hrow("Exit hotkey",
            self._edit(hk.get("exit", "f9"), capture_tag="hk_exit",
                on_change=lambda v: (hk.__setitem__("exit", v), self.cfg.save(), self.router.rebuild()))))
        L.addWidget(c)

        L.addStretch(1)
        return page

    # ======================================================
    # BUILDER tab — drag-and-drop custom macro composer
    # ======================================================
    def _build_builder_tab(self) -> QWidget:
        from custom_macros import BLOCK_CATALOG, block_meta
        self._BLOCK_CATALOG = BLOCK_CATALOG
        self._block_meta = block_meta

        page = QWidget()
        root_h = QHBoxLayout(page)
        root_h.setContentsMargins(14, 14, 14, 14)
        root_h.setSpacing(12)

        # ---- LEFT: macro list ----
        left_card = GlassCard("My Macros", "")
        left_card.setFixedWidth(210)
        self.macro_list = QListWidget()
        self.macro_list.setStyleSheet(f"""
            QListWidget {{
                background: {rgba(BG2, 0.6)};
                border: 1px solid {rgba(BORDER, 0.6)};
                border-radius: 8px;
                padding: 4px; outline: none;
            }}
            QListWidget::item {{
                padding: 8px 10px; border-radius: 6px; color: {TXT2};
            }}
            QListWidget::item:selected {{
                background: {rgba(ACC_SOFT, 0.7)}; color: {TXT};
            }}
            QListWidget::item:hover {{ background: {rgba(PANEL_HI, 0.8)}; }}
        """)
        self.macro_list.currentRowChanged.connect(self._builder_select_macro)
        left_card.addRow(self.macro_list)

        btn_row = QHBoxLayout()
        b_new = QPushButton("＋ New"); b_new.setObjectName("Ghost")
        b_new.clicked.connect(self._builder_new_macro)
        b_del = QPushButton("Delete"); b_del.setObjectName("Danger")
        b_del.clicked.connect(self._builder_delete_macro)
        btn_row.addWidget(b_new); btn_row.addWidget(b_del)
        left_card.addLayoutRow(btn_row)

        io_row = QHBoxLayout()
        b_import = QPushButton("⇣ Import"); b_import.setObjectName("Ghost")
        b_import.clicked.connect(self._builder_import_macro)
        b_export = QPushButton("⇡ Export"); b_export.setObjectName("Ghost")
        b_export.clicked.connect(self._builder_export_macro)
        io_row.addWidget(b_import); io_row.addWidget(b_export)
        left_card.addLayoutRow(io_row)
        root_h.addWidget(left_card)

        # ---- MIDDLE: sequence + header ----
        mid_card = GlassCard("Sequence", "")
        mid_v = QVBoxLayout()
        hdr = QGridLayout(); hdr.setHorizontalSpacing(12); hdr.setVerticalSpacing(6)
        hdr.addWidget(QLabel("Name"), 0, 0)
        self.b_name = QLineEdit(); self.b_name.setPlaceholderText("Untitled macro")
        self.b_name.editingFinished.connect(self._builder_commit_header)
        hdr.addWidget(self.b_name, 0, 1)

        hdr.addWidget(QLabel("Trigger"), 1, 0)
        self.b_trigger = CaptureEdit()
        self.b_trigger.setPlaceholderText("click & press key")
        self.b_trigger.focus_in.connect(self._set_capture)
        self.b_trigger.focus_out.connect(self._clear_capture)
        self.b_trigger.editingFinished.connect(self._builder_commit_header)
        hdr.addWidget(self.b_trigger, 1, 1)

        hdr.addWidget(QLabel("Enabled"), 2, 0)
        self.b_enabled = PillToggle(False)
        self.b_enabled.toggled.connect(lambda v: self._builder_commit_header())
        ew = QHBoxLayout(); ew.addWidget(self.b_enabled); ew.addStretch(1)
        ewc = QWidget(); ewc.setLayout(ew)
        hdr.addWidget(ewc, 2, 1)
        mid_v.addLayout(hdr)

        mid_v.addSpacing(8)
        seq_hdr = QLabel("Drag blocks here ↓   (reorder by dragging)")
        seq_hdr.setObjectName("SectionHint")
        mid_v.addWidget(seq_hdr)

        self.seq_list = QListWidget()
        self.seq_list.setDragDropMode(QAbstractItemView.DragDrop)
        self.seq_list.setDefaultDropAction(Qt.MoveAction)
        self.seq_list.setMovement(QListWidget.Free)
        self.seq_list.setStyleSheet(f"""
            QListWidget {{
                background: {rgba(BG2, 0.6)};
                border: 1px dashed {rgba(BORDER_HI, 0.9)};
                border-radius: 8px;
                padding: 6px; outline: none;
            }}
            QListWidget::item {{
                background: {rgba(PANEL, 0.9)};
                border: 1px solid {rgba(BORDER, 0.9)};
                border-radius: 6px;
                padding: 10px 12px; margin: 3px 0;
                color: {TXT};
            }}
            QListWidget::item:selected {{
                background: {rgba(ACC_SOFT, 0.85)};
                border: 1px solid {ACC};
            }}
            QListWidget::item:hover {{ border: 1px solid {rgba(BORDER_HI, 1)}; }}
        """)
        self.seq_list.model().rowsInserted.connect(self._seq_rows_changed)
        self.seq_list.model().rowsRemoved.connect(self._seq_rows_changed)
        self.seq_list.currentRowChanged.connect(self._builder_select_block)
        mid_v.addWidget(self.seq_list, 1)

        seq_btns = QHBoxLayout()
        b_delb = QPushButton("− Remove"); b_delb.setObjectName("Ghost")
        b_delb.clicked.connect(self._builder_remove_block)
        b_clr = QPushButton("Clear all"); b_clr.setObjectName("Ghost")
        b_clr.clicked.connect(self._builder_clear_blocks)
        seq_btns.addWidget(b_delb); seq_btns.addWidget(b_clr); seq_btns.addStretch(1)
        mid_v.addLayout(seq_btns)
        mid_card.addLayoutRow(mid_v)
        root_h.addWidget(mid_card, 1)

        # ---- RIGHT: palette + parameters ----
        right_v = QVBoxLayout(); right_v.setSpacing(12)
        pal_card = GlassCard("Blocks", "Drag into the sequence  or double-click")
        self.palette_list = QListWidget()
        self.palette_list.setDragEnabled(True)
        self.palette_list.setDragDropMode(QAbstractItemView.DragOnly)
        self.palette_list.setStyleSheet(f"""
            QListWidget {{
                background: {rgba(BG2, 0.6)};
                border: 1px solid {rgba(BORDER, 0.6)};
                border-radius: 8px;
                padding: 4px; outline: none;
            }}
            QListWidget::item {{
                padding: 10px 12px; border-radius: 6px; color: {TXT};
                margin: 2px 0;
            }}
            QListWidget::item:hover {{
                background: {rgba(ACC_SOFT, 0.5)};
                border: 1px solid {rgba(ACC, 0.7)};
            }}
        """)
        for entry in BLOCK_CATALOG:
            it = QListWidgetItem(f"  {entry['icon']}   {entry['label']}")
            it.setData(Qt.UserRole, entry["type"])
            self.palette_list.addItem(it)
        self.palette_list.itemDoubleClicked.connect(self._palette_double_click)
        pal_card.addRow(self.palette_list)
        right_v.addWidget(pal_card, 1)

        self.param_card = GlassCard("Parameters",
            "Select a block in the sequence to edit.")
        self.param_body = QVBoxLayout()
        self.param_card.addLayoutRow(self.param_body)
        right_v.addWidget(self.param_card, 1)
        right_wrap = QWidget(); right_wrap.setLayout(right_v)
        right_wrap.setFixedWidth(280)
        root_h.addWidget(right_wrap)

        self._current_macro_idx = -1
        self._current_block_idx = -1
        self._loading_sequence = False
        self._builder_refresh_list()
        return page

    def _builder_refresh_list(self):
        self.macro_list.blockSignals(True)
        self.macro_list.clear()
        for m in self.cfg.custom_macros():
            name = m.get("name") or "Untitled macro"
            trig = m.get("trigger_key") or "—"
            self.macro_list.addItem(f"{name}   ·   {trig}")
        self.macro_list.blockSignals(False)
        if 0 <= self._current_macro_idx < self.macro_list.count():
            self.macro_list.setCurrentRow(self._current_macro_idx)
        else:
            self._builder_load_selected(None)

    def _builder_new_macro(self):
        m = {"name": f"Macro {len(self.cfg.custom_macros()) + 1}",
             "enabled": False, "trigger_key": "", "blocks": []}
        idx = self.cfg.add_custom_macro(m)
        self.router.rebuild()
        self._current_macro_idx = idx
        self._builder_refresh_list()

    def _builder_delete_macro(self):
        if self._current_macro_idx < 0: return
        self.cfg.delete_custom_macro(self._current_macro_idx)
        self.router.rebuild()
        self._current_macro_idx = min(self._current_macro_idx,
                                      len(self.cfg.custom_macros()) - 1)
        self._builder_refresh_list()

    def _builder_export_macro(self):
        """Write the currently-selected macro to a .macro.json file."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import json, re
        if self._current_macro_idx < 0:
            QMessageBox.information(self, "Export macro",
                "Select a macro on the left first.")
            return
        m = dict(self.cfg.custom_macros()[self._current_macro_idx])
        # Strip internal/private fields we don't want to share. Right now
        # every field is shareable, but this is where we'd scrub if needed.
        payload = {
            "name":        m.get("name", "Untitled"),
            "enabled":     bool(m.get("enabled", False)),
            "trigger_key": m.get("trigger_key", ""),
            "blocks":      list(m.get("blocks") or []),
            # alxstore-compatible: can be dropped straight into the site's
            # Upload dropzone with kind=macro.
            "_alx_export": {"version": 1, "kind": "macro"},
        }
        # Suggest a filename based on the macro name.
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", payload["name"]).strip("-") or "macro"
        default = f"{safe}.macro.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export macro", default, "Macro files (*.macro.json *.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Export failed", f"Could not write file:\n{e}")
            return
        QMessageBox.information(self, "Export complete",
            f"Saved to:\n{path}\n\n"
            "You can drag this into alxstore → Upload, pick kind = Custom macro.")

    def _builder_import_macro(self):
        """Load a .macro.json into a new macro slot."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import json
        path, _ = QFileDialog.getOpenFileName(
            self, "Import macro", "", "Macro files (*.macro.json *.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Import failed",
                f"Could not read file:\n{e}")
            return

        # Accept several shapes:
        #   {name,enabled,trigger_key,blocks,...}     – a single macro
        #   {blocks: [...]}                           – bare block list
        #   {custom_macros:[...]} or [macro, ...]     – take the first
        macro = None
        if isinstance(data, list) and data:
            macro = data[0]
        elif isinstance(data, dict):
            if isinstance(data.get("custom_macros"), list) and data["custom_macros"]:
                macro = data["custom_macros"][0]
            elif "blocks" in data:
                macro = data
        if not isinstance(macro, dict) or not isinstance(macro.get("blocks"), list):
            QMessageBox.warning(self, "Import failed",
                "That file doesn't look like an ALX macro.")
            return

        # Build a clean entry; don't inherit someone else's trigger binding
        # by default (would silently hijack a key on first run).
        clean = {
            "name":        str(macro.get("name") or "Imported macro"),
            "enabled":     False,                         # user turns it on
            "trigger_key": "",                            # user binds it
            "blocks":      [b for b in (macro.get("blocks") or []) if isinstance(b, dict)],
        }
        idx = self.cfg.add_custom_macro(clean)
        self.router.rebuild()
        self._current_macro_idx = idx
        self._builder_refresh_list()
        QMessageBox.information(self, "Imported",
            f"\"{clean['name']}\" added — set a trigger key and enable it to use.")

    def _builder_select_macro(self, row: int):
        self._current_macro_idx = row
        self._builder_load_selected(row)

    def _builder_load_selected(self, row):
        # Populate the editor from saved state. Must suppress the
        # rowsInserted/rowsRemoved → _seq_rows_changed loop, which would
        # otherwise fire mid-load and overwrite the macro with the half-
        # populated sequence.
        self._loading_sequence = True
        try:
            self._current_block_idx = -1
            self._build_param_editor(None)
            self.seq_list.clear()
            if row is None or row < 0 or row >= len(self.cfg.custom_macros()):
                self.b_name.setText("")
                self.b_trigger.setText("")
                self.b_enabled.setChecked(False)
                return
            m = self.cfg.custom_macros()[row]
            self.b_name.setText(m.get("name", ""))
            self.b_trigger.setText(m.get("trigger_key", ""))
            self.b_enabled.setChecked(bool(m.get("enabled", False)))
            for b in (m.get("blocks") or []):
                self._seq_append_block(b)
        finally:
            self._loading_sequence = False

    def _seq_append_block(self, b: dict):
        it = QListWidgetItem(self._seq_item_label(b))
        it.setData(Qt.UserRole, dict(b))
        self.seq_list.addItem(it)

    def _seq_item_label(self, b: dict) -> str:
        meta = self._block_meta(b.get("type", ""))
        if not meta: return f"?   {b.get('type', '?')}"
        try:
            return f"{meta['icon']}    {meta['summary'](b)}"
        except Exception:
            return f"{meta['icon']}    {meta['label']}"

    def _palette_double_click(self, item: QListWidgetItem):
        if self._current_macro_idx < 0:
            self._builder_new_macro()
        block_type = item.data(Qt.UserRole)
        meta = self._block_meta(block_type)
        if not meta: return
        block = {"type": block_type, **dict(meta["defaults"])}
        self._seq_append_block(block)
        self._builder_commit_sequence()

    def _seq_rows_changed(self, *_args):
        """Convert raw palette drops into real block dicts; commit changes."""
        if getattr(self, "_loading_sequence", False):
            return  # we're populating from disk; don't echo back
        if self._current_macro_idx < 0:
            # dropped before a macro was selected — just make one
            self._builder_new_macro()
        for i in range(self.seq_list.count()):
            it = self.seq_list.item(i)
            if it.data(Qt.UserRole) is None:
                text = it.text().strip()
                block_type = None
                for entry in self._BLOCK_CATALOG:
                    if entry["label"] in text:
                        block_type = entry["type"]; break
                if block_type:
                    meta = self._block_meta(block_type)
                    block = {"type": block_type, **dict(meta["defaults"])}
                    it.setData(Qt.UserRole, block)
                    it.setText(self._seq_item_label(block))
                else:
                    self.seq_list.takeItem(i); return
        self._builder_commit_sequence()

    def _builder_select_block(self, row: int):
        self._current_block_idx = row
        if row < 0 or row >= self.seq_list.count():
            self._build_param_editor(None); return
        it = self.seq_list.item(row)
        self._build_param_editor(it.data(Qt.UserRole))

    def _build_param_editor(self, block):
        while self.param_body.count():
            item = self.param_body.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
            else:
                lay = item.layout()
                if lay:
                    while lay.count():
                        c = lay.takeAt(0)
                        cw = c.widget()
                        if cw: cw.deleteLater()
        if block is None:
            lbl = QLabel("No block selected.")
            lbl.setObjectName("SectionHint")
            self.param_body.addWidget(lbl)
            return
        meta = self._block_meta(block.get("type", ""))
        if not meta:
            self.param_body.addWidget(QLabel("Unknown block type."))
            return
        header = QLabel(f"{meta['icon']}    {meta['label']}")
        header.setStyleSheet(f"color: {ACC_HI}; font-weight: 700;")
        self.param_body.addWidget(header)
        for field, kind, default, label in meta["params"]:
            row = QHBoxLayout()
            lbl = QLabel(label); lbl.setFixedWidth(100)
            lbl.setObjectName("RowLabel")
            row.addWidget(lbl)
            val = block.get(field, default)
            if kind.startswith("choice:"):
                opts = kind.split(":", 1)[1].split(",")
                cb = QComboBox(); cb.addItems(opts); cb.setCurrentText(str(val))
                cb.currentTextChanged.connect(
                    lambda t, f=field: self._update_current_block(f, t))
                row.addWidget(cb, 1)
            else:
                e = QLineEdit(str(val))
                def _upd(text, f=field, k=kind):
                    v = text
                    if k == "int":
                        try: v = int(text) if text else 0
                        except ValueError: return
                    self._update_current_block(f, v)
                e.textChanged.connect(_upd)
                row.addWidget(e, 1)
            self.param_body.addLayout(row)
        self.param_body.addStretch(1)

    def _update_current_block(self, field: str, value):
        i = self._current_block_idx
        if i < 0 or i >= self.seq_list.count(): return
        it = self.seq_list.item(i)
        block = dict(it.data(Qt.UserRole) or {})
        block[field] = value
        it.setData(Qt.UserRole, block)
        it.setText(self._seq_item_label(block))
        self._builder_commit_sequence()

    def _builder_remove_block(self):
        i = self.seq_list.currentRow()
        if i < 0: return
        self.seq_list.takeItem(i)
        self._builder_commit_sequence()

    def _builder_clear_blocks(self):
        self.seq_list.clear()
        self._builder_commit_sequence()

    def _builder_commit_header(self):
        if self._current_macro_idx < 0: return
        m = dict(self.cfg.custom_macros()[self._current_macro_idx])
        m["name"] = self.b_name.text().strip() or "Untitled macro"
        m["trigger_key"] = self.b_trigger.text().strip()
        m["enabled"] = bool(self.b_enabled.isChecked())
        self.cfg.set_custom_macro(self._current_macro_idx, m)
        self.router.rebuild()
        row = self._current_macro_idx
        if row < self.macro_list.count():
            self.macro_list.item(row).setText(
                f"{m['name']}   ·   {m.get('trigger_key') or '—'}")

    def _builder_commit_sequence(self):
        if self._current_macro_idx < 0: return
        blocks = []
        for i in range(self.seq_list.count()):
            b = self.seq_list.item(i).data(Qt.UserRole)
            if isinstance(b, dict): blocks.append(b)
        m = dict(self.cfg.custom_macros()[self._current_macro_idx])
        m["blocks"] = blocks
        self.cfg.set_custom_macro(self._current_macro_idx, m)

    # --------------- footer ---------------
    def _build_footer(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(76)
        lay = QHBoxLayout(w); lay.setContentsMargins(24, 14, 24, 18); lay.setSpacing(12)
        self.status_dot = StatusDot(18)
        self.status_lbl = QLabel("OFF"); self.status_lbl.setObjectName("StatusDim")
        lay.addWidget(self.status_dot); lay.addWidget(self.status_lbl); lay.addStretch(1)
        btn1 = QPushButton("TOGGLE  (F8)"); btn1.setObjectName("Primary")
        btn1.clicked.connect(self._toggle_engine)
        lay.addWidget(btn1)
        btn2 = QPushButton("EXIT  (F9)"); btn2.setObjectName("Danger")
        btn2.clicked.connect(self._do_exit)
        lay.addWidget(btn2)
        return w

    # --------------- capture bridge ---------------
    def _set_capture(self, widget: CaptureEdit):
        self._capture_target = widget
        if self.listener:
            try: self.listener.push_mouse_ref()
            except Exception: pass

    def _clear_capture(self, widget: CaptureEdit):
        if self._capture_target is widget:
            self._capture_target = None
            if self.listener:
                try: self.listener.pop_mouse_ref()
                except Exception: pass

    def _on_capture(self, display_name) -> bool:
        """Called from the raw-input listener thread — must not touch widgets."""
        if self._capture_target is None:
            return False
        self._capture_signal.emit(str(display_name))
        return True

    def _apply_capture(self, name: str):
        tgt = self._capture_target
        if tgt is None: return
        store_name = {"mb4": "mb4", "mb5": "mb5"}.get(name.lower(), name)
        tgt.setText(store_name)

    # --------------- status ---------------
    def _refresh_status(self):
        st = self.engine.status()
        if st == "OFF":
            self.status_dot.setMode("off")
            self.status_lbl.setText("OFF"); self.status_lbl.setObjectName("StatusDim")
        elif st.startswith("HOLDING"):
            self.status_dot.setMode("holding")
            self.status_lbl.setText(st); self.status_lbl.setObjectName("Status")
        elif st.startswith("PAUSED"):
            self.status_dot.setMode("paused")
            self.status_lbl.setText(st); self.status_lbl.setObjectName("Status")
        else:
            self.status_dot.setMode("ready")
            self.status_lbl.setText("READY"); self.status_lbl.setObjectName("Status")
        # restyle to pick up objectName change
        self.status_lbl.style().unpolish(self.status_lbl)
        self.status_lbl.style().polish(self.status_lbl)

        # header
        on = self.engine.enabled
        self.hdr_dot.setMode("ready" if on else "off")
        self.hdr_lbl.setText("ON" if on else "OFF")
        self.hdr_lbl.setStyleSheet(
            f"font-size: 10pt; color: {ACC if on else DIM}; font-weight: 700;")

        # core banner
        try:
            self.lbl_main.setText("MACRO IS ON" if on else "MACRO IS OFF")
            self.lbl_main.setObjectName("Status" if on else "StatusDim")
            self.lbl_main.style().unpolish(self.lbl_main)
            self.lbl_main.style().polish(self.lbl_main)
        except Exception:
            pass

    def _toggle_engine(self):
        self.engine.toggle(); self._refresh_status()

    def _do_exit(self):
        try: self.on_exit()
        except Exception: pass
        QApplication.quit()

    def closeEvent(self, e):
        try: self.on_exit()
        except Exception: pass
        e.accept()

    # --------------- entry point ---------------
    def run(self):
        """Replacement for tk's mainloop(). Called by main.py."""
        self.show()
        QApplication.instance().exec()
