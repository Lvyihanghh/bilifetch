#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合集预览与选择对话框。

用户粘的是合集/列表链接时，先弹这个窗口让他预览清单、勾选要下的视频。
"""

import sys

from PyQt5.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QPushButton, QScrollArea,
                             QSizePolicy, QVBoxLayout, QWidget)

import bilifetch_collection as col

THUMB_W, THUMB_H = 96, 54


class CoverThread(QThread):
    """后台批量抓缩略图。抓到的图以 QImage 传回（QPixmap 必须在 GUI 线程里建）。"""

    ready = pyqtSignal(int, QImage)

    def __init__(self, urls, parent=None):
        super().__init__(parent)
        self.urls = urls          # [(index, url)]
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        import requests
        s = requests.Session()
        s.trust_env = False
        s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"})
        for idx, url in self.urls:
            if self._stop:
                break
            try:
                r = s.get(url, timeout=12)
                img = QImage()
                if img.loadFromData(r.content):
                    self.ready.emit(idx, img)
            except Exception:
                pass


class ItemRow(QWidget):
    """清单里的一行：勾选框 + 缩略图 + 标题 + 时长/播放量。"""

    def __init__(self, item, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.item = item
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 12, 8)
        lay.setSpacing(12)

        self.check = QCheckBox()
        self.check.setChecked(True)
        self.check.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.check, 0, Qt.AlignTop)

        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        self.thumb.setStyleSheet("background:#EFF2F7; border-radius:6px;")
        self.thumb.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.thumb, 0, Qt.AlignTop)

        box = QVBoxLayout()
        box.setSpacing(3)
        self.title = QLabel(item.get("title") or item.get("bvid"))
        self.title.setWordWrap(True)
        self.title.setStyleSheet("color:#22252B; font-size:13px;")
        meta = "%s · %s 播放" % (col.format_duration(item.get("duration")),
                                 col.format_views(item.get("view")))
        self.meta = QLabel(meta + "   " + item.get("bvid"))
        self.meta.setStyleSheet("color:#9AA2B2; font-size:11px;")
        box.addWidget(self.title)
        box.addWidget(self.meta)
        box.addStretch(1)
        lay.addLayout(box, 1)

    def set_cover(self, img):
        scaled = img.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        w, h = scaled.width(), scaled.height()
        scaled = scaled.copy((w - THUMB_W) // 2, (h - THUMB_H) // 2, THUMB_W, THUMB_H)
        self.thumb.setPixmap(QPixmap.fromImage(scaled))
        self.thumb.setStyleSheet("")


class CollectionDialog(QDialog):
    """合集预览窗口：列出所有视频，勾选后下载。"""

    def __init__(self, info, parent=None):
        super().__init__(parent)
        self.info = info
        self.rows = []
        self.setWindowTitle("BiliFetch · 选择要下载的视频")
        self.setMinimumSize(760, 620)
        self.resize(820, 700)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        # ---- 顶部：封面 + 名称 ----
        head = QFrame()
        head.setObjectName("card")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(16, 14, 16, 14)
        hl.setSpacing(14)
        self.cover = QLabel()
        self.cover.setFixedSize(120, 68)
        self.cover.setStyleSheet("background:#EFF2F7; border-radius:8px;")
        self.cover.setAlignment(Qt.AlignCenter)
        hl.addWidget(self.cover, 0)
        tbox = QVBoxLayout()
        tbox.setSpacing(4)
        t = QLabel(info.get("title") or "合集")
        t.setStyleSheet("font-size:17px; font-weight:700; color:#1B1F27;")
        t.setWordWrap(True)
        tbox.addWidget(t)
        sub = QLabel("%s · 共 %d 个视频" % (info.get("kind_label", "合集"), len(info.get("items") or [])))
        sub.setStyleSheet("font-size:12px; color:#9AA2B2;")
        tbox.addWidget(sub)
        if info.get("desc"):
            d = QLabel(info["desc"][:120])
            d.setStyleSheet("font-size:12px; color:#7A8394;")
            d.setWordWrap(True)
            tbox.addWidget(d)
        tbox.addStretch(1)
        hl.addLayout(tbox, 1)
        root.addWidget(head)

        # ---- 工具条：搜索 + 全选/反选 ----
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索标题…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        tools.addWidget(self.search, 1)
        for text, slot in (("全选", self._select_all), ("全不选", self._select_none),
                           ("反选", self._invert)):
            b = QPushButton(text)
            b.setObjectName("ghost")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            tools.addWidget(b)
        root.addLayout(tools)

        # ---- 清单 ----
        self.list = QListWidget()
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setStyleSheet(
            "QListWidget{background:#FFFFFF;border:1px solid #E7EBF3;border-radius:12px;}"
            "QScrollBar:vertical{background:#F4F6FA;width:10px;border-radius:5px;margin:2px;}"
            "QScrollBar::handle:vertical{background:#C8D0DE;border-radius:4px;min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}")
        items = info.get("items") or []
        for i, it in enumerate(items):
            row = ItemRow(it, i)
            itw = QListWidgetItem()
            itw.setSizeHint(QSize(0, 80))
            self.list.addItem(itw)
            self.list.setItemWidget(itw, row)
            self.rows.append(row)
        root.addWidget(self.list, 1)

        # ---- 底部 ----
        bottom = QHBoxLayout()
        self.counter = QLabel()
        self.counter.setStyleSheet("color:#7A8394; font-size:12px;")
        bottom.addWidget(self.counter)
        bottom.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("ghost")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("下载选中的")
        self.ok.setObjectName("primary")
        self.ok.setCursor(Qt.PointingHandCursor)
        self.ok.setMinimumWidth(130)
        self.ok.clicked.connect(self.accept)
        bottom.addWidget(cancel)
        bottom.addWidget(self.ok)
        root.addLayout(bottom)

        for row in self.rows:
            row.check.stateChanged.connect(self._update_count)
        self._update_count()

        # 封面 + 缩略图后台加载
        self._cover_thread = None
        QTimer.singleShot(0, self._load_covers)

    # ---------- 封面 ----------
    def _load_covers(self):
        items = self.info.get("items") or []
        cover = self.info.get("cover") or (items[0].get("pic") if items else "")
        if cover:
            self._cover_thread = CoverThread([(-1, cover)], self)
            self._cover_thread.ready.connect(self._on_cover)
            self._cover_thread.start()
        urls = [(i, it.get("pic")) for i, it in enumerate(items) if it.get("pic")]
        if urls:
            self._thumb_thread = CoverThread(urls[:120], self)
            self._thumb_thread.ready.connect(self._on_cover)
            self._thumb_thread.start()

    def _on_cover(self, idx, img):
        if idx < 0:
            scaled = img.scaled(self.cover.width(), self.cover.height(),
                                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            w, h = scaled.width(), scaled.height()
            scaled = scaled.copy((w - self.cover.width()) // 2, (h - self.cover.height()) // 2,
                                 self.cover.width(), self.cover.height())
            self.cover.setPixmap(QPixmap.fromImage(scaled))
            self.cover.setStyleSheet("")
        elif idx < len(self.rows):
            self.rows[idx].set_cover(img)

    # ---------- 选择 ----------
    def _visible_rows(self):
        kw = self.search.text().strip().lower()
        out = []
        for i, row in enumerate(self.rows):
            if not kw or kw in (row.item.get("title") or "").lower() or kw in row.item.get("bvid", "").lower():
                out.append((i, row))
        return out

    def _filter(self):
        vis = self._visible_rows()
        for i, row in enumerate(self.rows):
            self.list.setRowHidden(i, i not in {j for j, _ in vis})
        self._update_count()

    def _select_all(self):
        for _, row in self._visible_rows():
            row.check.setChecked(True)

    def _select_none(self):
        for _, row in self._visible_rows():
            row.check.setChecked(False)

    def _invert(self):
        for _, row in self._visible_rows():
            row.check.setChecked(not row.check.isChecked())

    def _update_count(self):
        n = sum(1 for r in self.rows if r.check.isChecked())
        self.counter.setText("已选 %d / %d 个" % (n, len(self.rows)))
        self.ok.setText("下载选中的 %d 个" % n if n else "请先选择")
        self.ok.setEnabled(n > 0)

    # ---------- 结果 ----------
    def selected_items(self):
        return [r.item for r in self.rows if r.check.isChecked()]

    def _stop_threads(self):
        for name in ("_cover_thread", "_thumb_thread"):
            t = getattr(self, name, None)
            if t is not None:
                t.stop()
                t.wait(1500)
                setattr(self, name, None)

    def done(self, r):
        self._stop_threads()
        super().done(r)

    def closeEvent(self, event):
        self._stop_threads()
        super().closeEvent(event)
