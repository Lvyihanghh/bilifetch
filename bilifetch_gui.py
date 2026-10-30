#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BiliFetch 图形界面（PyQt5）

和 bilifetch.py 共用同一套下载逻辑（bilifetch.py 里的 BiliClient / download_episode），
只是把命令行换成了窗口。

单独运行：python3 bilifetch_gui.py
打包后自检：BiliFetch --selftest <链接> <输出目录>
"""

import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
import traceback

from PyQt5.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, QSize,
                          Qt, QTimer, QObject, QThread, pyqtProperty, pyqtSignal, pyqtSlot)
from PyQt5.QtGui import (QBrush, QColor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap)
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
                             QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                             QPlainTextEdit, QPushButton, QSizePolicy, QStackedWidget,
                             QStatusBar, QVBoxLayout, QWidget)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bilifetch as core          # noqa: E402
from bilifetch_ui import (BLUE, BLUE_D, CARD, DARK, DARK_FG, INK, INK_2, INK_3,
                        LINE, PAGE, PINK, PINK_D, TRACK, Card, IconLabel,
                        SectionTitle, draw_fox, fade_in, make_icon)   # noqa: E402
import bilifetch_collection as collection        # noqa: E402
import bilifetch_collection_gui as collection_gui     # noqa: E402
import bilifetch_login as login_mod                    # noqa: E402
from bilifetch_login_gui import LoginDialog             # noqa: E402
from bilifetch_collection_gui import CollectionDialog   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 设计变量

QUALITY_CHOICES = [
    ("最高可得", 0),
    ("4K", 120),
    ("1080P60", 116),
    ("1080P+", 112),
    ("1080P", 80),
    ("720P60", 74),
    ("720P", 64),
    ("480P", 32),
    ("360P", 16),
]

QSS = """
QWidget { color: %INK%; }
QMainWindow, QDialog { background: %PAGE%; }

QFrame#panelDark {
    background: %DARK%;
    border: none;
    border-radius: 12px;
}
QLabel#appTitle { font-size: 21px; font-weight: 700; color: %INK%; }
QLabel#appSub   { font-size: 12px; color: %INK_3%; }
QLabel#secTitle { font-size: 12px; font-weight: 700; color: %INK_2%; letter-spacing: 1px; }
QLabel#fieldLbl { font-size: 12px; color: %INK_2%; }
QLabel#rowTitle { font-size: 13px; color: %INK%; }
QLabel#rowMeta  { font-size: 11px; color: %INK_3%; }
QLabel#hint     { font-size: 12px; color: %INK_3%; }
QLabel#loginChip {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FDECF2, stop:1 #E4F4FC);
    color: %INK_2%;
    border-radius: 15px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#logTitle { font-size: 12px; font-weight: 700; color: %INK_2%; letter-spacing: 1px; }
QLabel#barBrand { background: transparent; }

QLineEdit {
    background: #F7F9FC;
    border: 1px solid %LINE%;
    border-radius: 11px;
    padding: 10px 14px;
    selection-background-color: %BLUE%;
    selection-color: #ffffff;
}
QLineEdit:focus { border: 1px solid %BLUE%; background: #ffffff; }
QLineEdit:read-only { background: #F2F5F9; color: %INK_2%; }

QComboBox {
    background: #F7F9FC;
    border: 1px solid %LINE%;
    border-radius: 10px;
    padding: 8px 12px;
    min-width: 112px;
}
QComboBox:hover { border-color: #CFD8E8; }
QComboBox:focus { border-color: %BLUE%; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: none; }
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #E2E7F1;
    border-radius: 10px;
    padding: 5px;
    outline: none;
    selection-background-color: %BLUE%;
    selection-color: #ffffff;
}

/* 主界面用自绘的 FloatButton；这里的规则给合集对话框等原生按钮用 */
QPushButton {
    border: none;
    border-radius: 10px;
    padding: 9px 18px;
    font-weight: 600;
}
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %PINK%, stop:1 %BLUE%);
    color: #ffffff;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f2648d, stop:1 #1f9dd1);
}
QPushButton#primary:disabled { background: #CFD6E2; color: #F2F5F9; }
QPushButton#ghost {
    background: #EEF1F7;
    color: %INK_2%;
    padding: 8px 16px;
}
QPushButton#ghost:hover { background: #E3E8F2; }
QPushButton#ghost:pressed { background: #D8DFEB; }

QCheckBox { color: %INK_2%; spacing: 8px; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 6px;
    border: 1px solid #CBD3E1;
    background: #ffffff;
}
QCheckBox::indicator:hover { border-color: %BLUE%; }
QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 %PINK%, stop:1 %BLUE%);
    border-color: transparent;
}

QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { border: none; }

QPlainTextEdit {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1B2231, stop:1 %DARK%);
    color: %DARK_FG%;
    border: none;
    border-radius: 12px;
    padding: 12px 14px;
    font-family: Menlo, monospace;
    font-size: 12px;
    selection-background-color: %BLUE%;
    selection-color: #ffffff;
}

QStatusBar { background: transparent; color: %INK_3%; }
QStatusBar::item { border: none; }
QMenuBar { background: %PAGE%; color: %INK_2%; }
QMenuBar::item:selected { background: #E7EBF3; }
QMenu { background: #ffffff; border: 1px solid #E2E7F1; border-radius: 10px; padding: 5px; }
QMenu::item { padding: 7px 24px; border-radius: 7px; }
QMenu::item:selected { background: %BLUE%; color: #ffffff; }
QToolTip { background: #2A3140; color: #EDF1F7; border: none; padding: 5px 8px; border-radius: 6px; }
"""
for _k, _v in {"INK": INK, "INK_2": INK_2, "INK_3": INK_3, "PAGE": PAGE, "CARD": CARD,
                "LINE": LINE, "TRACK": TRACK, "DARK": DARK, "DARK_FG": DARK_FG,
                "PINK": PINK, "BLUE": BLUE}.items():
    QSS = QSS.replace("%" + _k + "%", _v)


# ---------------------------------------------------------------- 小图标


def load_app_icon():
    """窗口图标：优先用打包好的 .icns；源码运行时现画一只矢量狐狸。"""
    for c in (os.path.join(os.path.dirname(sys.executable), "..", "Resources", "icon.icns"),
              os.path.join(HERE, "packaging", "app", "icon_1024.png")):
        c = os.path.normpath(c)
        if os.path.exists(c):
            return QIcon(c)
    pm = QPixmap(128, 128)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    draw_fox(p, 14, 14, 100)
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------- 组件




class EmptyArt(QWidget):
    """空状态的小插画：圆角徽章 + 下载箭头。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 64)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        u = r.width() / 84.0          # 以 96px 画布为基准等比缩放
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0, QColor(255, 234, 242))
        grad.setColorAt(1, QColor(222, 243, 253))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 26 * u, 26 * u)
        cx, cy = r.center().x(), r.center().y()
        pen = QPen(QColor(255, 122, 158))
        pen.setWidthF(4.2 * u)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawLine(int(cx), int(cy - 16 * u), int(cx), int(cy + 8 * u))
        p.drawPolyline([QPoint(int(cx - 9 * u), int(cy - 1 * u)),
                        QPoint(int(cx), int(cy + 9 * u)),
                        QPoint(int(cx + 9 * u), int(cy - 1 * u))])
        p.drawLine(int(cx - 15 * u), int(cy + 17 * u), int(cx + 15 * u), int(cy + 17 * u))
        p.end()


class LogoTile(QWidget):
    """标题栏的小徽章：圆角渐变底 + 狐狸。"""

    def __init__(self, size=46, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        rad = r.width() * 0.26
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), rad, rad)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0, QColor(255, 233, 241))
        grad.setColorAt(1, QColor(219, 242, 253))
        p.fillPath(path, QBrush(grad))
        p.setClipPath(path)
        # 狐狸：纯矢量绘制，不依赖任何图片资源（打包后路径会变）
        m = r.width() * 0.86
        draw_fox(p, (r.width() - m) / 2, (r.height() - m) / 2 + r.height() * 0.03, m)
        p.end()




