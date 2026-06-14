import feedparser
import time
import os
import re
from datetime import datetime

ENGLISH_SOURCES = [
    {"name": "BBC News",           "url": "https://feeds.bbci.co.uk/news/rss.xml",          "color": "#BB1919", "cat": "General"},
    {"name": "CNN",                "url": "http://rss.cnn.com/rss/edition.rss",              "color": "#CC0000", "cat": "General"},
    {"name": "The Guardian",       "url": "https://www.theguardian.com/world/rss",           "color": "#052962", "cat": "World"},
    {"name": "Reuters",            "url": "https://www.reutersagency.com/feed/",             "color": "#FF8000", "cat": "Business"},
    {"name": "Sky News",           "url": "https://feeds.skynews.com/feeds/rss/home.xml",    "color": "#0072C6", "cat": "General"},
    {"name": "NPR",                "url": "https://feeds.npr.org/1001/rss.xml",              "color": "#1A1A1A", "cat": "World"},
    {"name": "ABC News",           "url": "https://abcnews.go.com/abcnews/topstories",       "color": "#0076A8", "cat": "General"},
    {"name": "Associated Press",   "url": "https://rsshub.app/apnews",                      "color": "#E53935", "cat": "World"},
]

ARABIC_SOURCES = [
    {"name": "الجزيرة",            "url": "https://www.aljazeera.net/rss/",                  "color": "#c0392b", "cat": "أخبار"},
    {"name": "بي بي سي عربي",      "url": "https://www.bbc.com/arabic/index.xml",            "color": "#BB1919", "cat": "أخبار"},
    {"name": "سكاي نيوز عربية",    "url": "https://www.skynewsarabia.com/rss/all",           "color": "#0072C6", "cat": "أخبار"},
    {"name": "فرانس 24 عربي",      "url": "https://www.france24.com/ar/rss",                 "color": "#002395", "cat": "أخبار"},
    {"name": "روسيا اليوم",        "url": "https://www.rt.com/rss/news/",                    "color": "#C22D2D", "cat": "أخبار"},
]

TRENDING_SOURCES = [
    {"name": "Google News",        "url": "https://news.google.com/rss",                    "color": "#4285F4", "cat": "Trending"},
    {"name": "BBC Trending",       "url": "https://feeds.bbci.co.uk/news/stories/rss.xml",  "color": "#BB1919", "cat": "Trending"},
    {"name": "Guardian UK",        "url": "https://www.theguardian.com/uk/rss",             "color": "#052962", "cat": "Trending"},
    {"name": "Reuters Top",        "url": "https://www.reutersagency.com/feed/",            "color": "#FF8000", "cat": "Trending"},
    {"name": "BBC Most Read",      "url": "https://feeds.bbci.co.uk/news/stories/rss.xml",  "color": "#BB1919", "cat": "Popular"},
    {"name": "Sky Popular",        "url": "https://feeds.skynews.com/feeds/rss/home.xml",   "color": "#0072C6", "cat": "Popular"},
]

def extract_image(entry):
    if hasattr(entry, 'media_content'):
        for m in entry.media_content:
            if 'url' in m: return m['url']
    if hasattr(entry, 'media_thumbnail'):
        for t in entry.media_thumbnail:
            if 'url' in t: return t['url']
    if hasattr(entry, 'enclosures'):
        for e in entry.enclosures:
            if hasattr(e, 'href') and e.href: return e.href
    summary = entry.get('summary', '')
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
    return m.group(1) if m else None

def fetch_news(sources, max_per_source=5):
    articles = []
    for source in sources:
        print(f"  Fetching {source['name']}...")
        try:
            feed = feedparser.parse(source["url"])
            count = 0
            for entry in feed.entries:
                if count >= max_per_source: break
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                published = entry.get("published", "")
                img = extract_image(entry)
                summary = re.sub(r'<[^>]+>', '', summary).strip()
                if len(summary) > 200: summary = summary[:200] + "..."
                articles.append({
                    "title": title, "link": link, "summary": summary,
                    "source": source["name"], "source_color": source["color"],
                    "category": source["cat"], "published": published, "image": img,
                })
                count += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  Error: {e}")
    return articles

