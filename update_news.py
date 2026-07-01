import sys, feedparser, time, os, re, json, socket, hashlib, subprocess, requests, asyncio, aiohttp, random
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from deep_translator import GoogleTranslator
from jinja2 import Template

socket.setdefaulttimeout(20)
ALGERIA_TZ = timezone(timedelta(hours=1))
BASE_URL = "https://1ymenn.github.io/dz-akhbar"
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

def _text_matches_title(text, title):
    """Check if extracted text is likely from the same article as the title."""
    if not title or not text:
        return False
    words = re.findall(r'[\u0600-\u06FF]{3,}|[a-zA-Z]{4,}', title)
    if not words:
        return True
    text_lower = text.lower()
    # Quick check: first 80 chars of title appears in text
    if title.lower()[:80] in text_lower:
        return True
    match_count = 0
    for w in words:
        w_lower = w.lower()
        if w_lower in text_lower:
            match_count += 1
        else:
            stripped = re.sub(r'^(ال|لل|ب|ل|و|ف)', '', w_lower)
            if stripped and len(stripped) >= 2 and stripped in text_lower:
                match_count += 1
    return match_count >= max(1, int(len(words) * 0.5))

def _clean_fluff(text, title=""):
    """Remove promotional/fluff from article text."""
    if not text:
        return text
    # Remove article title from start of text if present
    if title:
        t = re.escape(title.strip())
        text = re.sub(r'^' + t + r'[\s\n]*', '', text).strip()
    fluff_starts = ['شارك غرِّد أرسل', 'غرِّد أرسل', 'شارك غرّد', 'غرّد أرسل',
                    'شـارك', 'نشر الخبر', 'انشر الخبر', 'غرّد', 'غرد',
                    'أرسل الخبر', 'انشر', 'شارك على', 'غرد على',
                    'تابعنا على', 'تابعونا على', 'Follow us', 'Share this',
                    'انقر هنا', 'اضغط هنا', 'اضغط على', 'اقرأ أيضاً',
                    'اقرأ المزيد', 'المزيد من الأخبار', 'اخبار مشابهة',
                    'مقالات مشابهة', 'موضوعات ذات صلة', 'مقالات قد تهمك',
                    'اخبار قد تهمك', 'شاهد أيضاً', 'طالع أيضاً', 'الاخبار ذات الصلة',
                    'لا تنسى مشاركة الخبر', 'لا تنسى المشاركة', 'شاركونا رأيكم',
                    'أضفتعليقك', 'اكتب تعليقك', '_share', 'Share',
                    'علّق على', 'اضف تعليقاً', 'اكتب تعليقاً', 'نشر الخبر على',
                    'انشر الخبر على', 'غرّد الخبر',
                    'ابعث الخبر', 'أرسل لصديق', 'ارسل لصديق',
                    'رجل أعمال وسياسي', 'رجل أعمال ورجل سياسي', 'رجل سياسي ورجل أعمال',
                    'سياسي ورجل أعمال', 'رجل أعمال ورجل سياسي',
                    'رجل أعمال وسياسي مغربي', 'رجل أعمال وسياسي عراقي',
                    'رجل أعمال وسياسي سوري', 'رجل أعمال وسياسي لبناني',
                    'رجل أعمال وسياسي جزائري', 'رجل أعمال وسياسي مصري',
                    'رجل أعمال وسياسي تونسي', 'رجل أعمال وسيافي',
                    'رجل أعمال وسيافي', 'رجل أعمال وسيافي']
    fluff_full = ['التواصل الاجتماعي', 'رابط مختصر', 'تم نسخ الرابط',
                  'شـارك', 'اضغط هنا', 'شارك في التعليقات', 'علّق على الخبر',
                  'شارك الخبر', 'انشر الخبر', 'غرّد الخبر', 'أرسل الخبر',
                  'متابعة', 'المزيد', 'اقرأ أيضاً', 'المزيد من الأخبار',
                  'اخبار مشابهة', 'مقالات مشابهة', 'موضوعات ذات صلة',
                  'شارك على واتساب', 'شارك على فيسبوك', 'شارك على تويتر',
                  'شارك على لينكدإن', 'انشر على واتساب', 'انشر على فيسبوك']
    # Pattern to match image captions: "text, date (photographer/source)"
    _img_caption_re = re.compile(
        r'^.{5,120}(?:،|,)\s*\d{1,2}\s+\w+\s+\d{4}\s*\([^()]+/(?:getty|Getty|رويترز|Reuters|أناضول|الأناضول|فرانس برس|AFP| AFP)\)\s*$',
        re.IGNORECASE
    )
    fluff_end_re = [
        r'[\n\s]*إضغط\s+على\s+الصورة\s+لتحميل\s+تطبيق.*$',
        r'[\n\s]*للإطلاع\s+على\s+كل\s+الأخبار.*$',
        r'[\n\s]*على\s+البلاي\s+ستور.*$',
        r'[\n\s]*بلاي\s+ستور.*$',
        r'[\n\s]*PLAY\s+STORE.*$',
        r'[\n\s]*google\s+play.*$',
        r'[\n\s]*اشترك\s+في\s+قناتنا\s+على\s+يوتيوب.*$',
        r'[\n\s]*اشترك\s+في\s+قناتنا.*$',
        r'[\n\s]*قناة\s+الخبرTV.*$',
        r'[\n\s]*تم\s+نسخ\s+الرابط.*$',
        r'[\n\s]*©\s*(?:جميع\s+)?الحقوق\s+محفوظة.*$',
        r'[\n\s]*جميع\s+الحقوق\s+محفوظة.*$',
        r'[\n\s]*مختصر.*نسخ.*الرابط.*$',
        r'[\n\s]*رابط\s+مختصر.*$',
    ]
    junk_line_re = re.compile(
        r'^(?:'
        r'(?:صورة|صور)[:\s,]+.*'
        r'|(?:المصدر|المصادر)[:\s,]+.*'
        r'|(?:(?:تابعونا|تابعونا على)[:\s].*)'
        r'|(?:(?:اسم|أنا|هو|هي)\s+(?:كاتب|مؤلف|صحفي|مراسل|مذيع|مقدمة)[:\s].*)'
        r'|(?:(?: bbc |بي بي سي)(?:عربي)?(?:\s*$))'
        r'|(?:©\s*\d{4}(?:\s*,?\s*bbc)?)'
        r'|(?:آخر\s+تحديث[:\s].*)'
        r'|(?:تم\s+النشر\s+(?:أولاً|في)[:\s].*)'
        r'|(?:النشرة\s+الإخبارية.*)'
        r'|^(?:مراسل[ة]?\s+(?:لبي بيسي|للانباء|للشؤون|السياسية|للإذاعة|للقناتين|بي بي سي).*)$'
        r'|^(?:بي بي سي\s*[-–—]\s*.+)$'
        r'|^(?:مراسلا\s+.+)$'
        r'|^(?:مقدمة\s+.+)$'
        r'|^[\u0600-\u06FF\s]{3,40}$'
        r'|(?:share|whatsapp|facebook|twitter|telegram|linkedin|pinterest|email|reddit|irim_share|Share this|Follow us)'
        r'|(?:اضغط هنا للتنزيل|اضغط هنا|انقر هنا|اقرأ أيضاً|اقرأ المزيد)'
        r'|(?:المزيد من الأخبار|اخبار مشابهة|مقالات مشابهة|موضوعات ذات صلة)'
        r'|(?:مقالات قد تهمك|اخبار قد تهمك|شاهد أيضاً|طالع أيضاً)'
        r'|(?:لا تنسى مشاركة الخبر|لا تنسى المشاركة|شاركونا رأيكم)'
        r'|(?:أضفتعليقك|اكتب تعليقك|علّق على الخبر)'
        r'|(?:اضف تعليقاً|اكتب تعليقاً|نشر الخبر على)'
        r'|(?:انشر الخبر على|غرّد الخبر|ابعث الخبر|أرسل لصديق|ارسل لصديق)'
        r'|(?:irim_share_whatsapp|irim_share_facebook|irim_share_twitter|irim_share_telegram)'
        r'|(?:irim_share_linkedin|irim_share_email|irim_share_pinterest|irim_share_reddit)'
        r'|(?:irim_share_copy|irim_share)'
        r'|^(?:شارك\s|شارك$)'  # "شارك" only at start of line
        r'|^(?:غرّد\s|غرّد$|غرد\s|غرد$)'  # "غرّد" only at start of line
        r'|^(?:أرسل\s|أرسل$|انشر\s|انشر$)'  # "أرسل"/"انشر" only at start of line
        r'|^(?:تابعنا\s|تابعنا$|تابعونا\s|تابعونا$)'  # "تابعنا"/"تابعونا" only at start of line
        r'|(?:\(\s*[^()]{2,40}\s*/\s*(?:getty|رويترز|أناضول|فرانس برس|الأناضول|afp|reuters|getty| AFP| Reuters)\s*\))'  # photo caption: (source/getty)
        r'|^\s*\([^()]{0,10}(?:getty|رويترز|أناضول|فرانس برس|الأناضول|afp|reuters| AFP| Reuters)[^()]*\)\s*$'  # standalone caption line: ( Photographer/Getty)
        r'|^\s*\w+\s+\d{4}\s*\([^()]+\)\s*$'  # standalone: "يونيو 2026 (photographer/source)"
        r'|^\s*\d{1,2}\s+\w+\s+\d{4}\s*\([^()]+\)\s*$'  # "21 يونيو 2026 (photographer/source)"
        r'|^\s*\w+\s+\w+\s*\d{4}\s*\([^()]+\)\s*$'  # "الدوار البيضاء، 7 أكتوبر 2023 (فرانس برس)"
        r'|(?:رجل أعمال وسياسي|رجل أعمال ورجل سياسي|رجل سياسي ورجل أعمال)'  # person bio starts
        r'|^(?:\w+\s+){1,3}(?:سياسي|رجل أعمال|رجل سياسي|رجل أعمال وسياسي|رجل أعمال ورجل سياسي)'  # person bio: "X رجل أعمال وسياسي"
        r'|^(?:[^()]{5,80})\s*\(\s*[^()]{2,50}\s*/\s*(?:getty|رويترز|أناضول|فرانس برس|الأناضول|AFP|Reuters|Getty| AFP| Reuters)\s*\)\s*$'  # full caption: "text (photographer/source)"
        r')',
        re.IGNORECASE | re.MULTILINE
    )

    paras = text.split('\n\n')
    clean = []
    for p in paras:
        p_stripped = p.strip()
        # Skip entire paragraph if it's ONLY fluff
        if any(p_stripped.lower() == f.lower() for f in fluff_full):
            continue
        # Skip image captions
        if _img_caption_re.match(p_stripped):
            continue
        # Remove junk lines within paragraph
        lines = p_stripped.split('\n')
        lines = [l for l in lines if not junk_line_re.match(l.strip())]
        p_stripped = '\n'.join(lines).strip()
        # Clean fluff from beginning
        for fs in fluff_starts:
            if p_stripped.lower().startswith(fs.lower()):
                p_stripped = re.sub(r'^' + re.escape(fs) + r'[\s\d]*', '', p_stripped).strip()
                break
        # Clean fluff from end using regex
        for fe_re in fluff_end_re:
            p_stripped = re.sub(fe_re, '', p_stripped).strip()
        # Clean trailing punctuation
        p_stripped = p_stripped.rstrip('،.:- ')
        # Skip empty or very short paragraphs after cleaning
        if len(p_stripped) < 15:
            continue
        clean.append(p_stripped)
    result = '\n\n'.join(clean).strip()
    # Strip trailing period/comma from last line
    if result:
        last_newline = result.rfind('\n')
        if last_newline >= 0:
            last_line = result[last_newline+1:].rstrip('،.:- ')
            result = result[:last_newline+1] + last_line
        else:
            result = result.rstrip('،.:- ')
    return result if len(result) > 10 else ""