class FloatButton(QPushButton):
    """自绘按钮：悬停时整体上浮一点，按下时下沉，用 QPropertyAnimation 做过渡。"""

    def __init__(self, text, kind="primary", parent=None):
        super().__init__(text, parent)
        self.kind = kind
        self._lift = 0.0
        self._icon = None
        self._active = True
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        self._anim = QPropertyAnimation(self, b"lift", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def setGlyph(self, kind, color=INK_2, size=14):
        """给按钮配一个小图标（自绘时一起画）。"""
        self._icon = make_icon(kind, color, size)
        self.updateGeometry()

    def setActive(self, on):
        """分段按钮用：选中的是白药丸，没选中的是透明。"""
        self._active = on
        self.update()

    def _get_lift(self):
        return self._lift

    def _set_lift(self, v):
        self._lift = v
        self.update()

    lift = pyqtProperty(float, _get_lift, _set_lift)

    def enterEvent(self, e):
        self._anim.stop()
        self._anim.setStartValue(self._lift)
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._anim.stop()
        self._anim.setStartValue(self._lift)
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._anim.stop()
        self._anim.setStartValue(self._lift)
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().mousePressEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(0, 0, 0, -1)
        lift = int(2 * self._lift)
        if self.kind == "primary":
            grad = QLinearGradient(r.topLeft(), r.topRight())
            if not self.isEnabled():
                grad.setColorAt(0, QColor("#CFD6E2"))
                grad.setColorAt(1, QColor("#CFD6E2"))
                text_color = QColor("#F2F5F9")
            else:
                grad.setColorAt(0, QColor(PINK_D if self._lift > 0.01 else PINK))
                grad.setColorAt(1, QColor(BLUE_D if self._lift > 0.01 else BLUE))
                text_color = QColor("#ffffff")
            path = QPainterPath()
            path.addRoundedRect(QRectF(r).adjusted(0, lift, 0, -lift), 11, 11)
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawPath(path)
        else:
            p.setBrush(QColor("#EEF1F7"))
            p.setPen(Qt.NoPen)
            path = QPainterPath()
            path.addRoundedRect(QRectF(r).adjusted(0, lift, 0, -lift), 11, 11)
            p.drawPath(path)
            text_color = QColor(INK_2)
        if self.kind == "tab":
            # 分段按钮：选中的画成白药丸，没选中的留空
            path = QPainterPath()
            if self._active:
                p.setBrush(QColor("#ffffff"))
                p.setPen(Qt.NoPen)
                path.addRoundedRect(QRectF(r).adjusted(2, lift, -2, -lift), 9, 9)
                p.drawPath(path)
                text_color = QColor(INK)
            else:
                text_color = QColor(INK_3)
        p.setPen(QPen(text_color))
        f = self.font()
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        if self._icon is not None:
            fm = QFontMetrics(f)
            tw = fm.horizontalAdvance(self.text())
            iw = self._icon.width()
            total = tw + iw + 7
            x = r.center().x() - total // 2
            p.drawPixmap(int(x), int(r.center().y() - self._icon.height() / 2), self._icon)
            p.drawText(QRect(int(x + iw + 7), r.top(), tw, r.height()),
                       Qt.AlignVCenter | Qt.AlignLeft, self.text())
        else:
            p.drawText(r, Qt.AlignCenter, self.text())
        p.end()

    def sizeHint(self):
        s = super().sizeHint()
        f = QFont(self.font())
        f.setWeight(QFont.DemiBold)
        fm = QFontMetrics(f)
        w = fm.horizontalAdvance(self.text())
        if self._icon is not None:
            w += self._icon.width() + 7
        return QSize(w + 34, 38)


class SlimBar(QWidget):
    """自绘进度条：圆角轨道 + 粉蓝渐变，带平滑过渡和一道流光。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._shine = 0.0
        self.setFixedHeight(6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        # 流光：一道柔和高光缓慢扫过进度条
        self._shine_timer = QTimer(self)
        self._shine_timer.timeout.connect(self._tick_shine)
        self._shine_timer.start(70)     # 40ms 太密了，70ms 肉眼看不出差别

    def _tick_shine(self):
        if not self.isVisible() or self._value >= 99.5:
            return          # 看不见的、或已经满了，就别浪费重绘
        self._shine = (self._shine + 0.02) % 1.0
        self.update()

    def _get(self):
        return self._value

    def _set(self, v):
        self._value = v
        self.update()

    value = pyqtProperty(float, _get, _set)

    def setValue(self, v):
        if self._anim.state() == QPropertyAnimation.Running:
            self._anim.stop()
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(v)
        self._anim.start()

    def jumpTo(self, v):
        self._anim.stop()
        self._value = v
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(TRACK))
        p.drawRoundedRect(track, self.height() / 2.0, self.height() / 2.0)
        w = track.width() * self._value / 100.0
        if w > 0.5:
            grad = QLinearGradient(0, 0, max(w, 1), 0)
            grad.setColorAt(0, QColor(PINK))
            grad.setColorAt(1, QColor(BLUE))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(0, 0, w, self.height()),
                              self.height() / 2.0, self.height() / 2.0)
            # 流光
            if self._value < 99.5:
                cx = self._shine * (w + 40) - 20
                sh = QLinearGradient(cx - 18, 0, cx + 18, 0)
                sh.setColorAt(0.0, QColor(255, 255, 255, 0))
                sh.setColorAt(0.5, QColor(255, 255, 255, 90))
                sh.setColorAt(1.0, QColor(255, 255, 255, 0))
                p.setBrush(QBrush(sh))
                p.drawRoundedRect(QRectF(0, 0, w, self.height()),
                                  self.height() / 2.0, self.height() / 2.0)
        p.end()


class StatusChip(QLabel):
    """小圆角状态标签。"""

    STYLES = {
        "wait": ("#EFF2F7", INK_3),
        "run": ("#E4F4FC", BLUE),
        "done": ("#E6F7EF", "#22A06B"),
        "fail": ("#FDECEF", "#D64550"),
        "merge": ("#FDEEF3", PINK),
    }

    def __init__(self, text="等待", kind="wait", parent=None):
        super().__init__(text, parent)
        self.kind = kind
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(21)
        self.apply()

    def apply(self):
        bg, fg = self.STYLES.get(self.kind, self.STYLES["wait"])
        self.setStyleSheet("background:%s; color:%s; border-radius:10px;"
                           "font-size:11px; font-weight:600; padding:0 8px;" % (bg, fg))

    def setState(self, text, kind):
        self.setText(text)
        self.kind = kind
        self.apply()


class EpisodeRow(QWidget):
    """队列里的一行：标题 + 细进度条 + 状态标签。"""

    def __init__(self, index, title, parent=None):
        super().__init__(parent)
        self.setFixedHeight(62)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(10)
        num = QLabel("%02d" % index)
        num.setStyleSheet("color:%s; font-size:11px; font-weight:700;" % INK_3)
        num.setFixedWidth(20)
        self.title = QLabel(title)
        self.title.setObjectName("rowTitle")
        self.title.setMinimumWidth(160)
        self.chip = StatusChip("等待", "wait")
        top.addWidget(num)
        top.addWidget(self.title, 1)
        top.addWidget(self.chip)
        lay.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self.bar = SlimBar()
        self.meta = QLabel("")
        self.meta.setObjectName("rowMeta")
        self.meta.setFixedWidth(132)
        self.meta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bottom.addWidget(self.bar, 1)
        bottom.addWidget(self.meta)
        lay.addLayout(bottom)

    def set_progress(self, pct, readout=None):
        self.bar.setValue(int(pct))
        self.chip.setState("下载中", "run")
        if readout:
            self.meta.setText(readout)

    def set_stage(self, text, kind="run"):
        self.chip.setState(text, kind)

    def set_done(self, path=""):
        self.bar.jumpTo(100)
        self.chip.setState("完成", "done")
        self.meta.setText("")

    def set_failed(self, msg):
        self.chip.setState("失败", "fail")
        self.bar.jumpTo(0)
        self.title.setToolTip(msg)


class PulsingDot(QWidget):
    """状态栏里一闪一闪的小圆点。

    注意：QWidget 没有 opacity 属性（只有顶层窗口有 windowOpacity），
    所以这里用定时器 + 正弦相位自己画，不要用 QPropertyAnimation 动 opacity。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(9, 9)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(80)     # 40ms 太密，80ms 足够顺滑

    def _tick(self):
        if not self.isVisible():
            return          # 不在屏幕上就别重绘
        self._phase = (self._phase + 0.09) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        alpha = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(self._phase))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(251, 114, 153, int(alpha * 255)))
        p.drawEllipse(self.rect())


