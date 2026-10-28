#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享的视觉组件与配色（主窗口和浏览窗口共用，保证两处风格一致）。

单独拆一个模块是为了避开循环导入：
bilifetch_gui 依赖 bilifetch_collection_gui，反过来就不行了。
"""

import os

from PyQt5.QtCore import QPoint, QRectF, Qt, QTimer
from PyQt5.QtGui import (QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPixmap)
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

HERE = os.path.dirname(os.path.abspath(__file__))

PINK = "#FB7299"
PINK_D = "#F0628B"
BLUE = "#23ADE5"
BLUE_D = "#1C96CC"
INK = "#1B1F27"        # 主文字
INK_2 = "#5B6373"      # 次文字
INK_3 = "#9AA2B2"      # 弱文字
PAGE = "#F4F6FA"       # 页面底色
CARD = "#FFFFFF"
LINE = "#E7EBF3"
TRACK = "#EDF0F6"
DARK = "#121722"       # 日志面板
DARK_FG = "#B7C2D6"

def make_icon(kind, color, size=16):
    """用 QPainter 画几个简单图标，省得引 SVG 资源。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    s = size / 16.0
    if kind == "folder":
        p.drawPath(QPainterPath())  # 占位，下面用折线画
        p.drawLine(int(2 * s), int(5 * s), int(7 * s), int(5 * s))
        p.drawLine(int(7 * s), int(5 * s), int(8.5 * s), int(7 * s))
        p.drawLine(int(8.5 * s), int(7 * s), int(14 * s), int(7 * s))
        p.drawLine(int(14 * s), int(7 * s), int(12 * s), int(12.5 * s))
        p.drawLine(int(12 * s), int(12.5 * s), int(4 * s), int(12.5 * s))
        p.drawLine(int(4 * s), int(12.5 * s), int(2 * s), int(5 * s))
    elif kind == "film":
        p.drawRoundedRect(QRectF(2 * s, 3.5 * s, 12 * s, 9 * s), 1.6 * s, 1.6 * s)
        for i in (5, 9):
            p.drawPoint(int(i * s), int(5.2 * s))
            p.drawPoint(int(i * s), int(10.8 * s))
    elif kind == "play":
        path = QPainterPath()
        path.moveTo(6 * s, 4.5 * s)
        path.lineTo(12 * s, 8 * s)
        path.lineTo(6 * s, 11.5 * s)
        path.closeSubpath()
        p.setBrush(QColor(color))
        p.drawPath(path)
    elif kind == "stop":
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(4.5 * s, 4.5 * s, 7 * s, 7 * s), 1.4 * s, 1.4 * s)
    elif kind == "trash":
        p.drawLine(int(3 * s), int(5 * s), int(13 * s), int(5 * s))
        p.drawLine(int(6 * s), int(3 * s), int(10 * s), int(3 * s))
        p.drawRoundedRect(QRectF(4.5 * s, 5 * s, 7 * s, 8 * s), 1.2 * s, 1.2 * s)
    elif kind == "copy":
        p.drawRoundedRect(QRectF(5.5 * s, 5.5 * s, 8 * s, 8 * s), 1.4 * s, 1.4 * s)
        p.drawPolyline([QPoint(int(3.5 * s), int(10.5 * s)), QPoint(int(3.5 * s), int(3.5 * s)),
                        QPoint(int(10.5 * s), int(3.5 * s))])
    elif kind == "gear":
        p.drawEllipse(QRectF(5.5 * s, 5.5 * s, 5 * s, 5 * s))
    p.end()
    return pm

