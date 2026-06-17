#!/usr/bin/env python3
"""
Ticketlink Auto-booking Macro — Self-contained Edition
========================================================
티켓링크(ticketlink.co.kr) 실서비스 예매 자동화

Features:
  - 자체 Chromium 엔진 내장 (Playwright) — 아무 환경에서 바로 실행
  - 모바일 에뮬레이션으로 EverSafe/NHN ACE 봇탐지 우회
  - 초고속 스나이퍼 모드 (정각 예매)
  - 취소표(취켓팅) 모니터링 모드
  - 페이지 구조 분석 모드

Usage:
  # 예매 스나이핑
  python ticketlink_macro.py --product-id 63681 --target-time "2026-06-17 20:00:00"

  # 취소표 모니터링
  python ticketlink_macro.py --mode cancel --product-id 63681

  # 페이지 분석
  python ticketlink_macro.py --mode analyze --product-id 63811
"""

import subprocess, sys, os, asyncio, random, json, time, argparse
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# AUTO-SETUP
# ============================================================
def ensure_playwright():
    """자동으로 playwright + chromium 설치"""
    try:
        from playwright.async_api import async_playwright
        return True
    except ImportError:
        print("[SETUP] Installing playwright...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "playwright"])
        print("[SETUP] Installing Chromium...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("[SETUP] Ready.")
        return True

ensure_playwright()
from playwright.async_api import async_playwright

# ============================================================
# CONFIG
# ============================================================
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
BASE_URL = "https://m.ticketlink.co.kr"  # 모바일이 에버세이프 우회됨
PC_URL = "https://www.ticketlink.co.kr"

# ============================================================
# STEALTH SCRIPTS (내장)
# ============================================================
STEALTH_JS = """
// webdriver kill
Object.defineProperty(navigator, 'webdriver', { get: () => false });
// fake plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => { const a = [1,2,3,4,5]; a.item=i=>a[i]; a.namedItem=()=>null; a.refresh=()=>{}; return a; }
});
// chrome runtime
window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };
// permissions
if (navigator.permissions) {
    const oq = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = p => p.name === 'notifications'
        ? Promise.resolve({ state: 'prompt', onchange: null })
        : oq(p);
}
// languages
Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR','ko','en-US','en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'iPhone' });
Object.defineProperty(navigator, 'vendor', { get: () => 'Apple Computer, Inc.' });
"""

# ============================================================
# MACRO CORE
# ============================================================
class Ticketlink:
    def __init__(self, headless=True, mobile=True):
        self.headless = headless
        self.mobile = mobile
        self.pw = None
        self.browser = None
        self.page = None
        self.target_dt = None

    # ---- Browser ----
    async def start(self):
        self.pw = await async_playwright().start()
        args = [
            '--no-sandbox', '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins',
        ]
        if self.headless:
            args.append('--headless=new')

        self.browser = await self.pw.chromium.launch(headless=self.headless, args=args)

        ctx_opts = {
            'locale': 'ko-KR',
            'timezone_id': 'Asia/Seoul',
        }
        if self.mobile:
            ctx_opts['viewport'] = {'width': 390, 'height': 844}
            ctx_opts['user_agent'] = MOBILE_UA

        ctx = await self.browser.new_context(**ctx_opts)
        self.page = await ctx.new_page()
        await self.page.add_init_script(STEALTH_JS)
        self.page.set_default_timeout(20000)
        self.base = BASE_URL if self.mobile else PC_URL
        print(f"[+] Browser ready (mobile={self.mobile}, headless={self.headless})")

    async def hdelay(self, lo=0.03, hi=0.12):
        await asyncio.sleep(random.uniform(lo, hi))

    async def hclick(self, el):
        try:
            box = await el.bounding_box()
            if box:
                x = box['x'] + random.uniform(2, max(2, box['width']-2))
                y = box['y'] + random.uniform(2, max(2, box['height']-2))
                await self.page.mouse.move(x, y, steps=random.randint(3, 8))
        except: pass
        await self.hdelay()
        try:
            await el.click(timeout=3000)
        except:
            await el.click(force=True, timeout=3000)

    # ---- Navigation ----
    async def goto(self, pid, wait_ms=3000):
        url = f"{self.base}/product/{pid}"
        resp = await self.page.goto(url, wait_until='commit', timeout=15000)
        if resp and resp.status == 200:
            await asyncio.sleep(wait_ms / 1000)
        return resp

    # ---- Sniper ----
    async def snipe(self, product_id, target_dt):
        print(f"\n{'█'*55}")
        print(f"█  SNIPER — {target_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"█  Product: {product_id}")
        print(f"{'█'*55}")

        # Pre-load
        await self.goto(product_id, wait_ms=2000)
        print("[*] Pre-loaded. Waiting...")

        # Wait loop
        attempt = 0
        while datetime.now() < target_dt:
            remain = (target_dt - datetime.now()).total_seconds()
            if remain < 3:
                await self.page.reload(wait_until='commit')
                await asyncio.sleep(0.03)
            elif remain < 15:
                print(f"\r[*] T-{remain:.1f}s | rapid poll...", end='')
                await self.page.reload(wait_until='commit')
                await asyncio.sleep(0.2)
            else:
                if attempt % 30 == 0:
                    m, s = divmod(int(remain), 60)
                    print(f"[*] {m}m {s}s remaining...")
                await self.page.reload(wait_until='commit')
                await asyncio.sleep(1.5)
            attempt += 1

        print("\n[!!!] GO TIME!")

        # Sniping loop
        for i in range(300):
            try:
                await self.page.reload(wait_until='commit')
                await asyncio.sleep(0.01)

                # 모바일: "예매하기" 버튼 또는 활성화된 "판매예정"→"예매하기" 변경 감지
                reserve = await self.page.query_selector(
                    'button:has-text("예매하기"):not([disabled]), '
                    'a:has-text("예매하기"), '
                    '.btn_primary:has-text("예매")'
                )
                if not reserve:
                    # plan_sale 버튼이 예매하기로 변경되었는지 확인
                    reserve = await self.page.query_selector('.btn_primary:not(.plan_sale)')

                if reserve:
                    visible = await reserve.is_visible()
                    disabled = await reserve.get_attribute('disabled')
                    if visible and not disabled:
                        text = (await reserve.text_content() or '').strip()
                        print(f"[!!!] '{text}' active! Attempt {i}")
                        await self.hclick(reserve)
                        await asyncio.sleep(0.5)
                        await self._auto_select()
                        await self.page.screenshot(path=f"/tmp/tl_sniped_{product_id}.png")
                        print(f"[+] Screenshot saved")
                        return True

                if i % 50 == 49:
                    body = await self.page.evaluate('() => document.body?.innerText || ""')
                    if '예매하기' in body:
                        print(f"[*] '예매하기' text found in body at attempt {i}")

            except Exception as e:
                if i % 100 == 99:
                    print(f"[!] Error at {i}: {e}")

        print("[*] Max attempts reached")
        return False

    async def _auto_select(self):
        """날짜/회차 자동 선택"""
        await asyncio.sleep(0.5)
        print("[*] Auto-selecting...")

        # 날짜
        for sel in ['button[class*="date"]:not([disabled])',
                     'button[class*="day"]:not([disabled])',
                     '[class*="calendar"] button:not([disabled])']:
            try:
                btns = await self.page.query_selector_all(sel)
                for b in btns:
                    if await b.is_visible():
                        print(f"[+] Date: {sel}")
                        await self.hclick(b)
                        await asyncio.sleep(0.2)
                        break
                break
            except: continue

        # 회차
        for sel in ['button[class*="time"]:not([disabled])',
                     'button[class*="round"]:not([disabled])',
                     'button[class*="session"]:not([disabled])']:
            try:
                btns = await self.page.query_selector_all(sel)
                for b in btns:
                    if await b.is_visible():
                        print(f"[+] Time: {sel}")
                        await self.hclick(b)
                        await asyncio.sleep(0.2)
                        break
                break
            except: continue

        # 다음
        for txt in ['다음', '좌석선택', '선택완료', '결제하기']:
            try:
                btn = await self.page.query_selector(
                    f'button:has-text("{txt}"):not([disabled]), a:has-text("{txt}")'
                )
                if btn and await btn.is_visible():
                    print(f"[+] '{txt}'")
                    await self.hclick(btn)
                    break
            except: continue

    # ---- Cancel snipe ----
    async def cancel_snipe(self, product_id, duration_sec=600):
        print(f"[*] Cancel-snipe: {product_id} for {duration_sec}s")
        await self.goto(product_id)
        end = time.time() + duration_sec
        i = 0
        while time.time() < end:
            await self.page.reload(wait_until='commit')
            await asyncio.sleep(0.3)
            reserve = await self.page.query_selector(
                'button:has-text("예매하기"):not([disabled]), '
                '.btn_primary:not(.plan_sale)'
            )
            if reserve and await reserve.is_visible():
                text = (await reserve.text_content() or '').strip()
                print(f"[!!!] Cancel ticket: '{text}'")
                await self.hclick(reserve)
                await self._auto_select()
                return True
            i += 1
            if i % 60 == 0:
                print(f"[*] Monitoring... {i} checks")
        return False

    # ---- Analyze ----
    async def analyze(self, product_id):
        print(f"\n{'='*55}")
        print(f"[ANALYZE] Product {product_id}")
        print(f"{'='*55}")
        await self.goto(product_id, wait_ms=5000)
        await self.page.screenshot(path=f"/tmp/tl_analyze_{product_id}.png", full_page=True)
        body = await self.page.evaluate('() => document.body?.innerText || ""')
        print(f"Body ({len(body)} chars):")
        print(body[:600])

        # 버튼들
        btns = await self.page.evaluate('''() => {
            const r = [];
            document.querySelectorAll('button, a, [class*=btn]').forEach(el => {
                const t = (el.textContent||'').trim().slice(0,60);
                if (t) r.push({tag:el.tagName, text:t, class:(el.className||'').slice(0,50),
                              disabled:el.disabled, visible:el.offsetParent!==null});
            });
            return r;
        }''')
        print(f"\n[{len(btns)}] elements:")
        for b in btns:
            m = ''
            if any(k in b['text'] for k in ['예매','판매','보안','날짜','회차','좌석','다음','결제']): m=' 🔥'
            print(f"  [{b['tag']}] \"{b['text']}\"{m} class=\"{b['class']}\" disabled={b['disabled']}")

    # ---- Cleanup ----
    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.pw:
            await self.pw.stop()


# ============================================================
# CLI
# ============================================================
async def main():
    ap = argparse.ArgumentParser(description='Ticketlink Auto-booking Macro — Self-contained Edition')
    ap.add_argument('--product-id', '-p', required=True, help='상품 ID (예: 63681)')
    ap.add_argument('--mode', '-m', choices=['snipe','cancel','analyze'], default='snipe',
                    help='snipe=정각예매, cancel=취소표, analyze=분석')
    ap.add_argument('--target-time', '-t', help='예매 오픈 시간 "YYYY-MM-DD HH:MM:SS" (KST)')
    ap.add_argument('--target-epoch', type=int, default=0, help='Unix epoch (UTC)')
    ap.add_argument('--headless', action='store_true', default=True)
    ap.add_argument('--no-headless', dest='headless', action='store_false')
    ap.add_argument('--mobile', action='store_true', default=True)
    ap.add_argument('--pc', dest='mobile', action='store_false')
    args = ap.parse_args()

    macro = Ticketlink(headless=args.headless, mobile=args.mobile)

    try:
        await macro.start()

        if args.mode == 'analyze':
            await macro.analyze(args.product_id)

        elif args.mode == 'cancel':
            await macro.cancel_snipe(args.product_id)

        elif args.mode == 'snipe':
            if args.target_epoch > 0:
                target_dt = datetime.fromtimestamp(args.target_epoch)
            elif args.target_time:
                target_dt = datetime.strptime(args.target_time, '%Y-%m-%d %H:%M:%S')
            else:
                print("[!] --target-time or --target-epoch required for snipe mode")
                sys.exit(1)

            result = await macro.snipe(args.product_id, target_dt)
            print(f"[{'SUCCESS' if result else 'FAILED'}]")

    finally:
        await asyncio.sleep(1)
        await macro.close()

if __name__ == '__main__':
    asyncio.run(main())