DZ_LATEST = [
    {"n":"الشروق","u":"https://www.echoroukonline.com/feed/","c":"#c0392b"},
    {"n":"النهار","u":"https://www.ennaharonline.com/feed/","c":"#2980b9"},
    {"n":"الخبر","u":"https://elkhabar.com/feed/","c":"#2c3e50"},
    {"n":"البلاد","u":"https://www.elbilad.net/feed","c":"#27ae60"},
    {"n":"الحوار","u":"https://elhiwar.dz/feed/","c":"#e67e22"},
    {"n":"الهداف","u":"http://feeds.feedburner.com/GalerieArtciles","c":"#e74c3c"},
    {"n":"دزاير توب","u":"https://www.dzair-tube.dz/feed/","c":"#1abc9c"},
    {"n":"الجمهورية","u":"https://www.eldjoumhouria.dz/feed/","c":"#c0392b"},
    {"n":"الراية","u":"https://errayaonline.net/feed/","c":"#2980b9"},
    {"n":"الجزائر الجديدة","u":"https://www.eldjazaireldjadida.dz/feed/","c":"#16a085"},
    {"n":"الموعد","u":"https://elmaouid.dz/feed/","c":"#8e44ad"},
    {"n":"آخر ساعة","u":"https://www.akhbarsaa.com/feed/","c":"#27ae60"},
    {"n":"الطنين","u":"https://www.eltinneen.com/feed/","c":"#e74c3c"},
    {"n":"ال晚报","u":"https://www.elwatan.com/feed/","c":"#2980b9"},
    {"n":"الفجر","u":"https://www.el-fadjr.com/feed/","c":"#16a085"},
    {"n":"المساء","u":"https://www.elmassa.com/feed/","c":"#c0392b"},
    {"n":"الصباح","u":"https://www.elsabah.com/feed/","c":"#27ae60"},
    {"n":"الأحداث","u":"https://www.elhadath.com/feed/","c":"#e67e22"},
    {"n":"المستقبل","u":"https://www.elmustaqbal.com/feed/","c":"#8e44ad"},
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
    {"n":"جامعة البليدة 2","u":"https://www.univ-blida2.dz/feed/","c":"#d4ac0d"},
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
    {"n":"مركز تطوير التكنولوجيات المتطورة","u":"https://www.cdta.dz/feed/","c":"#16a085"},
    {"n":"جامعة الأمير عبد القادر","u":"https://www.univ-Constantine.dz/feed/","c":"#8e44ad"},
    {"n":"جامعة فرانتز فانون","u":"https://www.univ-bouira.dz/feed/","c":"#27ae60"},
    {"n":"جامعة خليل بوزيد","u":"https://www.univ-tlemcen.dz/feed/","c":"#117a65"},
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
    # Fix broken URLs where feed/article URL gets prepended (e.g. domain.com/feed///domain.com/...)
    m = re.match(r'^(https?://[^/]+)/[^/]*/{2,}[^/]+/(.+)$', u)
    if m:
        u = m.group(1) + '/' + m.group(2)
    # Upgrade WordPress thumbnail sizes
    m = re.search(r'-(\d+)x(\d+)\.(jpg|jpeg|png|gif|webp)', u, re.IGNORECASE)
    if m and int(m.group(1)) < 400:
        u = u.replace(f"-{m.group(1)}x{m.group(2)}", "")
    # elbilad.net: /original/ returns 404, use /article/d_ prefix instead
    if 'elbilad.net' in u:
        u = re.sub(r'/storage/images/original/', '/storage/images/article/d_', u)
        return u
    # elkhabar.com: /original/ returns 404, use /article/g_ prefix instead
    if 'elkhabar.com' in u:
        u = re.sub(r'/storage/images/original/', '/storage/images/article/g_', u)
        return u
    # Upgrade RT thumbnail → original (only for RT domains)
    if 'rtarabic.com' in u or 'mf.b37mrtl.ru' in u:
        u = re.sub(r'/thumbnail/', '/original/', u)
        u = re.sub(r'/article/', '/original/', u)
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
    # First try JSON-LD articleBody
    try:
        ld_matches = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page_html, re.DOTALL)
        for ld in ld_matches:
            try:
                data = json.loads(ld)
                if isinstance(data, dict):
                    # Handle @graph format
                    if '@graph' in data:
                        for item in data['@graph']:
                            body = item.get('articleBody', '')
                            if body and len(body) > 100:
                                return body
                    elif 'articleBody' in data:
                        body = data['articleBody']
                        if len(body) > 100:
                            return body
            except:
                pass
    except:
        pass
    # Specific handler for eldjoumhouria.dz (text in #textContent div)
    if "eldjoumhouria.dz" in link:
        m = re.search(r'id="textContent"\s*>(.*?)$', page_html, re.DOTALL|re.IGNORECASE)
        if m:
            chunk = m.group(1)
            # Find end of content: look for closing tags that signal end of article
            end_markers = ['</div>', '</article>', '<!-- Post Single', '<div class="sharethis']
            best_end = len(chunk)
            for marker in end_markers:
                idx = chunk.find(marker)
                if idx > 0 and idx < best_end:
                    best_end = idx
            content_html = chunk[:best_end]
            text = re.sub(r'<[^>]+>', ' ', content_html)
            text = html_mod.unescape(text)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 100:
                return text
    # Specific handler for alaraby.co.uk (<main> has full article, field--name-body only lead)
    if "alaraby.co.uk" in link:
        # Skip actual live blogs: check title or URL for live blog indicators (not CSS class names)
        is_live = False
        title_m = re.search(r'<title[^>]*>(.*?)</title>', page_html, re.DOTALL|re.IGNORECASE)
        if title_m and re.search(r'\blive\b.*(blog|updates|coverage)|مباشر|التحديثات الحية', title_m.group(1), re.IGNORECASE):
            is_live = True
        if re.search(r'/liveblog/|/live-blog/', link, re.IGNORECASE):
            is_live = True
        if is_live:
            meta_desc = re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)["\']', page_html, re.IGNORECASE)
            if meta_desc:
                desc = html_mod.unescape(meta_desc.group(1)).strip()
                if len(desc) > 50:
                    return desc
            return ""
        # Extract from <main> first (full article content)
        main_m = re.search(r'<main[^>]*>(.*?)</main>', page_html, re.DOTALL|re.IGNORECASE)
        if main_m:
            paras = re.findall(r'<p[^>]*>(.*?)</p>', main_m.group(1), re.DOTALL|re.IGNORECASE)
            clean = []
            seen = set()
            for p in paras:
                text = re.sub(r'<[^>]+>', ' ', p)
                text = html_mod.unescape(text)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) < 25:
                    continue
                # Skip photo captions (Getty, AP, AFP, etc.)
                if re.search(r'Getty|AP|AFP|فرانس برس|رويترز|كوستフرا|كوني فرانس|tass', text, re.IGNORECASE):
                    continue
                # Skip font/language indicator lines
                if re.search(r'\+?\s*الخط\s*-\s*(Arabic|English|French)', text):
                    continue
                # Stop at related articles section (short paragraph after long ones)
                if clean and len(text) < 50 and len(clean[-1]) > 100:
                    break
                # Dedup
                short = text[:60]
                if short in seen:
                    continue
                seen.add(short)
                clean.append(text)
            if clean and sum(len(x) for x in clean) > 200:
                return '\n\n'.join(clean)
        # Fallback: field--name-body (only has lead paragraphs)
        body_m = re.search(r'field--name-body[^>]*>(.*?)</div>\s*</div>\s*</div>', page_html, re.DOTALL|re.IGNORECASE)
        if not body_m:
            body_m = re.search(r'field--name-body[^>]*>(.*?)</div>', page_html, re.DOTALL|re.IGNORECASE)
        if body_m:
            paras = re.findall(r'<p[^>]*>(.*?)</p>', body_m.group(1), re.DOTALL|re.IGNORECASE)
            clean = []
            for p in paras:
                text = re.sub(r'<[^>]+>', ' ', p)
                text = html_mod.unescape(text)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) >= 25:
                    clean.append(text)
            if clean:
                return '\n\n'.join(clean)
    # Specific handler for aawsat.com (readability picks wrong content area)
    if "aawsat.com" in link:
        art_m = re.search(r'<article[^>]*>(.*?)</article>', page_html, re.DOTALL|re.IGNORECASE)
        if art_m:
            paras = re.findall(r'<p[^>]*>(.*?)</p>', art_m.group(1), re.DOTALL|re.IGNORECASE)
            clean = []
            for p in paras:
                text = re.sub(r'<[^>]+>', ' ', p)
                text = html_mod.unescape(text)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) >= 25:
                    clean.append(text)
            if clean:
                return '\n\n'.join(clean)
    # Try BBC __NEXT_DATA__ (Next.js SPA)
    if "bbc.com" in link:
        bbc_text = _extract_bbc_next_data(page_html)
        if bbc_text and len(bbc_text) > 50:
            return bbc_text
    # Try meta description (save for later fallback)
    meta_desc_text = ""
    try:
        meta_desc = re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)["\']', page_html, re.IGNORECASE)
        if meta_desc:
            meta_desc_text = html_mod.unescape(meta_desc.group(1)).strip()
    except:
        pass
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
        content_classes = ["artx", "editor-content", "entry-content", "article-body", "post-content", "story-body", "article-content", "post-body"]
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
            if len(text) > 50: return text
            return meta_desc_text if meta_desc_text else ""
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
    if not clean:
        return meta_desc_text if meta_desc_text else ""
    text = '\n\n'.join(clean)
    return text

def extract_video(link):
    if not link: return None
    html, _ = fetch_page(link)
    if not html: return None
    # Known site-wide background video IDs to skip
    _bg_vids = {'qYPOMpzl9Tg'}  # الجمهورية site background
    # Try to find video within article content area first
    article_area = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL|re.IGNORECASE)
    if not article_area:
        article_area = re.search(r'class="(?:article|post|entry|content)-body[^"]*"[^>]*>(.*?)</(?:div|section)>', html, re.DOTALL|re.IGNORECASE)
    search_html = article_area.group(1) if article_area else html
    # YouTube iframe embed
    m = re.search(r'<iframe[^>]+src="([^"]*youtube\.com/embed/([a-zA-Z0-9_-]+)[^"]*)"', search_html, re.IGNORECASE)
    if m and m.group(2) not in _bg_vids: return "youtube", m.group(2)
    # YouTube watch URL
    m = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', search_html, re.IGNORECASE)
    if m and m.group(1) not in _bg_vids: return "youtube", m.group(1)
    # Short youtu.be URL
    m = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', search_html, re.IGNORECASE)
    if m and m.group(1) not in _bg_vids: return "youtube", m.group(1)
    # Dailymotion
    m = re.search(r'dailymotion\.com/embed/video/([a-zA-Z0-9]+)', search_html, re.IGNORECASE)
    if m: return "dailymotion", m.group(1)
    # Facebook video
    m = re.search(r'facebook\.com/plugins/video\.php\?href=([^"&]+)', search_html, re.IGNORECASE)
    if m: return "facebook", m.group(1)
    return None

