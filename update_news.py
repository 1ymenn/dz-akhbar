import sys, feedparser, time, os, re, json, socket, hashlib, subprocess, requests, asyncio, aiohttp
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from deep_translator import GoogleTranslator
from jinja2 import Template

socket.setdefaulttimeout(20)
ALGERIA_TZ = timezone(timedelta(hours=1))
BASE_URL = "https://dz-akhbar.surge.sh"
CACHE_FILE = "cache.json"
HASH_FILE = "content_hash.txt"
TEMPLATE_FILE = "template.html"
LATEST_JSON = "latest_news.json"

_cache = {}
def load_cache():
    global _cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except:
            _cache = {}
def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False)

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def translate(text):
    if not text or is_arabic(text[:30]):
        return text, False
    h = hashlib.md5(text.encode()).hexdigest()
    if h in _cache:
        return _cache[h], True
    try:
        result = GoogleTranslator(source='auto', target='ar').translate(text[:5000])
        if result and result != text:
            _cache[h] = result
            return result, True
    except:
        pass
    return text, False

DZ_LATEST = [
    {"n":"الشروق","u":"https://www.echoroukonline.com/feed/","c":"#c0392b"},
    {"n":"النهار","u":"https://www.ennaharonline.com/feed/","c":"#2980b9"},
    {"n":"الخبر","u":"https://elkhabar.com/feed/","c":"#2c3e50"},
    {"n":"البلاد","u":"https://www.elbilad.net/feed","c":"#27ae60"},
    {"n":"الحوار","u":"https://elhiwar.dz/feed/","c":"#e67e22"},
    {"n":"الهداف","u":"http://feeds.feedburner.com/GalerieArtciles","c":"#e74c3c"},
    {"n":"DZfoot","u":"https://www.dzfoot.com/feed/","c":"#16a085"},
    {"n":"دزاير توب","u":"https://www.dzair-tube.dz/feed/","c":"#1abc9c"},
    {"n":"الجمهورية","u":"https://www.eldjoumhouria.dz/feed/","c":"#c0392b"},
    {"n":"الراية","u":"https://errayaonline.net/feed/","c":"#2980b9"},
    {"n":"الجزائر الجديدة","u":"https://www.eldjazaireldjadida.dz/feed/","c":"#16a085"},
    {"n":"الموعد","u":"https://elmaouid.dz/feed/","c":"#8e44ad"},
    {"n":"آخر ساعة","u":"https://www.akhbarsaa.com/feed/","c":"#27ae60"},
]
DZ_TRENDING = [
    {"n":"الشروق","u":"https://www.echoroukonline.com/feed/","c":"#c0392b"},
]
DZ_POPULAR = [
    {"n":"الشروق","u":"https://www.echoroukonline.com/feed/","c":"#c0392b"},
    {"n":"النهار","u":"https://www.ennaharonline.com/feed/","c":"#2980b9"},
    {"n":"البلاد","u":"https://www.elbilad.net/feed","c":"#27ae60"},
    {"n":"الهداف","u":"http://feeds.feedburner.com/GalerieArtciles","c":"#e74c3c"},
]
DZ_UNI = [
    {"n":"جامعة الجزائر 1","u":"https://www.univ-alger.dz/feed/","c":"#1a5276"},
    {"n":"USTHB","u":"https://www.usthb.dz/feed/","c":"#b7950b"},
    {"n":"جامعة بجاية","u":"https://www.univ-bejaia.dz/feed/","c":"#1e8449"},
    {"n":"جامعة وهران 1","u":"https://www.univ-oran1.dz/feed/","c":"#d35400"},
    {"n":"جامعة سطيف 1","u":"https://www.univ-setif.dz/feed/","c":"#8e44ad"},
    {"n":"جامعة عنابة","u":"https://www.univ-annaba.dz/feed/","c":"#2e86c1"},
    {"n":"جامعة تلمسان","u":"https://www.univ-tlemcen.dz/feed/","c":"#117a65"},
    {"n":"جامعة قسنطينة 1","u":"https://www.umc.edu.dz/feed/","c":"#7d3c98"},
    {"n":"جامعة البليدة 1","u":"https://www.univ-blida.dz/feed/","c":"#d4ac0d"},
    {"n":"جامعة بومرداس","u":"https://www.univ-boumerdes.dz/feed/","c":"#c0392b"},
    {"n":"جامعة ورقلة","u":"https://www.univ-ouargla.dz/feed/","c":"#e67e22"},
    {"n":"جامعة بسكرة","u":"https://www.univ-biskra.dz/feed/","c":"#16a085"},
    {"n":"جامعة المسيلة","u":"https://www.univ-msila.dz/feed/","c":"#2980b9"},
    {"n":"جامعة المدية","u":"https://www.univ-medea.dz/feed/","c":"#8e44ad"},
    {"n":"جامعة تيارت","u":"https://www.univ-tiaret.dz/feed/","c":"#e74c3c"},
    {"n":"جامعة سعيدة","u":"https://www.univ-saida.dz/feed/","c":"#27ae60"},
    {"n":"جامعة معسكر","u":"https://www.univ-mascara.dz/feed/","c":"#f39c12"},
    {"n":"جامعة سوق أهراس","u":"https://www.univ-soukahras.dz/feed/","c":"#1abc9c"},
    {"n":"جامعة الجلفة","u":"https://www.univ-djelfa.dz/feed/","c":"#34495e"},
    {"n":"جامعة الوادي","u":"https://www.univ-eloued.dz/feed/","c":"#2c3e50"},
    {"n":"جامعة تبسة","u":"https://www.univ-tebessa.dz/feed/","c":"#c0392b"},
    {"n":"جامعة ميلة","u":"https://www.univ-mila.dz/feed/","c":"#8e44ad"},
    {"n":"جامعة باتنة","u":"https://www.univ-batna.dz/feed/","c":"#2980b9"},
    {"n":"م. التعليم العالي","u":"https://www.mesrs.dz/feed/","c":"#2c3e50"},
    {"n":"المدرسة الوطنية Polytechnique وهران","u":"https://www.enp-oran.dz/feed/","c":"#e74c3c"},
    {"n":"المدرسة العليا للإعلام الآلي","u":"https://www.esi.dz/feed/","c":"#2980b9"},
    {"n":"مركز تطوير التكنولوجيات المتطورة","u":"https://www.cdta.dz/feed/","c":"#16a085"},
]
AR_UNI = [
    {"n":"جامعة بنها","u":"https://www.bu.edu.eg/rss.xml","c":"#27ae60"},
    {"n":"معهد التخطيط القومي (مصر)","u":"https://www.inp.edu.eg/feed/","c":"#e67e22"},
]
AR_LATEST = [
    {"n":"الجزيرة","u":"https://www.aljazeera.net/rss/","c":"#c0392b"},
    {"n":"بي بي سي عربي","u":"https://www.bbc.com/arabic/index.xml","c":"#BB1919"},
    {"n":"سكاي نيوز عربية","u":"https://www.skynewsarabia.com/rss/all","c":"#0072C6"},
    {"n":"فرانس 24 عربي","u":"https://www.france24.com/ar/middle-east/rss","c":"#002395"},
    {"n":"العربية","u":"https://www.alarabiya.net/rss/","c":"#1a8c3e"},
    {"n":"الحرة","u":"https://www.alhurra.com/rss/","c":"#1a5276"},
    {"n":"روسيا اليوم","u":"https://www.rtarabic.com/rss","c":"#c0392b"},
    {"n":"الميادين","u":"https://www.almayadeen.net/rss","c":"#e74c3c"},
    {"n":"العربي الجديد","u":"https://www.alaraby.co.uk/rss","c":"#27ae60"},
    {"n":"الشرق الأوسط","u":"https://aawsat.com/feed/","c":"#d4ac0d"},
]
AR_TRENDING = [
    {"n":"سكاي نيوز عربية","u":"https://www.skynewsarabia.com/rss/all","c":"#0072C6"},
    {"n":"العربية","u":"https://www.alarabiya.net/rss/","c":"#1a8c3e"},
]
AR_POPULAR = [
    {"n":"القدس العربي","u":"https://www.alquds.co.uk/feed/","c":"#2c3e50"},
    {"n":"إرم نيوز","u":"https://www.eremnews.com/rss/","c":"#e67e22"},
    {"n":"عربي 21","u":"https://arabi21.com/rss","c":"#27ae60"},
]
REGIONS = {
    "dz": {"latest": DZ_LATEST, "trending": DZ_TRENDING, "popular": DZ_POPULAR, "uni": DZ_UNI},
    "ar": {"latest": AR_LATEST, "trending": AR_TRENDING, "popular": AR_POPULAR, "uni": AR_UNI},
}

