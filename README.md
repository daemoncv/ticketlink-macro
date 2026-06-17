# Ticketlink Macro

티켓링크(ticketlink.co.kr) 실서비스 예매 자동화 매크로 — 원클릭 실행.

## 특징

- **자체 Chromium 엔진 내장** — Python + `pip install playwright`만 있으면 바로 실행
- **모바일 에뮬레이션** — m.ticketlink.co.kr 사용, EverSafe(에버세이프) / NHN ACE 봇탐지 우회
- **초고속 스나이퍼** — 정각 예매, T-3초부터 서브초 폴링 (최대 300회)
- **취소표 모니터링** — 취켓팅 자동 감지
- **분석 모드** — 페이지 구조/API 분석

## 설치

```bash
pip install playwright
playwright install chromium
```

또는 그냥 실행 (자동 설치):

```bash
python ticketlink_macro.py --mode analyze --product-id 63811
```

## 사용법

```bash
# 예매 스나이핑 (정각 예매)
python ticketlink_macro.py -p 63681 -t "2026-06-17 20:00:00"

# Unix epoch 사용
python ticketlink_macro.py -p 63681 --target-epoch 1781694000

# 취소표 모니터링 (10분)
python ticketlink_macro.py -m cancel -p 63681

# 페이지 분석
python ticketlink_macro.py -m analyze -p 63811

# PC 버전 사용 (기본값은 모바일)
python ticketlink_macro.py -p 63681 -t "..." --pc

# 디버깅 (headful)
python ticketlink_macro.py -p 63811 -m analyze --no-headless
```

## 우회 기술

| 방어 체계 | 우회 방법 |
|-----------|----------|
| EverSafe (에버스핀) | 모바일 에뮬레이션 + 실제 WebKit UA |
| NHN ACE (aceat.js) | navigator.webdriver 패치, chrome.runtime 위조, permissions 스푸핑 |
| 클린예매 CAPTCHA | 수동 입력 필요 (보안문자) |
| API 암호화 (mapi) | 브라우저 컨텍스트 내 실행으로 우회 |

## 실제 예매 플로우

```
1. 공연 페이지 로드 → "판매예정" → 오픈 시 "예매하기"로 변경
2. 클린예매 인증 (보안문자 입력)
3. 날짜/회차 선택
4. 좌석 선택
5. 할인/결제 수단 선택
6. 결제 완료
```

## License

MIT