# ---------------------------------------------------------------- 后台下载
class Worker(QObject):
    """后台线程：解析链接 -> 逐集下载。"""

    log_line = pyqtSignal(str)
    stage_changed = pyqtSignal(str, int, int)      # 集名, 已完成, 总数
    progress_changed = pyqtSignal(str, float, float, str)  # 集名, done字节, total字节, 说明
    item_finished = pyqtSignal(str, str)
    item_failed = pyqtSignal(str, str)
    cancelled = pyqtSignal(str)
    all_done = pyqtSignal()

    def __init__(self, url, out_dir, quality, all_episodes, cookie, threads, proxy,
                 items=None, audio_only=False):
        super().__init__()
        self.url = url
        self.items = items          # 直接指定要下的视频（合集勾选结果）
        self.out_dir = out_dir
        self.quality = quality
        self.all_episodes = all_episodes
        self.cookie = cookie
        self.threads = threads
        self.proxy = proxy
        self.audio_only = audio_only
        self._cancel = False
        self._client = None

    def cancel(self):
        self._cancel = True
        # 顺便把正在读的网络连接掐断：不掐的话，卡住的读要等到超时（最长 60 秒）
        # 才会去看取消标志，"停止"按钮会像失灵一样。
        c = getattr(self, "_client", None)
        if c is not None:
            try:
                c.cancel()
            except Exception:
                pass

    @pyqtSlot()
    def run(self):
        try:
            self._run()
        except Exception as e:
            self.log_line.emit("出错：%s" % e)
        finally:
            try:
                self.all_done.emit()
            except RuntimeError:
                pass          # 窗口已销毁，忽略
            # 线程自己退出事件循环。
            # 等 GUI 线程收到 all_done 再来调 quit() 会死锁：那时 GUI 线程
            # 可能正阻塞在 wait() 上等这个线程，于是谁也叫不动谁，
            # 线程永远停不下来（表现就是"停止之后没法重新开始"）。
            QThread.currentThread().quit()

    def _run(self):
        client = core.BiliClient(cookie=self.cookie, proxy=self.proxy or None)
        self._client = client          # 取消时用来掐断连接
        if self.items:
            # 合集勾选结果：展开成具体分 P（一个视频可能有多个分 P，全下）
            jobs = []
            for it in self.items:
                title = it.get("title") or it["bvid"]
                cid = it.get("cid")
                if cid is None:
                    try:
                        pages = client.pagelist(it["bvid"])
                    except Exception:
                        pages = []
                    if not pages:
                        continue
                    if len(pages) == 1:
                        jobs.append((title, it["bvid"], pages[0]["cid"]))
                    else:
                        for i, p in enumerate(pages):
                            part = p.get("part") or "P%d" % p.get("page")
                            name = title if i == 0 else "%s - %s" % (title, part)
                            jobs.append((name, it["bvid"], p["cid"]))
                else:
                    jobs.append((title, it["bvid"], cid))
        else:
            self.log_line.emit("解析链接：%s" % self.url)
            info = client.resolve(self.url)
            self.log_line.emit("  标题：%s" % info["title"])
            self.log_line.emit("  UP主：%s   时长：%d 秒" % (info["owner"], info["duration"]))
            jobs = core.plan_jobs(client, info, all_episodes=self.all_episodes)
        self.log_line.emit("  待下载：%d 集" % len(jobs))

        ffmpeg = core.find_executable("ffmpeg")
        if not ffmpeg:
            self.log_line.emit("找不到 ffmpeg，请先安装（macOS: brew install ffmpeg）")
            return
        self.log_line.emit("ffmpeg：%s" % ffmpeg)

        for idx, (name, bvid, cid) in enumerate(jobs, 1):
            if self._cancel:
                self.log_line.emit("已取消")
                return
            self.stage_changed.emit(name, idx - 1, len(jobs))

            def on_log(text):
                self.log_line.emit("  %s" % text)

            def on_progress(done, total, _n=name):
                self.progress_changed.emit(_n, done, total, "下载中")

            def on_stage(text, _n=name):
                self.progress_changed.emit(_n, 0, 0, text)

            if cid is None:
                self.log_line.emit("  跳过（拿不到 cid）：%s" % name)
                continue
            try:
                out = core.download_episode(
                    client, bvid, cid, name, self.out_dir,
                    quality=self.quality, threads=self.threads,
                    audio_only=self.audio_only, ffmpeg=ffmpeg,
                    on_log=on_log, on_progress=on_progress, on_stage=on_stage,
                    should_stop=lambda: self._cancel)
                self.item_finished.emit(name, out)
            except core.Cancelled:
                self.log_line.emit("  已取消")
                self.cancelled.emit(name)
                return
            except Exception as e:
                self.item_failed.emit(name, str(e))
                self.log_line.emit("  失败：%s" % e)


