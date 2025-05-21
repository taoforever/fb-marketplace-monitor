```python
import json
import time
import yagmail
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

# ===== 用户设置 =====
KEYWORDS = ["canoe", "kayak"]
CITY_URL = "https://www.facebook.com/marketplace/toronto/search?availability=in%20stock&query=canoe"
PRICE_MIN = 0
PRICE_MAX = 800

EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_TO = os.environ["EMAIL_TO"]

SEEN_FILE = Path("seen_items.json")
COOKIE_FILE = Path("fb_cookies.json")

# ===== 商品记录读取与保存 =====
def load_seen_ids():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen_ids(seen_ids):
    SEEN_FILE.write_text(json.dumps(list(seen_ids)))

# ===== 条件过滤器 =====
def matches_filters(title, price):
    if not any(kw.lower() in title.lower() for kw in KEYWORDS):
        return False
    if price is None:
        return False
    return PRICE_MIN <= price <= PRICE_MAX

# ===== 邮件通知 =====
def send_email(new_items, attachments=None):
    yag = yagmail.SMTP(EMAIL_SENDER, EMAIL_PASSWORD)
    subject = f"[FB Marketplace] 有 {len(new_items)} 条新商品"
    if new_items:
        body = "\n\n".join([f"{item['title']}\n價格: {item['price']}\n鏈接: {item['url']}" for item in new_items])
    else:
        body = "⚠ 未抓取到商品，请查看附件排查登录/页面问题"

    yag.send(to=EMAIL_TO, subject=subject, contents=body, attachments=attachments or [])
    print(f"[+] 郵件已發送（{len(new_items)} 條商品）")

# ===== 主抓取程序 =====
def scrape_marketplace():
    seen_ids = load_seen_ids()
    new_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # 加载 Cookie 实现登录
        if COOKIE_FILE.exists():
            cookies = json.loads(COOKIE_FILE.read_text())
            context.add_cookies(cookies)
            print("[+] 已加載 Cookie")
        else:
            print("[!] 缺少 fb_cookies.json")

        page = context.new_page()
        page.goto(CITY_URL)
        page.wait_for_timeout(8000)

        items = page.query_selector_all("div[role='article']")
        print(f"[+] 抓取到 {len(items)} 個商品")

        for item in items:
            try:
                title = item.query_selector("span").inner_text()
                url = item.query_selector("a").get_attribute("href")
                full_url = f"https://www.facebook.com{url}"
                price_text = item.query_selector("span:has-text('$')").inner_text()
                price = int(''.join(filter(str.isdigit, price_text)))

                if matches_filters(title, price):
                    item_id = full_url.split("item/")[-1].split("/")[0]
                    if item_id not in seen_ids:
                        new_items.append({"title": title, "price": price, "url": full_url})
                        seen_ids.add(item_id)
            except Exception:
                continue

        # 若没抓到商品，保存调试信息
        if not new_items:
            page.screenshot(path="debug.png")
            Path("debug.html").write_text(page.content())
            print("[=] 無商品，已保存 debug.png 和 debug.html")
            send_email([], attachments=["debug.png", "debug.html"])
        else:
            send_email(new_items)
            save_seen_ids(seen_ids)

        browser.close()

if __name__ == "__main__":
    scrape_marketplace()
