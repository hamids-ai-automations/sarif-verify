FROM python:3.12-slim

LABEL org.opencontainers.image.title="sarif-verify" \
      org.opencontainers.image.description="Validate SARIF 2.1.0 logs before GitHub code scanning uploads them." \
      org.opencontainers.image.source="https://github.com/hamids-ai-automations/sarif-verify" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY fixtures ./fixtures

RUN pip install --no-cache-dir .

# Self-test at build time: the bundled clean log must validate, and the demo
# must exit 1. A broken image never reaches a user.
RUN sarif-verify check fixtures/good.sarif \
 && (python -m sarif_verify.demo; test $? -eq 1)

WORKDIR /work

# ENTRYPOINT so `docker run image check /work/log.sarif` works as expected;
# the default command validates the bundled clean fixture.
ENTRYPOINT ["sarif-verify"]
CMD ["check", "/app/fixtures/good.sarif"]