class LoginCheckThread(QThread):
    """后台查登录态。

    以前是在主线程里查的 —— 一次网络请求最多卡 15 秒，
    开窗那一下整个界面是僵的。现在放到线程里，窗口立刻就能用。
    """

    done = pyqtSignal(str, str)      # 状态(ok/invalid/error), 昵称

    def __init__(self, cookie, proxy, parent=None):
        super().__init__(parent)
        self.cookie = cookie
        self.proxy = proxy

    def run(self):
        try:
            state, name = login_mod.check_login_state(self.cookie, self.proxy)
        except Exception:
            state, name = "error", ""
        self.done.emit(state, name)


class PreviewThread(QThread):
    """后台读链接内容。

    这一步是网络请求（要打 B 站好几个接口），放界面线程里做的话，
    窗口在读取期间是**完全僵的** —— 用户看到的就是"一点下载就卡住"。
    """

    done = pyqtSignal(object)      # info
    failed = pyqtSignal(str)

    def __init__(self, url, cookie, proxy, parent=None):
        super().__init__(parent)
        self.url = url
        self.cookie = cookie
        self.proxy = proxy

    def run(self):
        try:
            client = core.BiliClient(cookie=self.cookie, proxy=self.proxy or None)
            collection_gui.collection_client = client
            info = collection.fetch_preview(client, self.url)
            self.done.emit(info)
        except Exception as e:
            self.failed.emit(str(e))