def fetch_og_image(link):
    if not link:
        return None
    html, _ = fetch_page(link)
    if not html:
        return None
    _reject = re.compile(r'logo|icon|avatar|banner|spacer|pixel|nothumb|nothumbs_[dg]|no[._-]?image|placeholder|/default\.|DefaultImage|970x90', re.IGNORECASE)
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
            # Use parse_published_str for the real date (feedparser may default to today for custom formats)
            real_ts = parse_published_str(e.get("published", ""))
            if real_ts:
                if real_ts < cutoff_2d:
                    continue
            elif hasattr(e, 'published_parsed') and e.published_parsed:
                pub_ts = time.mktime(e.published_parsed)
                if pub_ts < cutoff_2d:
                    continue
            t = e.get("title", "")
            l = e.get("link", "")
            sm = e.get("summary", "")
            p = e.get("published", "")
            img = extract_image(e)
            if img and re.search(r'nothumb|nothumbs_[dg]|no[._-]?image|placeholder|/default\.|DefaultImage|970x90', img, re.IGNORECASE):
                img = None
            if not img:
                img = fetch_og_image(l)
            sm = re.sub(r'<[^>]+>', '', sm).strip()
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
            # Filter: Algeria El Djadida — only "أهم الأخبار" tag
            if source["n"] == "الجزائر الجديدة":
                tags = [tag.get("term", "") for tag in e.get("tags", [])]
                if "أهم الأخبار" not in tags:
                    continue
            # Filter: Al-Moubad — skip PDF archive page
            if source["n"] == "الموعد" and "اليومي" in t:
                continue
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
                a = txt_futures[f]
                if txt and _text_matches_title(txt, a.get("title", "")):
                    a["text"] = txt
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
    for a in arts:
        if a.get("text"):
            a["text"] = _clean_fluff(a["text"], a.get("title", ""))
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
    _reject = re.compile(r'logo|icon|avatar|banner|spacer|pixel|nothumb|nothumbs_[dg]|no[._-]?image|placeholder|/default\.|DefaultImage|970x90', re.IGNORECASE)
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
    # Check JSON-LD for image
    ld_matches = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    for ld in ld_matches:
        try:
            data = json.loads(ld)
            if isinstance(data, dict):
                img = data.get("image", "")
                if isinstance(img, list) and img:
                    img = img[0]
                if isinstance(img, str) and img:
                    img_url = strip_wp_thumb(img)
                    if not _reject.search(img_url):
                        return clean_url(img_url)
        except:
            pass
    imgs = re.findall(r'<img[^>]+src\s*=\s*"([^"]+\.(?:jpg|jpeg|png|gif|webp))"', html, re.IGNORECASE)
    for i in imgs:
        i = strip_wp_thumb(i)
        if not _reject.search(i):
            if not re.match(r'https?://', i):
                from urllib.parse import urljoin
                i = urljoin(link, i)
            return clean_url(i)
    return None

def _extract_bbc_next_data(html):
    """Extract full article text from BBC Arabic __NEXT_DATA__ (Next.js SPA)."""
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return ""
    try:
        nd = json.loads(m.group(1))
        pd = nd.get("props", {}).get("pageProps", {}).get("pageData", {})
        blocks = pd.get("content", {}).get("model", {}).get("blocks", [])
    except (json.JSONDecodeError, KeyError, TypeError):
        return ""
    # Block types to skip (junk)
    skip_types = {"video", "image", "rawImage", "aresMediaMetadata",
                  "relatedContent", "optimoLinkMetadata", "timestamp",
                  "socialMediaEmbed", "iframe", "gallery", "ticker",
                  "liveEvent", "podcast", "weather"}
    all_text = []
    def _walk(blocks, depth=0):
        for b in blocks:
            btype = b.get("type", "")
            model = b.get("model", {})
            # Skip junk block types entirely
            if btype in skip_types:
                continue
            if btype == "text":
                for ib in model.get("blocks", []):
                    ibtype = ib.get("type", "")
                    imodel = ib.get("model", {})
                    if ibtype == "paragraph":
                        for tb in imodel.get("blocks", []):
                            if tb.get("type") == "fragment":
                                frag = tb.get("model", {}).get("text", "").strip()
                                if frag:
                                    all_text.append(frag)
                    elif ibtype == "heading":
                        for tb in imodel.get("blocks", []):
                            if tb.get("type") == "fragment":
                                frag = tb.get("model", {}).get("text", "").strip()
                                if frag:
                                    all_text.append(frag)
            elif "blocks" in model:
                _walk(model["blocks"], depth + 1)
    _walk(blocks)
    return "\n\n".join(all_text)

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
                # Extract text: try JSON-LD articleBody first (most reliable)
                try:
                    import html as html_mod
                    ld_blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL|re.IGNORECASE)
                    for block in ld_blocks:
                        try:
                            ld = json.loads(block)
                            if isinstance(ld, list):
                                ld = ld[0] if ld else {}
                            # Handle @graph format
                            if "@graph" in ld:
                                for item in ld["@graph"]:
                                    body = item.get("articleBody", "")
                                    if body and len(body) > 50:
                                        a["text"] = body
                                        break
                            else:
                                body = ld.get("articleBody", "")
                                if body and len(body) > 50:
                                    a["text"] = body
                            if a.get("text"):
                                break
                        except:
                            pass
                except:
                    pass
                # Specific handler for aawsat.com (readability picks wrong content)
                if not a.get("text") and "aawsat.com" in link:
                    art_m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL|re.IGNORECASE)
                    if art_m:
                        paras = re.findall(r'<p[^>]*>(.*?)</p>', art_m.group(1), re.DOTALL|re.IGNORECASE)
                        clean = []
                        for p in paras:
                            text = re.sub(r'<[^>]+>', ' ', p)
                            text = html_mod.unescape(text)
                            text = re.sub(r'\s+', ' ', text).strip()
                            if len(text) >= 25:
                                clean.append(text)
                        if clean:
                            a["text"] = '\n\n'.join(clean)
                # Specific handler for eldjoumhouria.dz (text in #textContent div)
                if not a.get("text") and "eldjoumhouria.dz" in link:
                    m = re.search(r'id="textContent"\s*>(.*?)$', html, re.DOTALL|re.IGNORECASE)
                    if m:
                        chunk = m.group(1)
                        end_markers = ['</div>', '</article>', '<!-- Post Single', '<div class="sharethis']
                        best_end = len(chunk)
                        for marker in end_markers:
                            idx = chunk.find(marker)
                            if idx > 0 and idx < best_end:
                                best_end = idx
                        content_html = chunk[:best_end]
                        text = re.sub(r'<[^>]+>', ' ', content_html)
                        text = html_mod.unescape(text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        if len(text) > 100:
                            a["text"] = text
                # Specific handler for alaraby.co.uk (<main> has full article, field--name-body only lead)
                if not a.get("text") and "alaraby.co.uk" in link:
                    # Skip actual live blogs: check title or URL for live blog indicators
                    is_live = False
                    title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL|re.IGNORECASE)
                    if title_m and re.search(r'\blive\b.*(blog|updates|coverage)|مباشر|التحديثات الحية', title_m.group(1), re.IGNORECASE):
                        is_live = True
                    if re.search(r'/liveblog/|/live-blog/', link, re.IGNORECASE):
                        is_live = True
                    if is_live:
                        meta_desc = re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                        if meta_desc:
                            desc = html_mod.unescape(meta_desc.group(1)).strip()
                            if len(desc) > 50:
                                a["text"] = desc
                    # Extract from <main> first (full article content)
                    if not a.get("text"):
                        main_m = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL|re.IGNORECASE)
                        if main_m:
                            paras = re.findall(r'<p[^>]*>(.*?)</p>', main_m.group(1), re.DOTALL|re.IGNORECASE)
                            clean = []
                            seen = set()
                            for p in paras:
                                text = re.sub(r'<[^>]+>', ' ', p)
                                text = html_mod.unescape(text)
                                text = re.sub(r'\s+', ' ', text).strip()
                                if len(text) < 25:
                                    continue
                                if re.search(r'Getty|AP|AFP|فرانس برس|رويترز|كوستفرا|كوني فرانس|tass', text, re.IGNORECASE):
                                    continue
                                if re.search(r'\+?\s*الخط\s*-\s*(Arabic|English|French)', text):
                                    continue
                                if clean and len(text) < 50 and len(clean[-1]) > 100:
                                    break
                                short = text[:60]
                                if short in seen:
                                    continue
                                seen.add(short)
                                clean.append(text)
                            if clean and sum(len(x) for x in clean) > 200:
                                a["text"] = '\n\n'.join(clean)
                    # Fallback: field--name-body (only has lead paragraphs)
                    if not a.get("text"):
                        body_m = re.search(r'field--name-body[^>]*>(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL|re.IGNORECASE)
                        if not body_m:
                            body_m = re.search(r'field--name-body[^>]*>(.*?)</div>', html, re.DOTALL|re.IGNORECASE)
                        if body_m:
                            paras = re.findall(r'<p[^>]*>(.*?)</p>', body_m.group(1), re.DOTALL|re.IGNORECASE)
                            clean = []
                            for p in paras:
                                text = re.sub(r'<[^>]+>', ' ', p)
                                text = html_mod.unescape(text)
                                text = re.sub(r'\s+', ' ', text).strip()
                                if len(text) >= 25:
                                    clean.append(text)
                            if clean:
                                a["text"] = '\n\n'.join(clean)
                # Fallback: BBC __NEXT_DATA__ (Next.js SPA)
                if not a.get("text") and "bbc.com" in link:
                    bbc_text = _extract_bbc_next_data(html)
                    if bbc_text and len(bbc_text) > 50:
                        a["text"] = bbc_text
                # Fallback: targeted article selectors
                if not a.get("text"):
                    for sel in [r'<div[^>]*class="[^"]*(?:artx|article-body|article-content|entry-content|post-content|story-body|article__body)[^"]*"[^>]*>(.*?)</div>',
                                r'<article[^>]*>(.*?)</article>']:
                        m = re.search(sel, html, re.DOTALL|re.IGNORECASE)
                        if m:
                            raw = re.sub(r'<script[^>]*>.*?</script>', '', m.group(1), flags=re.DOTALL)
                            raw = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL)
                            paras = re.findall(r'<p[^>]*>(.*?)</p>', raw, re.DOTALL|re.IGNORECASE)
                            clean = []
                            for p in paras:
                                text = re.sub(r'<[^>]+>', ' ', p)
                                text = html_mod.unescape(text)
                                text = re.sub(r'\s+', ' ', text).strip()
                                if len(text) >= 25:
                                    clean.append(text)
                            if clean:
                                txt = '\n\n'.join(clean)
                                # Strong check: article title must appear at start of text
                                title_str = a.get("title", "")
                                title_lower = title_str.lower()
                                txt_lower = txt.lower()
                                # Check if title appears in first 200 chars
                                if title_lower[:50] in txt_lower[:200]:
                                    a["text"] = txt
                                    break
                                # Or first paragraph contains 60%+ title words
                                first_para = clean[0].lower() if clean else ""
                                title_words = re.findall(r'[\u0600-\u06FF]{3,}', title_str)
                                if title_words and first_para:
                                    matches = sum(1 for w in title_words if w.lower() in first_para)
                                    if matches >= len(title_words) * 0.6:
                                        a["text"] = txt
                                        break
                                clean = []
                # Fallback: readability with title validation
                if not a.get("text"):
                    try:
                        from readability import Document
                        doc = Document(html)
                        content_html = doc.summary()
                        paras = re.findall(r'<p[^>]*>(.*?)</p>', content_html, re.DOTALL|re.IGNORECASE)
                        clean = []
                        for p in paras:
                            text = re.sub(r'<[^>]+>', ' ', p)
                            text = html_mod.unescape(text)
                            text = re.sub(r'\s+', ' ', text).strip()
                            if len(text) >= 25:
                                clean.append(text)
                        if clean:
                            txt = '\n\n'.join(clean)
                            title_str = a.get("title", "")
                            if _text_matches_title(txt, title_str):
                                a["text"] = txt
                            else:
                                # Title doesn't match — try to find matching paragraphs
                                title_words = re.findall(r'[\u0600-\u06FF]{3,}', title_str)
                                matching = [p for p in clean if sum(1 for w in title_words if w in p) >= max(1, len(title_words) * 0.3)]
                                if matching and len(matching) >= 2:
                                    a["text"] = '\n\n'.join(matching)
                                elif len(clean) >= 3 and len(txt) >= 500:
                                    # Only trust if text is long enough to be a real article
                                    a["text"] = txt
                    except:
                        pass
                # Fallback: meta description
                if not a.get("text"):
                    meta_desc = re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                    if meta_desc:
                        desc = html_mod.unescape(meta_desc.group(1)).strip()
                        if len(desc) > 50:
                            a["text"] = desc
                # Extract video
                m = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]+)', html, re.IGNORECASE)
                if not m:
                    m = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', html, re.IGNORECASE)
                if not m:
                    m = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', html, re.IGNORECASE)
                if m and re.match(r'^[a-zA-Z0-9_-]+$', m.group(1)):
                    a["video"] = ("youtube", m.group(1))
                # Extract image if missing or is static/breaking placeholder or broken URL
                cur_img = a.get("image", "")
                is_static = bool(re.search(r'static\.|breaking|nothumb|nothumbs_[dg]|no[._-]?image|placeholder|/default\.|DefaultImage|970x90', cur_img, re.IGNORECASE)) if cur_img else False
                is_broken = bool(re.search(r'feed/{2,}|/original/.*(?:elbilad|elkhabar|elhiwar)', cur_img, re.IGNORECASE)) if cur_img else False
                if not cur_img or is_static or is_broken:
                    img = _extract_og_from_html(html, link)
                    if img:
                        a["image"] = img

        tasks = [_enhance_article(a) for a in all_articles if a.get("link")]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Fallback: if text is empty, use RSS summary (if it has real content)
        for a in all_articles:
            if not a.get("text") and a.get("summary"):
                sm = a["summary"]
                arabic_words = re.findall(r'[\u0600-\u06FF]{3,}', sm)
                if len(sm) >= 50 or len(arabic_words) >= 3:
                    a["text"] = sm
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
                            txt = '. '.join(chunks[:20])
                            if _text_matches_title(txt, a.get("title", "")):
                                a["text"] = txt
                except:
                    pass

        # Clean fluff from all article text
        for a in all_articles:
            if a.get("text"):
                a["text"] = _clean_fluff(a["text"], a.get("title", ""))

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