class Card(QFrame):
    """白色圆角卡片。

    自绘而不是靠 QSS：QSS 画不出柔和投影，而投影是"卡片浮起来"的关键。
    （用几层递减透明度的圆角矩形模拟模糊，比 QGraphicsDropShadowEffect 轻，
    也不会和淡入动画抢同一个 graphicsEffect 槽位。）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 18, 20, 18)
        self.layout.setSpacing(12)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        # 柔和投影：越靠外越淡，模拟高斯模糊
        p.setPen(Qt.NoPen)
        for i in range(7, 0, -1):
            sh = r.adjusted(-i * 0.4, -i * 0.2 + i * 0.8, i * 0.4, -i * 0.2 + i * 0.8)
            p.setBrush(QColor(40, 50, 80, 4))
            p.drawRoundedRect(sh, 16 + i * 0.5, 16 + i * 0.5)
        # 卡面
        p.setBrush(QColor(255, 255, 255))
        p.setPen(QPen(QColor(230, 235, 244), 1))
        p.drawRoundedRect(r, 16, 16)
        p.end()

    def add_title(self, text):
        t = SectionTitle(text)
        self.layout.addWidget(t)
        return t


class FadeOverlay(QWidget):
    """淡入用的遮罩：盖在目标控件上，用背景色盖住，alpha 渐变到 0。

    为什么不用 QGraphicsOpacityEffect：
    给自绘控件套 effect，Qt 会把控件重定向到 effect 自己的 pixmap，
    控件 paintEvent 里的 QPainter 和 effect 抢同一个绘制设备，
    控制台会刷 "A paint device can only be painted by one painter at a time"，
    实际也会画花。这里改成自己画一层半透明色块，干净。
    """

    def __init__(self, parent, color=PAGE):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._color = QColor(color)
        self._alpha = 255

    def paintEvent(self, e):
        if self._alpha <= 0:
            return
        p = QPainter(self)
        c = QColor(self._color)
        c.setAlpha(self._alpha)
        p.fillRect(self.rect(), c)
        p.end()

    def set_alpha(self, a):
        self._alpha = max(0, min(255, int(a)))
        self.update()


def fade_in(widget, duration=280, color=PAGE):
    """让 widget 从背景色淡入。返回定时器（控件销毁时自动跟着没）。"""
    old = getattr(widget, "_fade_overlay", None)
    if old is not None:
        old.setParent(None)
        old.deleteLater()

    ov = FadeOverlay(widget, color)
    ov.setGeometry(widget.rect())
    ov.show()
    ov.raise_()
    widget._fade_overlay = ov

    step = 16
    n = max(1, int(duration / step))
    state = {"i": 0}

    def tick():
        state["i"] += 1
        t = min(1.0, state["i"] / n)
        e = 1.0 - (1.0 - t) ** 3          # OutCubic，和其它动画一致
        ov.set_alpha(255 * (1.0 - e))
        if state["i"] >= n:
            timer.stop()
            ov.setParent(None)
            ov.deleteLater()
            widget._fade_overlay = None

    timer = QTimer(widget)
    timer.setInterval(step)
    timer.timeout.connect(tick)
    timer.start()
    return timer

class SectionTitle(QWidget):
    """带小色条的分区标题。"""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        bar = QLabel()
        bar.setFixedSize(3, 13)
        bar.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                          "stop:0 %s, stop:1 %s); border-radius: 1px;" % (PINK, BLUE))
        lbl = QLabel(text)
        lbl.setObjectName("secTitle")
        lay.addWidget(bar)
        lay.addWidget(lbl)
        lay.addStretch(1)

class IconLabel(QWidget):
    """图标 + 文字的小标签。"""

    def __init__(self, text, icon_kind=None, color=INK_3, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        if icon_kind:
            ic = QLabel()
            ic.setPixmap(make_icon(icon_kind, color, 15))
            ic.setFixedWidth(15)
            lay.addWidget(ic)
        self.label = QLabel(text)
        self.label.setObjectName("fieldLbl")
        lay.addWidget(self.label)
        lay.addStretch(1)



# ---------------------------------------------------------------- 狐狸
FOX_ORANGE = "#F0823A"
FOX_DARK = "#DD6A2A"
FOX_CREAM = "#FFF6EC"
FOX_NOSE = "#F2748A"
FOX_EYE = "#3A2A20"


def draw_fox(p, x, y, size):
    """画一个简约的狐狸头（纯矢量，任何尺寸都清晰）。

    和 App 图标是同一只狐狸。p 是已开启抗锯齿的 QPainter。
    """
    s = size / 100.0
    p.save()
    p.translate(x, y)
    p.setRenderHint(QPainter.Antialiasing)

    # 耳朵（两个三角）
    for sign in (-1, 1):
        ear = QPainterPath()
        if sign < 0:
            ear.moveTo(24 * s, 40 * s)
            ear.lineTo(14 * s, 8 * s)
            ear.lineTo(44 * s, 26 * s)
        else:
            ear.moveTo(76 * s, 40 * s)
            ear.lineTo(86 * s, 8 * s)
            ear.lineTo(56 * s, 26 * s)
        ear.closeSubpath()
        p.setBrush(QBrush(QColor(FOX_ORANGE)))
        p.setPen(Qt.NoPen)
        p.drawPath(ear)
        inner = QPainterPath()
        if sign < 0:
            inner.moveTo(27 * s, 37 * s)
            inner.lineTo(21 * s, 17 * s)
            inner.lineTo(38 * s, 28 * s)
        else:
            inner.moveTo(73 * s, 37 * s)
            inner.lineTo(79 * s, 17 * s)
            inner.lineTo(62 * s, 28 * s)
        inner.closeSubpath()
        p.setBrush(QBrush(QColor(FOX_DARK)))
        p.drawPath(inner)

    # 脸
    head = QPainterPath()
    head.addEllipse(QRectF(20 * s, 26 * s, 60 * s, 56 * s))
    p.setBrush(QBrush(QColor(FOX_ORANGE)))
    p.setPen(Qt.NoPen)
    p.drawPath(head)

    # 口鼻（白）
    muzzle = QPainterPath()
    muzzle.moveTo(50 * s, 92 * s)
    muzzle.lineTo(31 * s, 60 * s)
    muzzle.quadTo(50 * s, 46 * s, 69 * s, 60 * s)
    muzzle.closeSubpath()
    p.setBrush(QBrush(QColor(FOX_CREAM)))
    p.drawPath(muzzle)

    # 眼睛
    p.setBrush(QBrush(QColor(FOX_EYE)))
    p.drawEllipse(QRectF(33 * s, 48 * s, 9 * s, 11 * s))
    p.drawEllipse(QRectF(58 * s, 48 * s, 9 * s, 11 * s))
    # 高光
    p.setBrush(QBrush(QColor(255, 255, 255)))
    p.drawEllipse(QRectF(35 * s, 49 * s, 3.4 * s, 4 * s))
    p.drawEllipse(QRectF(60 * s, 49 * s, 3.4 * s, 4 * s))
    # 鼻子
    p.setBrush(QBrush(QColor(FOX_NOSE)))
    p.drawEllipse(QRectF(45.5 * s, 58 * s, 9 * s, 7 * s))
    p.restore()
