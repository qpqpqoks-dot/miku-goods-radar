#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIKU GOODS RADAR — 뉴스 수집 스크립트 v2
- Google News 검색 RSS (日/中/韓/英) + Mikufan + VNN
- 썸네일 추출 (feed 썸네일 → 본문 img → og:image 순서)
- 카테고리 분류 (피규어 / 굿즈·콜라보)
로컬 테스트: pip install feedparser requests && python fetch_news.py
"""
import json, re, time, hashlib
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import feedparser
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MikuGoodsRadar/2.0"

def gnews(query, hl, gl, ceid):
    return f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"

SOURCES = [
    dict(name="Google News 日", region="jp", prefiltered=True,
         url=gnews("初音ミク (グッズ OR コラボ OR フィギュア OR ねんどろいど OR カフェ)", "ja", "JP", "JP:ja")),
    dict(name="Google News 中", region="cn", prefiltered=True,
         url=gnews("初音未来 (联动 OR 周边 OR 手办 OR 联名 OR 粘土人)", "zh-CN", "CN", "CN:zh-Hans")),
    dict(name="Google News 韓", region="kr", prefiltered=True,
         url=gnews("하츠네 미쿠 (굿즈 OR 콜라보 OR 피규어 OR 넨도로이드)", "ko", "KR", "KR:ko")),
    dict(name="Google News 英", region="global", prefiltered=True,
         url=gnews('"Hatsune Miku" (merch OR collab OR figure OR nendoroid OR cafe OR goods)', "en-US", "US", "US:en")),
    dict(name="Mikufan", region="global", prefiltered=False,
         url="https://www.mikufan.com/feed/"),
    dict(name="VNN", region="global", prefiltered=False,
         url="https://www.vocaloidnews.net/feed/"),
]

GOODS_KW = [
    "グッズ", "コラボ", "フィギュア", "ねんどろいど", "カフェ", "ポップアップ", "限定", "プライズ",
    "merch", "merchandise", "collab", "figure", "nendoroid", "figma", "scale",
    "cafe", "pop-up", "popup", "plush", "goods", "store", "preorder", "pre-order", "prize",
    "联动", "周边", "手办", "联名", "粘土人", "굿즈", "콜라보", "피규어", "팝업", "넨도로이드",
]

FIGURE_KW = [
    "フィギュア", "ねんどろいど", "figma", "nendoroid", "figure", "scale", "プライズ", "prize",
    "手办", "粘土人", "피규어", "넨도로이드", "1/7", "1/8", "pop up parade",
]

REGION_HINTS = {
    "cn": ["china", "chinese", "taobao", "tmall", "bilibili", "weibo", "moeyu", "中国", "初音未来", "上海", "luckin"],
    "kr": ["korea", "korean", "한국", "韓国", "seoul"],
    "jp": ["japan", "日本", "tokyo", "東京", "akihabara", "magical mirai", "マジカルミライ"],
}

MAX_ITEMS = 80
OG_FETCH_LIMIT = 25   # og:image를 가져올 최대 기사 수 (Actions 시간 절약)


def norm_title(t):
    return re.sub(r"[^0-9a-zA-Z가-힣ぁ-んァ-ン一-龥]", "", (t or "").lower())


def detect_region(default, text):
    low = (text or "").lower()
    for region, hints in REGION_HINTS.items():
        if any(h in low for h in hints):
            return region
    return default


def detect_category(title):
    low = title.lower()
    return "figure" if any(k.lower() in low for k in FIGURE_KW) else "goods"


def parse_ts(entry):
    for key in ("published_parsed", "updated_parsed"):
        v = entry.get(key)
        if v:
            return time.mktime(v)
    return time.time()


def thumb_from_feed(entry):
    """RSS 항목 자체에서 썸네일 찾기"""
    for key in ("media_thumbnail", "media_content"):
        v = entry.get(key)
        if v and isinstance(v, list) and v[0].get("url"):
            return v[0]["url"]
    html = ""
    if entry.get("content"):
        try:
            html = entry.content[0].value or ""
        except Exception:
            pass
    html += entry.get("summary", "") or ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', html)
    return m.group(1) if m else None


def thumb_from_og(url):
    """기사 페이지의 og:image (Google News 리다이렉트 링크는 건너뜀)"""
    try:
        host = urlparse(url).netloc
        if "google" in host:
            return None
        r = requests.get(url, timeout=8, headers={"User-Agent": UA})
        m = (re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)', r.text)
             or re.search(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image', r.text))
        if m and m.group(1).startswith("http"):
            return m.group(1)
    except Exception:
        pass
    return None


def collect():
    items, seen = [], set()
    for src in SOURCES:
        try:
            feed = feedparser.parse(src["url"])
        except Exception as e:
            print(f"[skip] {src['name']}: {e}")
            continue
        for e in feed.entries[:40]:
            title = (e.get("title") or "").strip()
            link = e.get("link") or ""
            if not title or not link:
                continue
            if not src["prefiltered"]:
                low = title.lower()
                if not any(k.lower() in low for k in GOODS_KW):
                    continue
            key = hashlib.md5(norm_title(title)[:60].encode()).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            ts = parse_ts(e)
            items.append(dict(
                title=title,
                link=link,
                source=src["name"],
                region=detect_region(src["region"], title),
                category=detect_category(title),
                thumb=thumb_from_feed(e),
                date=datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                ts=int(ts),
            ))
    items.sort(key=lambda x: -x["ts"])
    items = items[:MAX_ITEMS]

    # og:image 보강 (썸네일 없는 상위 항목만)
    fetched = 0
    for it in items:
        if it["thumb"] or fetched >= OG_FETCH_LIMIT:
            continue
        if "google" in urlparse(it["link"]).netloc:
            continue
        it["thumb"] = thumb_from_og(it["link"])
        fetched += 1
    return items


def main():
    items = collect()
    out = dict(
        updated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        count=len(items),
        sample=False,
        items=items,
    )
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"saved {len(items)} items ({sum(1 for i in items if i['thumb'])} with thumbs)")


if __name__ == "__main__":
    main()
