#!/usr/bin/env python3
"""
Ticketlink Sniper - Production Macro
CDP Stealth Chromium connection
Target: ticketlink.co.kr real-time booking automation
"""

import asyncio, json, random, sys, time, os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

CDP_URL = "http://localhost:9222"
BASE_URL = "https://www.ticketlink.co.kr"
PRODUCT_ID = os.environ.get("TL_PRODUCT_ID", "63681")
TARGET_TIME = os.environ.get("TL_TARGET_TIME", "2026-06-17 20:00:00")
TARGET_EPOCH = int(os.environ.get("TL_TARGET_EPOCH", "0"))  # Override with epoch

# KST offset (UTC+9)
KST_OFFSET = 9 * 3600

async def hdelay(lo=0.03, hi=0.12):
    await asyncio.sleep(random.uniform(lo, hi))

async def hclick(page, el):
    try:
        box = await el.bounding_box()
        if box:
            x = box['x'] + random.uniform(2, max(2, box['width']-2))
            y = box['y'] + random.uniform(2, max(2, box['height']-2))
            await page.mouse.move(x, y, steps=random.randint(3, 8))
    except: pass
    await hdelay()
    try: await el.click(timeout=2000)
    except: await el.click(force=True, timeout=2000)

async def snipe_page(page, product_id):
    """Monitor and auto-click reserve button"""
    url = f"{BASE_URL}/product/{product_id}"
    print(f"[*] Loading: {url}")
    
    # Initial load
    resp = await page.goto(url, wait_until='domcontentloaded', timeout=15000)
    print(f"[*] Initial status: {resp.status if resp else '?'}")
    await asyncio.sleep(1)
    
    # Determine target datetime
    if TARGET_EPOCH > 0:
        target_dt = datetime.fromtimestamp(TARGET_EPOCH)
    else:
        # Parse as KST
        target_dt = datetime.strptime(TARGET_TIME, '%Y-%m-%d %H:%M:%S')
    
    print(f"[*] Target: {target_dt.strftime('%Y-%m-%d %H:%M:%S')} (epoch: {int(target_dt.timestamp())})")
    
    attempt = 0
    while True:
        now = datetime.now()
        remaining = (target_dt - now).total_seconds()
        
        if remaining <= 0:
            break
        
        if remaining < 3:
            # Sub-second refresh in final seconds
            await page.reload(wait_until='commit')
            await asyncio.sleep(0.03)
        elif remaining < 15:
            print(f"\r[*] T-{remaining:.1f}s | rapid polling...", end='')
            await page.reload(wait_until='domcontentloaded')
            await asyncio.sleep(0.2)
        else:
            if attempt % 30 == 0:
                mins = int(remaining / 60)
                secs = int(remaining % 60)
                print(f"[*] {mins}m {secs}s remaining...")
            await page.reload(wait_until='domcontentloaded')
            await asyncio.sleep(1.5)
        
        attempt += 1
    
    print("\n[!!!] TARGET TIME REACHED - SNIPING")
    
    # Rapid booking loop (max 300 attempts)
    for i in range(300):
        try:
            await page.reload(wait_until='commit')
            await asyncio.sleep(0.01)
            
            # Check for reserve button
            reserve = await page.query_selector(
                'button:has-text("예매하기"):not([disabled]), '
                'a:has-text("예매하기")'
            )
            
            if reserve:
                visible = await reserve.is_visible()
                disabled = await reserve.get_attribute('disabled')
                
                if visible and not disabled:
                    print(f"[!!!] RESERVE ACTIVE! Clicking... (attempt {i})")
                    await hclick(page, reserve)
                    await asyncio.sleep(0.3)
                    
                    # Auto-select options
                    await auto_select(page)
                    
                    # Screenshot
                    await page.screenshot(path=f"/tmp/tl_snipe_{product_id}.png")
                    print(f"[+] Screenshot saved")
                    return True
            
            # Status change detection
            if i % 50 == 49:
                body = await page.text_content('body') or ''
                if '예매 오픈 전' not in body:
                    print(f"[*] Status changed at attempt {i}")
                    
        except Exception as e:
            if i % 100 == 99:
                print(f"[!] Error at {i}: {e}")
    
    print("[*] Max attempts reached without success")
    return False

