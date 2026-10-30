#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 站扫码登录。

用官方的二维码登录接口：先取一个二维码，手机 B 站 App 扫一下确认，
再把拿到的 SESSDATA 等 cookie 交给下载器，就能下到 1080P 及以上。

接口：
  GET  https://passport.bilibili.com/x/passport-login/web/qrcode/generate
  GET  https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key=...

轮询返回的 data.code：
  0     成功
  86101 未扫码
  86090 已扫码未确认
  86038 二维码已失效
"""

import time
from urllib.parse import unquote


GEN_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# 登录后 B 站会下发的 cookie
KNOWN_COOKIES = ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5",
                 "sid", "buvid3", "buvid4", "b_nut", "buvid_fp", "b_lsid")

# 轮询结果
WAITING = "waiting"      # 未扫码
SCANNED = "scanned"      # 已扫码，等用户确认
DONE = "done"            # 成功
EXPIRED = "expired"      # 二维码失效
FAILED = "failed"


def _req():
    """requests 延迟导入（见 bilifetch.py 里同样的说明）。"""
    import requests
    return requests


class QrLogin:
    """一次二维码登录会话。"""

    def __init__(self, proxy=None):
        self.session = _req().Session()
        self.session.trust_env = False      # 别走系统代理，见 README 里的说明
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
        self.session.headers.update({
            "User-Agent": UA,
            "Referer": "https://passport.bilibili.com/login",
            "Origin": "https://passport.bilibili.com",
        })
        self.qrcode_key = None

    # ---------------- 二维码 ----------------
    def make_qr_png(self):
        """申请一个二维码，返回 (png bytes, qrcode_key)。"""
        r = self.session.get(GEN_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError("取二维码失败：%s" % data.get("message"))
        self.qrcode_key = data["data"]["qrcode_key"]
        url = data["data"]["url"]

        import qrcode
        img = qrcode.make(url, box_size=8, border=2)
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), self.qrcode_key

    # ---------------- 轮询 ----------------
    def poll(self):
        """轮询一次。返回 (状态, 说明, cookie串)。成功时 cookie 串非空。"""
        if not self.qrcode_key:
            return FAILED, "还没生成二维码", None
        r = self.session.get(POLL_URL,
                            params={"source": "main-web", "qrcode_key": self.qrcode_key},
                            timeout=15)
        r.raise_for_status()
        data = r.json().get("data") or {}
        code = data.get("code")
        msg = data.get("message") or ""

        if code == 0:
            cookie = self._collect_cookies(data.get("set_cookie") or "")
            return DONE, "登录成功", cookie
        if code == 86101:
            return WAITING, "等待扫码…", None
        if code == 86090:
            return SCANNED, "已扫码，请在手机上确认", None
        if code == 86038:
            return EXPIRED, "二维码已失效，请刷新", None
        return FAILED, msg or ("登录失败：%s" % code), None

    def _collect_cookies(self, set_cookie):
        """把登录后的 cookie 收成一行 Cookie 串。

        两个来源都取：轮询返回的 set_cookie（URL 编码），
        以及会话 cookie jar 里 B 站自己下发的。
        """
        pairs = {}
        if set_cookie:
            for part in unquote(set_cookie).split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    if k:
                        pairs[k.strip()] = v.strip()
        # 登录成功时服务端会下发 DedeUserID / DedeUserID__ckMd5 / SESSDATA / bili_jct
        for c in self.session.cookies:
            if c.domain and "bilibili" in c.domain:
                pairs[c.name] = c.value
        for c in self.session.cookies:
            if c.name in KNOWN_COOKIES:
                pairs.setdefault(c.name, c.value)
        return "; ".join("%s=%s" % (k, v) for k, v in pairs.items() if v)

    # ---------------- 查登录态 ----------------
    def whoami(self, cookie=""):
        """拿昵称。cookie 为空则用会话自带的。"""
        headers = {"Cookie": cookie} if cookie else {}
        try:
            r = self.session.get(NAV_URL, headers=headers, timeout=15)
            data = r.json().get("data") or {}
            if not data.get("isLogin"):
                return None
            return data.get("uname") or "已登录"
        except Exception:
            return None


def check_login_state(cookie="", proxy=None):
    """检查 cookie 是不是有效的登录态。

    返回 (状态, 昵称)，状态取值：
      ok      登录有效
      invalid 服务端明确说没登录（cookie 过期了）
      error   网络/其它错误（**不代表 cookie 失效**，别把用户踢下线）
    """
    if not cookie:
        return "invalid", ""
    s = _req().Session()
    s.trust_env = False
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    try:
        r = s.get(NAV_URL, headers={"Cookie": cookie}, timeout=15)
        data = r.json().get("data") or {}
    except Exception:
        return "error", ""
    if not data.get("isLogin"):
        return "invalid", ""
    return "ok", (data.get("uname") or "已登录")


def check_login(cookie="", proxy=None):
    """检查一串 cookie 是不是有效的登录态，返回昵称或 None。"""
    state, name = check_login_state(cookie, proxy)
    return name if state == "ok" else None
