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
    (re.compile(r"bilibili\.com/bangumi/play/ep(\d+)"), "ep"),
]

KIND_LABEL = {
    "season": "合集",
    "series": "视频列表",
    "fav": "收藏夹",
    "ss": "番剧",
    "ep": "番剧",
}


def detect_collection(text):
    """看链接是不是"多视频容器"。是则返回 {kind, mid, sid}，否则返回 None。

    番剧 ep 链接只有一个 id（没有 mid），所以按捕获组个数分别处理。
    """
    text = (text or "").strip()
    for pat, kind in _PATTERNS:
        m = pat.search(text)
        if m:
            groups = m.groups()
            if len(groups) >= 2:
                return {"kind": kind, "mid": groups[0], "sid": groups[1]}
            return {"kind": kind, "mid": "", "sid": groups[0]}
    return None


def _archives_of(a):
    """把两种接口返回的 archives 统一成同一种结构。"""
    return {
        "bvid": a.get("bvid"),
        "title": a.get("title") or "",
        "duration": int(a.get("duration") or 0),
        "pic": a.get("pic") or "",
        "view": (a.get("stat") or {}).get("view") or 0,
        "checked": True,
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
                          "pic": m.get("cover") or "", "view": 0, "checked": True})
        total = (d.get("page") or {}).get("total") or len(items)
        if len(items) >= total or len(medias) < 50:
            break
        page += 1
    return meta, items


def _fetch_bangumi(client, sid=None, ep_id=None):
    """番剧：pgc/view/web/season。

    这里有两个坑：
    1) episodes 数组里**同一集会出现两次**，一次是几十秒的短版切片、一次是真正的正片。
       官方 total 字段给的是"去重后的集数"，但直接取前 total 条会取到短版。
       ⇒ 按集号分组，每组取时长最长的那条。
    2) episode.duration 的单位是**毫秒**（view 接口才是秒）。
    另外 section[] 里是 PV花絮 / 高能速看 / UP主看灵笼 这类花絮分区。
    """
    params = {"ep_id": ep_id} if ep_id else {"season_id": sid}
    r = client.get_json(API + "/pgc/view/web/season", params)["result"]
    eps = r.get("episodes") or []

    # 按集号分组，每组留时长最长的（正片）
    best = {}
    for ep in eps:
        key = ep.get("title") or str(ep.get("id"))
        old = best.get(key)
        if old is None or (ep.get("duration") or 0) > (old.get("duration") or 0):
            best[key] = ep
    # 按集号排（数字在前）
    def ep_no(e):
        try:
            return int(e.get("title"))
        except (TypeError, ValueError):
            return 999
    main_eps = sorted(best.values(), key=ep_no)

    items = []
    for ep in main_eps:
        items.append({
            "bvid": ep.get("bvid"),
            "title": ep.get("long_title") or ep.get("title") or "",
            "duration": int(ep.get("duration") or 0) // 1000,   # 毫秒 -> 秒
            "pic": ep.get("cover") or "",
            "view": 0,
            "cid": ep.get("cid"),          # 番剧自带 cid，省一次查询
            "group": "正片",
            "current": str(ep.get("id")) == str(ep_id),
            "checked": (str(ep.get("id")) == str(ep_id)) if ep_id else True,
            "no": ep.get("title") or "",
        })
    # 花絮 / 二创分区，默认不勾也不显示
    for sec in (r.get("section") or []):
        label = sec.get("title") or "花絮"
        for ep in (sec.get("episodes") or []):
            items.append({
                "bvid": ep.get("bvid"),
                "title": ep.get("long_title") or ep.get("title") or "",
                "duration": int(ep.get("duration") or 0) // 1000,
                "pic": ep.get("cover") or "",
                "view": 0,
                "cid": ep.get("cid"),
                "group": label,
                "current": False,
                "checked": False,
                "extra": True,
                "no": "",
            })
    meta = {"name": r.get("season_title") or "番剧", "cover": r.get("cover") or ""}
    meta["total"] = len(main_eps)
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
    elif kind == "ep":
        # ep 是"合集里的某一集"：列出整个合集，并标出当前这一集
        meta, items = _fetch_bangumi(client, ep_id=sid)
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


def fetch_preview(client, url):
    """统一预览入口：合集/列表/收藏夹 -> 清单；单个视频 -> 它的分 P 清单。

    返回和 fetch_collection 一样的结构，图形界面用同一个对话框展示。
    """
    if detect_collection(url):
        return fetch_collection(client, url)

    info = client.resolve(url)
    pages = info.get("pages") or []
    items = []
    for i, p in enumerate(pages):
        items.append({
            "bvid": info["bvid"],
            "cid": p.get("cid"),
            "title": p.get("part") or ("P%d" % (i + 1)),
            "duration": int(p.get("duration") or 0),
            "pic": info.get("cover") or "",
            "view": 0,
            "checked": True,
        })
    if not items:
        items = [{
            "bvid": info["bvid"], "cid": info.get("cid"),
            "title": info.get("title") or info["bvid"],
            "duration": int(info.get("duration") or 0),
            "pic": info.get("cover") or "", "view": 0,
        }]
    return {
        "title": info.get("title") or "",
        "cover": info.get("cover") or "",
        "desc": info.get("brief") or "",
        "kind": "video",
        "kind_label": "视频",
        "owner": info.get("owner") or "",
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
