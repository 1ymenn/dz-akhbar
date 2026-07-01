import re
html = open('index.html', 'r', encoding='utf-8').read()

# Verify fixes
print("=== VERIFICATION ===")

# 1. CSP
csp_match = re.search(r"script-src\s+([^;]+)", html)
if csp_match:
    print("CSP script-src:", csp_match.group(1))
    print("  Has unsafe-inline:", "'unsafe-inline'" in csp_match.group(1))

# 2. Modal CSS
print("Modal CSS:", ".mod-overlay.open{display:flex}" in html)

# 3. Click handler
print("Click handler:", "document.addEventListener('click'" in html)
print("  Has .ac[data-link]:", ".ac[data-link]" in html)
print("  Has .sb-link[data-link]:", ".sb-link[data-link]" in html)

# 4. openModal function
print("openModal:", "function openModal(el)" in html)

# 5. Attribute escaping
# Check first card's data-title for broken quotes
titles = re.findall(r'data-title="([^"]*)"', html)
print(f"Titles: {len(titles)} total")
bad = sum(1 for t in titles if len(t) < 3)
print(f"  Suspiciously short (<3): {bad}")

# 6. data-txt with &#10;
txts = re.findall(r'data-txt="([^"]*)"', html)
with_nl = sum(1 for t in txts if '&#10;' in t)
print(f"data-txt: {len(txts)} total, {with_nl} with newlines")

# 7. Total articles
articles = re.findall(r'class="ac" data-id=', html)
print(f"Article cards: {len(articles)}")
