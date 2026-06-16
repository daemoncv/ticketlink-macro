#!/usr/bin/env python3
"""
Ticketlink Macro v3 - CDP Stealth Edition
Connects to pre-existing Stealth Chromium via CDP (port 9222)
Bypasses EverSafe via real browser profile + extension-based stealth
"""

import asyncio
import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from playwright.async_api import async_playwright

# ============================================================
CONFIG = {
    "base_url": "https://www.ticketlink.co.kr",
    "mobile_url": "https://m.ticketlink.co.kr",
    "cdp_url": "http://localhost:9222",
    "product_id": "63811",  # EPEX 4th CONCERT
    "page_timeout": 20000,
    "click_delay": (0.05, 0.15),
}

# ============================================================

class TLMacro:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        
    async def connect_cdp(self):
        """Connect to existing Stealth Chromium via CDP"""
        print(f"[*] Connecting to CDP: {CONFIG['cdp_url']}")
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.connect_over_cdp(CONFIG['cdp_url'])
        
        # Get first page or create new
        pages = self.browser.contexts[0].pages if self.browser.contexts else []
        if pages:
            self.page = pages[0]
            print(f"[+] Reusing existing page: {self.page.url[:80]}")
        else:
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='ko-KR',
                timezone_id='Asia/Seoul',
            )
            self.page = await self.context.new_page()
            print("[+] Created new page")
        
        # Set shorter timeouts
        self.page.set_default_timeout(CONFIG['page_timeout'])
        
        # Don't wait for networkidle - EverSafe causes infinite loop
        # Use domcontentloaded instead
        
        print(f"[+] CDP connection established")
        print(f"[+] Current URL: {self.page.url}")
        return self
    
    async def hdelay(self, lo=0.05, hi=0.15):
        await asyncio.sleep(random.uniform(lo, hi))
    
    async def hclick(self, el):
        """Human-like click"""
        try:
            box = await el.bounding_box()
            if box:
                x = box['x'] + random.uniform(2, max(2, box['width']-2))
                y = box['y'] + random.uniform(2, max(2, box['height']-2))
                await self.page.mouse.move(x, y, steps=random.randint(3, 8))
        except:
            pass
        await self.hdelay()
        try:
            await el.click(timeout=3000)
        except:
            await el.click(force=True, timeout=3000)
    
    async def goto(self, url, wait_for="domcontentloaded"):
        """Navigate without networkidle (EverSafe blocks it)"""
        print(f"[*] Navigating: {url}")
        try:
            resp = await self.page.goto(url, wait_until=wait_for, timeout=15000)
            status = resp.status if resp else '?'
            print(f"[+] Status: {status}")
            await asyncio.sleep(1)  # Let JS settle
            return resp
        except Exception as e:
            print(f"[!] Navigation error: {e}")
            return None
    
    async def safe_text(self, selector):
        """Get text content safely"""
        try:
            el = await self.page.query_selector(selector)
            if el:
                return (await el.text_content() or '').strip()
        except:
            pass
        return ''
    
    async def find_clickable(self, texts, timeout=2000):
        """Find first clickable element matching any text"""
        for text in texts:
            try:
                sel = f'button:has-text("{text}"):not([disabled]), a:has-text("{text}")'
                btn = await self.page.wait_for_selector(sel, timeout=timeout)
                if btn:
                    return btn, text
            except:
                continue
        return None, None
    
    # ============================================================
    
    async def analyze_product(self, product_id=None):
        pid = product_id or CONFIG['product_id']
        url = f"{CONFIG['base_url']}/product/{pid}"
        
        print(f"\n{'='*60}")
        print(f"[ANALYZE] Product {pid}")
        print(f"{'='*60}")
        
        await self.goto(url)
        await asyncio.sleep(2)
        
        # Title
        title = await self.page.title()
        print(f"Title: {title}")
        
        # Screenshot
        await self.page.screenshot(path="/tmp/tl_v3_product.png", full_page=False)
        print("[+] Screenshot: /tmp/tl_v3_product.png")
        
        # Status detection
        body = await self.page.text_content('body') or ''
        
        status_map = {
            '예매 오픈 전': 'NOT_OPEN',
            '판매예정': 'SCHEDULED', 
            '예매마감': 'CLOSED',
            '판매종료': 'ENDED',
            '매진': 'SOLD_OUT',
            '예매하기': 'RESERVABLE',
        }
        
        print("\n[STATUS]")
        for keyword, status in status_map.items():
            if keyword in body:
                print(f"  [{status}] '{keyword}' detected")
        
        # Find all buttons
        buttons = await self.page.query_selector_all('button, a[role="button"], [onclick]')
        print(f"\n[{len(buttons)}] interactive elements")
        
        # Key buttons
        key_texts = ['예매하기', '좌석선택', '날짜선택', '회차선택', '다음', '선택완료']
        for text in key_texts:
            btn = await self.page.query_selector(f'button:has-text("{text}"), a:has-text("{text}")')
            if btn:
                visible = await btn.is_visible()
                disabled = await btn.get_attribute('disabled')
                cls = await btn.get_attribute('class') or ''
                print(f"  [{text}] visible={visible} disabled={disabled} class='{cls[:60]}'")
        
        # Save HTML
        html = await self.page.content()
        Path("/tmp/tl_v3_product.html").write_text(html, encoding='utf-8')
        print(f"\n[+] HTML: /tmp/tl_v3_product.html ({len(html)} bytes)")
        
        return body
    
    async def analyze_login(self):
        print(f"\n{'='*60}")
        print("[ANALYZE] Login Flow")
        print(f"{'='*60}")
        
        await self.goto(f"{CONFIG['base_url']}/login")
        await asyncio.sleep(2)
        
        await self.page.screenshot(path="/tmp/tl_v3_login.png", full_page=True)
        print("[+] Screenshot: /tmp/tl_v3_login.png")
        
        # Find PAYCO login link
        payco = await self.page.query_selector('a[href*="payco"], a[href*="oauth"], img[alt*="PAYCO"]')
        if payco:
            href = await payco.get_attribute('href') or ''
            print(f"[+] PAYCO login: {href[:120]}")
        
        # Login form
        form = await self.page.query_selector('form')
        if form:
            action = await form.get_attribute('action') or ''
            method = await form.get_attribute('method') or 'GET'
            print(f"[+] Login form: {method} {action}")
        
        inputs = await self.page.query_selector_all('input')
        for inp in inputs:
            name = await inp.get_attribute('name') or ''
            typ = await inp.get_attribute('type') or 'text'
            ph = await inp.get_attribute('placeholder') or ''
            print(f"  input: name='{name}' type='{typ}' placeholder='{ph}'")
        
        return True
    
    async def sniper_mode(self, product_id, open_time_str):
        """
        Precise sniping:
        1. Pre-load page
        2. Poll aggressively near open time
        3. Click reserve button the millisecond it appears
        """
        target = datetime.strptime(open_time_str, '%Y-%m-%d %H:%M:%S')
        
        print(f"\n{'█'*60}")
        print(f"█  SNIPER MODE")
        print(f"█  Target: {target.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"█  Product: {product_id}")
        print(f"{'█'*60}")
        
        url = f"{CONFIG['base_url']}/product/{product_id}"
        
        # Pre-load
        await self.goto(url)
        print("[*] Pre-loaded. Waiting...")
        
        attempt = 0
        while True:
            now = datetime.now()
            remaining = (target - now).total_seconds()
            
            if remaining <= 0:
                # GO TIME
                break
            
            if remaining < 3:
                # Ultra-aggressive: sub-second refresh
                await self.page.reload(wait_until='commit')
                await asyncio.sleep(0.03)
            elif remaining < 10:
                print(f"\r[*] T-{remaining:.1f}s | rapid refresh...", end='')
                await self.page.reload(wait_until='domcontentloaded')
                await asyncio.sleep(0.2)
            else:
                if attempt % 20 == 0:
                    print(f"[*] {remaining:.0f}s remaining, refreshing...")
                await self.page.reload(wait_until='domcontentloaded')
                await asyncio.sleep(1)
            
            attempt += 1
        
        print("\n[!!!] GO TIME! Sniping...")
        
        # Rapid booking loop
        for i in range(200):
            try:
                await self.page.reload(wait_until='commit')
                await asyncio.sleep(0.01)  # Minimal delay
                
                # Try to find reserve button
                reserve = await self.page.query_selector(
                    'button:has-text("예매하기"):not([disabled]), '
                    'a:has-text("예매하기")'
                )
                
                if reserve:
                    visible = await reserve.is_visible()
                    disabled = await reserve.get_attribute('disabled')
                    
                    if visible and not disabled:
                        print(f"[!!!] RESERVE BUTTON ACTIVE! Attempt {i}")
                        await self.hclick(reserve)
                        
                        # Wait for next page
                        await asyncio.sleep(0.5)
                        await self.page.screenshot(path="/tmp/tl_v3_sniped.png")
                        print("[+] Post-click screenshot: /tmp/tl_v3_sniped.png")
                        
                        # Auto-select
                        await self._auto_select_all()
                        return True
                
                # Check status change
                if i % 30 == 29:
                    body = await self.page.text_content('body') or ''
                    if '예매 오픈 전' not in body:
                        print(f"[*] Status text changed at attempt {i}")
                    
            except Exception as e:
                if i % 50 == 49:
                    print(f"[!] Error at {i}: {e}")
        
        print("[*] Max attempts reached")
        return False
    
    async def _auto_select_all(self):
        """Auto-select date/round and proceed"""
        print("[*] Auto-selecting options...")
        
        # Wait for page
        await asyncio.sleep(0.5)
        
        # Date selection
        date_selectors = [
            'button[class*="date"]:not([disabled])',
            'button[class*="day"]:not([disabled])', 
            'select[name*="date"] option',
            '[class*="calendar"] button:not([disabled])',
        ]
        for sel in date_selectors:
            try:
                btns = await self.page.query_selector_all(sel)
                if btns:
                    for btn in btns:
                        if await btn.is_visible():
                            print(f"[+] Selecting date: {sel}")
                            await self.hclick(btn)
                            await asyncio.sleep(0.2)
                            break
                    break
            except:
                continue
        
        # Round/time selection
        time_selectors = [
            'button[class*="time"]:not([disabled])',
            'button[class*="round"]:not([disabled])',
            'button[class*="session"]:not([disabled])',
        ]
        for sel in time_selectors:
            try:
                btns = await self.page.query_selector_all(sel)
                if btns:
                    for btn in btns:
                        if await btn.is_visible():
                            print(f"[+] Selecting time: {sel}")
                            await self.hclick(btn)
                            await asyncio.sleep(0.2)
                            break
                    break
            except:
                continue
        
        # Next/confirm
        next_texts = ['다음', '좌석선택', '선택완료', '결제하기']
        for text in next_texts:
            try:
                btn = await self.page.query_selector(
                    f'button:has-text("{text}"):not([disabled]), '
                    f'a:has-text("{text}")'
                )
                if btn and await btn.is_visible():
                    print(f"[+] Clicking: '{text}'")
                    await self.hclick(btn)
                    await asyncio.sleep(0.5)
                    break
            except:
                continue
        
        # Screenshot after auto-select
        await self.page.screenshot(path="/tmp/tl_v3_selected.png")
        print("[+] Post-selection screenshot: /tmp/tl_v3_selected.png")
    
    async def monitor_network(self, product_id=None):
        """Monitor network for API discovery"""
        pid = product_id or CONFIG['product_id']
        
        print(f"\n{'='*60}")
        print("[NETWORK] API Discovery Mode")
        print(f"{'='*60}")
        
        calls = []
        
        def log_request(request):
            url = request.url
            if any(k in url for k in ['api', 'oc.', 'auth', 'reserve', 'booking', 'seat', 'payco']):
                calls.append({
                    'method': request.method,
                    'url': url,
                    'type': request.resource_type,
                })
        
        self.page.on('request', log_request)
        
        await self.goto(f"{CONFIG['base_url']}/product/{pid}")
        await asyncio.sleep(3)
        
        # Try to trigger more API calls
        try:
            date_btn = await self.page.query_selector('[class*="date"] button, select[name*="date"]')
            if date_btn:
                await self.hclick(date_btn)
                await asyncio.sleep(0.5)
        except:
            pass
        
        print(f"\n[+] Captured {len(calls)} API calls:")
        seen = set()
        for c in calls:
            key = (c['method'], c['url'][:80])
            if key not in seen:
                seen.add(key)
                print(f"  {c['method']:6} [{c['type']}] {c['url'][:130]}")
        
        return calls
    
    async def close(self):
        if self.playwright:
            await self.playwright.stop()


# ============================================================
async def main():
    import argparse
    ap = argparse.ArgumentParser(description='Ticketlink Macro v3 - CDP Stealth')
    ap.add_argument('--product-id', default=CONFIG['product_id'])
    ap.add_argument('--mode', choices=['analyze', 'login', 'network', 'snipe'], default='analyze')
    ap.add_argument('--target-time', help='Snipe target: YYYY-MM-DD HH:MM:SS')
    args = ap.parse_args()
    
    macro = TLMacro()
    
    try:
        await macro.connect_cdp()
        
        if args.mode == 'analyze':
            await macro.analyze_product(args.product_id)
            await macro.analyze_login()
        elif args.mode == 'login':
            await macro.analyze_login()
        elif args.mode == 'network':
            await macro.monitor_network(args.product_id)
        elif args.mode == 'snipe':
            if not args.target_time:
                print("[!] --target-time required for snipe mode")
                sys.exit(1)
            await macro.sniper_mode(args.product_id, args.target_time)
    
    finally:
        print("\n[*] Done. Closing CDP connection...")
        await macro.close()

if __name__ == '__main__':
    asyncio.run(main())
