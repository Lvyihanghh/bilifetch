#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 站扫码登录对话框。"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout)

import bilifetch_login as login_mod


class LoginDialog(QDialog):
    """显示二维码，轮询登录状态，成功后把 cookie 交给调用方。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录 B 站")
        self.setFixedSize(360, 500)
        self.cookie = ""
        self.nickname = ""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._login = login_mod.QrLogin()

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        tip = QLabel("用手机「哔哩哔哩」App 扫下方二维码")
        tip.setAlignment(Qt.AlignCenter)
        tip.setStyleSheet("font-size:14px; font-weight:600; color:#1B1F27;")
        root.addWidget(tip)

        self.qr = QLabel()
        self.qr.setFixedSize(260, 260)
        self.qr.setAlignment(Qt.AlignCenter)
        self.qr.setStyleSheet("background:#FFFFFF; border:1px solid #E7EBF3; border-radius:12px;")
        root.addWidget(self.qr, 0, Qt.AlignHCenter)

        self.status = QLabel("正在获取二维码…")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setStyleSheet("font-size:12px; color:#7A8394;")
        root.addWidget(self.status)

        self.btn_refresh = QPushButton("刷新二维码")
        self.btn_refresh.setObjectName("ghost")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._new_qr)
        root.addWidget(self.btn_refresh)

        root.addStretch(1)
        self._new_qr()

    def _new_qr(self):
        self.status.setText("正在获取二维码…")
        self.btn_refresh.setEnabled(False)
        try:
            png, key = self._login.make_qr_png()
            pm = QPixmap()          # loadFromData 返回 bool，得自己建 QPixmap
            if not pm.loadFromData(png):
                raise RuntimeError("二维码图片解码失败")
            # 二维码原图有 400 多像素，而标签只有 260pt —— 不缩放的话 QLabel
            # 会按原尺寸画、然后被裁掉一截，手机扫到的是残缺码（表现为"扫码没反应"）。
            # 这里按 2x 缩到刚好填满标签，Retina 上也不糊。
            dpr = 2.0
            pm = pm.scaled(int(self.qr.width() * dpr), int(self.qr.height() * dpr),
                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            self.qr.setPixmap(pm)
            self.status.setText("等待扫码…")
            self._timer.start(2000)
        except Exception as e:
            self.status.setText("获取二维码失败：%s" % e)
        self.btn_refresh.setEnabled(True)

    def _poll(self):
        try:
            state, msg, cookie = self._login.poll()
        except Exception as e:
            self._timer.stop()
            self.status.setText("网络错误：%s" % e)
            return
        if state == login_mod.DONE:
            self._timer.stop()
            self.cookie = cookie or ""
            self.nickname = self._login.whoami(self.cookie) or "已登录"
            self.status.setText("✓ 登录成功：%s" % self.nickname)
            self.qr.setText("✓")
            self.btn_refresh.setText("完成")
            self.btn_refresh.setEnabled(False)
            QTimer.singleShot(900, self.accept)
        elif state == login_mod.SCANNED:
            self.status.setText("已扫码，请在手机上点「确认登录」")
        elif state == login_mod.WAITING:
            self.status.setText("等待扫码…")
        elif state == login_mod.EXPIRED:
            self._timer.stop()
            self.status.setText("二维码已失效，点「刷新二维码」重试")
        else:
            self.status.setText(msg)

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
