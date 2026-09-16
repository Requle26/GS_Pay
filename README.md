# GS_Pay
경소페이

경북소프트웨어마이스터고등학교에서 사용하는 축제 포인트 환전 서비스입니다.

학생증에 내장되어있는 NFC태그를 사용합니다

## 개발 환경

```bash
# 가상환경 활성화
source .venv/bin/activate

# 서버 실행 (자동 새로고침)
uvicorn app.main:app --reload
```

브라우저에서 http://127.0.0.1:8000 을 열면 됩니다. API 문서는 http://127.0.0.1:8000/docs 에서 확인할 수 있습니다.