def clean_url(u):
    if not u: return u
    u = u.replace("\\/", "/")
    # Upgrade WordPress thumbnail sizes
    m = re.search(r'-(\d+)x(\d+)\.(jpg|jpeg|png|gif|webp)', u, re.IGNORECASE)
    if m and int(m.group(1)) < 400:
        u = u.replace(f"-{m.group(1)}x{m.group(2)}", "")
    return u

def extract_image(entry):
    for attr in ['media_content','media_thumbnail']:
        if hasattr(entry,attr):
            for m in getattr(entry,attr):
                if 'url' in m: return clean_url(m['url'])
    if hasattr(entry,'enclosures'):
        for e in entry.enclosures:
            if hasattr(e,'href') and e.href and not e.href.endswith(('.mp3','.m4a','.ogg')):
                return clean_url(e.href)
    for link in entry.get('links',[]):
        if link.get('rel') in ('enclosure','image','og:image') or link.get('type','').startswith('image'):
            return clean_url(link.get('href'))
    if hasattr(entry,'content'):
        for c in entry.content:
            if hasattr(c,'value'):
                m=re.search(r'<img[^>]+src=["\']([^"\']+)["\']',c.value)
                if m: return clean_url(m.group(1))
    s=entry.get('summary',entry.get('description',''))
    m=re.search(r'<img[^>]+src=["\']([^"\']+)["\']',s)
    if m: return clean_url(m.group(1))
    m=re.search(r'<img[^>]+src=["\']([^"\']+)["\']',str(entry))
    return clean_url(m.group(1)) if m else None

_page_cache = {}

def fetch_page(link):
    if not link or link in _page_cache:
        return _page_cache.get(link, (None, None))
    if not re.match(r'^https?://[\w.-]+', link):
        _page_cache[link] = (None, None)
        return None, None
    try:
        r = requests.get(link, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            _page_cache[link] = (r.text, link)
            return r.text, link
    except:
        pass
    _page_cache[link] = (None, None)
    return None, None

from readability import Document
import html as html_mod

def extract_text(link):
    page_html, _ = fetch_page(link)
    if not page_html: return ""
    try:
        doc = Document(page_html)
        content_html = doc.summary()
    except:
        content_html = ""
    # Extract text from <p> tags in the readable content
    paras = re.findall(r'<p[^>]*>(.*?)</p>', content_html, re.DOTALL|re.IGNORECASE)
    content_len = len(re.sub(r'<[^>]+>', ' ', content_html).strip())
    if not paras or (len(paras) < 5 and content_len < 800):
        # Fallback: try common content containers first, then <article>, then largest <div>
        fallback_html = ""
        content_classes = ["editor-content", "entry-content", "article-body", "post-content", "story-body", "article-content", "post-body"]
        for cls in content_classes:
            idx = page_html.find(cls)
            if idx > 0:
                div_start = page_html.rfind("<div", 0, idx)
                section_start = page_html.rfind("<section", 0, idx)
                tag_start = max(div_start, section_start)
                if tag_start >= 0:
                    tag_name = "div" if tag_start == div_start else "section"
                    end_tag = "</" + tag_name + ">"
                    depth = 1
                    i = page_html.find(">", tag_start) + 1
                    while i < len(page_html) and depth > 0:
                        ci = page_html.find("<", i)
                        if ci < 0: break
                        if page_html[ci:ci+len(end_tag)] == end_tag:
                            depth -= 1
                            i = ci + len(end_tag)
                        elif page_html[ci:ci+2+len(tag_name)] == "<" + tag_name:
                            depth += 1
                            i = ci + 2 + len(tag_name)
                        else:
                            i = ci + 1
                    candidate = page_html[tag_start:i]
                    ps_count = len(re.findall(r'<p>', candidate)) + len(re.findall(r'<p ', candidate))
                    if ps_count >= 3:
                        fallback_html = candidate
                        break
        if not fallback_html:
            m = re.search(r'<article[^>]*>(.*?)</article>', page_html, re.DOTALL|re.IGNORECASE)
            if m:
                # Within <article>, find the container with most <p> tags
                article_inner = m.group(1)
                inner_divs = re.findall(r'<div[^>]*>(.*?)</div>', article_inner, re.DOTALL)
                if inner_divs:
                    best = max(inner_divs, key=lambda d: len(re.findall(r'<p>', d)))
                    if len(re.findall(r'<p>', best)) >= 5:
                        fallback_html = best
        if not fallback_html:
            divs = re.findall(r'<div[^>]*>(.*?)</div>', page_html, re.DOTALL)
            if divs:
                best = max(divs, key=lambda d: len(re.findall(r'<p>', d)))
                if len(re.findall(r'<p>', best)) >= 5:
                    fallback_html = best
        if fallback_html:
            paras = re.findall(r'<p[^>]*>(.*?)</p>', fallback_html, re.DOTALL|re.IGNORECASE)
        if not paras:
            text = re.sub(r'<[^>]+>', ' ', page_html)
            text = html_mod.unescape(text)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 50: return text[:8000]
            return ""
    clean = []
    for p in paras:
        text = re.sub(r'<[^>]+>', ' ', p)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) < 25: continue
        # Skip pure sharing lines
        if re.match(r'^(شارك|غرّد|أرسل|طباعة|إرسال)\s', text) and len(text) < 80: continue
        if sum(1 for c in text if c.isdigit()) / max(len(text), 1) > 0.5 and len(text) < 50: continue
        clean.append(text)
    if not clean: return ""
    text = '\n\n'.join(clean)
    if len(text) > 3000:
        text = text[:8000]
        last = max(text.rfind('.'), text.rfind('،'), text.rfind('?'), text.rfind('!'))
        if last > 1000: text = text[:last+1]
    return text

def extract_video(link):
    if not link: return None
    html, _ = fetch_page(link)
    if not html: return None
    # YouTube iframe embed
    m = re.search(r'<iframe[^>]+src="([^"]*youtube\.com/embed/([a-zA-Z0-9_-]+)[^"]*)"', html, re.IGNORECASE)
    if m: return "youtube", m.group(2)
    # YouTube watch URL
    m = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', html, re.IGNORECASE)
    if m: return "youtube", m.group(1)
    # Short youtu.be URL
    m = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', html, re.IGNORECASE)
    if m: return "youtube", m.group(1)
    # Dailymotion
    m = re.search(r'dailymotion\.com/embed/video/([a-zA-Z0-9]+)', html, re.IGNORECASE)
    if m: return "dailymotion", m.group(1)
    # Facebook video
    m = re.search(r'facebook\.com/plugins/video\.php\?href=([^"&]+)', html, re.IGNORECASE)
    if m: return "facebook", m.group(1)
    return None