# ---------------------------------------------------------------- 主窗口
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BiliFetch")
        self.setWindowIcon(load_app_icon())
        self.setMinimumSize(920, 660)
        self.resize(980, 780)
        self.worker = None
        self.thread = None
        self.rows = {}
        self._stopping = False   # 点过「停止」，正在收尾
        self._pending_browse = False    # 收尾完成后要接着做的事
        self._pending_clear = False
        self._pending_download = None
        self._speed = {}      # 集名 -> (时刻, 已下字节)，用来算速度
        self._ema = {}        # 集名 -> 平滑后的速度
        self._anims = []
        self._build_ui()
        self._load_settings()
        # 登录检查放到后台线程（QTimer 只是把它推迟到窗口画完之后）
        QTimer.singleShot(60, self._check_login)

    # ---------------- 界面 ----------------
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 0, 24, 16)
        root.setSpacing(14)

        # 顶部品牌条
        brand = QLabel()
        brand.setFixedHeight(4)
        brand.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                            "stop:0 %s, stop:0.5 %s, stop:1 %s);"
                            "border-bottom-left-radius:2px; border-bottom-right-radius:2px;"
                            % (PINK, BLUE, PINK))
        root.addWidget(brand)

        # ---- 标题区 ----
        head = QHBoxLayout()
        head.setSpacing(13)
        logo = LogoTile(46)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        t = QLabel("BiliFetch")
        t.setObjectName("appTitle")
        s = QLabel("B 站视频下载器 · 番剧 / 分P / b23.tv 短链")
        s.setObjectName("appSub")
        titles.addWidget(t)
        titles.addWidget(s)
        head.addWidget(logo)
        head.addLayout(titles)
        head.addStretch(1)
        # 登录状态：已登录显示胶囊 + 退出登录；未登录显示扫码登录按钮
        self.login_chip = QLabel("")
        self.login_chip.setObjectName("loginChip")
        self.login_chip.setVisible(False)
        head.addWidget(self.login_chip)
        self.btn_logout = FloatButton("退出登录", "ghost")
        self.btn_logout.setFixedHeight(34)
        self.btn_logout.setVisible(False)
        self.btn_logout.setToolTip("清除本机保存的登录状态")
        self.btn_logout.clicked.connect(self.on_logout)
        head.addWidget(self.btn_logout)
        # 登录入口放主界面右上角，必须一眼能看到（之前藏在折叠的「高级」里，等于没有）
        self.btn_login = FloatButton("扫码登录 · 解锁 1080P", "primary")
        self.btn_login.setGlyph("play", "#ffffff", 13)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setFixedHeight(34)
        self.btn_login.setToolTip("用手机 B 站 App 扫码登录，未登录最高只能拿到 480P")
        self.btn_login.clicked.connect(self.on_login)
        head.addWidget(self.btn_login)
        root.addLayout(head)
        root.addSpacing(2)

        # ---- 主卡：链接 + 选项（合成一张，别拆成两张卡）----
        card = Card()
        card.layout.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("粘贴 B 站链接，回车即可浏览")
        self.url_edit.setMinimumHeight(40)
        self.url_edit.returnPressed.connect(self.on_browse)
        self.btn_start = FloatButton("浏览…", "primary")
        self.btn_start.setGlyph("film", "#ffffff", 14)
        self.btn_start.setMinimumWidth(122)
        self.btn_start.setMinimumHeight(40)
        self.btn_start.setToolTip("读取链接内容，预览后挑着下载")
        self.btn_start.clicked.connect(self.on_browse)
        row.addWidget(self.url_edit, 1)
        row.addWidget(self.btn_start)
        card.layout.addLayout(row)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:%s; border:none;" % LINE)
        card.layout.addWidget(line)

        opt = QHBoxLayout()
        opt.setSpacing(12)

        self.out_edit = QLineEdit()
        self.out_edit.setReadOnly(True)
        self.out_edit.setMinimumWidth(240)
        self.btn_pick = FloatButton("选择…", "ghost")
        self.btn_pick.clicked.connect(self.on_pick_dir)
        col1 = QHBoxLayout()
        col1.setSpacing(8)
        col1.addWidget(IconLabel("保存到", "folder"))
        col1.addWidget(self.out_edit, 1)
        col1.addWidget(self.btn_pick)
        opt.addLayout(col1, 1)

        self.quality_box = QComboBox()
        for label, qid in QUALITY_CHOICES:
            self.quality_box.addItem(label, qid)
        self.quality_box.setCursor(Qt.PointingHandCursor)
        self.quality_box.setToolTip("未登录时 B 站最高只给 480P，登录后才有 1080P 及以上")
        col2 = QHBoxLayout()
        col2.setSpacing(8)
        col2.addWidget(IconLabel("画质", "film"))
        col2.addWidget(self.quality_box)
        opt.addLayout(col2)

        self.btn_adv = FloatButton("高级", "ghost")
        self.btn_adv.setGlyph("gear", INK_2, 13)
        self.btn_adv.setFixedWidth(84)
        self.btn_adv.setToolTip("Cookie / 代理等高级设置")
        self.btn_adv.clicked.connect(self._toggle_adv)
        opt.addWidget(self.btn_adv)
        opt.addStretch(1)
        card.layout.addLayout(opt)
        root.addWidget(card)
        self.card_link = card

        # ---- 高级卡（收起）----
        self.adv_card = Card()
        self.adv_card.add_title("高级")
        av = QHBoxLayout()
        av.setSpacing(10)
        self.cookie_edit = QLineEdit()
        self.cookie_edit.setPlaceholderText("浏览器 F12 里复制的整段 Cookie（登录后才能拿高清）")
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("代理，如 http://127.0.0.1:7890，留空直连")
        self.proxy_edit.setFixedWidth(230)
        av.addWidget(IconLabel("Cookie", "gear"))
        av.addWidget(self.cookie_edit, 1)
        av.addWidget(IconLabel("代理", "gear"))
        av.addWidget(self.proxy_edit, 0)
        self.adv_card.layout.addLayout(av)
        self.adv_card.setVisible(False)
        root.addWidget(self.adv_card)

        # ---- 队列 / 日志：同一张卡，分段切换 ----
        # 之前是两张卡各占一半高度，日志那块大部分时间是个空黑框，看着像没做完。
        qcard = Card()
        qhead = QHBoxLayout()
        qhead.setSpacing(8)

        track = QWidget()
        track.setFixedHeight(34)
        track.setStyleSheet("background:#F1F4F9; border-radius:10px;")
        tlay = QHBoxLayout(track)
        tlay.setContentsMargins(3, 3, 3, 3)
        tlay.setSpacing(2)
        self.tab_queue = FloatButton("下载队列", "tab")
        self.tab_log = FloatButton("运行日志", "tab")
        for b in (self.tab_queue, self.tab_log):
            b.setFixedHeight(28)
            b.setCursor(Qt.PointingHandCursor)
            tlay.addWidget(b)
        self.tab_queue.clicked.connect(lambda: self._switch_tab(True))
        self.tab_log.clicked.connect(lambda: self._switch_tab(False))
        qhead.addWidget(track)
        qhead.addStretch(1)

        self.btn_stop = FloatButton("停止", "ghost")
        self.btn_stop.setGlyph("stop", INK_2, 13)
        self.btn_stop.setFixedWidth(84)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_clear = FloatButton("清空", "ghost")
        self.btn_clear.setFixedWidth(74)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_copy = FloatButton("复制", "ghost")
        self.btn_copy.setGlyph("copy", INK_2, 13)
        self.btn_copy.setFixedWidth(66)
        self.btn_copy.clicked.connect(self.on_copy_log)
        self.btn_logclear = FloatButton("清空", "ghost")
        self.btn_logclear.setGlyph("trash", INK_2, 13)
        self.btn_logclear.setFixedWidth(66)
        self.btn_logclear.clicked.connect(self.on_clear_log)
        for b in (self.btn_stop, self.btn_clear, self.btn_copy, self.btn_logclear):
            qhead.addWidget(b)
        qcard.layout.addLayout(qhead)

        self.stack = QStackedWidget()

        # 队列页
        page_q = QWidget()
        ql = QVBoxLayout(page_q)
        ql.setContentsMargins(0, 0, 0, 0)
        ql.setSpacing(8)
        self.list = QListWidget()
        self.list.setMinimumHeight(110)
        self.empty_hint = QWidget()
        eh = QVBoxLayout(self.empty_hint)
        eh.setContentsMargins(0, 4, 0, 6)
        eh.setSpacing(8)
        eh.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)   # 插画和文字整体居中
        art = EmptyArt()
        eh.addWidget(art, 0, Qt.AlignHCenter)
        tip = QLabel("还没有任务 —— 把 B 站链接粘到上面，点「浏览…」挑选内容")
        tip.setObjectName("hint")
        tip.setAlignment(Qt.AlignCenter)
        eh.addWidget(tip)
        ql.addWidget(self.empty_hint)
        ql.addWidget(self.list, 1)
        self.list.setVisible(False)
        self.stack.addWidget(page_q)

        # 日志页
        page_l = QWidget()
        ll = QVBoxLayout(page_l)
        ll.setContentsMargins(0, 0, 0, 0)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(108)
        self.log_view.setMaximumBlockCount(3000)
        ll.addWidget(self.log_view, 1)
        self.stack.addWidget(page_l)

        qcard.layout.addWidget(self.stack, 1)
        # 空状态是竖排的（插画在上、文字在下），卡片给够高度，
        # 否则窗口一矮，Qt 会把两个控件压到重叠
        qcard.setMinimumHeight(240)
        root.addWidget(qcard, 1)
        self.card_queue = qcard
        self.card_log = qcard
        self._switch_tab(True)

        self.setCentralWidget(central)

        # 窗口最小尺寸交给布局算：内容挤不下时 Qt 会把控件压到重叠
        need_h = root.minimumSize().height()
        self.setMinimumSize(920, max(660, need_h + 6))
        self.resize(980, max(800, need_h + 60))
        self._compact_h = self.height()      # 高级卡收起时的高度

        sb = QStatusBar()
        self.setStatusBar(sb)
        self.dot = PulsingDot()
        self.dot.setVisible(False)
        sb.addPermanentWidget(self.dot)
        self.status_msg = QLabel("就绪")
        self.status_msg.setObjectName("rowMeta")
        sb.addWidget(self.status_msg, 1)
        self.btn_open = FloatButton("打开输出目录", "ghost")
        self.btn_open.setGlyph("folder", INK_2, 13)
        self.btn_open.setFixedHeight(26)
        self.btn_open.setFixedWidth(112)
        self.btn_open.clicked.connect(self.on_open_dir)
        sb.addPermanentWidget(self.btn_open)

        m = self.menuBar().addMenu("文件")
        m.addAction("打开输出目录", self.on_open_dir)
        m.addAction("退出", self.close)
        m2 = self.menuBar().addMenu("帮助")
        m2.addAction("关于", self.on_about)

        QTimer.singleShot(0, self._play_intro)

    def _play_intro(self):
        """入场：窗口渐显 + 各卡片错开淡入。

        淡入走 bilifetch_ui.fade_in（自己盖半透明遮罩），
        不用 QGraphicsOpacityEffect —— 那东西和自绘控件的 QPainter
        会抢同一个绘制设备，界面会画花。
        整窗渐显用 windowOpacity 就够了（顶层窗口专有属性）。
        """
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(340)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._anims.append(anim)

        for i, card in enumerate((self.card_link, self.card_queue)):
            QTimer.singleShot(60 + i * 70, lambda c=card: self._fade_in(c))

    def _fade_in(self, widget):
        fade_in(widget, 280, PAGE)

    def _switch_tab(self, show_queue):
        """队列 / 日志 两个分段。"""
        self.stack.setCurrentIndex(0 if show_queue else 1)
        self.tab_queue.setActive(show_queue)
        self.tab_log.setActive(not show_queue)
        self.btn_stop.setVisible(show_queue)
        self.btn_clear.setVisible(show_queue)
        self.btn_stop.setEnabled(bool(self.worker))      # 没任务时「停止」是灰的
        self.btn_copy.setVisible(not show_queue)
        self.btn_logclear.setVisible(not show_queue)

    def _toggle_adv(self):
        """齿轮按钮：展开/收起高级设置。"""
        on = not self.adv_card.isVisible()
        self.adv_card.setVisible(on)
        self.btn_adv.setText("收起" if on else "高级")
        if on:
            self._fade_in(self.adv_card)
        # 高级卡一进一出，布局所需高度就变了；窗口跟着长/缩，
        # 不然下面的卡片会被压到互相重叠。
        need = self.centralWidget().layout().minimumSize().height() + 60
        if on:
            self.resize(self.width(), max(self.height(), need))
        else:
            self.resize(self.width(), max(need, self._compact_h))

    # ---------------- 事件 ----------------
    def _set_login_state(self, nickname):
        """更新右上角的登录显示：已登录显示胶囊 + 退出登录，否则显示扫码登录。"""
        if nickname:
            self.login_chip.setText("已登录 · %s" % nickname)
            self.login_chip.setVisible(True)
            self.btn_logout.setVisible(True)
            self.btn_login.setVisible(False)
        else:
            self.login_chip.setVisible(False)
            self.btn_logout.setVisible(False)
            self.btn_login.setVisible(True)
            self.btn_login.setText("扫码登录 · 解锁 1080P")
            self.btn_login.setGlyph("play", "#ffffff", 13)
            self.btn_login.setToolTip("用手机 B 站 App 扫码登录，未登录最高只能拿到 480P")

    def on_logout(self):
        """退出登录：清掉本机保存的登录态。"""
        if QMessageBox.question(self, "退出登录",
                                "要退出当前账号吗？下次下载需要重新扫码登录。",
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) != QMessageBox.Yes:
            return
        self.cookie_edit.clear()
        self._set_login_state(None)
        self.status_msg.setText("已退出登录")
        self.append_log("已退出登录")
        self._save_settings()

    def on_login(self):
        """扫码登录，拿到 Cookie 后存下来（高清画质需要）。"""
        dlg = LoginDialog(self)
        dlg.exec_()
        if not dlg.cookie:
            self.status_msg.setText("未登录")
            return
        self.cookie_edit.setText(dlg.cookie)
        self._set_login_state(dlg.nickname or "已登录")
        self.status_msg.setText("已登录：%s" % (dlg.nickname or ""))
        self.append_log("登录成功：%s（高清画质已解锁）" % (dlg.nickname or ""))
        self._save_settings()      # 立刻存盘，别等退出时才写（万一中途崩了会丢登录态）

    def on_pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择保存目录", self.out_edit.text())
        if d:
            self.out_edit.setText(d)

    def on_open_dir(self):
        path = self.out_edit.text()
        if not os.path.isdir(path):
            QMessageBox.warning(self, "目录不存在", path)
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", path])
        else:
            os.startfile(path)

    def on_copy_log(self):
        QApplication.clipboard().setText(self.log_view.toPlainText())
        self.status_msg.setText("日志已复制到剪贴板")

    def on_clear_log(self):
        self.log_view.clear()

    def on_clear(self):
        # 正在收尾时不要在界面线程里等（会卡住窗口）——记下来，停了自动清
        if self._busy():
            self._pending_clear = True
            self.status_msg.setText("正在停止，停完就清空")
            return
        self._do_clear()

    def _do_clear(self):
        self.list.clear()
        self.rows = {}
        self.list.setVisible(False)
        self.empty_hint.setVisible(True)

    def on_stop(self):
        if self.worker:
            self.worker.cancel()
            self._stopping = True
            self.status_msg.setText("正在停止…")
            self.btn_stop.setEnabled(False)

    def on_about(self):
        QMessageBox.about(
            self, "关于 BiliFetch",
            "BiliFetch %s\n\n"
            "B 站视频下载器（图形版）\n"
            "支持番剧 ep/ss、普通视频 av/bv、b23.tv 短链。\n\n"
            "仅供学习研究，请遵守 B 站用户协议。" % core.VERSION)

    def on_browse(self):
        """浏览：读出链接内容 -> 预览 -> 勾选 -> 确认下载。"""
        if self._busy():
            # 上一个任务还在收尾：**不要在界面线程里等**（会卡住整个窗口）。
            # 先记下来，线程一停就自动继续。
            self._pending_browse = True
            self.status_msg.setText("正在停止，马上继续…")
            return
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.information(self, "提示", "先粘贴一个 B 站链接")
            return

        self.btn_start.setEnabled(False)
        self.btn_start.setText("读取中…")
        self.status_msg.setText("正在读取…")
        self._preview_url = url
        # 读取是网络请求，放后台线程 —— 否则窗口在读取期间完全僵住
        self._preview_thread = PreviewThread(
            url, self.cookie_edit.text().strip(),
            self.proxy_edit.text().strip(), self)
        self._preview_thread.done.connect(self._on_preview)
        self._preview_thread.failed.connect(self._on_preview_failed)
        self._preview_thread.start()

    def _on_preview_failed(self, msg):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("浏览…")
        self.status_msg.setText("读取失败")
        QMessageBox.warning(self, "读取失败", msg)

    def _on_preview(self, info):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("浏览…")
        self.status_msg.setText("就绪")
        if not info or not info.get("items"):
            QMessageBox.information(self, "提示", "这个链接里没有可下载的内容")
            return

        url = self._preview_url
        dlg = CollectionDialog(info, url, self)
        dlg.url_edit.setText(url)
        if dlg.exec_() == QDialog.Accepted:
            items = dlg.selected_items()
            if items:
                self._start_download(url, items=items, audio_only=dlg.audio_only)

    def _start_download(self, url, items=None, audio_only=False):
        # 上一个线程可能还在收尾：绝不能覆盖它（运行中的 QThread 被析构 → Qt abort），
        # 也**不能等**（界面会卡住）。记下来，线程一停就自动开始。
        if self.thread is not None:
            self._pending_download = (url, items, audio_only)
            self.status_msg.setText("正在停止，马上开始…")
            return
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads", "BiliFetch")
        out_dir = self.out_edit.text().strip() or default_dir
        # 必须是绝对路径：相对路径会跟着"从 Dock 启动时 CWD=/"这种奇怪状态跑，
        # 存不进去时下面会直接抛异常。
        out_dir = os.path.abspath(os.path.expanduser(out_dir))
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(
                self, "保存目录不可用",
                "没法用这个目录：\n%s\n\n(%s)\n\n已经改用 %s" % (out_dir, e, default_dir))
            out_dir = default_dir
            os.makedirs(out_dir, exist_ok=True)
        self.out_edit.setText(out_dir)

        self.list.clear()
        self.rows = {}
        self.list.setVisible(True)
        self.empty_hint.setVisible(False)
        self.btn_start.setEnabled(False)
        self.btn_start.setText("下载中…")
        self.btn_stop.setEnabled(True)
        self.dot.setVisible(True)
        self.status_msg.setText("下载中…")

        self.worker = Worker(
            url=url, out_dir=out_dir,
            quality=self.quality_box.currentData(),
            all_episodes=False,
            cookie=self.cookie_edit.text().strip(),
            threads=16, proxy=self.proxy_edit.text().strip(),
            items=items, audio_only=audio_only)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log_line.connect(self.append_log)
        self.worker.stage_changed.connect(self.on_stage_changed)
        self.worker.progress_changed.connect(self.on_progress)
        self.worker.item_finished.connect(self.on_item_finished)
        self.worker.item_failed.connect(self.on_item_failed)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.all_done.connect(lambda t=self.thread: self.on_all_done(t))
        # 记住是哪个线程：旧线程收尾时不能把"新任务"的引用清掉
        # （停止后马上重开，旧线程的 finished 回调会把新线程的引用抹掉，
        #   新线程运行中被析构 → Qt 直接 abort）
        self.thread.finished.connect(lambda t=self.thread: self._on_thread_finished(t))
        self.thread.start()

    def append_log(self, text):
        self.log_view.appendPlainText(text)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_stage_changed(self, name, idx, total):
        row = EpisodeRow(idx + 1, name)
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 64))
        self.list.addItem(item)
        self.list.setItemWidget(item, row)
        self.rows[name] = row
        self._fade_in(row)

    def on_progress(self, name, done, total, stage):
        row = self.rows.get(name)
        if not row:
            return
        if not total:
            row.set_stage(stage if stage in ("合并", "转封装") else "处理中",
                          "merge" if stage in ("合并", "转封装") else "run")
            return
        pct = done * 100.0 / total
        pct = max(0.0, min(100.0, pct))     # 夹一下，别让异常值把进度条画歪
        now = time.time()
        prev = self._speed.get(name)
        if prev is None or done < prev[1]:
            # 第一次，或者换了流（视频流 -> 音频流，done 归零）—— 重新起算
            self._speed[name] = (now, done)
            self._ema.pop(name, None)
            readout = "%d%%" % pct
        elif now - prev[0] >= 0.25:
            sp = (done - prev[1]) / (now - prev[0])
            self._speed[name] = (now, done)
            # 指数平滑：短窗口的速度很跳，做个 EMA 让读数稳一点
            prev_ema = self._ema.get(name)
            self._ema[name] = sp if prev_ema is None else prev_ema * 0.65 + sp * 0.35
            readout = "%d%%  %.1f MB/s" % (pct, self._ema[name] / 1e6)
        else:
            readout = None          # 窗口没到，保留上一次的读数，别闪
        if readout:
            row.set_progress(pct, readout)
        else:
            row.set_progress(pct)

    def on_item_finished(self, name, path):
        row = self.rows.get(name)
        if row:
            row.set_done(path)
        self.append_log("  完成：%s" % os.path.basename(path))

    def on_item_failed(self, name, msg):
        row = self.rows.get(name)
        if row:
            row.set_failed(msg)

    def on_cancelled(self, name):
        row = self.rows.get(name)
        if row:
            row.set_stage("已取消", "fail")
        self.status_msg.setText("已取消")
        self.btn_stop.setEnabled(True)

    def on_all_done(self, thread=None):
        if thread is not None and thread is not self.thread:
            return          # 旧任务的收尾，别去动新任务
        self.btn_start.setEnabled(True)
        self.btn_start.setText("浏览…")
        self.btn_stop.setEnabled(False)
        self.dot.setVisible(False)
        if self.status_msg.text() != "已取消":
            self.status_msg.setText("完成")
        # 线程的事件循环还活着（started 触发的槽跑完就空转），
        # 不 quit 掉的话 isRunning() 永远为真 —— 之后就没法再开新任务、也没法清空。
        if self.thread:
            self.thread.quit()

    def _on_thread_finished(self, thread=None):
        """线程真正退出了：把状态清干净，并处理排队的后续操作。"""
        if thread is not None and thread is not self.thread:
            return          # 已经是下一个任务的线程了，别动它
        self.worker = None
        self.thread = None
        self._stopping = False
        self.btn_start.setEnabled(True)
        self.btn_start.setText("浏览…")
        self.btn_stop.setEnabled(False)
        self.dot.setVisible(False)
        if self.status_msg.text() in ("下载中…", "正在停止…"):
            self.status_msg.setText("就绪")

        # 排队的事：清空 / 继续浏览 / 开始下载 —— 都在这里接上
        if self._pending_clear:
            self._pending_clear = False
            self._do_clear()
        if self._pending_download:
            url, items, audio_only = self._pending_download
            self._pending_download = None
            QTimer.singleShot(0, lambda: self._start_download(url, items, audio_only))
        elif self._pending_browse:
            self._pending_browse = False
            QTimer.singleShot(0, self.on_browse)

    def _busy(self):
        """当前是否有任务在跑。"""
        return bool(self.thread and self.thread.isRunning())

    # ---------------- 设置持久化 ----------------
    def _settings_path(self):
        base = os.path.expanduser("~")
        if sys.platform == "darwin":
            base = os.path.join(base, "Library", "Application Support")
        d = os.path.join(base, "BiliFetch")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "settings.json")

    def _load_settings(self):
        default = os.path.join(os.path.expanduser("~"), "Downloads", "BiliFetch")
        try:
            with open(self._settings_path(), encoding="utf-8") as fp:
                s = json.load(fp)
            self.out_edit.setText(s.get("out_dir", default))
            self.cookie_edit.setText(s.get("cookie", ""))
            self.proxy_edit.setText(s.get("proxy", ""))
        except Exception:
            self.out_edit.setText(default)

    def _check_login(self):
        """启动时看看存的 Cookie 还能不能用（放后台线程，别卡住开窗）。"""
        cookie = self.cookie_edit.text().strip()
        if not cookie:
            self._set_login_state(None)
            return
        self._login_thread = LoginCheckThread(
            cookie, self.proxy_edit.text().strip() or None, self)
        self._login_thread.done.connect(self._on_login_checked)
        self._login_thread.start()

    def _on_login_checked(self, state, name):
        """登录态检查结果。

        注意：网络错误（state == "error"）**不能**当成"登录失效"——
        以前这里一失败就把 cookie 清掉，用户于是每次都要重新扫码。
        """
        if state == "ok":
            self._set_login_state(name)
            self.status_msg.setText("已登录：%s" % name)
        elif state == "invalid":
            self.cookie_edit.clear()       # 服务端说确实没登录了，才清
            self._set_login_state(None)
            self.status_msg.setText("登录已失效，点右上角扫码重新登录")
            self._save_settings()
        else:
            # 网络不通，登录态先留着，别把用户踢下线
            self._set_login_state("已登录" if self.cookie_edit.text().strip() else None)
            self.status_msg.setText("网络不通，暂时无法验证登录状态")

    def _save_settings(self):
        try:
            with open(self._settings_path(), "w", encoding="utf-8") as fp:
                json.dump({"out_dir": self.out_edit.text(),
                           "cookie": self.cookie_edit.text(),
                           "proxy": self.proxy_edit.text()}, fp)
        except Exception:
            pass

    def closeEvent(self, event):
        self._save_settings()
        if not self._stop_worker():
            QMessageBox.information(self, "正在退出", "下载线程还没停下来，请稍后再关一次。")
            event.ignore()
            return
        # 登录检查线程也不能在运行中被析构（一样会 abort）
        lt = getattr(self, "_login_thread", None)
        if lt is not None and lt.isRunning():
            lt.wait(3000)
        event.accept()

    def _stop_worker(self):
        """取消下载并等后台线程收尾。返回 True 表示已经干净停下。

        QThread 在运行中被销毁会让 Qt 直接 abort（SIGABRT，崩溃弹窗），
        所以这里必须等到线程真的结束。
        """
        if self.worker:
            self.worker.cancel()
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            if not self.thread.wait(15000):
                return False
        return True


