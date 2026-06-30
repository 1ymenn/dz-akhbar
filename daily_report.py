#!/usr/bin/env python3
"""
تقرير يومي - dz-akhbar
يجلب إحصائيات الزوار من GoatCounter ويرسل تقرير على الإيميل
"""
import os
import sys
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import requests

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# تحميل .env
def load_env():
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

load_env()

# ═══════════════════════════════════════════════════════════════
# الإعدادات
# ═══════════════════════════════════════════════════════════════
GOATCOUNTER_CODE = os.environ.get("GOATCOUNTER_CODE", "")
GOATCOUNTER_TOKEN = os.environ.get("GOATCOUNTER_TOKEN", "")
EMAIL_TO = os.environ.get("REPORT_EMAIL", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


# ═══════════════════════════════════════════════════════════════
# GoatCounter API
# ═══════════════════════════════════════════════════════════════
def get_goatcounter_stats(days=7):
    if not GOATCOUNTER_CODE or not GOATCOUNTER_TOKEN:
        return None
    
    api_base = f"https://{GOATCOUNTER_CODE}.goatcounter.com/api/v0"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GOATCOUNTER_TOKEN}"
    }
    
    today = datetime.now()
    start = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    
    stats = {}
    
    try:
        r = requests.get(f"{api_base}/stats/total", headers=headers, params={
            "period-start": start, "period-end": end
        }, timeout=10)
        if r.ok:
            data = r.json()
            stats["total_pageviews"] = data.get("total", [{}])[0].get("count", 0) if data.get("total") else 0
            stats["total_visitors"] = data.get("total_unique", [{}])[0].get("count", 0) if data.get("total_unique") else 0
    except Exception as e:
        print(f"  Error: {e}")
    
    try:
        r = requests.get(f"{api_base}/stats/hits", headers=headers, params={
            "period-start": start, "period-end": end
        }, timeout=10)
        if r.ok:
            data = r.json()
            stats["daily"] = [{"date": d.get("day",""), "pageviews": d.get("count",0), "visitors": d.get("count_unique",0)} for d in data.get("hits", [])]
    except Exception as e:
        print(f"  Error: {e}")
    
    try:
        r = requests.get(f"{api_base}/paths", headers=headers, params={
            "period-start": start, "period-end": end, "limit": 10
        }, timeout=10)
        if r.ok:
            data = r.json()
            stats["top_pages"] = [{"path": p.get("path",""), "pageviews": p.get("count",0), "visitors": p.get("count_unique",0)} for p in data.get("paths", [])[:10]]
    except Exception as e:
        print(f"  Error: {e}")
    
    try:
        r = requests.get(f"{api_base}/paths", headers=headers, params={
            "period-start": start, "period-end": end, "limit": 5
        }, timeout=10)
        if r.ok:
            data = r.json()
            stats["referrers"] = []
            for path in data.get("paths", [])[:5]:
                for ref in path.get("refs", [])[:5]:
                    if ref.get("ref", ""):
                        stats["referrers"].append({"referrer": ref.get("ref",""), "pageviews": ref.get("count",0)})
    except Exception as e:
        print(f"  Error: {e}")
    
    return stats


