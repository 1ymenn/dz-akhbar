# إعداد التقرير اليومي

## 1. إعداد GoatCounter (تتبع الزوار)

### الخطوة 1: إنشاء حساب
1. اذهب إلى https://www.goatcounter.com/signup
2. أدخل اسم الموقع (مثل: `dz-akhbar`)
3. أدخل إيميلك وكلمة المرور
4. ستكون النطاق: `dz-akhbar.goatcounter.com`

### الخطوة 2: الحصول على التوكن
1. سجل الدخول إلى `dz-akhbar.goatcounter.com`
2. اذهب إلى [Username] → API
3. أنشئ توكن جديد (اسم: "daily-report")
4. انسخ التوكن

### الخطوة 3: إضافة التتبع إلى الموقع
أضف هذا الكود في `template.html` قبل `</body>`:

```html
<script data-goatcounter="https://dz-akhbar.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
```

## 2. إعداد Gmail API (إرسال الإيميل)

### الخطوة 1: إنشاء مشروع Google Cloud
1. اذهب إلى https://console.cloud.google.com
2. أنشئ مشروع جديد (اسم: "dz-akhbar-report")
3. فعّل Gmail API من المكتبة

### الخطوة 2: إنشاء OAuth2 Credentials
1. اذهب إلى APIs & Services → Credentials
2. أنشئ OAuth 2.0 Client ID
3. النوع: Desktop App
4. حمّل الملف باسم `credentials.json`

### الخطوة 3: وضع الملفات
1. ضع `credentials.json` في مجلد `news-site`
2. عند التشغيل الأول، سيفتح متصفح للمصادقة
3. سجل الدخول بحسابك
4. سيُنشأ `token.json` تلقائياً

## 3. المتغيرات البيئية

أنشئ ملف `.env` أو اضبط المتغيرات:

```
GOATCOUNTER_CODE=dz-akhbar
GOATCOUNTER_TOKEN=your_token_here
REPORT_EMAIL=1ymenchougui@gmail.com
```

## 4. التشغيل

```bash
# تثبيت المكتبات
pip install requests google-api-python-client google-auth google-auth-oauthlib

# تشغيل التقرير
python daily_report.py
```

## 5. الجدولة

### Task Scheduler (Windows)
```powershell
# تشغيل كل يوم الساعة 7 صباحاً
schtasks /create /tn "dz-akhbar-report" /tr "C:\path\to\python.exe C:\path\to\daily_report.py" /sc daily /st 07:00
```

### GitHub Actions
أضف في `.github/workflows/daily-report.yml`:
```yaml
name: Daily Report
on:
  schedule:
    - cron: '0 5 * * *'  # 05:00 UTC = 07:00 Algeria
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install requests google-api-python-client google-auth google-auth-oauthlib
      - run: python daily_report.py
        env:
          GOATCOUNTER_CODE: ${{ secrets.GOATCOUNTER_CODE }}
          GOATCOUNTER_TOKEN: ${{ secrets.GOATCOUNTER_TOKEN }}
          REPORT_EMAIL: ${{ secrets.REPORT_EMAIL }}
          GMAIL_CREDENTIALS: ${{ secrets.GMAIL_CREDENTIALS }}
```