def parse_published_str(published_str):
    """Parse a published string and return a timestamp, or 0 if unparseable."""
    if not published_str:
        return 0
    now = time.time()
    # Try DD-MM-YYYY format (e.g. "20:39 | 22-06-2026")
    m = re.search(r'(\d{1,2})-(\d{1,2})-(\d{4})\b', published_str)
    if m:
        d, mo, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return time.mktime(time.struct_time((year, mo, d, 0, 0, 0, 0, 0, -1)))
        except:
            pass
    # Try DD-MM-YY format (e.g. "19:47 | 04-05-20")
    m = re.search(r'(\d{1,2})-(\d{1,2})-(\d{2})\b', published_str)
    if m:
        d, mo, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = 2000 + yy if yy < 50 else 1900 + yy
        try:
            return time.mktime(time.struct_time((year, mo, d, 0, 0, 0, 0, 0, -1)))
        except:
            pass
    # Try Mon, DD Mon YYYY (e.g. "Sat, 20 Jun 2026")
    months = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
              'janvier':1,'février':2,'mars':3,'avril':4,'mai':5,'juin':6,'juillet':7,'août':8,'septembre':9,'octobre':10,'novembre':11,'décembre':12}
    for eng, num in months.items():
        if eng in published_str.lower():
            dm = re.search(r'(\d{1,2})\s+' + eng, published_str.lower())
            ym = re.search(r'(\d{4})', published_str)
            if dm and ym:
                try:
                    return time.mktime(time.struct_time((int(ym.group(1)), num, int(dm.group(1)), 0, 0, 0, 0, 0, -1)))
                except:
                    pass
    # Try DD/MM/YYYY
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', published_str)
    if m:
        try:
            return time.mktime(time.struct_time((int(m.group(3)), int(m.group(2)), int(m.group(1)), 0, 0, 0, 0, 0, -1)))
        except:
            pass
    return 0

# ============================================================
# PRE-PUBLISH FIXER: translate, complete, ensure periods
# ============================================================
def _is_arabic(text):
    """Check if text is predominantly Arabic."""
    if not text:
        return False
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    return arabic_chars > len(text) * 0.3

def _ensure_period(text):
    """Ensure article text ends with a period."""
    if not text:
        return text
    text = text.rstrip()
    if text and text[-1] not in '.。!！?؟…':
        # Clean trailing punctuation before adding period
        text = text.rstrip('،,:-–— ')
        if len(text) > 10:
            text += '.'
    return text

def _fix_incomplete_text(text, title=""):
    """Fix incomplete/truncated article text."""
    if not text:
        return text
    text = text.strip()
    # If text is very short, it's likely incomplete
    if len(text) < 50:
        return ""
    # Check if text ends mid-sentence (no punctuation)
    last_line = text.split('\n')[-1].strip()
    if last_line and last_line[-1] not in '.。!！?؟…':
        # Try to complete the sentence
        if len(last_line) > 20:
            # Sentence is long enough, just add period
            text = text.rstrip() + '.'
    # Check for common truncation patterns
    truncation_patterns = [
        r'[,،]\s*$',  # Ends with comma
        r':\s*$',     # Ends with colon
        r'[-–—]\s*$', # Ends with dash
        r'\.\.\.\s*$',  # Ends with ellipsis
        r'و\s*$',     # Ends with "and"
        r'في\s*$',    # Ends with "in"
        r'على\s*$',   # Ends with "on"
        r'من\s*$',    # Ends with "from"
        r'إلى\s*$',   # Ends with "to"
        r'عن\s*$',    # Ends with "about"
        r'بين\s*$',   # Ends with "between"
        r'بعد\s*$',   # Ends with "after"
        r'قبل\s*$',   # Ends with "before"
        r'أن\s*$',    # Ends with "that"
        r'إن\s*$',    # Ends with "that"
        r'لا\s*$',    # Ends with "no"
        r'لم\s*$',    # Ends with "did not"
        r'لن\s*$',    # Ends with "will not"
        r'قد\s*$',    # Ends with "may"
        r'كان\s*$',   # Ends with "was"
        r'يكون\s*$',  # Ends with "be"
        r'هو\s*$',    # Ends with "he"
        r'هي\s*$',    # Ends with "she"
        r'هم\s*$',    # Ends with "they"
        r'هن\s*$',    # Ends with "they (f)"
        r'أنت\s*$',   # Ends with "you"
        r'أنتِ\s*$',  # Ends with "you (f)"
        r'أنتما\s*$', # Ends with "you (dual)"
        r'أنتم\s*$',  # Ends with "you (pl)"
        r'أنتن\s*$',  # Ends with "you (pl f)"
        r'نحن\s*$',   # Ends with "we"
        r'أنا\s*$',   # Ends with "I"
    ]
    for pat in truncation_patterns:
        if re.search(pat, text):
            text = text.rstrip('،,:-–— ') + '.'
            break
    return text

def fix_articles_before_publish(articles):
    """Fix all articles before publishing: translate, complete, ensure periods."""
    fixed_count = 0
    translated_count = 0
    period_count = 0
    incomplete_count = 0

    for a in articles:
        txt = a.get("text", "")
        if not txt:
            continue

        original = txt

        # 1. Fix incomplete text
        txt = _fix_incomplete_text(txt, a.get("title", ""))
        if txt != original and len(txt) == 0:
            incomplete_count += 1

        # 2. Translate if not Arabic
        if txt and not _is_arabic(txt):
            try:
                translated = GoogleTranslator(source='auto', target='ar').translate(txt[:5000])
                if translated and len(translated) > 20:
                    txt = translated
                    translated_count += 1
            except:
                pass  # Keep original if translation fails

        # 3. Ensure ends with period
        if txt:
            before = txt
            txt = _ensure_period(txt)
            if txt != before:
                period_count += 1

        if txt != a.get("text", ""):
            a["text"] = txt
            fixed_count += 1

    return {
        "fixed": fixed_count,
        "translated": translated_count,
        "periods_added": period_count,
        "incomplete_removed": incomplete_count
    }

# ============================================================
# ARTICLE VALIDATION & REPAIR
# ============================================================
def validate_articles(articles, session=None):
    """Check article quality and try to repair issues.
    Returns dict with counts: total, no_text, no_image, by_source."""
    stats = {"total": len(articles), "no_text": 0, "no_image": 0,
             "by_source": {}}
    for a in articles:
        src = a.get("source_clean", "?")
        if src not in stats["by_source"]:
            stats["by_source"][src] = {"total": 0, "no_text": 0, "no_image": 0,
                                       "text_ok": 0, "image_ok": 0}
        stats["by_source"][src]["total"] += 1
        txt = a.get("text")
        img = a.get("image")
        if not txt or len(txt.strip()) < 25:
            stats["no_text"] += 1
            stats["by_source"][src]["no_text"] += 1
        else:
            stats["by_source"][src]["text_ok"] += 1
        if not img:
            stats["no_image"] += 1
            stats["by_source"][src]["no_image"] += 1
        else:
            stats["by_source"][src]["image_ok"] += 1
    return stats

def print_validation_report(stats):
    no_t = stats["no_text"]
    no_i = stats["no_image"]
    pct_t = (stats["total"] - no_t) / max(stats["total"], 1) * 100
    pct_i = (stats["total"] - no_i) / max(stats["total"], 1) * 100
    print(f"\n{'='*50}")
    print(f" [VALIDATION] Article Quality Report")
    print(f"{'='*50}")
    print(f" Total articles : {stats['total']}")
    print(f" With text     : {stats['total'] - no_t}/{stats['total']} ({pct_t:.0f}%)")
    print(f" With image    : {stats['total'] - no_i}/{stats['total']} ({pct_i:.0f}%)")
    for src in sorted(stats["by_source"]):
        s = stats["by_source"][src]
        if s["no_text"] > 0 or s["no_image"] > 0:
            issues = []
            if s["no_text"] > 0:
                issues.append(f"no_text={s['no_text']}")
            if s["no_image"] > 0:
                issues.append(f"no_image={s['no_image']}")
            print(f"  [{src}] {s['total']} articles - {', '.join(issues)}")
    print(f" {'='*50}\n")

def validate_live_site(url="https://1ymenn.github.io/dz-akhbar"):
    """Pre-update health check - verify live site is working."""
    import urllib.request
    import urllib.error
    print(f"  Pre-update check: {url}...")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read()
                if len(body) > 1000 and resp.status == 200:
                    print(f"  Live site: OK ({resp.status}, {len(body)} bytes)")
                    return True
                else:
                    print(f"  Live site: SMALL/BAD ({len(body)} bytes)")
        except Exception as e:
            print(f"  Attempt {attempt+1}: {e}")
        if attempt < 2:
            time.sleep(5)
    print(f"  WARNING: Live site unreachable!")
    return False