def fetch_og_image(link):
    if not link:
        return None
    html, _ = fetch_page(link)
    if not html:
        return None
    _reject = re.compile(r'logo|icon|avatar|banner|spacer|pixel|nothumb|no[._-]?image|placeholder|/default\.|DefaultImage|970x90', re.IGNORECASE)
    def strip_wp_thumb(url):
        return re.sub(r'-\d+x\d+\.(jpg|jpeg|png|gif|webp)$', r'.\1', url, flags=re.IGNORECASE)
    for pat in [r'<meta\s+property="og:image"\s+content="([^"]+)"',
                r'<meta\s+content="([^"]+)"\s+property="og:image"',
                r'<meta\s+name="twitter:image"\s+content="([^"]+)"']:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            img_url = strip_wp_thumb(m.group(1))
            if not _reject.search(img_url):
                return clean_url(img_url)
    imgs = re.findall(r'<img[^>]+src\s*=\s*"([^"]+\.(?:jpg|jpeg|png|gif|webp))"', html, re.IGNORECASE)
    for i in imgs:
        i = strip_wp_thumb(i)
        if not _reject.search(i):
            if not re.match(r'https?://', i):
                from urllib.parse import urljoin
                i = urljoin(link, i)
            return clean_url(i)
    return None

def fetch_source(source, max_per_source):
    arts = []
    cutoff_2d = time.time() - 2*86400
    feed = None
    for attempt in range(3):
        try:
            feed = feedparser.parse(source["u"])
            if feed and feed.entries:
                break
            if attempt < 2:
                time.sleep(2)
        except Exception:
            if attempt < 2:
                time.sleep(2)
    if not feed or not feed.entries:
        print(f"  WARN: {source['n']} returned 0 entries after 3 attempts")
        return arts
    try:
        cnt = 0
        for e in feed.entries:
            if cnt >= max_per_source:
                break
            # Skip articles older than 2 days
            if hasattr(e, 'published_parsed') and e.published_parsed:
                pub_ts = time.mktime(e.published_parsed)
                if pub_ts < cutoff_2d:
                    continue
            t = e.get("title", "")
            l = e.get("link", "")
            sm = e.get("summary", "")
            p = e.get("published", "")
            img = extract_image(e)
            if img and re.search(r'nothumb|no[._-]?image|placeholder|/default\.|DefaultImage|970x90', img, re.IGNORECASE):
                img = None
            if not img:
                img = fetch_og_image(l)
            sm = re.sub(r'<[^>]+>', '', sm).strip()
            if len(sm) > 200:
                sm = sm[:200] + "..."
            translated_flag = ""
            if not is_arabic(source["n"]):
                new_t, was_t = translate(t)
                if was_t:
                    t = new_t
                    translated_flag = " | مترجم"
                new_sm, _ = translate(sm[:1000])
                if new_sm:
                    sm = new_sm[:200] + "..."
                    translated_flag = " | مترجم"
            arts.append({"title": t, "link": l, "summary": sm, "source": source["n"] + translated_flag,
                         "source_clean": source["n"], "source_color": source["c"],
                         "published": p, "published_parsed": e.get("published_parsed"), "image": img})
            cnt += 1
        time.sleep(0.1)
    except Exception as ex:
        print(f"  ERR: {source['n']} parse error: {ex}")
    return arts

def fetch_news(sources, max_per_source):
    arts = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(fetch_source, s, max_per_source): s["n"] for s in sources}
        for f in as_completed(futures):
            try:
                arts.extend(f.result())
            except:
                pass
    # Fetch article text in parallel
    with ThreadPoolExecutor(max_workers=20) as ex:
        txt_futures = {}
        for a in arts:
            if a.get("link"):
                txt_futures[ex.submit(extract_text, a["link"])] = a
        for f in as_completed(txt_futures):
            try:
                txt = f.result()
                txt_futures[f]["text"] = txt
            except:
                pass
        # Fallback: if text is empty, use RSS summary
        for a in arts:
            if not a.get("text") and a.get("summary"):
                a["text"] = a["summary"]
    # Extract video embeds in parallel
    with ThreadPoolExecutor(max_workers=20) as ex:
        vid_futures = {}
        for a in arts:
            if a.get("link"):
                vid_futures[ex.submit(extract_video, a["link"])] = a
        for f in as_completed(vid_futures):
            try:
                vid = f.result()
                if vid:
                    vid_futures[f]["video"] = vid
            except:
                pass
    return arts

# ============================================================
# ASYNC FETCHING (aiohttp) - 3x faster than ThreadPoolExecutor
# ============================================================
async def async_fetch_page(session, link, sem):
    """Async version of fetch_page with rate limiting."""
    if not link or link in _page_cache:
        return _page_cache.get(link, (None, None))
    if not re.match(r'^https?://[\w.-]+', link):
        _page_cache[link] = (None, None)
        return None, None
    async with sem:
        try:
            async with session.get(link, timeout=aiohttp.ClientTimeout(total=15),
                                   headers={"User-Agent": "Mozilla/5.0"}) as resp:
                if resp.status == 200:
                    text = await resp.text(errors='ignore')
                    _page_cache[link] = (text, link)
                    return text, link
        except Exception:
            pass
    _page_cache[link] = (None, None)
    return None, None