SELFTEST_RESULT = os.path.join(tempfile.gettempdir(), "bilifetch_selftest.txt")


def gui_excepthook(etype, value, tb):
    """槽里抛了异常时的兜底：弹窗报错，别让程序直接消失。

    PyQt5 的默认行为是 qFatal() -> abort()：一个没接住的异常就会把整个
    App 打死，用户看到的是"点一下程序就没了"（崩溃报告里是 SIGABRT，
    栈是 pyqt5_err_print -> QMessageLogger::fatal）。
    装上自己的 excepthook 就能把它变成一个错误弹窗。
    """
    text = "".join(traceback.format_exception(etype, value, tb))
    sys.stderr.write(text)
    try:
        QMessageBox.critical(None, "出错了",
                             "这一步没能完成：\n%s\n\n（完整信息见终端输出，程序还在运行）"
                             % value)
    except Exception:
        pass


def selftest_exit(url, out_dir, wait_ms=4000):
    """打包后的自检：开着界面下到一半就关窗口，看会不会 SIGABRT。

    QThread 在运行中被销毁会让 Qt 直接 abort（进程退出码 134），
    所以这条自检能直接回答"下载中退出到底崩不崩"。
    """
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    win = MainWindow()
    # 自检不能碰用户自己的设置：MainWindow 退出时会 _save_settings()，
    # 把测试用的输出目录写进用户的 settings.json（曾经因此把用户设置写坏过）
    win._settings_path = lambda: os.path.join(
        tempfile.gettempdir(), "bilifetch_selftest_settings.json")
    win.out_edit.setText(out_dir)
    win.show()
    # 万一线程没停下，closeEvent 会弹模态框 —— 自检里不能被它卡住
    QMessageBox.information = staticmethod(lambda *a, **k: None)

    QTimer.singleShot(1200, lambda: win._start_download(url))

    state = {"running": True, "downloading": False}

    def bye():
        # 关之前先确认线程真的在跑（不然这条自检就是空跑）
        state["downloading"] = bool(win.thread and win.thread.isRunning())
        win.close()                       # 走 closeEvent -> _stop_worker
        state["running"] = bool(win.thread and win.thread.isRunning())

    QTimer.singleShot(wait_ms, bye)
    QTimer.singleShot(wait_ms + 30000, app.quit)
    app.exec_()

    ok = state["downloading"] and not state["running"]
    if not state["downloading"]:
        text = "FAIL 下载根本没开始，这条自检不算数\n"
    elif state["running"]:
        text = "FAIL 退出时线程还在跑\n"
    else:
        text = "OK 下载中关窗口，线程干净收尾\n"
    try:
        with open(SELFTEST_RESULT, "w", encoding="utf-8") as fp:
            fp.write(text)
    except OSError:
        pass
    print(text.strip())
    return 0 if ok else 1


