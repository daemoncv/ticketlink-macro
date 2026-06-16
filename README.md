# Ticketlink Macro

티켓링크(ticketlink.co.kr) 실서비스 예매 자동화 매크로.  
CDP Stealth Chromium 기반으로 EverSafe(에버세이프) 및 NHN ACE 봇탐지 우회.

## Features

- **스나이퍼 모드**: 지정 시간 정각에 초고속 예매 시도 (최대 300회/초 폴링)
- **취소표 모드**: 취소표(취켓팅) 발생 시 자동 예매
- **분석 모드**: 상품 페이지 구조, 로그인 플로우, API 엔드포인트 분석
- **CDP 기반**: 실제 Chromium 브라우저에 연결하여 탐지 우회

## Architecture

```
ticketlink.co.kr (Frontend)
    ├── mapi.ticketlink.co.kr (API Server) — 암호화된 쿼리 파라미터 사용
    ├── oc.ticketlink.co.kr (Order/Checkout)
    ├── id.payco.com (PAYCO OAuth 로그인)
    └── EverSafe (에버스핀) + NHN ACE 봇탐지
```

## Setup

```bash
# 1. Stealth Chromium 실행 (CDP on port 9222)
./start_stealth_chromium.sh

# 2. Python venv
python3 -m venv venv && source venv/bin/activate
pip install playwright && python -m playwright install chromium

# 3. 환경변수
export TL_PRODUCT_ID=63681       # 상품 ID
export TL_TARGET_EPOCH=1781694000 # 타겟 시간 (Unix epoch)
export TL_MODE=snipe              # snipe | cancel | analyze
```

## Usage

```bash
# 스나이퍼 모드 (정각 예매)
TL_PRODUCT_ID=63681 TL_TARGET_EPOCH=1781694000 python ticketlink_sniper.py

# 취소표 모니터링
TL_MODE=cancel TL_PRODUCT_ID=63681 python ticketlink_sniper.py

# 분석 모드
python ticketlink_macro_v3.py --mode analyze --product-id 63681

# 네트워크 API 분석
python ticketlink_macro_v3.py --mode network --product-id 63681
```

## Security Bypass

- **EverSafe**: CDP 연결 + 실제 브라우저 프로필 + extension 기반 stealth
- **NHN ACE**: `navigator.webdriver` 패치, `chrome.runtime` 위조, WebGL 스푸핑
- **API 암호화**: 브라우저 컨텍스트 내에서만 유효한 토큰 → API 직접 호출 불가, 브라우저 자동화만 가능

## License

MIT
