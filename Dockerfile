# Render's native Python buildpack runs the build as a non-root user, so
# `playwright install --with-deps` fails trying to `su` to root to apt-get
# install Chromium's system libraries (no root password available there).
# Docker RUN steps execute as root by default, so the same install works
# here with no privilege escalation needed at all.
FROM python:3.12-slim

WORKDIR /app

# Playwright's own installer detects the OS and pulls whatever system
# packages the exact Chromium revision (matching the pinned playwright pip
# version below) needs - no manual apt list to maintain here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN python -m playwright install --with-deps chromium

COPY . .

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