# ═══════════════════════════════════════════════════════════════
# إرسال إيميل عبر Gmail SMTP
# ═══════════════════════════════════════════════════════════════
def send_email(subject, body):
    if not GMAIL_APP_PASSWORD:
        return False, "GMAIL_APP_PASSWORD not set"
    
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, GMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        return True, "Sent"
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════════════════════════
# إنشاء التقرير
# ═══════════════════════════════════════════════════════════════
def generate_report(stats, news_data=None):
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    L = []
    L.append("=" * 50)
    L.append(f"تقرير يومي - جريدة الجزائر")
    L.append(f"التاريخ: {today.strftime('%Y-%m-%d')}")
    L.append("=" * 50)
    L.append("")
    
    L.append("إحصائيات الموقع")
    L.append("-" * 30)
    
    if stats:
        L.append(f"  اجمالي المشاهدات: {stats.get('total_pageviews', 0):,}")
        L.append(f"  الزوار الفريدون: {stats.get('total_visitors', 0):,}")
        
        if stats.get("daily"):
            today_stats = None
            yesterday_stats = None
            for d in stats["daily"]:
                if d["date"] == today.strftime("%Y-%m-%d"):
                    today_stats = d
                elif d["date"] == yesterday.strftime("%Y-%m-%d"):
                    yesterday_stats = d
            
            if today_stats:
                L.append(f"  اليوم: {today_stats['pageviews']:,} مشاهدة / {today_stats['visitors']:,} زائر")
            if yesterday_stats:
                L.append(f"  امس: {yesterday_stats['pageviews']:,} مشاهدة / {yesterday_stats['visitors']:,} زائر")
            
            if today_stats and yesterday_stats and yesterday_stats["pageviews"] > 0:
                change = ((today_stats["pageviews"] - yesterday_stats["pageviews"]) / yesterday_stats["pageviews"]) * 100
                sign = "+" if change > 0 else ""
                L.append(f"  التغيير: {sign}{change:.1f}%")
    else:
        L.append("  لا توجد بيانات")
    
    L.append("")
    
    if stats and stats.get("top_pages"):
        L.append("افضل الصفحات")
        L.append("-" * 30)
        for i, page in enumerate(stats["top_pages"][:5], 1):
            path = page["path"]
            if path == "/": path = "الصفحة الرئيسية"
            elif path.startswith("#article/"): path = f"مقال"
            L.append(f"  {i}. {path}")
            L.append(f"     مشاهدات: {page['pageviews']:,} / زوار: {page['visitors']:,}")
        L.append("")
    
    if stats and stats.get("referrers"):
        L.append("المراجع")
        L.append("-" * 30)
        for ref in stats["referrers"][:5]:
            L.append(f"  - {ref['referrer']}: {ref['pageviews']:,} زيارة")
        L.append("")
    
    if news_data:
        L.append("ملخص الاخبار")
        L.append("-" * 30)
        
        dz_count = len([a for a in news_data if a.get("region") == "dz"])
        ar_count = len([a for a in news_data if a.get("region") == "ar"])
        total_articles = len(news_data)
        
        L.append(f"  اجمالي الاخبار: {total_articles}")
        L.append(f"  اخبار جزائرية: {dz_count}")
        L.append(f"  اخبار عربية: {ar_count}")
        
        sources = {}
        for a in news_data:
            src = a.get("source", "غير معروف")
            sources[src] = sources.get(src, 0) + 1
        
        L.append(f"  المصادر ({len(sources)}):")
        for src, count in sorted(sources.items(), key=lambda x: -x[1])[:10]:
            L.append(f"    - {src}: {count} خبر")
        
        with_text = len([a for a in news_data if a.get("text")])
        with_image = len([a for a in news_data if a.get("image")])
        L.append(f"  الاخبار مع النص: {with_text}/{total_articles}")
        L.append(f"  الاخبار مع الصورة: {with_image}/{total_articles}")
    
    L.append("")
    L.append("=" * 50)
    L.append(f"وقت الانشاء: {today.strftime('%H:%M:%S')}")
    L.append(f"الموقع: https://1ymenn.github.io/dz-akhbar")
    L.append("=" * 50)
    
    return "\n".join(L)


# ═══════════════════════════════════════════════════════════════
# الرئيسية
# ═══════════════════════════════════════════════════════════════
def main():
    print("=" * 50)
    print("تقرير يومي - dz-akhbar")
    print("=" * 50)
    
    print("\n1. جلب احصائيات الزوار...")
    stats = get_goatcounter_stats(days=7)
    
    print("2. جلب بيانات الاخبار...")
    news_data = None
    try:
        with open("latest_news.json", "r", encoding="utf-8") as f:
            raw = json.load(f)
            news_data = raw.get("articles", raw) if isinstance(raw, dict) else raw
    except Exception as e:
        print(f"   تحذير: {e}")
    
    print("3. انشاء التقرير...")
    report = generate_report(stats, news_data)
    
    report_file = f"report_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"   تم الحفظ: {report_file}")
    
    print("\n" + report)
    
    print("\n4. ارسال التقرير على الايميل...")
    ok, msg = send_email(f"تقرير يومي - {datetime.now().strftime('%Y-%m-%d')}", report)
    if ok:
        print("   تم الارسال بنجاح!")
    else:
        print(f"   خطأ: {msg}")
    
    print("\nانتهى!")


if __name__ == "__main__":
    main()