def build_articles(articles, lang):
    cards = ""
    colors = ["#667eea","#764ba2","#f093fb","#f5576c","#4facfe","#00f2fe","#43e97b","#38f9d7","#fa709a","#fee140","#a18cd1","#fbc2eb"]
    for a in articles:
        title = a["title"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")
        summary = a["summary"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")[:200] if a["summary"] else ""
        img = a.get("image")
        img_html = f'<div class="article-img" style="background-image:url(\'{img}\')"></div>' if img else f'<div class="article-img" style="background:linear-gradient(135deg,{colors[hash(title)%len(colors)]},{colors[(hash(title)+1)%len(colors)]})"></div>'
        rtl = 'style="direction:rtl;text-align:right"' if lang == "ar" else ""
        cards += f'''
        <div class="article" onclick="window.open(\'{a["link"].replace("&","&amp;")}\',\'_blank\')" data-title="{title.lower()}" data-source="{a["source"].lower()}" {rtl}>
            {img_html}
            <div class="article-body">
                <div class="article-meta">
                    <span class="article-source" style="background:{a["source_color"]}">{a["source"]}</span>
                    <span class="article-date">{a["published"][:16]}</span>
                </div>
                <div class="article-title">{title}</div>
                <div class="article-excerpt">{summary}</div>
            </div>
        </div>'''
    return cards

def generate_html(en_articles, ar_articles, trending_articles, popular_articles):
    now = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    en_cards = build_articles(en_articles, "en")
    ar_cards = build_articles(ar_articles, "ar")
    tr_cards = build_articles(trending_articles, "en")
    pop_cards = build_articles(popular_articles, "en")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NewsHub — World News Aggregator</title>
    <style>
        :root {{ --bg: #f0f2f5; --card-bg: #fff; --text: #1a1a2e; --text2: #666; --text3: #888; --filter-bg: #fff; --badge-bg: #e8e8e8; --badge-text: #555; --border: #ddd; --search-bg: #fff; --shadow: rgba(0,0,0,0.06); --shadow-h: rgba(0,0,0,0.1); }}
        body.dark {{ --bg: #121212; --card-bg: #1e1e1e; --text: #e0e0e0; --text2: #aaa; --text3: #777; --filter-bg: #1e1e1e; --badge-bg: #333; --badge-text: #aaa; --border: #333; --search-bg: #2a2a2a; --shadow: rgba(0,0,0,0.2); --shadow-h: rgba(0,0,0,0.3); }}
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif; background:var(--bg); color:var(--text); transition:background .3s,color .3s; }}
        .top-bar {{ background:#1a1a2e; color:#aaa; font-size:12px; padding:8px 0; position:sticky; top:0; z-index:1000; }}
        .top-inner {{ max-width:1400px; margin:0 auto; padding:0 20px; display:flex; justify-content:space-between; align-items:center; }}
        .top-links a {{ color:#aaa; text-decoration:none; margin-right:16px; transition:color .2s; cursor:pointer; font-size:12px; vertical-align:middle; }}
        .top-links a:hover {{ color:#fff; }}
        .dark-toggle {{ display:inline-block; padding:4px 14px; border-radius:20px; font-size:13px; font-weight:700; background:#333; color:#ffd700; border:2px solid #ffd700; transition:all .3s; margin-left:8px; }}
        .dark-toggle:hover {{ background:#ffd700; color:#333; }}
        body.dark .dark-toggle {{ background:#ffd700; color:#333; border-color:#ffd700; }}
        body.dark .dark-toggle:hover {{ background:#333; color:#ffd700; }}
        .header {{ background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%); color:white; padding:30px 0 25px; }}
        .header-inner {{ max-width:1400px; margin:0 auto; padding:0 20px; text-align:center; }}
        .site-title {{ font-size:46px; font-weight:900; letter-spacing:2px; }}
        .site-title span {{ color:#e94560; }}
        .site-tagline {{ font-size:14px; color:#8899aa; margin-top:6px; }}
        .last-update {{ font-size:12px; color:#667788; margin-top:8px; }}
        .controls {{ max-width:1400px; margin:20px auto 0; padding:0 20px; display:flex; gap:12px; flex-wrap:wrap; align-items:center; }}
        .search-box {{ flex:1; min-width:200px; position:relative; }}
        .search-box input {{ width:100%; padding:10px 40px; border:2px solid var(--border); border-radius:8px; font-size:14px; outline:none; transition:border .2s; background:var(--search-bg); color:var(--text); }}
        .search-box input:focus {{ border-color:#e94560; }}
        .search-icon {{ position:absolute; left:12px; top:50%; transform:translateY(-50%); color:#999; }}
        .refresh-btn {{ padding:10px 24px; background:#e94560; color:white; border:none; border-radius:8px; font-size:14px; font-weight:600; cursor:pointer; transition:background .2s; white-space:nowrap; }}
        .refresh-btn:hover {{ background:#c0392b; }}
        .stats {{ font-size:13px; color:#888; }}
        .tabs {{ max-width:1400px; margin:20px auto 0; padding:0 20px; display:flex; gap:0; }}
        .tab {{ padding:12px 36px; font-size:14px; font-weight:700; border:none; cursor:pointer; background:#e0e0e0; color:#666; border-radius:8px 8px 0 0; transition:all .2s; }}
        .tab:hover {{ background:#d0d0d0; }}
        .tab.active {{ background:#1a1a2e; color:white; }}
        .container {{ max-width:1400px; margin:0 auto 30px; padding:0 20px; }}
        .section {{ display:none; }}
        .section.active {{ display:block; }}
        .sub-tabs {{ display:flex; gap:0; margin:10px 0 0; }}
        .sub-tab {{ padding:8px 18px; font-size:12px; font-weight:600; border:none; cursor:pointer; background:var(--badge-bg); color:var(--badge-text); border-radius:6px 6px 0 0; transition:all .2s; }}
        .sub-tab.active {{ background:#e94560; color:white; }}
        .filter-bar {{ display:flex; gap:8px; flex-wrap:wrap; margin:15px 0; padding:12px 16px; background:var(--filter-bg); border-radius:10px; box-shadow:0 1px 4px var(--shadow); align-items:center; }}
        .filter-label {{ font-size:12px; font-weight:700; color:var(--text3); text-transform:uppercase; margin-right:6px; }}
        .cat-badge {{ padding:4px 12px; border-radius:14px; font-size:11px; font-weight:600; cursor:pointer; background:var(--badge-bg); color:var(--badge-text); border:none; transition:all .2s; }}
        .cat-badge:hover {{ background:#d0d0d0; }}
        .cat-badge.active {{ background:#1a1a2e; color:white; }}
        .src-badge {{ padding:4px 12px; border-radius:14px; font-size:11px; font-weight:600; cursor:pointer; color:white; border:none; transition:all .2s; }}
        .src-badge.active {{ transform:scale(1.08); box-shadow:0 2px 8px rgba(0,0,0,0.2); }}
        .src-badge.inactive {{ opacity:0.4; }}
        .clear-filter {{ font-size:11px; color:#e94560; cursor:pointer; text-decoration:underline; margin-left:8px; }}
        .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(360px,1fr)); gap:20px; }}
        .article {{ background:var(--card-bg); border-radius:10px; overflow:hidden; box-shadow:0 1px 4px var(--shadow); cursor:pointer; transition:all .25s; }}
        .article:hover {{ transform:translateY(-3px); box-shadow:0 6px 20px var(--shadow-h); }}
        .article-img {{ height:180px; background-size:cover; background-position:center; }}
        .article-body {{ padding:18px; }}
        .article-meta {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }}
        .article-source {{ padding:2px 10px; border-radius:10px; font-size:10px; font-weight:700; color:white; text-transform:uppercase; }}
        .article-date {{ font-size:11px; color:var(--text3); }}
        .article-title {{ font-size:16px; font-weight:700; color:var(--text); margin-bottom:8px; line-height:1.35; }}
        .article-excerpt {{ font-size:13px; color:var(--text2); line-height:1.55; }}
        .no-results {{ text-align:center; padding:60px; color:var(--text3); font-size:16px; }}
        .section-label {{ font-size:18px; font-weight:700; margin:20px 0 10px; color:var(--text); display:flex; align-items:center; gap:8px; }}
        .section-label .icon {{ font-size:22px; }}
        .footer {{ background:#1a1a2e; color:#8899aa; text-align:center; padding:30px 20px; margin-top:40px; font-size:13px; line-height:1.8; }}
        .footer a {{ color:#e94560; text-decoration:none; }}
        body.dark .footer {{ background:#0a0a0a; }}
        @media (max-width:768px) {{ .grid {{ grid-template-columns:1fr; }} .site-title {{ font-size:28px; }} .tab {{ padding:10px 20px; font-size:12px; }} .controls {{ flex-direction:column; }} .search-box {{ width:100%; }} }}
    </style>
</head>
<body>
    <div class="top-bar">
        <div class="top-inner">
            <div class="top-links">
                <a onclick="switchLang('ar')">العربية</a>
                <a onclick="switchLang('en')">English</a>
                <a onclick="toggleDark()" class="dark-toggle" id="darkToggle">🌙 Dark Mode</a>
            </div>
            <div>{now}</div>
        </div>
    </div>
    <div class="header">
        <div class="header-inner">
            <div class="site-title">News<span>Hub</span></div>
            <div class="site-tagline">Real-time news from top sources worldwide • أخبار عاجلة من أشهر المصادر</div>
            <div class="last-update">Last updated: {now} • {len(en_articles)+len(ar_articles)+len(trending_articles)+len(popular_articles)} articles</div>
        </div>
    </div>
    <div class="tabs">
        <button class="tab active" onclick="switchLang('ar')">أخبار العربية</button>
        <button class="tab" onclick="switchLang('en')">English News</button>
    </div>
    <div class="controls">
        <div class="search-box">
            <span class="search-icon">🔍</span>
            <input type="text" id="searchInput" placeholder="Search articles..." oninput="searchArticles()">
        </div>
        <button class="refresh-btn" onclick="refreshNews()" id="refreshBtn">⟳ Refresh News</button>
        <span class="stats" id="articleCount">{len(en_articles)+len(ar_articles)} articles</span>
    </div>

    <!-- Arabic Section -->
    <div class="container">
        <div id="ar-section" class="section active" style="direction:rtl; text-align:right;">
            <div class="filter-bar" id="arFilters">
                <span class="filter-label">المصدر:</span>
                {"".join(f'<span class="src-badge" style="background:{s["color"]}" onclick="filterArSource(\'{s["name"].lower()}\')">{s["name"]}</span>' for s in ARABIC_SOURCES)}
                <span class="clear-filter" onclick="clearFilters('ar')">مسح</span>
            </div>
            <div class="grid" id="arGrid">{ar_cards}</div>
            <div class="no-results" id="arNoResults" style="display:none">لا توجد مقالات تطابق بحثك.</div>
        </div>
    </div>

    <!-- English Section -->
    <div class="container">
        <div id="en-section" class="section">
            <div class="sub-tabs">
                <button class="sub-tab active" onclick="switchEnTab('latest')">📰 Latest</button>
                <button class="sub-tab" onclick="switchEnTab('trending')">🔥 Trending on Social</button>
                <button class="sub-tab" onclick="switchEnTab('popular')">⭐ Most Read</button>
            </div>

            <div id="en-latest">
                <div class="filter-bar" id="enFilters">
                    <span class="filter-label">Source:</span>
                    {"".join(f'<span class="src-badge" style="background:{s["color"]}" onclick="filterEnSource(\'{s["name"].lower()}\')">{s["name"]}</span>' for s in ENGLISH_SOURCES)}
                    <span class="clear-filter" onclick="clearFilters('en')">Clear</span>
                </div>
                <div class="grid" id="enGrid">{en_cards}</div>
                <div class="no-results" id="enNoResults" style="display:none">No articles match your search.</div>
            </div>

            <div id="en-trending" style="display:none">
                <div class="section-label"><span class="icon">🔥</span> Trending on Social Media</div>
                <div class="grid" id="trGrid">{tr_cards}</div>
            </div>

            <div id="en-popular" style="display:none">
                <div class="section-label"><span class="icon">⭐</span> Most Read</div>
                <div class="grid" id="popGrid">{pop_cards}</div>
            </div>
        </div>
    </div>

    <div class="footer">
        <p>NewsHub © 2026 — All articles belong to their respective owners. Non-commercial aggregator.</p>
        <p><a href="#" onclick="scrollToTop()">↑ Back to top</a></p>
    </div>

    <script>
        let currentLang = 'ar';
        let enSourceFilter = null, arSourceFilter = null;
        let currentEnTab = 'latest';

        function switchLang(lang) {{
            currentLang = lang;
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(lang + '-section').classList.add('active');
            document.querySelectorAll('.tab')[lang === 'ar' ? 0 : 1].classList.add('active');
            searchArticles();
        }}

        function switchEnTab(tab) {{
            currentEnTab = tab;
            document.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
            document.getElementById('en-latest').style.display = tab === 'latest' ? 'block' : 'none';
            document.getElementById('en-trending').style.display = tab === 'trending' ? 'block' : 'none';
            document.getElementById('en-popular').style.display = tab === 'popular' ? 'block' : 'none';
            // Find and activate correct sub-tab
            document.querySelectorAll('.sub-tab').forEach((t,i) => {{
                if (i === (tab === 'latest' ? 0 : tab === 'trending' ? 1 : 2)) t.classList.add('active');
            }});
        }}

        function searchArticles() {{
            const q = document.getElementById('searchInput').value.toLowerCase();
            const lang = currentLang;
            if (lang === 'ar') {{
                filterGrid('arGrid', 'arNoResults', q);
            }} else {{
                if (currentEnTab === 'latest') filterGrid('enGrid', 'enNoResults', q);
                else if (currentEnTab === 'trending') filterGrid('trGrid', null, q);
                else filterGrid('popGrid', null, q);
            }}
            updateCount();
        }}

        function filterGrid(gridId, noResId, q) {{
            const grid = document.getElementById(gridId);
            if (!grid) return;
            const articles = grid.querySelectorAll('.article');
            let count = 0;
            articles.forEach(a => {{
                const title = a.getAttribute('data-title') || '';
                const source = a.getAttribute('data-source') || '';
                const show = !q || title.includes(q) || source.includes(q);
                a.style.display = show ? '' : 'none';
                if (show) count++;
            }});
            if (noResId) {{
                document.getElementById(noResId).style.display = count === 0 ? 'block' : 'none';
            }}
        }}

        function filterEnSource(src) {{
            enSourceFilter = enSourceFilter === src ? null : src;
            updateSrcBadges('enFilters', enSourceFilter);
            if (enSourceFilter) {{
                document.querySelectorAll('#enGrid .article').forEach(a => {{
                    a.style.display = (a.getAttribute('data-source') === enSourceFilter) ? '' : 'none';
                }});
            }} else {{
                document.querySelectorAll('#enGrid .article').forEach(a => a.style.display = '');
            }}
            searchArticles();
        }}

        function filterArSource(src) {{
            arSourceFilter = arSourceFilter === src ? null : src;
            updateSrcBadges('arFilters', arSourceFilter);
            if (arSourceFilter) {{
                document.querySelectorAll('#arGrid .article').forEach(a => {{
                    a.style.display = (a.getAttribute('data-source') === arSourceFilter) ? '' : 'none';
                }});
            }} else {{
                document.querySelectorAll('#arGrid .article').forEach(a => a.style.display = '');
            }}
            searchArticles();
        }}

        function updateSrcBadges(containerId, activeVal) {{
            document.getElementById(containerId).querySelectorAll('.src-badge').forEach(b => {{
                const val = b.textContent.toLowerCase().trim();
                b.classList.toggle('active', val === activeVal);
                b.classList.toggle('inactive', activeVal && val !== activeVal);
            }});
        }}

        function clearFilters(lang) {{
            if (lang === 'en') enSourceFilter = null;
            else arSourceFilter = null;
            document.getElementById(lang + 'Filters').querySelectorAll('.active,.inactive').forEach(b => b.classList.remove('active', 'inactive'));
            document.getElementById('searchInput').value = '';
            document.querySelectorAll('.article').forEach(a => a.style.display = '');
            searchArticles();
        }}

        function updateCount() {{
            const visible = document.querySelectorAll('.article[style*="display: "], .article:not([style*="display: none"])').length;
            document.getElementById('articleCount').textContent = document.querySelectorAll('.article').length + ' articles';
        }}

        function toggleDark() {{
            document.body.classList.toggle('dark');
            const isDark = document.body.classList.contains('dark');
            localStorage.setItem('darkMode', isDark);
            document.getElementById('darkToggle').textContent = isDark ? '☀️ Light Mode' : '🌙 Dark Mode';
        }}
        if (localStorage.getItem('darkMode') === 'true') {{ document.body.classList.add('dark'); document.getElementById('darkToggle').textContent = '☀️ Light Mode'; }}

        function refreshNews() {{ window.location.href = window.location.pathname + '?refresh=' + Date.now(); }}
        function scrollToTop() {{ window.scrollTo({{ top:0, behavior:'smooth' }}); }}
    </script>
</body>
</html>'''

def main():
    base = os.path.dirname(__file__)
    print("=" * 50)
    print(" NEWSHUB - NEWS AGGREGATOR".upper())
    print("=" * 50)
    print(f"\n[1/3] English news ({len(ENGLISH_SOURCES)} sources)...")
    en = fetch_news(ENGLISH_SOURCES)
    print(f"  Got {len(en)} articles")
    print(f"\n[2/3] Arabic news ({len(ARABIC_SOURCES)} sources)...")
    ar = fetch_news(ARABIC_SOURCES)
    print(f"  Got {len(ar)} articles")
    print(f"\n[3/3] Trending & Most Read ({len(TRENDING_SOURCES)} sources)...")
    trending_popular = fetch_news(TRENDING_SOURCES)
    print(f"  Got {len(trending_popular)} articles")
    tr = [a for a in trending_popular if a["category"] == "Trending"]
    pop = [a for a in trending_popular if a["category"] == "Popular"]
    print(f"\nGenerating HTML page...")
    html = generate_html(en, ar, tr, pop)
    with open(os.path.join(base, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    total = len(en) + len(ar) + len(tr) + len(pop)
    print(f"Done! {len(en)} EN + {len(ar)} AR + {len(tr)} Trending + {len(pop)} Popular = {total} articles")

if __name__ == "__main__":
    main()
