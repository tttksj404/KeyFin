# syntax=docker/dockerfile:1
# FDT AI Coaching service — CPU-only (no GPU). Build context = ai/coaching/.
# Serves FastAPI (coaching_service) + FDT engine (numpy). LLM은 외부 엔드포인트로만 호출.

# ── Build stage: hatchling wheel(자체 포함: coaching_service + fdt + 매니페스트 + 차트에셋) ──
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /build
COPY . .
RUN uv build --wheel --out-dir /dist

# ── Runtime stage ──
FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PYTHONUNBUFFERED=1 \
    COACHING_DATABASE=/data/coaching.sqlite3
WORKDIR /app
COPY --from=builder /dist/*.whl /tmp/
# 휠 + 런타임 의존성(fastapi·uvicorn·numpy·httpx2·websockets 등) 설치
RUN uv pip install --system --no-cache /tmp/*.whl && rm -f /tmp/*.whl
# 비루트 + 쓰기 가능한 상태 디렉터리(SQLite)
RUN useradd -m -u 10001 app && mkdir -p /data && chown -R app:app /data
USER app
VOLUME ["/data"]
EXPOSE 8000
# /healthz는 공개(무인증). 컨테이너 헬스체크.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3).status==200 else 1)"
# from_environment()가 COACHING_* 환경변수를 읽어 앱을 구성. COACHING_CLIENTS 없으면 기동 실패(fail-closed).
CMD ["uvicorn", "coaching_service.api:from_environment", "--factory", "--host", "0.0.0.0", "--port", "8000"]
