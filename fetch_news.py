#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIKU GOODS RADAR — 수집 스크립트 v3
[뉴스] Google News RSS(日/中/韓/英) + Mikufan + VNN
[구매] Good Smile Company(굿스마이라) / AmiAmi 상품 검색 — 실제 예약·판매 페이지
- 썸네일 추출 (구매처는 상품 이미지 기본 제공)
- 한국어 번역 (구글 무료 endpoint 다중화, 캐시)
- 카테고리(피규어/굿즈) + 타입(news/shop) 분류
로컬: pip install feedparser requests beautifulsoup4
"""
import json, re, time, hashlib, html, os
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import feedparser
import requests
try:
    from curl_cffi import requests as creq   # 브라우저 TLS 지문 (Cloudflare/AmiAmi 우회)
    HAS_CURL = True
except Exception:
    HAS_CURL = False

def cget(url, **kw):
    """curl_cffi 우선(브라우저 impersonate), 실패 시 일반 requests"""
    kw.setdefault("timeout", 15)
    if HAS_CURL:
        try:
            return creq.get(url, impersonate="chrome120", **kw)
        except Exception:
            pass
    return S.get(url, **kw)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
S = requests.Session(); S.headers.update({"User-Agent": UA})
DEBUG = {}

# ============================================================ 번역
TR_CACHE_FILE = "tr_cache.json"
try:
    TR_CACHE = json.load(open(TR_CACHE_FILE, encoding="utf-8"))
except Exception:
    TR_CACHE = {}

def translate(text, sl):
    if not text or sl == "ko":
        return None
    key = f"{sl}:{text}"
    if key in TR_CACHE:
        return TR_CACHE[key]
    endpoints = [
        "https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl=ko&dt=t&q={q}",
        "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={sl}&tl=ko&q={q}",
    ]
    for ep in endpoints:
        try:
            r = S.get(ep.format(sl=sl, q=quote(text)), timeout=12)
            j = r.json()
            if isinstance(j, list) and j and isinstance(j[0], list):
                out = "".join(seg[0] for seg in j[0] if seg and seg[0])
            elif isinstance(j, list):
                out = j[0] if isinstance(j[0], str) else None
            else:
                out = None
            if out and out.strip() and out.strip() != text.strip():
                TR_CACHE[key] = out.strip()
                return out.strip()
        except Exception:
            continue
    return None

# ============================================================ 뉴스 소스
def gnews(query, hl, gl, ceid):
    return f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"

NEWS_SOURCES = [
    dict(name="Google News 日", region="jp", lang="ja", prefiltered=True,
         url=gnews("初音ミク (グッズ OR コラボ OR フィギュア OR ねんどろいど OR カフェ OR 予約)", "ja", "JP", "JP:ja")),
    dict(name="Google News 中", region="cn", lang="zh-CN", prefiltered=True,
         url=gnews("初音未来 (联动 OR 周边 OR 手办 OR 联名 OR 粘土人 OR 预售)", "zh-CN", "CN", "CN:zh-Hans")),
    dict(name="Google News 韓", region="kr", lang="ko", prefiltered=True,
         url=gnews("하츠네 미쿠 (굿즈 OR 콜라보 OR 피규어 OR 넨도로이드 OR 예약)", "ko", "KR", "KR:ko")),
    dict(name="Google News 英", region="global", lang="en", prefiltered=True,
         url=gnews('"Hatsune Miku" (merch OR collab OR figure OR nendoroid OR cafe OR goods)', "en-US", "US", "US:en")),
    dict(name="Mikufan", region="global", lang="en", prefiltered=False,
         url="https://www.mikufan.com/feed/"),
    dict(name="VNN", region="global", lang="en", prefiltered=False,
         url="https://www.vocaloidnews.net/feed/"),
]

GOODS_KW = ["グッズ","コラボ","フィギュア","ねんどろいど","カフェ","ポップアップ","限定","プライズ","予約",
    "merch","merchandise","collab","figure","nendoroid","figma","scale","cafe","pop-up","popup","plush","goods","store","preorder","pre-order","prize",
    "联动","周边","手办","联名","粘土人","预售","굿즈","콜라보","피규어","팝업","넨도로이드","예약"]
FIGURE_KW = ["フィギュア","ねんどろいど","figma","nendoroid","figure","scale","プライズ","prize","手办","粘土人","피규어","넨도로이드","1/7","1/8","1/4","pop up parade","スケール"]
REGION_HINTS = {
    "cn": ["china","chinese","taobao","tmall","bilibili","weibo","moeyu","中国","初音未来","上海","luckin"],
    "kr": ["korea","korean","한국","韓国","seoul"],
    "jp": ["japan","日本","tokyo","東京","akihabara","magical mirai","マジカルミライ"],
}

# ============================================================ 구매처(쇼핑몰)
# goodsmile.info(제품 정보 사이트) 검색 — 판매 페이지(.com)로 직접 링크, 봇 차단 약함
GSI_SEARCH = "https://www.goodsmile.info/en/products/page/{p}?utf8=%E2%9C%93&q%5Bgoods_id_eq%5D=&q%5Bname_or_actors_name_or_specs_name_cont%5D=Hatsune+Miku"
AMIAMI_API = "https://api.amiami.com/api/v1.0/items?pagecnt=1&pagemax=40&lang=eng&s_keywords=hatsune+miku"

MAX_NEWS, MAX_SHOP, OG_LIMIT = 60, 40, 22

def norm(t): return re.sub(r"[^0-9a-zA-Z가-힣ぁ-んァ-ン一-龥]", "", (t or "").lower())
def detect_region(default, text):
    low=(text or "").lower()
    for reg,hints in REGION_HINTS.items():
        if any(h in low for h in hints): return reg
    return default
def detect_cat(title):
    low=title.lower()
    return "figure" if any(k.lower() in low for k in FIGURE_KW) else "goods"
def parse_ts(e):
    for k in ("published_parsed","updated_parsed"):
        if e.get(k): return time.mktime(e[k])
    return time.time()

def get_feed(url):
    try: return feedparser.parse(S.get(url,timeout=15).content)
    except Exception: return feedparser.parse(url)

def thumb_feed(e):
    for k in ("media_thumbnail","media_content"):
        v=e.get(k)
        if v and isinstance(v,list) and v[0].get("url"): return v[0]["url"]
    h=""
    if e.get("content"):
        try: h=e.content[0].value or ""
        except Exception: pass
    h+=e.get("summary","") or ""
    m=re.search(r'<img[^>]+src=["\']([^"\']+)',h)
    return m.group(1) if m else None
def thumb_og(url):
    try:
        if "google" in urlparse(url).netloc: return None
        r=S.get(url,timeout=8)
        m=(re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)',r.text)
           or re.search(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image',r.text))
        if m and m.group(1).startswith("http"): return m.group(1)
    except Exception: pass
    return None

# ---------- 뉴스 수집
def collect_news():
    items, seen = [], set()
    for src in NEWS_SOURCES:
        try:
            feed=get_feed(src["url"]); print(f"[news {src['name']}] {len(feed.entries)}")
        except Exception as ex:
            print("[skip]",src["name"],ex); continue
        for e in feed.entries[:40]:
            title=(e.get("title") or "").strip(); link=e.get("link") or ""
            if not title or not link: continue
            if not src["prefiltered"] and not any(k.lower() in title.lower() for k in GOODS_KW): continue
            k=hashlib.md5(norm(title)[:60].encode()).hexdigest()
            if k in seen: continue
            seen.add(k); ts=parse_ts(e)
            items.append(dict(title=title,title_ko=None,link=link,source=src["name"],
                region=detect_region(src["region"],title),category=detect_cat(title),
                type="news",lang=src["lang"],thumb=thumb_feed(e),
                date=datetime.fromtimestamp(ts,tz=timezone.utc).strftime("%Y-%m-%d"),ts=int(ts)))
    items.sort(key=lambda x:-x["ts"]); items=items[:MAX_NEWS]
    f=0
    for it in items:
        if it["thumb"] or f>=OG_LIMIT: continue
        if "google" in urlparse(it["link"]).netloc: continue
        it["thumb"]=thumb_og(it["link"]); f+=1
    return items

# ---------- 구매처 수집
def is_miku(text):
    low=(text or "").lower()
    return ("miku" in low) or ("初音" in text) or ("ミク" in text) or ("미쿠" in text)

def collect_gsc():
    """Good Smile은 봇 차단/JS 렌더링으로 직접 수집 불가 — 비활성(딥링크 버튼으로 대체)"""
    DEBUG["gsc"]="disabled (JS-rendered)"
    return []

def collect_amiami():
    out=[]; dbg=""
    try:
        r=cget(AMIAMI_API,headers={"X-User-Key":"amiami_dev","Referer":"https://www.amiami.com/"})
        dbg=f"http{r.status_code}/{len(r.content)}/curl{HAS_CURL}"
        DEBUG["amiami_body"]=r.text[:600]
        j=r.json()
        for it in j.get("items",[]):
            title=(it.get("gname") or "").strip()
            if not is_miku(title): continue
            code=it.get("gcode","")
            img=it.get("main_image_url") or it.get("thumb_url") or it.get("image_on") or ""
            if img and img.startswith("//"): img="https:"+img
            elif img and img.startswith("/"): img="https://img.amiami.com"+img
            elif img and not img.startswith("http"): img="https://img.amiami.com/"+img
            out.append(dict(title=title,title_ko=None,
                link=f"https://www.amiami.com/eng/detail/?gcode={code}",source="AmiAmi",
                region="jp",category=detect_cat(title),type="shop",lang="en",
                thumb=img or None,
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),ts=int(time.time())))
    except Exception as ex:
        dbg=f"err:{ex}"
    DEBUG["amiami"]=f"{dbg} -> {len(out)}"
    print(f"[shop AmiAmi] {len(out)} ({dbg})")
    return out

def collect_shop():
    items=collect_amiami()  # GSC 비활성
    seen=set(); uniq=[]
    for it in items:
        k=hashlib.md5(norm(it["title"])[:60].encode()).hexdigest()
        if k in seen: continue
        seen.add(k); uniq.append(it)
    return uniq[:MAX_SHOP]

def load_prev_shop():
    """직전 data.json에서 구매(shop) 항목 회수 — 공식몰이 막힌 회차 대비"""
    try:
        prev=json.load(open("data.json",encoding="utf-8"))
        return [it for it in prev.get("items",[]) if it.get("type")=="shop"]
    except Exception:
        return []

def main():
    news=collect_news()
    shop=collect_shop()
    reused=False
    if len(shop) < 3:                      # 거의 못 받았으면(차단 추정) 이전 결과 유지
        prev=load_prev_shop()
        if len(prev) > len(shop):
            shop=prev; reused=True
            print(f"[shop] blocked this run -> reusing {len(prev)} previous items")
    allitems=shop+news  # 구매처 먼저
    # 한국어 번역 (日/中 + 영어 쇼핑 항목도 한국어 병기)
    tcount=0
    for it in allitems:
        if it["lang"] in ("ja","zh-CN","en"):
            ko=translate(it["title"], it["lang"])
            if ko: it["title_ko"]=ko; tcount+=1
    json.dump(TR_CACHE, open(TR_CACHE_FILE,"w",encoding="utf-8"), ensure_ascii=False)
    out=dict(updated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
             count=len(allitems),news=len(news),shop=len(shop),shop_reused=reused,sample=False,debug=DEBUG,items=allitems)
    json.dump(out, open("data.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"saved {len(allitems)} (news {len(news)} / shop {len(shop)}) | translated {tcount} | thumbs {sum(1 for i in allitems if i.get('thumb'))}")

if __name__=="__main__":
    main()
