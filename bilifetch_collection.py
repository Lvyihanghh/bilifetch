#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合集 / 视频列表 / 收藏夹 的解析与列举。

B 站上"多个视频归到一起"的容器有好几种，链接形态也不同：

  1. UP 主合集        space.bilibili.com/{mid}/lists/{sid}?type=season
  2. UP 主视频列表     space.bilibili.com/{mid}/lists/{sid}?type=series
  3. 老格式合集        space.bilibili.com/{mid}/channel/seriesdetail?sid={sid}
  4. 番剧（一季多集）   bilibili.com/bangumi/play/ss{sid}
  5. 收藏夹          space.bilibili.com/{mid}/favlist?fid={fid}

接口参考上游 nICEnnnnnnnLee/BilibiliDown 的 URL4ChannelSeriesParser 等解析器。
"""

import re
import unicodedata

API = "https://api.bilibili.com"

# (正则, 类型)  类型: season=合集, series=视频列表, fav=收藏夹, ss=番剧季
_PATTERNS = [
    (re.compile(r"space\.bilibili\.com/(\d+)/lists/(\d+)\?type=season"), "season"),
    (re.compile(r"space\.bilibili\.com/(\d+)/lists/(\d+)\?type=series"), "series"),
    (re.compile(r"space\.bilibili\.com/(\d+)/channel/seriesdetail\?sid=(\d+)"), "auto"),
    (re.compile(r"space\.bilibili\.com/(\d+)/lists/(\d+)"), "auto"),
    (re.compile(r"space\.bilibili\.com/(\d+)/favlist\?fid=(\d+)"), "fav"),
    (re.compile(r"bilibili\.com/bangumi/play/ss(\d+)"), "ss"),
]

KIND_LABEL = {
    "season": "合集",
    "series": "视频列表",
    "fav": "收藏夹",
    "ss": "番剧",
}


def detect_collection(text):
    """看链接是不是"多视频容器"。是则返回 {kind, mid, sid}，否则返回 None。"""
    text = (text or "").strip()
    for pat, kind in _PATTERNS:
        m = pat.search(text)
        if m:
            return {"kind": kind, "mid": m.group(1), "sid": m.group(2)}
    return None


def _archives_of(a):
    """把两种接口返回的 archives 统一成同一种结构。"""
    return {
        "bvid": a.get("bvid"),
        "title": a.get("title") or "",
        "duration": int(a.get("duration") or 0),
        "pic": a.get("pic") or "",
        "view": (a.get("stat") or {}).get("view") or 0,
    }


def _fetch_season(client, mid, sid):
    """UP 主合集：x/polymer/web-space/seasons_archives_list（分页）。"""
    items = []
    page = 1
    meta = {}
    while True:
        d = client.get_json(API + "/x/polymer/web-space/seasons_archives_list",
                            {"mid": mid, "season_id": sid, "sort_reverse": "false",
                             "page_num": page, "page_size": 50})["data"]
        meta = d.get("meta") or {}
        archives = d.get("archives") or []
        if not archives:
            break
        items += [_archives_of(a) for a in archives]
        total = (d.get("page") or {}).get("total") or len(items)
        if len(items) >= total or len(archives) < 50:
            break
        page += 1
    return meta, items


def _fetch_series(client, mid, sid):
    """UP 主视频列表：x/series/archives（分页）。"""
    items = []
    page = 1
    meta = {}
    while True:
        d = client.get_json(API + "/x/series/archives",
                            {"mid": mid, "series_id": sid, "only_normal": "true",
                             "sort": "asc", "pn": page, "ps": 50})["data"]
        archives = d.get("archives") or []
        if not archives:
            break
        items += [_archives_of(a) for a in archives]
        total = (d.get("page") or {}).get("total") or len(items)
        if len(items) >= total or len(archives) < 50:
            break
        page += 1
    # 列表接口不带名称，用 x/series/series 单独取（注意 seasons_series_list 的 page_size 上限只有 20）
    try:
        meta = (client.get_json(API + "/x/series/series", {"series_id": sid})["data"]
                or {}).get("meta") or {}
    except Exception:
        meta = {}
    if not meta.get("name"):
        try:
            il = (client.get_json(API + "/x/polymer/web-space/seasons_series_list",
                                   {"mid": mid, "page_num": 1, "page_size": 20})["data"]
                  or {}).get("items_lists") or {}
            for s in (il.get("series_list") or []):
                m = s.get("meta") or {}
                if str(m.get("series_id")) == str(sid):
                    meta = m
                    break
        except Exception:
            pass
    return meta, items


def _fetch_fav(client, mid, sid):
    """收藏夹：x/v3/fav/resource/list。"""
    items = []
    page = 1
    meta = {}
    while True:
        d = client.get_json(API + "/x/v3/fav/resource/list",
                            {"media_id": sid, "pn": page, "ps": 50, "platform": "web"})["data"]
        if not meta:
            info = d.get("info") or {}
            meta = {"name": info.get("title") or "收藏夹", "cover": info.get("cover") or ""}
        medias = d.get("medias") or []
        if not medias:
            break
        for m in medias:
            items.append({"bvid": m.get("bvid"), "title": m.get("title") or "",
                          "duration": int(m.get("duration") or 0),
                          "pic": m.get("cover") or "", "view": 0})
        total = (d.get("page") or {}).get("total") or len(items)
        if len(items) >= total or len(medias) < 50:
            break
        page += 1
    return meta, items


def _fetch_bangumi(client, sid):
    """番剧一季：pgc/view/web/season（episodes 里直接带 cid）。"""
    r = client.get_json(API + "/pgc/view/web/season", {"season_id": sid})["result"]
    items = []
    for ep in (r.get("episodes") or []):
        items.append({
            "bvid": ep.get("bvid"),
            "title": ep.get("long_title") or ep.get("title") or "",
            "duration": int(ep.get("duration") or 0),
            "pic": ep.get("cover") or "",
            "view": 0,
            "cid": ep.get("cid"),          # 番剧自带 cid，省一次查询
        })
    meta = {"name": r.get("season_title") or "番剧", "cover": r.get("cover") or ""}
    return meta, items


def fetch_collection(client, url):
    """把合集链接展开成可预览的清单。

    返回 {"title","cover","kind","kind_label","items":[...]}，
    每个 item 有 bvid/title/duration/pic/view（cid 可选）。
    """
    det = detect_collection(url)
    if not det:
        return None
    kind, mid, sid = det["kind"], det["mid"], det["sid"]

    if kind == "ss":
        meta, items = _fetch_bangumi(client, sid)
        kind = "bangumi"
    elif kind == "fav":
        meta, items = _fetch_fav(client, mid, sid)
    elif kind == "season":
        meta, items = _fetch_season(client, mid, sid)
    else:   # auto / series
        try:
            meta, items = _fetch_series(client, mid, sid)
        except Exception:
            meta, items = {}, []
        if not items:
            # 老格式链接不分 season/series，两种都试一下
            try:
                meta2, items2 = _fetch_season(client, mid, sid)
                if items2:
                    meta, items, kind = meta2, items2, "season"
            except Exception:
                pass
        if kind == "auto":
            kind = "series"

    title = meta.get("name") or meta.get("title") or ("%s %s" % (KIND_LABEL.get(kind, "合集"), sid))
    return {
        "title": title,
        "cover": meta.get("cover") or "",
        "desc": meta.get("description") or "",
        "kind": kind,
        "kind_label": KIND_LABEL.get(kind, "合集"),
        "items": items,
    }


def format_duration(sec):
    """秒 -> mm:ss / h:mm:ss。"""
    sec = int(sec or 0)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def format_views(n):
    """播放量 -> 中文可读。"""
    n = int(n or 0)
    if n >= 10000:
        return "%.1f 万" % (n / 10000.0)
    return str(n)


def pad_display(text, width):
    """按显示宽度补空格（中文算两列），让列表能对齐。"""
    text = str(text)
    w = sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)
    return text + " " * max(0, width - w)