async def auto_select(page):
    """Auto-select date, round, and proceed"""
    await asyncio.sleep(0.5)
    
    # Date selection
    for sel in ['button[class*="date"]:not([disabled])', 
                'button[class*="day"]:not([disabled])',
                '[class*="calendar"] button:not([disabled])']:
        try:
            btns = await page.query_selector_all(sel)
            for btn in btns:
                if await btn.is_visible():
                    print(f"[+] Selecting date")
                    await hclick(page, btn)
                    await asyncio.sleep(0.2)
                    break
            break
        except: continue
    
    # Round/time selection
    for sel in ['button[class*="time"]:not([disabled])',
                'button[class*="round"]:not([disabled])',
                'button[class*="session"]:not([disabled])']:
        try:
            btns = await page.query_selector_all(sel)
            for btn in btns:
                if await btn.is_visible():
                    print(f"[+] Selecting time")
                    await hclick(page, btn)
                    await asyncio.sleep(0.2)
                    break
            break
        except: continue
    
    # Next step
    for text in ['다음', '좌석선택', '선택완료', '결제하기']:
        try:
            btn = await page.query_selector(
                f'button:has-text("{text}"):not([disabled]), a:has-text("{text}")'
            )
            if btn and await btn.is_visible():
                print(f"[+] Clicking '{text}'")
                await hclick(page, btn)
                await asyncio.sleep(0.3)
                break
        except: continue

async def cancel_snipe(page, product_id):
    """Monitor for cancelled tickets (취켓팅)"""
    url = f"{BASE_URL}/product/{product_id}"
    print(f"[*] Cancel-snipe mode: {url}")
    
    await page.goto(url, wait_until='domcontentloaded', timeout=15000)
    await asyncio.sleep(1)
    
    for i in range(600):  # 10 minutes of monitoring
        try:
            await page.reload(wait_until='commit')
            await asyncio.sleep(0.5)
            
            # Look for active reserve button
            reserve = await page.query_selector(
                'button:has-text("예매하기"):not([disabled]), '
                'a:has-text("예매하기"), '
                'button:has-text("취소표"):not([disabled])'
            )
            
            if reserve and await reserve.is_visible():
                text = (await reserve.text_content() or '').strip()
                disabled = await reserve.get_attribute('disabled')
                if not disabled:
                    print(f"[!!!] '{text}' available! Booking...")
                    await hclick(page, reserve)
                    await auto_select(page)
                    return True
            
            if i % 60 == 59:
                print(f"[*] Monitoring... ({i+1} refreshes)")
                
        except Exception as e:
            await asyncio.sleep(0.3)
    
    return False

async def main():
    mode = os.environ.get("TL_MODE", "snipe")
    product_id = PRODUCT_ID
    
    print(f"█ Ticketlink Sniper")
    print(f"█ Mode: {mode} | Product: {product_id}")
    print(f"█ CDP: {CDP_URL}")
    
    pw = await async_playwright().start()
    
    try:
        browser = await pw.chromium.connect_over_cdp(CDP_URL)
        pages = browser.contexts[0].pages
        page = pages[0] if pages else await browser.contexts[0].new_page()
        
        page.set_default_timeout(15000)
        
        if mode == "snipe":
            result = await snipe_page(page, product_id)
        elif mode == "cancel":
            result = await cancel_snipe(page, product_id)
        else:
            print(f"[!] Unknown mode: {mode}")
            result = False
        
        status = "SUCCESS" if result else "FAILED"
        print(f"\n[{status}] Macro completed")
        
    except Exception as e:
        print(f"[!] Fatal error: {e}")
    finally:
        await pw.stop()

if __name__ == '__main__':
    asyncio.run(main())