def selftest(url, out_dir):
    """打包后的自检：不开界面，真下一次，把结果写到文件里。

    PyInstaller 打包最容易在 SSL 证书、隐藏依赖上翻车，
    所以要能在"打包完的 .app"里真跑一次下载，而不是只看窗口能打开。
    """
    try:
        client = core.BiliClient()
        info = client.resolve(url)
        jobs = core.plan_jobs(client, info)
        name, bvid, cid = jobs[0]
        out = core.download_episode(client, bvid, cid, name, out_dir,
                                     ffmpeg=core.find_executable("ffmpeg"))
        with open(SELFTEST_RESULT, "w", encoding="utf-8") as fp:
            fp.write("OK\n%s\n" % out)
        return 0
    except Exception as e:
        with open(SELFTEST_RESULT, "w", encoding="utf-8") as fp:
            fp.write("FAIL\n%s\n" % e)
        return 1


def selftest_collection(url, out_dir):
    """打包自检：读合集 -> 取第一个视频 -> 真下载一次。"""
    try:
        client = core.BiliClient()
        info = collection.fetch_collection(client, url)
        if not info or not info.get("items"):
            raise RuntimeError("合集里没有视频")
        it = info["items"][0]
        pages = client.pagelist(it["bvid"])
        out = core.download_episode(client, it["bvid"], pages[0]["cid"],
                                     it["title"], out_dir,
                                     ffmpeg=core.find_executable("ffmpeg"))
        with open(SELFTEST_RESULT, "w", encoding="utf-8") as fp:
            fp.write("OK\n%s %s\n%s\n" % (info["title"], len(info["items"]), out))
        return 0
    except Exception as e:
        with open(SELFTEST_RESULT, "w", encoding="utf-8") as fp:
            fp.write("FAIL\n%s\n" % e)
        return 1


