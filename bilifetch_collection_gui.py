#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合集预览与选择对话框。

用户粘的是合集/列表链接时，先弹这个窗口让他预览清单、勾选要下的视频。
"""

import sys

from PyQt5.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                             QSizePolicy, QVBoxLayout, QWidget)

import bilifetch as core
import bilifetch_collection as col
from bilifetch_ui import Card, SectionTitle   # noqa: E402

THUMB_W, THUMB_H = 96, 54

# 还没停干净的抓图线程先挂在这里：对话框销毁时不能把它们一起带走
# （运行中的 QThread 被析构 → Qt abort），等它们自己结束再删。
_live_threads = []


def _release_thread(t):
    """线程自己跑完了：撤掉引用并删除。"""
    if t in _live_threads:
        _live_threads.remove(t)
    try:
        t.deleteLater()
    except RuntimeError:
        pass

# 读取合集用的客户端，由主窗口在打开对话框前设置（这样能用上 Cookie / 代理）
collection_client = None


class CoverThread(QThread):
    """后台批量抓缩略图。

    用线程池并发抓（一张图 ~200ms，串行抓 91 张要等十几秒），
    抓到的图以 QImage 传回（QPixmap 必须在 GUI 线程里建）。
    """

    WORKERS = 10

    ready = pyqtSignal(int, QImage)

    def __init__(self, urls, parent=None, size=(THUMB_W, THUMB_H)):
        super().__init__(parent)
        self.urls = urls          # [(index, url)]
        self.size = size          # 缩放到多大（后台做，别在界面线程里做）
        self._stop = False

    def stop(self):
        self._stop = True

    def _fetch(self, url):
        import requests
        s = requests.Session()
        s.trust_env = False
        s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"})
        r = s.get(url, timeout=12)
        img = QImage()
        if not img.loadFromData(r.content):
            return None
        # 缩放放后台做：B 站封面原图是 1920x1080，
        # 在界面线程里 scaled() 一次要十几毫秒，91 张图会把界面拖得一顿一顿的
        w0, h0 = self.size
        scaled = img.scaled(w0, h0, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        w, h = scaled.width(), scaled.height()
        return scaled.copy((w - w0) // 2, (h - h0) // 2, w0, h0)

    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        if not self.urls:
            return
        pool = ThreadPoolExecutor(max_workers=self.WORKERS)
        try:
            futures = {pool.submit(self._fetch, url): idx for idx, url in self.urls}
            for fut in as_completed(futures):
                if self._stop:
                    break
                try:
                    img = fut.result()
                except Exception:
                    img = None
                if img is not None:
                    self.ready.emit(futures[fut], img)
        finally:
            # 不用 with：with 退出时会等所有在途请求跑完（每个最长 12 秒），
            # 对话框关了还得等半天。这里不等，让后台自己收尾。
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except TypeError:          # 老版本 Python 没有 cancel_futures
                pool.shutdown(wait=False)


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
        self.check.setChecked(item.get("checked", True))
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
        group = item.get("group") or ""
        bits = []
        if item.get("no"):
            bits.append("第%s集" % item["no"])
        bits.append(col.format_duration(item.get("duration")))
        if item.get("view"):
            bits.append("%s 播放" % col.format_views(item.get("view")))
        if group and group != "正片":
            bits.append(group)
        bits.append(item.get("bvid") or "")
        self.meta = QLabel(" · ".join(bits))
        self.meta.setStyleSheet("color:#9AA2B2; font-size:11px;")
        box.addWidget(self.title)
        box.addWidget(self.meta)
        box.addStretch(1)
        lay.addLayout(box, 1)

    def set_cover(self, img):
        # 缩放已经在后台线程做过了，这里只做 QImage -> QPixmap（很快）
        self.thumb.setPixmap(QPixmap.fromImage(img))
        self.thumb.setStyleSheet("")


class CollectionDialog(QDialog):
    """浏览 / 预览窗口：贴链接 -> 读出清单 -> 勾选 -> 确认下载。

    合集/列表/收藏夹会列出全部视频；单个视频会列出它的各个分 P。
    """

    def __init__(self, info=None, url="", parent=None):
        super().__init__(parent)
        self.info = info or {}
        self.rows = []
        self._items = []      # 原始条目（self.rows 里可能是 None，见 _populate）
        self.setWindowTitle("BiliFetch · 浏览")
        self.setMinimumSize(760, 620)
        self.resize(840, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        # ---- 顶部：链接输入 + 读取 ----
        urlrow = QHBoxLayout()
        urlrow.setSpacing(8)
        self.url_edit = QLineEdit(url)
        self.url_edit.setPlaceholderText("在这里粘贴 B 站链接（合集 / 番剧 / 单个视频都行）")
        self.url_edit.returnPressed.connect(self._reload)
        btn_load = QPushButton("读取")
        btn_load.setObjectName("ghost")
        btn_load.setCursor(Qt.PointingHandCursor)
        btn_load.clicked.connect(self._reload)
        urlrow.addWidget(self.url_edit, 1)
        urlrow.addWidget(btn_load)
        root.addLayout(urlrow)

        # ---- 顶部：封面 + 名称 ----
        head = Card()
        hl = head.layout
        hl.setSpacing(14)
        self.cover = QLabel()
        self.cover.setFixedSize(120, 68)
        self.cover.setStyleSheet("background:#EFF2F7; border-radius:8px;")
        self.cover.setAlignment(Qt.AlignCenter)
        hl.addWidget(self.cover, 0)
        tbox = QVBoxLayout()
        tbox.setSpacing(4)
        t = QLabel(info.get("title") or "合集")
        t.setObjectName("titleLabel")
        t.setStyleSheet("font-size:17px; font-weight:700; color:#1B1F27;")
        t.setWordWrap(True)
        tbox.addWidget(t)
        owner = info.get("owner") or ""
        sub = QLabel("%s · 共 %d 个%s" % (info.get("kind_label", "合集"), len(info.get("items") or []),
                                          "　·　" + owner if owner else ""))
        sub.setObjectName("subLabel")
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
        self.thumb_label = QLabel("")
        self.thumb_label.setObjectName("hint")
        tools.addWidget(self.thumb_label)
        self.chk_extra = QCheckBox("含花絮/二创")
        self.chk_extra.setToolTip("番剧除了正片还有 PV、花絮、二创解析等分区")
        self.chk_extra.toggled.connect(self._toggle_extra)
        tools.addWidget(self.chk_extra)
        # 只下音频放这里：属于"这次要什么"的选项，不该占主界面
        self.chk_audio = QCheckBox("只下音频")
        self.chk_audio.setToolTip("只保存音频（m4a），不下载视频画面")
        tools.addWidget(self.chk_audio)
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
        items = self.info.get("items") or []
        self._populate(items)
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
        self.ok = QPushButton("确认下载")
        self.ok.setObjectName("primary")
        self.ok.setCursor(Qt.PointingHandCursor)
        self.ok.setMinimumWidth(130)
        self.ok.clicked.connect(self.accept)
        bottom.addWidget(cancel)
        bottom.addWidget(self.ok)
        root.addLayout(bottom)

        for row in self.rows:
            if row is not None:
                row.check.stateChanged.connect(self._update_count)
        self._update_count()

        # 封面 + 缩略图后台加载
        self._cover_thread = None
        self._live_extra_threads = []
        QTimer.singleShot(0, self._load_covers)

    def _populate(self, items):
        """按条目建列表。

        花絮/二创默认是折叠的，它们的**行控件先不建** ——
        一集 101 条全建要 700 多个控件、160ms，窗口打开那一下明显发涩；
        等用户真展开时再补建。
        """
        self.list.clear()
        self.rows = []
        self._items = list(items)
        # 建行控件期间关掉刷新：setItemWidget 每调一次都要重排一次列表，
        # 开着刷新会白白重排十几遍（一次 4~5ms，几十行就是上百毫秒）
        self.list.setUpdatesEnabled(False)
        try:
            self._fill_rows(items)
        finally:
            self.list.setUpdatesEnabled(True)

    def _fill_rows(self, items):
        for i, it in enumerate(items):
            itw = QListWidgetItem()
            itw.setSizeHint(QSize(0, 80))
            self.list.addItem(itw)
            if it.get("extra"):
                self.rows.append(None)          # 花絮：等展开时再建
                self.list.setRowHidden(i, True)
            else:
                row = ItemRow(it, i)
                self.list.setItemWidget(itw, row)
                self.rows.append(row)
                row.check.stateChanged.connect(self._update_count)

    def _build_extra_rows(self):
        """展开花絮时，把它们的行控件补建出来。"""
        built = False
        for i, it in enumerate(self._items):
            if it.get("extra") and self.rows[i] is None:
                row = ItemRow(it, i)
                row.check.stateChanged.connect(self._update_count)
                self.rows[i] = row
                self.list.setItemWidget(self.list.item(i), row)
                built = True
        return built

    # ---------- 重新读取 ----------
    def _reload(self):
        """按当前链接重新读清单。"""
        url = self.url_edit.text().strip()
        if not url:
            return
        self.setCursor(Qt.WaitCursor)
        try:
            info = collection.fetch_preview(collection_client, url)
        except Exception as e:
            self.setCursor(Qt.ArrowCursor)
            QMessageBox.warning(self, "读取失败", str(e))
            return
        self.setCursor(Qt.ArrowCursor)
        if not info or not info.get("items"):
            QMessageBox.information(self, "提示", "这个链接里没有可下载的内容")
            return
        self.info = info
        self._rebuild()

    def _rebuild(self):
        """按新 info 重建列表。"""
        info = self.info
        self.setWindowTitle("BiliFetch · 浏览 · %s" % (info.get("title") or ""))
        t = self.findChild(QLabel, "titleLabel")
        if t:
            t.setText(info.get("title") or "")
        s = self.findChild(QLabel, "subLabel")
        if s:
            owner = info.get("owner") or ""
            s.setText("%s · 共 %d 个%s" % (info.get("kind_label", "合集"),
                                          len(info.get("items") or []),
                                          "　·　" + owner if owner else ""))
        self._populate(info.get("items") or [])
        for row in self.rows:
            if row is not None:
                row.check.stateChanged.connect(self._update_count)
        self._update_count()
        self._load_covers()

    # ---------- 封面 ----------
    def _load_covers(self):
        items = self.info.get("items") or []
        cover = self.info.get("cover") or (items[0].get("pic") if items else "")
        if cover:
            self._cover_thread = CoverThread(
                [(-1, cover)], self, size=(self.cover.width(), self.cover.height()))
            self._cover_thread.ready.connect(self._on_cover)
            self._cover_thread.start()
        urls = [(i, it.get("pic")) for i, it in enumerate(items)
                if it.get("pic") and not it.get("extra")]
        if urls:
            self._thumb_thread = CoverThread(urls[:120], self)
            self._thumb_thread.ready.connect(self._on_cover)
            self._thumb_thread.start()

    def _on_cover(self, idx, img):
        # 图已经在后台缩放好了，这里只做 QImage -> QPixmap
        if idx < 0:
            self.cover.setPixmap(QPixmap.fromImage(img))
            self.cover.setStyleSheet("")
        elif idx < len(self.rows) and self.rows[idx] is not None:
            self.rows[idx].set_cover(img)
            self._update_thumb_count()

    def _update_thumb_count(self):
        """缩略图加载进度提示。"""
        total = sum(1 for it in self._items if not it.get("extra"))
        got = sum(1 for it, r in zip(self._items, self.rows)
                  if not it.get("extra") and r is not None
                  and r.thumb.pixmap() is not None and not r.thumb.pixmap().isNull())
        self.thumb_label.setText("缩略图 %d/%d" % (got, total) if got < total else "")

    # ---------- 选择 ----------
    def _toggle_extra(self, on):
        """花絮/二创分区默认折叠，勾上才显示。"""
        if on:
            self._build_extra_rows()      # 行控件这时才建
            self._load_extra_covers()
        for i, it in enumerate(self._items):
            if it.get("extra"):
                self.list.setRowHidden(i, not on)
        self._update_count()

    def _load_extra_covers(self):
        """展开花絮后，补抓它们的缩略图。"""
        urls = [(i, it.get("pic")) for i, it in enumerate(self._items)
                if it.get("extra") and it.get("pic") and self.rows[i] is not None]
        if not urls:
            return
        t = CoverThread(urls[:120], self)
        t.ready.connect(self._on_cover)
        t.finished.connect(lambda th=t: _release_thread(th))
        self._live_extra_threads.append(t)
        t.start()

    def _extra_count(self):
        return sum(1 for it in self._items if it.get("extra"))

    def _visible_rows(self):
        kw = self.search.text().strip().lower()
        out = []
        for i, it in enumerate(self._items):
            if not kw or kw in (it.get("title") or "").lower() or kw in (it.get("bvid") or "").lower():
                out.append((i, it))
        return out

    def _filter(self):
        vis = self._visible_rows()
        keep = {j for j, _ in vis}
        for i in range(len(self._items)):
            self.list.setRowHidden(i, i not in keep)
        self._update_count()

    def _select_all(self):
        """全选：作用于当前可见的条目（花絮折叠时不勾它）。"""
        for i, row in enumerate(self.rows):
            if row is not None and not self.list.isRowHidden(i):
                row.check.setChecked(True)

    def _select_none(self):
        for i, row in enumerate(self.rows):
            if row is not None and not self.list.isRowHidden(i):
                row.check.setChecked(False)

    def _invert(self):
        for i, row in enumerate(self.rows):
            if row is not None and not self.list.isRowHidden(i):
                row.check.setChecked(not row.check.isChecked())

    def _update_count(self):
        vis = [i for i in range(len(self._items)) if not self.list.isRowHidden(i)]
        n = sum(1 for i in vis
                if self.rows[i] is not None and self.rows[i].check.isChecked())
        extra = self._extra_count()
        txt = "已选 %d / %d 个" % (n, len(vis))
        if extra and not self.chk_extra.isChecked():
            txt += "（另有 %d 个花絮未显示）" % extra
        self.counter.setText(txt)
        self.ok.setText("确认下载 %d 个" % n if n else "请先选择")
        self.ok.setEnabled(n > 0)

    # ---------- 结果 ----------
    def selected_items(self):
        return [self._items[i] for i, r in enumerate(self.rows)
                if r is not None and r.check.isChecked() and not self.list.isRowHidden(i)]

    @property
    def audio_only(self):
        """只下音频（在浏览窗口里勾）。"""
        return self.chk_audio.isChecked()

    def _stop_threads(self):
        """停掉后台抓图线程。

        关键：抓图线程可能正卡在网络请求上（超时 12 秒），
        等 1.5 秒未必能停干净。**运行中的 QThread 被析构会让 Qt 直接 abort**，
        所以等不干净时要把它从父子关系里摘出来、并且 Python 侧继续持有引用，
        等它自己跑完再删 —— 提前删（GC）同样会炸。
        """
        threads = [getattr(self, name, None) for name in ("_cover_thread", "_thumb_thread")]
        threads += list(getattr(self, "_live_extra_threads", []))
        for t in threads:
            if t is None:
                continue
            t.stop()
            if t.wait(1500):
                t.deleteLater()
            else:
                t.setParent(None)
                _live_threads.append(t)
                t.finished.connect(lambda th=t: _release_thread(th))
            setattr(self, name, None)

    def done(self, r):
        self._stop_threads()
        super().done(r)

    def closeEvent(self, event):
        self._stop_threads()
        super().closeEvent(event)