async def repair_missing_text(articles):
    """Re-fetch articles with missing text using aggressive extraction."""
    sem = asyncio.Semaphore(10)
    connector = aiohttp.TCPConnector(limit=15, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        async def _repair_one(a):
            link = a.get("link")
            if not link or a.get("text", "").strip():
                return
            html, _ = await async_fetch_page(session, link, sem)
            if not html:
                return
            # Try readability first
            try:
                from readability import Document
                doc = Document(html)
                ch = doc.summary()
                paras = re.findall(r'<p[^>]*>(.*?)</p>', ch, re.DOTALL|re.IGNORECASE)
                clean = []
                for p in paras:
                    text = re.sub(r'<[^>]+>', ' ', p)
                    import html as html_mod
                    text = html_mod.unescape(text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if len(text) >= 25:
                        clean.append(text)
                if clean:
                    txt = '\n\n'.join(clean)
                    if _text_matches_title(txt, a.get("title", "")):
                        a["text"] = txt
                        return
            except:
                pass
            # Aggressive: extract <article> or <main> content
            for tag in [r'<article[^>]*>(.*?)</article>', r'<main[^>]*>(.*?)</main>',
                        r'<div[^>]*class="[^"]*(?:article|content|post|entry|story|text|body|detail)[^"]*"[^>]*>(.*?)</div>']:
                m = re.search(tag, html, re.DOTALL | re.IGNORECASE)
                if m:
                    raw = re.sub(r'<script[^>]*>.*?</script>', '', m.group(1), flags=re.DOTALL)
                    raw = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL)
                    raw = re.sub(r'<[^>]+>', ' ', raw)
                    import html as html_mod
                    raw = html_mod.unescape(raw)
                    raw = re.sub(r'\s+', ' ', raw).strip()
                    chunks = [c.strip() for c in re.split(r'[.!?؟!.\n]', raw) if len(c.strip()) > 40]
                    if chunks:
                        txt = '. '.join(chunks[:20])
                        if _text_matches_title(txt, a.get("title", "")):
                            a["text"] = txt
                            return
            # Last resort: full page text
            raw = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
            raw = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL)
            raw = re.sub(r'<[^>]+>', ' ', raw)
            import html as html_mod
            raw = html_mod.unescape(raw)
            raw = re.sub(r'\s+', ' ', raw).strip()
            chunks = [c.strip() for c in re.split(r'[.!?؟!.\n]', raw) if len(c.strip()) > 40]
            if chunks:
                txt = '. '.join(chunks[:20])
                if _text_matches_title(txt, a.get("title", "")):
                    a["text"] = txt
        tasks = [_repair_one(a) for a in articles if not a.get("text", "").strip()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

async def repair_missing_image(articles):
    """Re-fetch articles with missing images using more extraction patterns."""
    sem = asyncio.Semaphore(10)
    connector = aiohttp.TCPConnector(limit=15, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        async def _repair_one(a):
            link = a.get("link")
            if not link or a.get("image"):
                return
            html, _ = await async_fetch_page(session, link, sem)
            if html:
                img = _extract_og_from_html(html, link)
                if img:
                    a["image"] = img
        tasks = [_repair_one(a) for a in articles if not a.get("image") and a.get("link")]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

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
            "published": a.get("published", "")[:20],
            "region": a.get("region", "dz"),
            "category": classify_category(a.get("title", "")),
        })
    outpath = os.path.join(base_dir, LATEST_JSON)
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(ALGERIA_TZ).isoformat(), "articles": latest},
                  f, ensure_ascii=False, indent=2)
    print(f"latest_news.json: {len(latest)} articles")

def esc(text):
    return text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;").replace("\n","&#10;").replace("\r","")

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
        if sm:
            sm = _ensure_period(sm)
        img = a.get("image")
        if img and re.search(r'nothumb|no[._-]?image|nothumbs_[dg]|placeholder|/default\.|DefaultImage|970x90', img, re.IGNORECASE):
            img = None
        c1 = colors[hash(t) % len(colors)]
        c2 = colors[(hash(t)+1) % len(colors)]
        if img:
            ie = esc(img)
            ih = f'<div class="ai has-img" style="background:linear-gradient(135deg,{c1},{c2})"><img src="{ie}" data-src="{ie}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.display=\'none\'" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"><div class="io"></div></div>'
        else:
            ic = ["📰","📋","📌","🔖","📊","📈","📑","🗞️"][hash(t) % 8]
            ih = f'<div class="ai no-img" style="background:linear-gradient(135deg,{c1},{c2})"><div class="ii">{ic}</div></div>'
        el = sanitize_url(a["link"])
        sc = esc(a["source"])
        raw_txt = a.get("text", "")
        if raw_txt:
            raw_txt = _clean_fluff(raw_txt, a.get("title", ""))
            raw_txt = _ensure_period(raw_txt)
        txt = esc(raw_txt)
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
        img_attr = f' data-img="{ie}"' if img else ""
        # Reading time and sentiment
        reading_time = _calc_reading_time(a.get("text", ""))
        sentiment, sent_score = _analyze_sentiment(a.get("text", ""))
        sent_icon = "😐" if sentiment == "neutral" else ("😊" if sentiment == "positive" else "😟")
        cards += f'<div class="a{lm}" data-t="{t.lower()}" data-s="{a["source_clean"].lower()}" data-r="{r}" data-cat="{cat}"><div class="ac" data-id="{uid}" data-link="{el}" data-title="{t}" data-source="{sc}" data-src-color="{a["source_color"]}" data-txt="{txt}"{vid_attr}{img_attr}>{ih}{vid_icon}<div class="ab"><div class="am"><span class="as" style="background:{a["source_color"]}">{sc}</span><span class="ad">📖 {reading_time} دقيقة • {sent_icon} {esc(a["published"][:20])}</span></div><div class="at">{t}</div><div class="ae">{sm}</div></div></div><div class="sb-btn" data-share="1" title="مشاركة">↗</div></div>'
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

def _calc_reading_time(text):
    """Calculate reading time in minutes for Arabic text."""
    if not text:
        return 1
    words = len(text.split())
    # Arabic ~200 wpm
    minutes = max(1, round(words / 200))
    return minutes

def _extract_keywords(text, title="", max_keywords=5):
    """Extract keywords from Arabic text for related articles."""
    if not text and not title:
        return []
    combined = f"{title} {text}"
    # Common Arabic stop words
    stop_words = {'في', 'من', 'على', 'إلى', 'عن', 'مع', 'هذا', 'هذه', 'التي', 'الذي',
                  'أن', 'إن', 'لا', 'ما', 'كان', 'يكون', 'قد', 'لم', 'حتى', 'أو', 'بل',
                  'و', 'ف', 'ب', 'ل', 'ال', 'ي', 'ن', 'ت', 'ث', 'ج', 'ح', 'خ', 'د', 'ذ',
                  'ر', 'ز', 'س', 'ش', 'ص', 'ض', 'ط', 'ظ', 'ع', 'غ', 'ق', 'ك', 'م', 'ه',
                  'و', 'ي', 'اء', 'ات', 'ين', 'ون', 'ان', 'تم', 'أي', 'كل', 'بها',
                  'more', 'than', 'the', 'and', 'for', 'that', 'this', 'with', 'from',
                  'has', 'have', 'was', 'were', 'are', 'been', 'will', 'would', 'could',
                  'should', 'may', 'might', 'can', 'shall', 'must'}
    words = re.findall(r'[\u0600-\u06FF]{3,}', combined)
    freq = {}
    for w in words:
        if w not in stop_words and len(w) > 3:
            freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:max_keywords]]

def _find_related_articles(article, all_articles, max_related=4):
    """Find related articles based on keywords and source."""
    title = article.get("title", "")
    text = article.get("text", "")
    source = article.get("source", "")
    keywords = _extract_keywords(text, title)
    if not keywords:
        return []
    scored = []
    for a in all_articles:
        if a.get("link") == article.get("link"):
            continue
        a_title = a.get("title", "")
        a_text = a.get("text", "")
        a_combined = f"{a_title} {a_text}"
        score = 0
        for kw in keywords:
            if kw in a_combined:
                score += 1
        # Bonus for same source
        if a.get("source") == source:
            score += 2
        if score >= 2:
            scored.append((score, a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:max_related]]

def _analyze_sentiment(text):
    """Simple Arabic sentiment analysis."""
    if not text:
        return "neutral", 0
    positive_words = ['نجاح', 'فوز', 'إنجاز', 'تطور', 'تحسن', 'تقدم', 'أمل', 'سعادة',
                      'نصر', 'إنقاذ', 'مساعدة', 'دعم', 'تعاون', 'سلام', 'حرية', 'عدل']
    negative_words = ['فشل', 'خسارة', 'أزمة', 'مشاكل', 'عنف', 'حرب', 'قتل', 'دمار',
                      'فقر', 'مرض', 'موت', 'كارثة', 'إخفاق', 'تراجع', 'مشاكل', 'توتر']
    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)
    total = pos_count + neg_count
    if total == 0:
        return "neutral", 0
    score = (pos_count - neg_count) / total
    if score > 0.2:
        return "positive", score
    elif score < -0.2:
        return "negative", score
    return "neutral", 0

def build_sidebar_list(articles, max_items=6):
    items = ""
    for i, a in enumerate(articles[:max_items]):
        t = esc(a["title"])
        l = sanitize_url(a["link"])
        s = esc(a["source"])
        c = a["source_color"]
        raw_txt = _clean_fluff(a.get("text", ""), a.get("title", "")) if a.get("text") else ""
        raw_txt = _ensure_period(raw_txt)
        txt = esc(raw_txt)
        uid = hashlib.md5((a["title"] + a["link"]).encode()).hexdigest()[:8]
        vid = a.get("video")
        vid_id = ""
        if vid and re.match(r'^[a-zA-Z0-9_-]+$', str(vid[1])):
            vid_id = vid[1][:50]
        vid_attr = f' data-video="{vid_id}"' if vid_id else ""
        items += f'<li><span class="sb-link" data-id="{uid}" data-link="{l}" data-title="{t}" data-source="{s}" data-src-color="{c}" data-txt="{txt}"{vid_attr}><span class="sb-dot" style="background:{c}"></span><span class="sb-text">{t}</span></span></li>'
    return f'<ul class="sb-list">{items}</ul>' if items else ""

def build_featured(art):
    if not art: return ""
    t = esc(art["title"])
    sm = esc(art["summary"])[:200] if art["summary"] else ""
    if sm:
        sm = _ensure_period(sm)
    img = art.get("image")
    colors = ["#667eea","#764ba2","#f093fb","#f5576c","#4facfe","#00f2fe","#43e97b","#38f9d7","#fa709a","#fee140","#a18cd1","#fbc2eb"]
    c1 = colors[hash(t) % len(colors)]
    c2 = colors[(hash(t)+1) % len(colors)]
    if img:
        ie = esc(img)
        ih = f'<div class="ftr-img" style="background:linear-gradient(135deg,{c1},{c2})"><img src="{ie}" data-src="{ie}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.display=\'none\'" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"><div class="ftr-overlay"></div></div>'
    else:
        ih = f'<div class="ftr-img ftr-no-img" style="background:linear-gradient(135deg,{c1},{c2})"><div class="ii">📰</div></div>'
    el = sanitize_url(art["link"])
    return f'<div class="ftr-art"><div class="ftr-inner">{ih}<div class="ftr-body"><span class="ftr-src" style="background:{art["source_color"]}">{esc(art["source"])}</span><div class="ftr-title">{t}</div><div class="ftr-summary">{sm}</div><div class="ftr-meta"><span>{esc(art["published"][:20])}</span></div></div></div></div>'

def build_badges(rid):
    return "".join(f'<span class="sb-b" style="background:{s["c"]}" data-badge="{s["n"]}">{s["n"]}</span>' for s in REGIONS[rid]["latest"])