def main():
    # 打包自检：--selftest <链接> <输出目录> / --selftest-collection <合集链接> <输出目录>
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        out_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser("~/Downloads")
        sys.exit(selftest(sys.argv[2], out_dir))
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest-login":
        # 生成二维码存成 png：验证打包后 qrcode / PIL 都在（登录功能能不能用的关键）
        try:
            png, key = login_mod.QrLogin().make_qr_png()
            out = os.path.join(tempfile.gettempdir(), "bilifetch_qr.png")
            with open(out, "wb") as fp:
                fp.write(png)
            print("OK %s %d bytes" % (key, len(png)))
            sys.exit(0)
        except Exception as e:
            print("FAIL %s" % e)
            sys.exit(1)
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest-collection":
        out_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser("~/Downloads")
        sys.exit(selftest_collection(sys.argv[2], out_dir))
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest-exit":
        out_dir = sys.argv[3] if len(sys.argv) > 3 else tempfile.gettempdir()
        sys.exit(selftest_exit(sys.argv[2], out_dir))

    app = QApplication(sys.argv)
    app.setApplicationName("BiliFetch")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    sys.excepthook = gui_excepthook
    win = MainWindow()
    win.show()
    # 开窗之后再后台预热 requests（首次导入 170ms）。
    # 不能在开窗前预热：import 是持 GIL 的，放前面只是把等待挪个地方，
    # 窗口反而还是那么久才出来。放在开窗后，用户还在看界面时它自己就加载好了。
    QTimer.singleShot(250, lambda: threading.Thread(target=core.warm_up, daemon=True).start())

    def shutdown():
        # ⌘Q 退出不会触发窗口的 closeEvent，这里补上取消 + 等线程收尾
        # （不等的话 QThread 会在运行中被销毁 → Qt abort → 崩溃弹窗）
        win._stop_worker()
        lt = getattr(win, "_login_thread", None)
        if lt is not None and lt.isRunning():
            lt.wait(3000)

    app.aboutToQuit.connect(shutdown)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
