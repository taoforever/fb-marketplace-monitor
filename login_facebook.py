# login_facebook.py
from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()

    page = context.new_page()
    page.goto("https://www.facebook.com/login")

    print("[*] 请手动登录 Facebook...")
    page.wait_for_timeout(60000)  # 给你 60 秒时间手动登录

    # 登录后保存 cookies
    cookies = context.cookies()
    with open("fb_cookies.json", "w") as f:
        json.dump(cookies, f)

    print("[+] 登录成功，已保存 cookies。")
    browser.close()