def build_trending_topics(articles, max_topics=10):
    """Build trending topics from article keywords."""
    all_keywords = {}
    for a in articles[:200]:
        title = a.get("title", "")
        text = a.get("text", "")
        keywords = _extract_keywords(text, title, max_keywords=3)
        for kw in keywords:
            if kw not in all_keywords:
                all_keywords[kw] = {"count": 0, "articles": []}
            all_keywords[kw]["count"] += 1
            if len(all_keywords[kw]["articles"]) < 3:
                all_keywords[kw]["articles"].append(a)
    sorted_topics = sorted(all_keywords.items(), key=lambda x: x[1]["count"], reverse=True)[:max_topics]
    if not sorted_topics:
        return "<p style='color:var(--text3);font-size:14px'>لا توجد مواضيع رائجة حالياً</p>"
    html = '<div class="trending-grid">'
    for keyword, data in sorted_topics:
        count = data["count"]
        articles_list = data["articles"]
        heat = "🔥" if count >= 5 else ("📈" if count >= 3 else "📊")
        html += f'<div class="trending-item" onclick="searchTopic(\'{esc(keyword)}\')">'
        html += f'<div class="trending-keyword">{heat} {esc(keyword)}</div>'
        html += f'<div class="trending-count">{count} مقال</div>'
        html += '<div class="trending-articles">'
        for a in articles_list[:2]:
            html += f'<div class="trending-article" data-id="{hashlib.md5((a["title"]+a["link"]).encode()).hexdigest()[:8]}" data-link="{sanitize_url(a["link"])}" data-title="{esc(a["title"])}" data-source="{esc(a["source"])}" data-src-color="{a["source_color"]}" data-txt="{esc(_ensure_period(_clean_fluff(a.get("text",""),a.get("title",""))))}">{esc(a["title"][:60])}...</div>'
        html += '</div></div>'
    html += '</div>'
    return html

def build_news_schema(articles, max_items=30):
    """Generate NewsArticle JSON-LD schema for Google News."""
    items = []
    for a in articles[:max_items]:
        title = a.get("title", "")
        link = a.get("link", "")
        img = a.get("image", "")
        source = a.get("source", "")
        published = a.get("published", "")
        summary = a.get("summary", "")
        if not title or not link:
            continue
        item = {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": title[:110],
            "url": link,
            "datePublished": published,
            "author": {"@type": "Organization", "name": source},
            "publisher": {"@type": "Organization", "name": source},
            "description": summary[:200] if summary else "",
        }
        if img:
            item["image"] = img
        items.append(item)
    if not items:
        return ""
    schema = {"@context": "https://schema.org", "@graph": items}
    return f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>'

def build_analytics_dashboard(articles):
    """Build analytics dashboard with statistics."""
    # Source statistics
    source_counts = {}
    for a in articles:
        source = a.get("source", "غير معروف")
        source_counts[source] = source_counts.get(source, 0) + 1
    sorted_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Category statistics
    category_counts = {}
    for a in articles:
        cat = classify_category(a.get("title", ""))
        category_counts[cat] = category_counts.get(cat, 0) + 1
    sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    
    # Reading time statistics
    total_reading_time = sum(_calc_reading_time(a.get("text", "")) for a in articles)
    avg_reading_time = total_reading_time // max(len(articles), 1)
    
    # Sentiment statistics
    sentiments = {"positive": 0, "negative": 0, "neutral": 0}
    for a in articles:
        sentiment, _ = _analyze_sentiment(a.get("text", ""))
        sentiments[sentiment] = sentiments.get(sentiment, 0) + 1
    
    html = '<div class="analytics-grid">'
    
    # Total articles card
    html += f'<div class="analytics-card"><div class="analytics-number">{len(articles)}</div><div class="analytics-label">إجمالي المقالات</div></div>'
    
    # Total sources card
    html += f'<div class="analytics-card"><div class="analytics-number">{len(source_counts)}</div><div class="analytics-label">المصادر النشطة</div></div>'
    
    # Average reading time card
    html += f'<div class="analytics-card"><div class="analytics-number">{avg_reading_time} دقيقة</div><div class="analytics-label">متوسط وقت القراءة</div></div>'
    
    # Sentiment card
    sentiment_emoji = "😐" if sentiments["neutral"] >= sentiments["positive"] and sentiments["neutral"] >= sentiments["negative"] else ("😊" if sentiments["positive"] >= sentiments["negative"] else "😟")
    html += f'<div class="analytics-card"><div class="analytics-number">{sentiment_emoji}</div><div class="analytics-label">المزاج العام</div></div>'
    
    html += '</div>'
    
    # Source statistics
    html += '<div class="analytics-section"><h3 class="analytics-section-title">📊 إحصائيات المصادر</h3>'
    html += '<div class="analytics-bar-chart">'
    max_count = max(source_counts.values()) if source_counts else 1
    for source, count in sorted_sources[:8]:
        width = (count / max_count) * 100
        html += f'<div class="analytics-bar-row"><span class="analytics-bar-label">{esc(source)}</span><div class="analytics-bar-container"><div class="analytics-bar" style="width:{width}%"></div></div><span class="analytics-bar-value">{count}</span></div>'
    html += '</div></div>'
    
    # Category statistics
    html += '<div class="analytics-section"><h3 class="analytics-section-title">📁 إحصائيات التصنيفات</h3>'
    html += '<div class="analytics-tags">'
    for cat, count in sorted_cats:
        cat_names = {"سياسة": "🏛️", "رياضة": "⚽", "اقتصاد": "💰", "تكنولوجيا": "💻", "ثقافة": "📚", "صحة": "🏥", "教育": "🎓", "أمن": "🔒", "دولي": "🌍", "أخرى": "📋"}
        emoji = cat_names.get(cat, "📋")
        html += f'<span class="analytics-tag">{emoji} {esc(cat)} ({count})</span>'
    html += '</div></div>'
    
    return html

def generate_sitemap(all_articles):
    links = {}
    for a in all_articles:
        link = a.get("link", "")
        if not link:
            continue
        pub = a.get("published", "")
        links[link] = pub
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n')
        f.write('  xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n')
        f.write(f'  <url><loc>{BASE_URL}/</loc><changefreq>always</changefreq><priority>1.0</priority></url>\n')
        today = datetime.now().strftime("%Y-%m-%d")
        for url, pub in list(links.items())[:500]:
            ts = parse_published_str(pub) or safe_mktime(None)
            if ts:
                lastmod = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            else:
                lastmod = today
            f.write(f'  <url><loc>{esc(url)}</loc><lastmod>{lastmod}</lastmod><changefreq>daily</changefreq><priority>0.7</priority></url>\n')
        f.write('</urlset>\n')
    print(f"  sitemap.xml: {len(links)} URLs")

def content_hash(articles):
    h = hashlib.sha256()
    for a in articles:
        if a.get("link") and a.get("title"):
            h.update((a["link"] + a["title"] + a.get("published","")).encode())
    return h.hexdigest()