async def async_fetch_source(session, source, max_per_source, sem):
    """Async version of fetch_source - parses RSS (CPU-bound, runs in executor)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fetch_source, source, max_per_source)

async def async_fetch_og_images(session, articles, sem):
    """Fetch og:image for articles that have no image, in parallel."""
    async def _fetch_one(a):
        if a.get("image") or not a.get("link"):
            return
        async with sem:
            html, _ = await async_fetch_page(session, a["link"], sem)
            if html:
                img = _extract_og_from_html(html, a["link"])
                if img:
                    a["image"] = img

    tasks = [_fetch_one(a) for a in articles if not a.get("image") and a.get("link")]
    await asyncio.gather(*tasks, return_exceptions=True)

def _extract_og_from_html(html, link):
    """Extract og:image from raw HTML (helper for async path)."""
    _reject = re.compile(r'logo|icon|avatar|banner|spacer|pixel|nothumb|no[._-]?image|placeholder|/default\.|DefaultImage|970x90', re.IGNORECASE)
    def strip_wp_thumb(url):
        return re.sub(r'-\d+x\d+\.(jpg|jpeg|png|gif|webp)$', r'.\1', url, flags=re.IGNORECASE)
    for pat in [r'<meta\s+property="og:image"\s+content="([^"]+)"',
                r'<meta\s+content="([^"]+)"\s+property="og:image"',
                r'<meta\s+name="twitter:image"\s+content="([^"]+)"']:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            img_url = strip_wp_thumb(m.group(1))
            if not _reject.search(img_url):
                return clean_url(img_url)
    imgs = re.findall(r'<img[^>]+src\s*=\s*"([^"]+\.(?:jpg|jpeg|png|gif|webp))"', html, re.IGNORECASE)
    for i in imgs:
        i = strip_wp_thumb(i)
        if not _reject.search(i):
            if not re.match(r'https?://', i):
                from urllib.parse import urljoin
                i = urljoin(link, i)
            return clean_url(i)
    return None

async def async_fetch_all(regions, max_per_source):
    """Main async fetcher - fetches all sources concurrently."""
    sem = asyncio.Semaphore(20)
    connector = aiohttp.TCPConnector(limit=30, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Phase 1: Fetch all RSS feeds concurrently
        tasks = []
        source_map = {}
        for rid in regions:
            for cat in regions[rid]:
                for s in regions[rid][cat]:
                    if s["n"] not in source_map:
                        source_map[s["n"]] = s
                        tasks.append(async_fetch_source(session, s, max_per_source, sem))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_articles = []
        ok_count = 0
        fail_count = 0
        for idx, r in enumerate(results):
            if isinstance(r, list):
                all_articles.extend(r)
                if r:
                    ok_count += 1
                else:
                    fail_count += 1
            else:
                fail_count += 1
        print(f"  Feed results: {ok_count} ok, {fail_count} empty/failed out of {len(results)}")

        # Phase 2: Fetch article text + video + images in parallel
        async def _enhance_article(a):
            link = a.get("link")
            if not link:
                return
            html, _ = await async_fetch_page(session, link, sem)
            if html:
                # Extract text
                try:
                    from readability import Document
                    doc = Document(html)
                    content_html = doc.summary()
                    paras = re.findall(r'<p[^>]*>(.*?)</p>', content_html, re.DOTALL|re.IGNORECASE)
                    clean = []
                    for p in paras:
                        text = re.sub(r'<[^>]+>', ' ', p)
                        import html as html_mod
                        text = html_mod.unescape(text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        if len(text) >= 25:
                            clean.append(text)
                    if clean:
                        a["text"] = '\n\n'.join(clean)[:8000]
                except:
                    pass
                # Extract video
                m = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]+)', html, re.IGNORECASE)
                if not m:
                    m = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', html, re.IGNORECASE)
                if not m:
                    m = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', html, re.IGNORECASE)
                if m and re.match(r'^[a-zA-Z0-9_-]+$', m.group(1)):
                    a["video"] = ("youtube", m.group(1))
                # Extract image if still missing
                if not a.get("image"):
                    img = _extract_og_from_html(html, link)
                    if img:
                        a["image"] = img

        tasks = [_enhance_article(a) for a in all_articles if a.get("link")]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Fallback: if text is empty, use RSS summary
        for a in all_articles:
            if not a.get("text") and a.get("summary"):
                a["text"] = a["summary"]
            # Last resort: try simple extraction from page
            if not a.get("text") and a.get("link"):
                try:
                    html2, _ = await async_fetch_page(session, a["link"], sem)
                    if html2:
                        # Strip all tags, get raw text
                        raw = re.sub(r'<script[^>]*>.*?</script>', '', html2, flags=re.DOTALL|re.IGNORECASE)
                        raw = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL|re.IGNORECASE)
                        raw = re.sub(r'<[^>]+>', ' ', raw)
                        import html as html_mod
                        raw = html_mod.unescape(raw)
                        raw = re.sub(r'\s+', ' ', raw).strip()
                        # Find the longest text chunk (likely the article body)
                        chunks = [c.strip() for c in re.split(r'[.!?؟!.\n]', raw) if len(c.strip()) > 40]
                        if chunks:
                            a["text"] = '. '.join(chunks[:20])[:8000]
                except:
                    pass

        return all_articles

# ============================================================
# DIFFERENTIAL UPDATE
# ============================================================
def content_hash(articles):
    data = sorted([(a.get("title",""), a.get("link","")) for a in articles])
    return hashlib.md5(json.dumps(data, ensure_ascii=False).encode()).hexdigest()

def safe_mktime(t):
    if not t: return 0
    try:
        return time.mktime(t)
    except (OverflowError, ValueError, OSError):
        return 0

# ============================================================
# HYBRID: latest_news.json for client-side refresh
# ============================================================
def generate_latest_json(articles, base_dir):
    latest = []
    for a in articles[:50]:
        latest.append({
            "title": a.get("title", ""),
            "link": a.get("link", ""),
            "summary": a.get("summary", "")[:150],
            "source": a.get("source_clean", ""),
            "source_color": a.get("source_color", "#666"),
            "image": a.get("image") or "",
            "published": a.get("published", "")[:16],
            "region": a.get("region", "dz"),
            "category": classify_category(a.get("title", "")),
        })
    outpath = os.path.join(base_dir, LATEST_JSON)
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(ALGERIA_TZ).isoformat(), "articles": latest},
                  f, ensure_ascii=False, indent=2)
    print(f"latest_news.json: {len(latest)} articles")

def esc(text):
    return text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")

def sanitize_url(url):
    if not url: return url
    return "#" if re.match(r'^(javascript|data|vbscript):', url, re.IGNORECASE) else url

def classify_category(title):
    t = title.lower()
    cats = {
        "سياسة": ["رئيس", "حكومة", "وزير", "انتخاب", "برلمان", "سياسي", "حزب", "دبلوماسي", "رئيس مجلس", "نواب", "تشريع", "선거", "ㄘ政", "ㄘرلمان", "ㄘحزب", "conciliation", "اتفاق", "اتفاقي", "مفاوضات", "حوار سياسي", "قرار سياسي", "صلاحيات", "رئاس", "شيوخ", "كونغرس", "مجلس الشيوخ", "مجلس النواب", "ال白色的房子", "البيت الأبيض", "ترامب", "نتنياهو", "بايدن", "السناتور", "الكونغرس", "سلا", "ال鱿鱼", "الحرب", "حرب", " Milit", "عسكري", "جيش", "قوات", "هجوم", "قصف", "ضربات", "تهدد", "رد عسكري", "امن قومي", "امن داخلي", "امن عام"],
        "رياضة": ["مباراة", "كرة", "رياض", "لاعب", "بطول", "فريق", "مدرب", "دوري", "هدف", "فوز", "هزيم", "نجم", "sport", "match", "football", "gol", "مونديال", "كأس العالم", "الخضر", "منتخب", "كأس", "دوري أبطال", " league", "champion", "Olymp", "ألعاب أولمبية", "أولمبياد", "gymnase", "athletic", "تنس", "ملاكمة", "مصارعة", "سباحة", " Athletics", "FIFA"],
        "اقتصاد": ["اقتصاد", "سوق", "مال", "بنك", "سعر", "تجار", "صناع", "نفط", "غاز", "استثم", "dinar", "تجاري", "مالي", "ضرائب", "ضريبة", "ميزاني", "تصدير", "وارد", "بورص", "أسهم", "عملة", "ال_central", "المركزي", " inflation", "deficit", "PIB", "GDP", "chomage", "emploi", "مصرف", "قرض", "قروض", "تمويل", " ريع", "نفطي", "طاقة", "كهرباء", "miner", "منجم", " تعدين", "فوسفات", "حديد", "فولاذ", " automotive", "سيارات", "طاقة متجددة", "شمسية", " wind"],
        "تقنية": ["تقني", "هاتف", "ذكي", "رقمن", "إنترنت", "تطبيق", "تكنولوجيا", "حاسوب", "روبوت", "ذكاء اصطناع", "tech", "app", "digital", "cyber", "AI", "software", "hardware", " data", "رقمي", "الالكتروني", " الكتروني"],
        "ثقافة": ["ثقافة", "فن", "سينما", "موسيقى", "أدب", "كتاب", "معرض", "مسرح", "literature", "art", "music", "cinema", " مهرجان", "festival", "фильم", "فيلم", " سينما"],
        "صحة": ["صحة", "مستشفى", "طبي", "Doctor", "health", "hospital", "virus", "vaccin", "علاج", "مرض", "epidem", "pandemi", "وباء", "تطعيم", "لقاح"],
    }
    for cat, keywords in cats.items():
        if any(kw in t for kw in keywords):
            return cat
    return "عام"

def build_articles(articles):
    cards = ""
    colors = ["#667eea","#764ba2","#f093fb","#f5576c","#4facfe","#00f2fe","#43e97b","#38f9d7","#fa709a","#fee140","#a18cd1","#fbc2eb"]
    for idx, a in enumerate(articles):
        t = esc(a["title"])
        sm = esc(a["summary"])[:200] if a["summary"] else ""
        img = a.get("image")
        if img and re.search(r'nothumb|no[._-]?image|placeholder|/default\.|DefaultImage|970x90', img, re.IGNORECASE):
            img = None
        c1 = colors[hash(t) % len(colors)]
        c2 = colors[(hash(t)+1) % len(colors)]
        if img:
            ie = esc(img)
            ih = f'<div class="ai has-img" style="background:linear-gradient(135deg,{c1},{c2})"><img src="{ie}" alt="" loading="lazy" onerror="this.style.display=\'none\'" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"><div class="io"></div></div>'
        else:
            ic = ["📰","📋","📌","🔖","📊","📈","📑","🗞️"][hash(t) % 8]
            ih = f'<div class="ai no-img" style="background:linear-gradient(135deg,{c1},{c2})"><div class="ii">{ic}</div></div>'
        el = sanitize_url(a["link"])
        src_esc = esc(a["source"])
        txt = esc(a.get("text", "")[:8000])
        lm = " lm" if idx >= 40 else ""
        r = a.get("region", "dz")
        cat = classify_category(a["title"])
        uid = hashlib.md5((a["title"] + a["link"]).encode()).hexdigest()[:8]
        vid = a.get("video")
        vid_id = ""
        if vid and re.match(r'^[a-zA-Z0-9_-]+$', str(vid[1])):
            vid_id = vid[1][:50]
        vid_attr = f' data-video="{vid_id}"' if vid_id else ""
        vid_icon = '<div class="vi">▶</div>' if vid else ""
        cards += f'<div class="a{lm}" data-t="{t.lower()}" data-s="{a["source_clean"].lower()}" data-r="{r}" data-cat="{cat}"><div class="ac" data-id="{uid}" data-link="{el}" data-title="{t}" data-source="{src_esc}" data-src-color="{a["source_color"]}" data-txt="{txt}"{vid_attr}>{ih}{vid_icon}<div class="ab"><div class="am"><span class="as" style="background:{a["source_color"]}">{src_esc}</span><span class="ad">{esc(a["published"][:16])}</span></div><div class="at">{t}</div><div class="ae">{sm}</div></div></div><div class="sb-btn" data-share="1" title="مشاركة">↗</div></div>'
    return cards

def build_badges_all():
    seen = set()
    parts = []
    for rid in ["dz", "ar"]:
        for s in REGIONS[rid]["latest"]:
            key = s["n"].lower()
            if key not in seen:
                seen.add(key)
                parts.append(f'<span class="sb-b" style="background:{s["c"]}" data-badge="{key}">{s["n"]}</span>')
    return "".join(parts)

def build_sidebar_list(articles, max_items=6):
    items = ""
    for i, a in enumerate(articles[:max_items]):
        t = esc(a["title"])
        l = sanitize_url(a["link"])
        s = esc(a["source"])
        c = a["source_color"]
        txt = esc(a.get("text", "")[:8000])
        uid = hashlib.md5((a["title"] + a["link"]).encode()).hexdigest()[:8]
        vid = a.get("video")
        vid_id = ""
        if vid and re.match(r'^[a-zA-Z0-9_-]+$', str(vid[1])):
            vid_id = vid[1][:50]
        vid_attr = f' data-video="{vid_id}"' if vid_id else ""
        items += f'<li><span class="sb-link" data-id="{uid}" data-link="{l}" data-title="{t}" data-source="{s}" data-src-color="{c}" data-txt="{txt}"{vid_attr}><span class="sb-rank" style="background:{c}">{i+1}</span><span class="sb-text">{t}</span></span></li>'
    return f'<ol class="sb-list">{items}</ol>' if items else ""

def build_featured(art):
    if not art: return ""
    t = esc(art["title"])
    sm = esc(art["summary"])[:200] if art["summary"] else ""
    img = art.get("image")
    colors = ["#667eea","#764ba2","#f093fb","#f5576c","#4facfe","#00f2fe","#43e97b","#38f9d7","#fa709a","#fee140","#a18cd1","#fbc2eb"]
    c1 = colors[hash(t) % len(colors)]
    c2 = colors[(hash(t)+1) % len(colors)]
    if img:
        ie = esc(img)
        ih = f'<div class="ftr-img" style="background:linear-gradient(135deg,{c1},{c2})"><img src="{ie}" alt="" loading="lazy" onerror="this.style.display=\'none\'" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"><div class="ftr-overlay"></div></div>'
    else:
        ih = f'<div class="ftr-img ftr-no-img" style="background:linear-gradient(135deg,{c1},{c2})"><div class="ii">📰</div></div>'
    el = sanitize_url(art["link"])
    return f'<div class="ftr-art"><div class="ftr-inner">{ih}<div class="ftr-body"><span class="ftr-src" style="background:{art["source_color"]}">{esc(art["source"])}</span><div class="ftr-title">{t}</div><div class="ftr-summary">{sm}</div><div class="ftr-meta"><span>{esc(art["published"][:16])}</span></div></div></div></div>'

def build_badges(rid):
    return "".join(f'<span class="sb-b" style="background:{s["c"]}" data-badge="{s["n"]}">{s["n"]}</span>' for s in REGIONS[rid]["latest"])

def generate_sitemap(all_articles):
    links = set()
    for a in all_articles:
        links.add(a["link"])
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        f.write(f'  <url><loc>{BASE_URL}/</loc><priority>1.0</priority></url>\n')
        for url in list(links)[:500]:
            f.write(f'  <url><loc>{esc(url)}</loc><priority>0.6</priority></url>\n')
        f.write('</urlset>\n')
    print(f"  sitemap.xml: {len(links)} URLs")

def content_hash(articles):
    h = hashlib.sha256()
    for a in articles:
        if a.get("link") and a.get("title"):
            h.update((a["link"] + a["title"] + a.get("published","")).encode())
    return h.hexdigest()

CSS = r""":root{--bg:#121212;--card-bg:#1E1E1E;--text:#E0E0E0;--text2:#B0B0B0;--text3:#808080;--filter-bg:#1A1A1A;--badge-bg:#2A2A2A;--badge-text:#B0B0B0;--border:#333333;--shadow:rgba(0,0,0,0.3);--shadow-h:rgba(0,0,0,0.5);--accent:#D21034;--accent-hover:#E8183A;--gold:#D4A017;--line:#2A2A2A;--red:#D21034;--green:#006633}
body.light{--bg:#F5F5F5;--card-bg:#FFFFFF;--text:#1A1A1A;--text2:#555555;--text3:#999999;--filter-bg:#FAFAFA;--badge-bg:#EEEEEE;--badge-text:#555555;--border:#E0E0E0;--shadow:rgba(0,0,0,0.06);--shadow-h:rgba(0,0,0,0.12);--accent:#D21034;--accent-hover:#B00E2D;--gold:#B8860B;--line:#E0E0E0}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Noto Sans Arabic','Cairo',sans-serif;background:var(--bg);color:var(--text);line-height:1.7;-webkit-font-smoothing:antialiased;font-size:16px}
.flag-bar{height:4px;background:linear-gradient(90deg,#006633 33.33%,#fff 33.33%,#fff 66.66%,#D21034 66.66%);position:sticky;top:0;z-index:1001}
.top-bar{background:#1A1A1A;border-bottom:1px solid #2A2A2A;padding:8px 0;position:sticky;top:4px;z-index:1000;backdrop-filter:blur(10px)}
.ti{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:center}
.tb-r{display:flex;align-items:center;gap:14px}
.clock{color:#D4A017;font-weight:700;font-size:14px;direction:ltr;display:inline-block;letter-spacing:0.5px}
.dt-btn{padding:6px 14px;border-radius:18px;font-size:12px;font-weight:700;cursor:pointer;background:transparent;color:#D4A017;border:1.5px solid #D4A017;transition:all .25s;font-family:inherit}
.dt-btn:hover{background:#D4A017;color:#1A1A1A}
.masthead{border-bottom:1px solid var(--line);padding:28px 0 20px;text-align:center}
.mh-inner{max-width:1200px;margin:0 auto;padding:0 24px}
.mh-title{font-family:'Cairo',sans-serif;font-size:52px;font-weight:900;letter-spacing:1px;color:var(--text);line-height:1.2}
.mh-title .red{color:var(--red)}.mh-title .gold{color:var(--gold)}
.mh-meta{display:flex;justify-content:center;gap:24px;font-size:13px;color:var(--text3);margin-top:10px;align-items:center;flex-wrap:wrap}
.ticker{border-bottom:1px solid var(--line);background:var(--filter-bg);padding:8px 0;overflow:hidden}
.ticker-inner{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;align-items:center;gap:12px}
.ticker-label{background:var(--red);color:#fff;padding:4px 12px;border-radius:16px;font-size:12px;font-weight:700;flex-shrink:0}
.ticker-text{font-size:14px;color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.ctrls{max-width:1200px;margin:14px auto 0;padding:0 24px;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.rf-btn{padding:12px 24px;background:var(--accent);color:#fff;border:none;border-radius:12px;font-size:14px;font-weight:700;cursor:pointer;transition:all .2s;white-space:nowrap;font-family:inherit}
.rf-btn:hover{background:var(--accent-hover);transform:translateY(-1px)}
.stats{font-size:13px;color:var(--text3);white-space:nowrap}
.sub-ts{max-width:1200px;margin:12px auto 0;padding:0 24px;display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}
.sub-ts::-webkit-scrollbar{display:none}
.sub-t{padding:10px 24px;font-size:14px;font-weight:700;border:none;cursor:pointer;background:var(--badge-bg);color:var(--badge-text);border-radius:20px;transition:all .2s;font-family:inherit;white-space:nowrap;flex-shrink:0}
.sub-t:hover{background:#3A3A3A;color:var(--text)}.sub-t.active{background:var(--red);color:#fff}
.ct{max-width:1200px;margin:0 auto 30px;padding:0 24px}
.tc{display:none}.tc.active{display:block}
.sb-fav{display:inline-block;padding:4px 12px;border-radius:14px;font-size:11px;font-weight:700;cursor:pointer;color:#fff;background:var(--red);margin:2px;transition:all .2s;opacity:0.85}.sb-fav:hover{opacity:1}
.ftr-art{margin:18px 0;background:var(--card-bg);border:1px solid var(--border);border-radius:14px;overflow:hidden;cursor:pointer;transition:all .3s}
.ftr-art:hover{box-shadow:0 8px 24px var(--shadow-h);border-color:var(--red);transform:translateY(-2px)}
.ftr-inner{display:grid;grid-template-columns:1fr 1fr;min-height:320px}
.ftr-img{position:relative;background:var(--card-bg);overflow:hidden}
.ftr-img img{width:100%;height:100%;object-fit:cover}
.ftr-img .ftr-overlay{position:absolute;inset:0;background:linear-gradient(90deg,transparent 40%,rgba(0,0,0,0.4))}
.ftr-no-img{display:flex;align-items:center;justify-content:center;font-size:60px}
.ftr-body{padding:28px 32px;display:flex;flex-direction:column;justify-content:center}
.ftr-src{display:inline-block;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:700;color:#fff;margin-bottom:12px;width:fit-content}
.ftr-title{font-family:'Cairo',sans-serif;font-size:30px;font-weight:900;color:var(--text);line-height:1.3;margin-bottom:14px}
.ftr-summary{font-size:16px;color:var(--text2);line-height:1.8;overflow:hidden;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical}
.ftr-meta{display:flex;gap:14px;margin-top:14px;font-size:13px;color:var(--text3);align-items:center}
.ftr-share{width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,0.08);border:none;font-size:13px;cursor:pointer;transition:all .2s;display:flex;align-items:center;justify-content:center;color:var(--text2)}
.ftr-share:hover{background:var(--red);color:#fff}
.content-wrap{display:flex;gap:28px;align-items:flex-start}
.main-content{flex:1;min-width:0}
.sidebar{width:340px;flex-shrink:0;position:sticky;top:80px}
.sb-widget{background:var(--card-bg);border:1px solid var(--border);border-radius:14px;padding:22px 24px;margin-bottom:18px}
.sb-uni{border-right:3px solid var(--red)}
.sb-uni .sb-list li a{font-size:16px;line-height:1.6;padding:10px 14px}
.sb-uni .sb-text{font-size:16px}
.sb-wtitle{font-family:'Cairo',sans-serif;font-size:18px;font-weight:700;color:var(--text);margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid var(--red);display:flex;align-items:center;gap:8px}
.sb-list{margin:0;padding:0;list-style:none}
.sb-list li{margin-bottom:10px;line-height:1.4}
.sb-list li a,.sb-link{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--text);padding:10px 14px;border-radius:10px;transition:all .2s;font-size:15px;line-height:1.6;cursor:pointer}
.sb-list li a:hover,.sb-link:hover{background:var(--filter-bg);color:var(--red)}
.sb-rank{width:28px;height:28px;border-radius:50%;color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.sb-text{overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;flex:1;font-size:15px;color:var(--text)}
@media(max-width:1024px) and (min-width:768px){.sidebar{width:100%;position:static;display:grid!important;grid-template-columns:1fr 1fr;gap:14px}.sb-widget{margin-bottom:0}}
.gr{column-count:3;column-gap:18px}
.a{background:var(--card-bg);border-radius:14px;overflow:hidden;box-shadow:0 2px 8px var(--shadow);transition:all .3s;border:1px solid var(--border);position:relative;break-inside:avoid;margin-bottom:18px;display:inline-block;width:100%}
.a:hover{box-shadow:0 8px 20px var(--shadow-h);border-color:var(--red);transform:translateY(-3px)}
.ac{cursor:pointer;display:block}
.ai{aspect-ratio:16/9;background-size:cover;background-position:center;position:relative;overflow:hidden}
.ai img{width:100%;height:100%;object-fit:cover}
.ai .io{position:absolute;inset:0;background:linear-gradient(transparent 50%,rgba(0,0,0,0.5))}
.ai.no-img{display:flex;align-items:center;justify-content:center;background:var(--filter-bg)!important}
.ai .ii{font-size:40px;opacity:0.25}
.ab{padding:16px 18px 20px}
.am{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:8px}
.as{padding:4px 10px;border-radius:10px;font-size:11px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:55%}
.ad{font-size:12px;color:var(--text3);white-space:nowrap;direction:ltr;display:inline-block}
.at{font-family:'Cairo',sans-serif;font-size:20px;font-weight:700;color:var(--text);margin-bottom:10px;line-height:1.4}
.ae{font-size:15px;color:var(--text2);line-height:1.7;overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
.vi{position:absolute;top:12px;right:12px;width:36px;height:36px;border-radius:50%;background:rgba(211,16,52,0.9);color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;z-index:5;box-shadow:0 2px 8px rgba(0,0,0,0.3)}
.sb-btn{position:absolute;top:12px;left:12px;width:32px;height:32px;border-radius:50%;background:rgba(0,0,0,0.4);color:#fff;border:2px solid rgba(255,255,255,0.15);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;cursor:pointer;transition:all .25s;z-index:5}
.sb-btn:hover{background:var(--red);border-color:var(--red)}
body.light .sb-btn{background:rgba(255,255,255,0.8);border-color:rgba(0,0,0,0.1);color:#333}
body.light .sb-btn:hover{background:var(--red);color:#fff;border-color:var(--red)}
.nr{text-align:center;padding:48px 24px;color:var(--text3);font-size:16px}
.sl{font-family:'Cairo',sans-serif;font-size:15px;font-weight:700;margin:14px 0 12px;color:var(--text);display:flex;align-items:center;gap:8px;padding:10px 0;border-bottom:1px solid var(--line)}
.sl .ico{font-size:16px}
.a.lm{display:none}
.lm-btn{display:block;margin:16px auto;padding:12px 32px;background:var(--accent);color:#fff;border:none;border-radius:12px;font-size:14px;font-weight:700;cursor:pointer;transition:all .2s;font-family:inherit}
.lm-btn:hover{background:var(--accent-hover);transform:translateY(-1px)}
.ftr-sec{border-top:1px solid var(--line);padding:24px 0;margin-top:30px;text-align:center;color:var(--text3);font-size:13px}
.ftr-sec .lk{display:flex;justify-content:center;gap:16px;margin-bottom:8px}
.ftr-sec a{color:var(--accent);text-decoration:none;font-weight:600}
.mod-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:2000;justify-content:center;align-items:center;padding:20px;backdrop-filter:blur(4px)}.mod-progress{position:absolute;top:0;left:0;height:3px;background:var(--accent);z-index:10;transition:width .15s;width:0%}
.mod-overlay.open{display:flex}
.mod-box{background:var(--card-bg);border-radius:16px;width:100%;max-width:720px;max-height:85vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.5);border:1px solid var(--border);position:relative}
.mod-head{display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid var(--border);min-height:60px;position:sticky;top:0;background:var(--card-bg);z-index:5}
.mh-src{display:inline-block;padding:4px 14px;border-radius:10px;font-size:12px;font-weight:700;color:#fff}
.mh-close{width:44px;height:44px;border-radius:50%;border:none;background:rgba(255,255,255,0.08);color:var(--text2);font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s;flex-shrink:0}
.mh-close:hover{background:var(--red);color:#fff}
.mod-title{font-family:'Cairo',sans-serif;font-size:28px;font-weight:900;color:var(--text);padding:20px 24px 0;line-height:1.4}
.mod-body{padding:20px 24px;overflow-y:auto;flex:1;font-size:18px;line-height:2;color:var(--text2);scroll-behavior:smooth}
.mod-body p{margin-bottom:18px}
.mod-footer{display:flex;gap:10px;padding:16px 24px;border-top:1px solid var(--border);flex-wrap:wrap}
.mod-btn{padding:10px 20px;border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;transition:all .2s;text-decoration:none;display:inline-flex;align-items:center;gap:6px;font-family:inherit;border:none}
.mod-btn-primary{background:var(--accent);color:#fff}.mod-btn-primary:hover{background:var(--accent-hover)}
.mod-btn-secondary{background:var(--badge-bg);color:var(--text2);border:1px solid var(--border)}.mod-btn-secondary:hover{background:#3A3A3A}
.mod-btn-share{background:var(--badge-bg);color:var(--text2);border:1px solid var(--border);font-size:16px;padding:10px 14px;border-radius:10px;cursor:pointer;transition:all .2s}.mod-btn-share:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.mod-readmore{display:block;text-align:center;margin-top:20px;padding:12px 20px;background:var(--accent);color:#fff;border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;transition:all .2s}.mod-readmore:hover{opacity:.85;transform:translateY(-1px)}
.mod-body::-webkit-scrollbar{width:6px}
.mod-body::-webkit-scrollbar-track{background:transparent}
.mod-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
@media(max-width:600px){.mod-overlay{padding:0;align-items:stretch}.mod-overlay .mod-box{max-height:100vh;height:100vh;border-radius:0;max-width:100%}.mod-head{padding:12px 16px;min-height:56px;position:sticky;top:0;background:rgba(18,18,18,0.95);backdrop-filter:blur(10px);z-index:10}.mod-head .mh-close{width:48px;height:48px;font-size:24px;background:rgba(255,255,255,0.1);border-radius:50%}.mod-title{padding:16px 16px 0;font-size:22px;line-height:1.5}.mod-body{padding:16px;font-size:17px;line-height:1.9}.mod-footer{flex-direction:column;gap:10px;padding:16px;border-bottom:1px solid var(--border)}.mod-footer .mod-btn{justify-content:center;padding:14px 16px;font-size:15px;border-radius:12px}}
@media(max-width:768px){.sidebar{display:none!important}html{font-size:15px}.ti{padding:0 16px}.masthead{padding:18px 0 14px}.mh-title{font-size:36px}.mh-meta{gap:14px;font-size:12px}.sub-ts,.ctrls,.ct{padding:0 16px}.gr{column-count:2;column-gap:14px}.ai{aspect-ratio:16/9}.ab{padding:12px 14px 16px}.at{font-size:18px}.ae{font-size:14px}.sb-btn{width:28px;height:28px;font-size:11px;top:8px;left:8px}.ftr-art{margin:12px 0}.ftr-inner{grid-template-columns:1fr}.ftr-img{height:200px}.ftr-body{padding:20px 22px}.ftr-title{font-size:24px}.ftr-summary{font-size:15px;-webkit-line-clamp:3}}
@media(max-width:480px){.mh-title{font-size:28px}.gr{column-count:1}.ai{height:auto;aspect-ratio:16/9}.ab{padding:10px 12px 14px}.at{font-size:17px}.ae{font-size:13px}.ftr-title{font-size:20px}.ftr-img{height:160px}.ftr-body{padding:16px 18px}.mod-title{font-size:22px}.mod-body{font-size:16px}}"""

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    load_cache()
    print("=" * 50)
    print(" News Aggregator - dz-akhbar (async)")
    print("=" * 50)

    t0 = time.time()
    # Use async fetcher for 3x speed improvement
    all_articles = asyncio.run(async_fetch_all(REGIONS, max_per_source=15))
    fetch_time = time.time() - t0
    print(f"Fetched {len(all_articles)} articles in {fetch_time:.1f}s (async)")

    # Organize into regions/categories
    result = {"dz": {"latest":[], "trending":[], "popular":[], "uni":[]},
              "ar": {"latest":[], "trending":[], "popular":[], "uni":[]}}
    for a in all_articles:
        src = a.get("source_clean", "")
        # Determine region from source
        for rid in ["dz", "ar"]:
            for cat in REGIONS[rid]:
                for s in REGIONS[rid][cat]:
                    if s["n"] == src:
                        a["region"] = rid
                        if cat in result[rid]:
                            result[rid][cat].append(a)
                        break

    # Remove articles older than 3 days
    cutoff_3d = time.time() - 3*86400
    for rid in ["dz", "ar"]:
        for cat in result[rid]:
            kept = []
            for a in result[rid][cat]:
                pp = a.get("published_parsed")
                if pp:
                    try:
                        if time.mktime(pp) >= cutoff_3d:
                            kept.append(a)
                    except:
                        kept.append(a)
                else:
                    kept.append(a)
            result[rid][cat] = kept

    # Sort by date (newest first)
    for rid in ["dz", "ar"]:
        for cat in result[rid]:
            result[rid][cat].sort(key=lambda a: safe_mktime(a.get("published_parsed")), reverse=True)

    # Rebuild all_articles from filtered results
    all_articles = []
    for rid in ["dz", "ar"]:
        for cat in result[rid]:
            for a in result[rid][cat]:
                a["region"] = rid
            all_articles.extend(result[rid][cat])

    # Merge all regions into a single feed
    merged = {"latest": [], "trending": [], "popular": [], "uni": []}
    for rid in ["dz", "ar"]:
        for cat in result[rid]:
            if cat in merged:
                merged[cat].extend(result[rid][cat])
    for cat in merged:
        merged[cat].sort(key=lambda a: safe_mktime(a.get("published_parsed")), reverse=True)

    # Re-assign trending/popular to use all articles (for rich images)
    # uni uses articles from DZ_UNI + AR_UNI RSS sources only
    merged["trending"] = merged["latest"][:]
    merged["popular"] = merged["latest"][:]

    print(f"\nRendering template...")
    now_ar = datetime.now().strftime("%A, %d %B %Y - %I:%M %p")
    dz_total = len(merged["latest"])
    ar_total = sum(len(result["ar"][k]) for k in ["latest"])
    grand_total = dz_total + ar_total

    cards = {}
    for k in ["latest","trending","popular","uni"]:
        arts = merged.get(k, [])
        if k == "latest" and len(arts) > 1:
            arts = arts[1:]
        cards[k] = build_articles(arts)
    badges = build_badges_all()

    featured_dz = build_featured(result["dz"]["latest"][0] if result["dz"]["latest"] else None)

    ft_data_js = []
    for a in result["dz"]["latest"][:6]:
        ft_data_js.append({
            "title": esc(a["title"]),
            "link": sanitize_url(a["link"]),
            "summary": esc(a["summary"])[:200],
            "source": esc(a["source"]),
            "sc": a["source_color"],
            "img": esc(a.get("image") or ""),
            "pub": esc(a["published"][:16]),
        })
    _js_safe = lambda s: s.replace('<', '\\u003c').replace('>', '\\u003e')
    ft_json = _js_safe(json.dumps(ft_data_js, ensure_ascii=False))

    sb_pop = build_sidebar_list(merged["popular"])
    sb_uni = build_sidebar_list(merged.get("uni", []))

    ticker_items = [{"title": esc(a["title"]), "id": hashlib.md5((a["title"] + a["link"]).encode()).hexdigest()[:8]} for a in merged["latest"][:30]]
    ticker_json = _js_safe(json.dumps(ticker_items, ensure_ascii=False))

    rg_js = {"latest": len(merged["latest"]), "trending": len(merged["trending"]), "popular": len(merged["popular"]), "uni": len(merged["uni"])}
    rg_json = _js_safe(json.dumps(rg_js, ensure_ascii=False))

    with open(os.path.join(base, TEMPLATE_FILE), "r", encoding="utf-8") as f:
        tmpl = Template(f.read())
    html = tmpl.render(
        css=CSS, title="جريدة الجزائر — aggregator الأخبار الجزائرية",
        meta_desc="أخبار الجزائر العاجلة من أشهر الصحف الجزائرية: الشروق، النهار، الخبر، البلاد، الحوار + أخبار الجامعات و المعاهد",
        now_ar=now_ar, total=grand_total,
        cards_latest=cards["latest"], cards_trending=cards["trending"],
        cards_popular=cards["popular"], cards_uni=cards["uni"],
        featured_dz=featured_dz,
        rg_json=rg_json, ticker_json=ticker_json, ft_json=ft_json,
        sb_pop=sb_pop, sb_uni=sb_uni,
    )

    outpath = os.path.join(base, "index.html")
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html: {len(html)} bytes")

    # Generate latest_news.json for hybrid client-side refresh
    generate_latest_json(all_articles, base)

    generate_sitemap(all_articles)
    save_cache()
    print(f"cache.json: {len(_cache)} entries")

    ch = content_hash(all_articles)
    prev = ""
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r") as f:
            prev = f.read().strip()
    changed = (ch != prev)
    with open(HASH_FILE, "w") as f:
        f.write(ch)

    print(f"Done! DZ:{dz_total} AR:{ar_total} = {grand_total} total | {'CHANGED' if changed else 'UNCHANGED'}")

    if not changed:
        print("No content changes, skipping deploy.")
    return changed

def health_check(url, retries=3, delay=10):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and len(r.text) > 1000:
                print(f"  Health check #{i+1}: OK ({r.status_code}, {len(r.text)} bytes)")
                return True
            else:
                print(f"  Health check #{i+1}: BAD (status={r.status_code}, len={len(r.text)})")
        except Exception as e:
            print(f"  Health check #{i+1}: FAILED ({e})")
        if i < retries - 1:
            time.sleep(delay)
    return False

if __name__ == "__main__":
    SITE_URL = "https://dz-akhbar.surge.sh"
    once = "--once" in sys.argv
    while True:
        # Pre-update health check (3x)
        print(f"Pre-update health check for {SITE_URL}...")
        pre_ok = health_check(SITE_URL, retries=3, delay=10)

        t0 = time.time()
        changed = main()
        elapsed = time.time() - t0
        print(f"Total build time: {elapsed:.1f}s")
        if changed:
            if not once:
                print("\nDeploying to Surge.sh...")
                npx = "npx" if os.name != "nt" else "npx.cmd"
                r = subprocess.run([npx, "surge", "./", "https://dz-akhbar.surge.sh"],
                                   timeout=300)
                if r.returncode == 0:
                    print("Deploy successful!")
                else:
                    print("Deploy failed (return code: %d). Site may not have updated." % r.returncode)

                # Post-update health check (3x)
                print(f"Post-update health check for {SITE_URL}...")
                post_ok = health_check(SITE_URL, retries=3, delay=10)
                if not post_ok:
                    print("WARNING: Site may be down after deploy!")
                elif not pre_ok:
                    print("WARNING: Site was down before update, now back up.")
            else:
                print("Build done (--once mode, deploy handled by CI).")
        else:
            print("No changes — deploy skipped.")

        # Schedule next run at 6:00 AM Algeria time (UTC+1)
        now_algeria = datetime.now(ALGERIA_TZ)
        target = now_algeria.replace(hour=6, minute=0, second=0, microsecond=0)
        if now_algeria >= target:
            target += timedelta(days=1)
        sleep_time = (target - now_algeria).total_seconds()
        print(f"Next update at 06:00 Algeria time (in {sleep_time/3600:.1f} hours)")
        if once:
            print("--once mode: exiting.")
            break
        time.sleep(sleep_time)
