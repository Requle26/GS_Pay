# GS_Pay
경소페이

경북소프트웨어마이스터고등학교에서 사용하는 축제 포인트 환전 서비스입니다.

학생증에 내장되어있는 NFC태그를 사용합니다

로컬 환경 : uvicorn app.main:app --reload --env-file .env

## 개발 환경

```bash
# 가상환경 활성화
source .venv/bin/activate

# 서버 실행 (자동 새로고침)
uvicorn app.main:app --reload --env-file .env
```

브라우저에서 http://127.0.0.1:8000 을 열면 됩니다. API 문서는 http://127.0.0.1:8000/docs 에서 확인할 수 있습니다.

## 관리자 로그인 설정

1. `.env.example`을 참고해 `.env`에 `SUPABASE_PUBLISHABLE_KEY`를 추가합니다.
2. Supabase Authentication에서 관리자 이메일·비밀번호 계정을 만듭니다.
3. 해당 Auth 사용자 UUID와 같은 값을 `admins.id`에 저장하고, `status`를 `ACTIVE`로 설정합니다.

Vercel에는 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`를 환경 변수로 추가합니다. 운영 환경에서는 `COOKIE_SECURE=true`를 사용합니다.
