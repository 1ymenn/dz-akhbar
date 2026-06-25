#!/usr/bin/env python3
"""
Newsletter Sender - sends daily digest to subscribers via Gmail SMTP.
Usage: python send_newsletter.py
"""
import os, sys, json, smtplib, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GMAIL_USER = os.getenv("EMAIL_FROM", "1ymenchougui@gmail.com")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD", "")
REPORT_EMAIL = os.getenv("REPORT_EMAIL", "1ymenchougui@gmail.com")
BASE_DIR = Path(__file__).parent
SUBSCRIBERS_FILE = BASE_DIR / "subscribers.json"
LATEST_NEWS_FILE = BASE_DIR / "latest_news.json"

def load_subscribers():
    if not SUBSCRIBERS_FILE.exists():
        return []
    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [s for s in data.get("subscribers", []) if s.get("active", True)]

def save_subscribers(subscribers):
    data = {"subscribers": subscribers, "last_sent": datetime.now().isoformat()}
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_latest_news():
    if not LATEST_NEWS_FILE.exists():
        return []
    with open(LATEST_NEWS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("articles", [])[:20]

def build_newsletter_html(articles, date_str):
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Tahoma,sans-serif;background:#121212;color:#E0E0E0;margin:0;padding:20px}}
.container{{max-width:600px;margin:0 auto;background:#1E1E1E;border-radius:12px;overflow:hidden}}
.header{{background:linear-gradient(135deg,#D21034,#8B0000);padding:30px;text-align:center}}
.header h1{{color:#fff;font-size:28px;margin:0}}
.header p{{color:rgba(255,255,255,0.8);font-size:14px;margin-top:8px}}
.content{{padding:24px}}
.article{{background:#2A2A2A;border-radius:10px;padding:16px;margin-bottom:14px;border-right:4px solid #D21034}}
.article-title{{font-size:16px;font-weight:700;color:#fff;margin-bottom:6px;line-height:1.5}}
.article-source{{display:inline-block;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700;color:#fff;margin-bottom:8px}}
.article-summary{{font-size:14px;color:#B0B0B0;line-height:1.7}}
.article-link{{display:inline-block;margin-top:8px;color:#D4A017;text-decoration:none;font-size:13px;font-weight:600}}
.footer{{background:#1A1A1A;padding:20px;text-align:center;color:#808080;font-size:12px}}
.footer a{{color:#D21034;text-decoration:none}}
.stats{{display:flex;justify-content:center;gap:20px;margin:16px 0}}
.stat{{text-align:center}}
.stat-num{{font-size:24px;font-weight:900;color:#D4A017}}
.stat-label{{font-size:12px;color:#808080}}
</style></head>
<body>
<div class="container">
<div class="header">
<h1>جريدة الجزائر</h1>
<p>النشرة البريدية اليومية - {date_str}</p>
</div>
<div class="content">
<div class="stats">
<div class="stat"><div class="stat-num">{len(articles)}</div><div class="stat-label">مقال</div></div>
<div class="stat"><div class="stat-num">{len(set(a.get('source','') for a in articles))}</div><div class="stat-label">مصدر</div></div>
</div>
<h2 style="color:#D4A017;font-size:18px;border-bottom:2px solid #D21034;padding-bottom:8px">🔥 أبرز الأخبار</h2>
"""
    for i, a in enumerate(articles[:10]):
        title = a.get("title", "بدون عنوان")
        source = a.get("source", "غير معروف")
        summary = a.get("summary", "")[:150]
        link = a.get("link", "#")
        colors = ["#c0392b","#2980b9","#27ae60","#e67e22","#8e44ad","#16a085","#2c3e50","#e74c3c"]
        color = colors[hash(source) % len(colors)]
        html += f"""
<div class="article">
<span class="article-source" style="background:{color}">{source}</span>
<div class="article-title">{title}</div>
<div class="article-summary">{summary}...</div>
<a href="{link}" class="article-link">← اقرأ المزيد</a>
</div>"""

    html += f"""
</div>
<div class="footer">
<p>جريدة الجزائر © {datetime.now().year} — جميع المقالات مملوكة لأصحابها</p>
<p>لإلغاء الاشتراك: <a href="mailto:{GMAIL_USER}?subject=إلغاء اشتراك النشرة&body=أريد إلغاء اشتراكي في النشرة البريدية">اضغط هنا</a></p>
</div>
</div>
</body></html>"""
    return html

def build_newsletter_text(articles, date_str):
    text = f"جريدة الجزائر - النشرة البريدية اليومية\n"
    text += f"التاريخ: {date_str}\n"
    text += f"عدد المقالات: {len(articles)}\n"
    text += "=" * 50 + "\n\n"
    text += "🔥 أبرز الأخبار:\n\n"
    for i, a in enumerate(articles[:10], 1):
        title = a.get("title", "بدون عنوان")
        source = a.get("source", "غير معروف")
        summary = a.get("summary", "")[:100]
        link = a.get("link", "#")
        text += f"{i}. [{source}] {title}\n"
        text += f"   {summary}...\n"
        text += f"   {link}\n\n"
    text += "=" * 50 + "\n"
    text += f"جريدة الجزائر © {datetime.now().year}\n"
    text += "لإلغاء الاشتراك، رد على هذا البريد بـ 'إلغاء'\n"
    return text

def send_email(to_email, subject, html_body, text_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"  Error sending to {to_email}: {e}")
        return False

def main():
    print("=" * 50)
    print("newsletter Sender - dz-akhbar")
    print("=" * 50)
    subscribers = load_subscribers()
    active_subscribers = [s for s in subscribers if s.get("active", True)]
    print(f"Subscribers: {len(active_subscribers)} active / {len(subscribers)} total")
    if not active_subscribers:
        print("No active subscribers. Skipping.")
        return
    articles = load_latest_news()
    print(f"Articles loaded: {len(articles)}")
    if not articles:
        print("No articles found. Skipping.")
        return
    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"جريدة الجزائر - أحدث الأخبار {date_str}"
    html_body = build_newsletter_html(articles, date_str)
    text_body = build_newsletter_text(articles, date_str)
    sent = 0
    failed = 0
    for sub in active_subscribers:
        email = sub.get("email", "")
        if not email:
            continue
        print(f"Sending to: {email}...", end=" ")
        if send_email(email, subject, html_body, text_body):
            print("OK")
            sent += 1
            sub["last_sent"] = datetime.now().isoformat()
        else:
            print("FAILED")
            failed += 1
        time.sleep(1)
    save_subscribers(subscribers)
    print(f"\nResults: {sent} sent, {failed} failed")
    print("=" * 50)

if __name__ == "__main__":
    main()
