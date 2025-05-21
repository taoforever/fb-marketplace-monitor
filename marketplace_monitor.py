import os
import json
import yagmail
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# ========== 参数配置 ==========
KEYWORDS = ["canoe", "kayak"]
CITY_URL = "https://www.facebook.com/marketplace/toronto/search?availability=in%20stock&query=canoe"
PRICE_MIN = 0
PRICE_MAX = 800

EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_TO = os.environ["EMAIL_TO"]
COOKIE_FILE = Path("fb_cookies.json")
SEEN_FILE = Path("seen_items.json")

# ========== 工具函数 ==========

def load_seen_ids():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen_ids(seen_ids):
    SEEN_FILE.write_text(json.dumps(list(seen_ids)))

def matches_filters(title, price):
    if not any(kw.lower() in title.lower() for kw in KEYWORDS):
        return False
    if price is None:
        return False
    return PRICE_MIN <= price <= PRICE_MAX

def send_email(new_items, attachments=None):
    yag = yagmail.SMTP(EMAIL_SENDER, EMAIL_PASSWORD)
    if new_items:
        subject = f"[FB Marketplace] 有 {len(new_items)} 条新匹配信息"
        body = "\n\n".join([f"{item['title']}\n价格: {item['price']}\n链接: {item['url']}" for item in new_items])
    else:
        subject = "[FB Marketplace] 没有匹配商品，已附上调试截图和页面源代码"
        body = "没有抓取到任何商品，详见附件 debug.png 和 debug.html。"

    yag.send(to=EMAIL_TO, subject=subject, contents=body, attachments=attachments)
    print(f"[+] 邮件已发送，共 {len(new_items)} 条新信息（含附件 {attachments}）")

if COOKIE_FILE.exists():
    cookies = json.loads(COOKIE_FILE.read_text())
    context = browser.new_context()
    context.add_cookies(cookies)
    print("[+] 已加载 cookies")
else:
    context = browser.new_context()


# ========== 抓取核心函数 ==========

def scrape_marketplace():
    seen_ids = load_seen_ids()
    new_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # 注入 cookie 模拟登录
        if COOKIE_FILE.exists():
            cookies = json.loads(COOKIE_FILE.read_text())
            context.add_cookies(cookies)
            print("[+] 已加载 cookies")

        page = context.new_page()
        print(f"[+] 正在访问: {CITY_URL}")
        page.goto(CITY_URL, timeout=60000)
        page.wait_for_timeout(5000)

        items = page.query_selector_all("div[role='article']")
        print(f"[+] 抓取到 {len(items)} 个商品")

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
                        new_items.append({
                            "title": title,
                            "price": price,
                            "url": full_url
                        })
                        seen_ids.add(item_id)
            except Exception:
                continue

        # 如果没有新商品，保存 debug 信息
        if not new_items:
            page.screenshot(path="debug.png", full_page=True)
            Path("debug.html").write_text(page.content())
            print("[=] 没有商品，已保存 debug.png 和 debug.html")
            send_email([], attachments=["debug.png", "debug.html"])
        else:
            send_email(new_items)
            save_seen_ids(seen_ids)

        browser.close()


# ========== 主函数 ==========
if __name__ == "__main__":
    scrape_marketplace()
