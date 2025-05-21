import json
import time
import yagmail
from pathlib import Path
from playwright.sync_api import sync_playwright
import os

# ===== 从环境变量读取用户配置 =====
KEYWORDS = ["canoe"]
CITY_URL = "https://www.facebook.com/marketplace/toronto/search?availability=in%20stock&query=canoe"  # 修改为你要监控的城市
PRICE_MIN = 0
PRICE_MAX = 800

EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_TO = os.environ["EMAIL_TO"]

SEEN_FILE = Path("seen_items.json")


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
    subject = f"[FB Marketplace] 有 {len(new_items)} 条新匹配信息" if new_items else "[FB Marketplace] 抓取失败或无匹配信息"
    if new_items:
        body = "\n\n".join([f"{item['title']}\n价格: {item['price']}\n链接: {item['url']}" for item in new_items])
    else:
        body = "此次运行未能抓取到任何商品，已附上调试截图和页面 HTML 文件。"

    yag.send(to=EMAIL_TO, subject=subject, contents=body, attachments=attachments)
    print(f"[+] 邮件已发送，附带调试文件: {attachments}")




def scrape_marketplace():
    seen_ids = load_seen_ids()
    new_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print(f"[+] 正在访问: {CITY_URL}")
        page.goto(CITY_URL)
        page.wait_for_timeout(5000)

        # 保存截图与 HTML 供调试
        page.screenshot(path="debug.png")
        with open("debug.html", "w", encoding="utf-8") as f:
            f.write(page.content())
            
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

        browser.close()

    if new_items:
        send_email(new_items)
        save_seen_ids(seen_ids)
    else:
        print("[=] 没有发现新的匹配商品")
        send_email([], attachments=["debug.png", "debug.html"])


if __name__ == "__main__":
    scrape_marketplace()  # 只执行一次