CSS = r""":root{--bg:#0f1419;--card-bg:#1a2332;--text:#e8e8e8;--text2:#b0b8c4;--text3:#6b7a8d;--filter-bg:#151d28;--badge-bg:#1e2d3d;--badge-text:#8899aa;--border:#253040;--shadow:rgba(0,0,0,0.4);--shadow-h:rgba(0,0,0,0.6);--accent:#1da1f2;--accent-hover:#1a91da;--gold:#f5a623;--line:#1e2d3d;--red:#e0245e;--green:#17bf63}
body.light{--bg:#f0f2f5;--card-bg:#ffffff;--text:#14171a;--text2:#536471;--text3:#8899a6;--filter-bg:#f7f9f9;--badge-bg:#eff3f4;--badge-text:#536471;--border:#eff3f4;--shadow:rgba(0,0,0,0.05);--shadow-h:rgba(0,0,0,0.1);--accent:#1da1f2;--accent-hover:#1a91da;--gold:#d4a017;--line:#eff3f4;--red:#e0245e;--green:#17bf63}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Noto Sans Arabic','Cairo',sans-serif;background:var(--bg);color:var(--text);line-height:1.7;-webkit-font-smoothing:antialiased;font-size:16px}
.flag-bar{height:3px;background:linear-gradient(90deg,#006233 33.33%,#fff 33.33%,#fff 66.66%,#D21034 66.66%);position:sticky;top:0;z-index:1001}
.top-bar{background:var(--card-bg);border-bottom:1px solid var(--border);padding:8px 0;position:sticky;top:3px;z-index:1000;backdrop-filter:blur(12px)}
.ti{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:center}
.tb-r{display:flex;align-items:center;gap:14px}
.clock{color:var(--gold);font-weight:700;font-size:14px;direction:ltr;display:inline-block;letter-spacing:0.5px}
.dt-btn{padding:6px 14px;border-radius:18px;font-size:12px;font-weight:700;cursor:pointer;background:transparent;color:var(--gold);border:1.5px solid var(--gold);transition:all .25s;font-family:inherit}
.dt-btn:hover{background:var(--gold);color:#0f1419}
.ds img[data-src]{min-height:80px;background:#222!important}
body.ds .ai{background:#1a1a1a!important}
.masthead{border-bottom:3px solid var(--accent);padding:32px 0 24px;text-align:center;background:var(--card-bg)}
.mh-inner{max-width:1200px;margin:0 auto;padding:0 24px}
.mh-title{font-family:'Cairo',sans-serif;font-size:56px;font-weight:900;letter-spacing:2px;color:var(--text);line-height:1.2;text-shadow:0 2px 8px rgba(0,0,0,0.2)}
.mh-title .red{color:var(--accent)}.mh-title .gold{color:var(--gold)}
.mh-meta{display:flex;justify-content:center;gap:24px;font-size:13px;color:var(--text3);margin-top:12px;align-items:center;flex-wrap:wrap}
.ticker{border-bottom:1px solid var(--border);background:var(--card-bg);padding:10px 0;overflow:hidden}
.ticker-inner{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;align-items:center;gap:12px}
.ticker-label{background:var(--red);color:#fff;padding:5px 14px;border-radius:16px;font-size:12px;font-weight:700;flex-shrink:0;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.7}}
.ticker-text{font-size:14px;color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.ctrls{max-width:1200px;margin:14px auto 0;padding:0 24px;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.rf-btn{padding:12px 24px;background:var(--accent);color:#fff;border:none;border-radius:12px;font-size:14px;font-weight:700;cursor:pointer;transition:all .2s;white-space:nowrap;font-family:inherit}
.rf-btn:hover{background:var(--accent-hover);transform:translateY(-1px)}
.stats{font-size:13px;color:var(--text3);white-space:nowrap}
.sub-ts{max-width:1200px;margin:12px auto 0;padding:0 24px;display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}
.sub-ts::-webkit-scrollbar{display:none}
.sub-t{padding:10px 24px;font-size:14px;font-weight:700;border:none;cursor:pointer;background:var(--badge-bg);color:var(--badge-text);border-radius:20px;transition:all .2s;font-family:inherit;white-space:nowrap;flex-shrink:0}
.sub-t:hover{background:#2a3a4a;color:var(--text)}.sub-t.active{background:var(--accent);color:#fff}
.ct{max-width:1200px;margin:0 auto 30px;padding:0 24px}
.tc{display:none}.tc.active{display:block}
.sb-fav{display:inline-block;padding:4px 12px;border-radius:14px;font-size:11px;font-weight:700;cursor:pointer;color:#fff;background:var(--accent);margin:2px;transition:all .2s;opacity:0.85}.sb-fav:hover{opacity:1}
.ftr-art{margin:18px 0;background:var(--card-bg);border:1px solid var(--border);border-radius:16px;overflow:hidden;cursor:pointer;transition:all .3s}
.ftr-art:hover{box-shadow:0 12px 32px var(--shadow-h);border-color:var(--accent);transform:translateY(-3px)}
.ftr-inner{display:grid;grid-template-columns:1.2fr 1fr;min-height:340px}
.ftr-img{position:relative;background:var(--card-bg);overflow:hidden}
.ftr-img img{width:100%;height:100%;object-fit:cover;transition:transform .5s}
.ftr-art:hover .ftr-img img{transform:scale(1.03)}
.ftr-img .ftr-overlay{position:absolute;inset:0;background:linear-gradient(90deg,transparent 40%,rgba(0,0,0,0.5))}
.ftr-no-img{display:flex;align-items:center;justify-content:center;font-size:60px}
.ftr-body{padding:28px 32px;display:flex;flex-direction:column;justify-content:center}
.ftr-src{display:inline-block;padding:5px 14px;border-radius:12px;font-size:12px;font-weight:700;color:#fff;margin-bottom:14px;width:fit-content}
.ftr-title{font-family:'Cairo',sans-serif;font-size:30px;font-weight:900;color:var(--text);line-height:1.3;margin-bottom:14px}
.ftr-summary{font-size:16px;color:var(--text2);line-height:1.8;overflow:hidden;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical}
.ftr-meta{display:flex;gap:14px;margin-top:14px;font-size:13px;color:var(--text3);align-items:center}
.ftr-share{width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,0.08);border:none;font-size:13px;cursor:pointer;transition:all .2s;display:flex;align-items:center;justify-content:center;color:var(--text2)}
.ftr-share:hover{background:var(--accent);color:#fff}
.content-wrap{max-width:1200px;margin:0 auto;padding:20px 24px;display:grid;grid-template-columns:1fr 320px;gap:28px;align-items:start}
.main-content{min-width:0}
.sidebar{position:sticky;top:80px;max-height:calc(100vh - 100px);overflow-y:auto;scrollbar-width:thin;scrollbar-color:var(--border) transparent}
.sb-widget{background:var(--card-bg);border:1px solid var(--border);border-radius:16px;padding:22px 24px;margin-bottom:18px;transition:all .3s}
.sb-widget:hover{border-color:var(--accent)}
.sb-uni{border-right:3px solid var(--accent)}
.sb-uni .sb-list li a{font-size:16px;line-height:1.6;padding:10px 14px}
.sb-uni .sb-text{font-size:16px}
.sb-wtitle{font-family:'Cairo',sans-serif;font-size:16px;font-weight:700;color:var(--text);margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid var(--accent);display:flex;align-items:center;gap:8px}
.sb-list{margin:0;padding:0;list-style:none}
.sb-list li{margin-bottom:10px;line-height:1.4}
.sb-list li a,.sb-link{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--text);padding:10px 14px;border-radius:12px;transition:all .2s;font-size:15px;line-height:1.6;cursor:pointer}
.sb-list li a:hover,.sb-link:hover{background:var(--filter-bg);color:var(--accent)}
.sb-rank{width:28px;height:28px;border-radius:50%;color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.sb-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.sb-text{overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;flex:1;font-size:15px;color:var(--text)}
@media(max-width:1024px) and (min-width:768px){.sidebar{width:100%;position:static;display:grid!important;grid-template-columns:1fr 1fr;gap:14px}.sb-widget{margin-bottom:0}}
.gr{column-count:2;column-gap:20px}
.a{background:var(--card-bg);border-radius:16px;overflow:hidden;box-shadow:0 2px 8px var(--shadow);transition:all .3s;border:1px solid var(--border);position:relative;break-inside:avoid;margin-bottom:20px;display:inline-block;width:100%}
.a:hover{box-shadow:0 12px 28px var(--shadow-h);border-color:var(--accent);transform:translateY(-3px)}
.ac{cursor:pointer;display:block}
.ai{aspect-ratio:16/9;background-size:cover;background-position:center;position:relative;overflow:hidden}
.ai img{width:100%;height:100%;object-fit:cover;transition:transform .4s}
.a:hover .ai img{transform:scale(1.04)}
.ai .io{position:absolute;inset:0;background:linear-gradient(transparent 50%,rgba(0,0,0,0.6))}
.ai.no-img{display:flex;align-items:center;justify-content:center;background:var(--filter-bg)!important}
.ai .ii{font-size:40px;opacity:0.25}
.ab{padding:20px 22px 24px}
.am{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:8px;flex-wrap:wrap}
.as{padding:5px 12px;border-radius:12px;font-size:13px;font-weight:700;color:#fff;white-space:nowrap;flex-shrink:0}
.ad{font-size:13px;color:var(--text3);white-space:nowrap;direction:ltr;display:inline-block}
.at{font-family:'Cairo',sans-serif;font-size:22px;font-weight:700;color:var(--text);margin-bottom:12px;line-height:1.5;transition:color .2s}
.a:hover .at{color:var(--accent)}
.ae{font-size:16px;color:var(--text2);line-height:1.8;overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
.vi{position:absolute;top:12px;right:12px;width:36px;height:36px;border-radius:50%;background:rgba(29,161,242,0.9);color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;z-index:5;box-shadow:0 2px 8px rgba(0,0,0,0.3)}
.sb-btn{position:absolute;top:12px;left:12px;width:32px;height:32px;border-radius:50%;background:rgba(0,0,0,0.4);color:#fff;border:2px solid rgba(255,255,255,0.15);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;cursor:pointer;transition:all .25s;z-index:5}
.sb-btn:hover{background:var(--accent);border-color:var(--accent)}
body.light .sb-btn{background:rgba(255,255,255,0.8);border-color:rgba(0,0,0,0.1);color:#333}
body.light .sb-btn:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.nr{text-align:center;padding:48px 24px;color:var(--text3);font-size:16px}
.sl{font-family:'Cairo',sans-serif;font-size:15px;font-weight:700;margin:14px 0 12px;color:var(--text);display:flex;align-items:center;gap:8px;padding:10px 0;border-bottom:1px solid var(--line)}
.sl .ico{font-size:16px}
.a.lm{display:none}
.lm-btn{display:block;margin:16px auto;padding:12px 32px;background:var(--accent);color:#fff;border:none;border-radius:12px;font-size:14px;font-weight:700;cursor:pointer;transition:all .2s;font-family:inherit}
.lm-btn:hover{background:var(--accent-hover);transform:translateY(-1px)}
.ftr-sec{border-top:1px solid var(--border);padding:24px 0;margin-top:30px;text-align:center;color:var(--text3);font-size:13px}
.ftr-sec .lk{display:flex;justify-content:center;gap:16px;margin-bottom:8px}
.ftr-sec a{color:var(--accent);text-decoration:none;font-weight:600}
.trending-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;padding:16px 0}
.trending-item{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:16px;cursor:pointer;transition:all .2s}
.trending-item:hover{border-color:var(--red);transform:translateY(-2px);box-shadow:0 4px 12px var(--shadow)}
.trending-keyword{font-family:'Cairo',sans-serif;font-size:16px;font-weight:700;color:var(--text);margin-bottom:6px}
.trending-count{font-size:12px;color:var(--text3);margin-bottom:10px}
.trending-articles{display:flex;flex-direction:column;gap:6px}
.trending-article{font-size:13px;color:var(--text2);padding:6px 8px;background:var(--filter-bg);border-radius:6px;cursor:pointer;transition:all .15s;line-height:1.5}
.trending-article:hover{background:var(--accent);color:#fff}
.reading-time{font-size:11px;color:var(--text3);display:flex;align-items:center;gap:4px}
.sentiment-badge{font-size:11px;padding:2px 6px;border-radius:8px;display:inline-flex;align-items:center;gap:2px}
.sentiment-positive{background:rgba(0,102,51,0.15);color:#006633}
.sentiment-negative{background:rgba(210,16,52,0.15);color:#D21034}
.sentiment-neutral{background:rgba(128,128,128,0.15);color:#808080}
.bookmark-btn{font-size:11px;padding:4px 8px;border-radius:6px;cursor:pointer;transition:all .2s}
.bookmark-btn:hover{background:var(--gold);color:#fff}
.bookmark-btn.active{background:var(--gold);color:#fff}
.history-item{display:flex;align-items:center;gap:8px;padding:6px 8px;border-bottom:1px solid var(--border);font-size:13px;cursor:pointer;transition:all .15s}
.history-item:hover{background:var(--filter-bg)}
.history-time{color:var(--text3);font-size:11px;white-space:nowrap}
.history-title{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.newsletter-form{margin:16px 0;padding:16px;background:var(--card-bg);border:1px solid var(--border);border-radius:12px;max-width:400px;margin-left:auto;margin-right:auto}
.newsletter-title{font-weight:700;margin-bottom:8px;color:var(--text)}
.newsletter-desc{font-size:13px;color:var(--text3);margin-bottom:10px}
.newsletter-input{flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:8px;background:var(--filter-bg);color:var(--text);font-size:13px;font-family:inherit}
.newsletter-btn{padding:8px 16px;background:var(--accent);color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit}
.newsletter-btn:hover{background:var(--accent-hover)}
.analytics-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:24px}
.analytics-card{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:20px;text-align:center;transition:all .2s}
.analytics-card:hover{border-color:var(--accent);transform:translateY(-2px)}
.analytics-number{font-family:'Cairo',sans-serif;font-size:32px;font-weight:900;color:var(--accent);margin-bottom:8px}
.analytics-label{font-size:14px;color:var(--text2);font-weight:600}
.analytics-section{margin-bottom:24px}
.analytics-section-title{font-family:'Cairo',sans-serif;font-size:18px;font-weight:700;color:var(--text);margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid var(--accent)}
.analytics-bar-chart{display:flex;flex-direction:column;gap:10px}
.analytics-bar-row{display:flex;align-items:center;gap:12px}
.analytics-bar-label{width:120px;font-size:13px;color:var(--text2);text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.analytics-bar-container{flex:1;height:24px;background:var(--filter-bg);border-radius:12px;overflow:hidden}
.analytics-bar{height:100%;background:linear-gradient(90deg,var(--accent),var(--gold));border-radius:12px;transition:width .5s ease}
.analytics-bar-value{width:40px;font-size:13px;color:var(--text3);font-weight:700}
.analytics-tags{display:flex;flex-wrap:wrap;gap:8px}
.analytics-tag{padding:6px 12px;background:var(--filter-bg);border-radius:16px;font-size:13px;color:var(--text2);transition:all .2s}
.analytics-tag:hover{background:var(--accent);color:#fff}
.mod-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.88);z-index:2000;justify-content:center;align-items:center;padding:20px;backdrop-filter:blur(12px)}.mod-progress{position:absolute;top:0;left:0;height:3px;background:var(--accent);z-index:10;transition:width .15s;width:0%}
.mod-overlay.open{display:flex}
.mod-box{background:var(--card-bg);border-radius:20px;width:100%;max-width:720px;max-height:88vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,0.7);border:1px solid var(--border);position:relative}
.mod-head{display:flex;justify-content:space-between;align-items:center;padding:12px 18px;border-bottom:1px solid var(--border);min-height:48px;position:sticky;top:0;background:var(--card-bg);z-index:5}
.mh-src{display:inline-block;padding:4px 12px;border-radius:10px;font-size:11px;font-weight:700;color:#fff}
.mh-close{width:34px;height:34px;border-radius:50%;border:none;background:rgba(255,255,255,0.06);color:var(--text3);font-size:15px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s;flex-shrink:0}
.mh-close:hover{background:var(--red);color:#fff}
.mod-title{font-family:'Cairo',sans-serif;font-size:26px;font-weight:900;color:var(--text);padding:18px 22px 0;line-height:1.5}
.mod-body{padding:16px 22px;overflow-y:auto;flex:1;font-size:17px;line-height:2;color:var(--text2);scroll-behavior:smooth}
.mod-body p{margin-bottom:14px}
.mod-footer{display:flex;gap:8px;padding:12px 18px;border-top:1px solid var(--border);flex-wrap:wrap;align-items:center;flex-shrink:0;background:var(--card-bg)}
.mod-btn{padding:8px 16px;border-radius:10px;font-size:12px;font-weight:600;cursor:pointer;transition:all .2s;text-decoration:none;display:inline-flex;align-items:center;gap:4px;font-family:inherit;border:none}
.mod-btn-primary{background:var(--accent);color:#fff;font-size:12px}.mod-btn-primary:hover{background:var(--accent-hover)}
.mod-btn-secondary{background:transparent;color:var(--text3);border:1px solid var(--border);font-size:12px;padding:8px 14px;border-radius:10px}.mod-btn-secondary:hover{background:rgba(255,255,255,0.05);color:var(--text2)}
.mod-btn-share{background:transparent;color:var(--text3);border:1px solid var(--border);font-size:13px;padding:8px 14px;border-radius:10px;cursor:pointer;transition:all .2s}.mod-btn-share:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.mod-readmore{display:block;text-align:center;margin-top:20px;padding:14px 22px;background:var(--accent);color:#fff;border-radius:12px;text-decoration:none;font-weight:700;font-size:15px;transition:all .2s}.mod-readmore:hover{opacity:.85;transform:translateY(-1px)}
.mod-body::-webkit-scrollbar{width:6px}
.mod-body::-webkit-scrollbar-track{background:transparent}
.mod-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
@media(max-width:768px){.content-wrap{display:block;padding:12px 14px;gap:0}.sidebar{display:none!important}.main-content{width:100%}.masthead{padding:16px 0 12px}.mh-title{font-size:32px;letter-spacing:1px}.mh-meta{gap:10px;font-size:11px;margin-top:8px}.flag-bar{height:3px}.top-bar{padding:6px 0}.ti{padding:0 14px}.tb-r{gap:10px}.clock{font-size:12px}.dt-btn{padding:5px 10px;font-size:11px}.ticker{padding:6px 0}.ticker-inner{padding:0 14px}.ticker-label{font-size:11px;padding:3px 10px}.ticker-text{font-size:12px}.sub-ts{padding:0 14px;gap:4px;margin-top:8px}.sub-t{padding:8px 16px;font-size:12px;border-radius:16px}.ctrls{padding:0 14px;margin-top:10px}.rf-btn{padding:10px 18px;font-size:13px;border-radius:10px}.gr{column-count:2;column-gap:12px}.a{border-radius:12px;margin-bottom:12px}.ai{aspect-ratio:16/9}.ai img{transition:none}.a:hover .ai img{transform:none}.ab{padding:14px 16px 18px}.am{margin-bottom:8px}.as{font-size:12px;padding:4px 10px}.ad{font-size:11px}.at{font-size:18px;margin-bottom:8px;line-height:1.4}.ae{font-size:14px;line-height:1.7;-webkit-line-clamp:3}.sb-btn{width:28px;height:28px;font-size:11px;top:8px;left:8px}.vi{width:32px;height:32px;font-size:13px;top:8px;right:8px}.ftr-art{margin:10px 0;border-radius:12px}.ftr-inner{grid-template-columns:1fr;min-height:auto}.ftr-img{height:180px}.ftr-body{padding:16px}.ftr-title{font-size:20px;line-height:1.3}.ftr-summary{font-size:13px;-webkit-line-clamp:2}.ftr-meta{font-size:11px;gap:10px}.ftr-sec{padding:16px 14px;margin-top:20px}html{font-size:15px}.mod-overlay{padding:0}.mod-overlay .mod-box{max-height:100vh;height:100vh;border-radius:0;max-width:100%;overflow:hidden}.mod-head{padding:10px 14px;min-height:44px;background:var(--card-bg);border-bottom:1px solid var(--border);z-index:10;flex-shrink:0}.mod-head .mh-close{width:32px;height:32px;font-size:14px;background:rgba(255,255,255,0.08);border-radius:50%}.mod-title{padding:14px 16px 0;font-size:20px;line-height:1.4;flex-shrink:0}.mod-body{padding:14px 16px;font-size:16px;line-height:1.9;flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;min-height:0}.mod-footer{gap:6px;padding:10px 14px;border-top:1px solid var(--border);flex-direction:row;flex-wrap:wrap;align-items:center;flex-shrink:0;background:var(--card-bg);z-index:10}.mod-footer .mod-btn{padding:6px 10px;font-size:10px;border-radius:8px;flex-shrink:0}}
@media(max-width:480px){.mh-title{font-size:24px}.mh-meta{flex-wrap:wrap;justify-content:center;font-size:10px}.gr{column-count:1;column-gap:0}.a{margin-bottom:14px}.ab{padding:16px 18px 20px}.at{font-size:19px;line-height:1.4}.ae{font-size:15px;line-height:1.7;-webkit-line-clamp:3}.as{font-size:12px}.ad{font-size:11px}.sub-t{padding:6px 12px;font-size:11px}.ftr-title{font-size:17px}.ftr-summary{font-size:12px}.mod-title{font-size:18px}.mod-body{font-size:15px;line-height:1.8}}"""

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    load_cache()

    # Pre-flight: Check live site health
    if "--skip-check" not in sys.argv:
        validate_live_site()

    print("=" * 50)
    print(" News Aggregator - dz-akhbar (async)")
    print("=" * 50)

    t0 = time.time()
    # Use async fetcher for 3x speed improvement
    all_articles = asyncio.run(async_fetch_all(REGIONS, max_per_source=15))
    fetch_time = time.time() - t0
    print(f"Fetched {len(all_articles)} articles in {fetch_time:.1f}s (async)")

    # Validate fetched articles
    stats = validate_articles(all_articles)
    print_validation_report(stats)
    if stats["no_text"] > 0:
        print(f"  Repairing {stats['no_text']} articles with missing text...")
        asyncio.run(repair_missing_text(all_articles))
    if stats["no_image"] > 0:
        print(f"  Repairing {stats['no_image']} articles with missing images...")
        asyncio.run(repair_missing_image(all_articles))
    # Second validation after repair
    stats2 = validate_articles(all_articles)
    repaired_text = stats["no_text"] - stats2["no_text"]
    repaired_img = stats["no_image"] - stats2["no_image"]
    print(f"  Repair results: {repaired_text} text fixed, {repaired_img} images fixed ({stats2['no_text']} text, {stats2['no_image']} images still missing)")

    # Pre-publish fixer: translate, complete, ensure periods
    print(f"\n  [PRE-PUBLISH] Fixing articles before publishing...")
    fix_result = fix_articles_before_publish(all_articles)
    print(f"  Pre-publish results: {fix_result['fixed']} fixed, {fix_result['translated']} translated, {fix_result['periods_added']} periods added, {fix_result['incomplete_removed']} incomplete removed")

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

    # Remove articles older than 2 days
    cutoff_3d = time.time() - 2*86400
    for rid in ["dz", "ar"]:
        for cat in result[rid]:
            kept = []
            for a in result[rid][cat]:
                # Use parse_published_str for the real date
                real_ts = parse_published_str(a.get("published", ""))
                if real_ts:
                    if real_ts >= cutoff_3d:
                        kept.append(a)
                else:
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

    # Sort by date (newest first) - use real_ts for accurate sorting
    for rid in ["dz", "ar"]:
        for cat in result[rid]:
            result[rid][cat].sort(key=lambda a: parse_published_str(a.get("published", "")) or safe_mktime(a.get("published_parsed")), reverse=True)

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
        merged[cat].sort(key=lambda a: parse_published_str(a.get("published", "")) or safe_mktime(a.get("published_parsed")), reverse=True)
        random.shuffle(merged[cat])

    # Re-assign trending/popular to use all articles (for rich images)
    # uni uses articles from DZ_UNI + AR_UNI RSS sources only
    merged["trending"] = merged["latest"][:]
    merged["popular"] = merged["latest"][:]

    # Final fluff cleanup on all articles before rendering
    cleaned_count = 0
    for k in merged:
        for a in merged[k]:
            if a.get("text"):
                cleaned = _clean_fluff(a["text"], a.get("title", ""))
                if cleaned != a["text"]:
                    cleaned_count += 1
                a["text"] = cleaned
    for a in all_articles:
        if a.get("text"):
            a["text"] = _clean_fluff(a["text"], a.get("title", ""))
    if cleaned_count:
        print(f"  Cleaned {cleaned_count} articles from fluff")

    # Remove articles without images before publishing
    for k in list(merged.keys()):
        before = len(merged[k])
        merged[k] = [a for a in merged[k] if a.get("image")]
        after = len(merged[k])
        if before != after:
            print(f"  Filtered {k}: {before} -> {after} (removed {before - after} without images)")

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
            "pub": esc(a["published"][:20]),
        })
    _js_safe = lambda s: s.replace('<', '\\u003c').replace('>', '\\u003e')
    ft_json = _js_safe(json.dumps(ft_data_js, ensure_ascii=False))

    sb_pop = build_sidebar_list(merged["popular"])
    sb_uni = build_sidebar_list(merged.get("uni", []))

    ticker_items = [{"title": esc(a["title"]), "id": hashlib.md5((a["title"] + a["link"]).encode()).hexdigest()[:8]} for a in merged["latest"][:30]]
    ticker_json = _js_safe(json.dumps(ticker_items, ensure_ascii=False))

    rg_js = {"latest": len(merged["latest"]), "trending": len(merged["trending"]), "popular": len(merged["popular"]), "uni": len(merged["uni"])}
    rg_json = _js_safe(json.dumps(rg_js, ensure_ascii=False))

    news_schema = build_news_schema(merged["latest"][:30])

    with open(os.path.join(base, TEMPLATE_FILE), "r", encoding="utf-8") as f:
        tmpl = Template(f.read())
    build_timestamp = int(time.time())
    trending_topics_html = build_trending_topics(all_articles)
    analytics_html = build_analytics_dashboard(all_articles)
    github_token = os.getenv("GITHUB_TOKEN", "")
    html = tmpl.render(
        css=CSS, title="جريدة الجزائر — aggregator الأخبار الجزائرية",
        meta_desc="أخبار الجزائر العاجلة من أشهر الصحف الجزائرية: الشروق، النهار، الخبر، البلاد، الحوار + أخبار الجامعات و المعاهد",
        now_ar=now_ar, total=grand_total,
        cards_latest=cards["latest"], cards_trending=cards["trending"],
        cards_popular=cards["popular"], cards_uni=cards["uni"],
        featured_dz=featured_dz,
        rg_json=rg_json, ticker_json=ticker_json, ft_json=ft_json,
        sb_pop=sb_pop, sb_uni=sb_uni,
        build_timestamp=build_timestamp,
        news_schema=news_schema,
        trending_topics_html=trending_topics_html,
        analytics_html=analytics_html,
        GITHUB_TOKEN=github_token,
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
    SITE_URL = "https://1ymenn.github.io/dz-akhbar"
    once = "--once" in sys.argv
    while True:

        t0 = time.time()
        changed = main()
        elapsed = time.time() - t0
        print(f"Total build time: {elapsed:.1f}s")
        if changed:
            if not once:
                print("\nDeploy handled by GitHub Actions...")

                # Post-update health check (3x)
                print(f"Post-update health check for {SITE_URL}...")
                post_ok = health_check(SITE_URL, retries=3, delay=10)
                if not post_ok:
                    print("WARNING: Site may be down after deploy!")
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
