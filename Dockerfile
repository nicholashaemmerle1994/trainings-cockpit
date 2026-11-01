FROM node:22-alpine AS web

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TC_DATA_DIR=/data \
    TC_WEB_DIST=/app/web/dist

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY --from=web /web/dist ./web/dist

RUN useradd --create-home --uid 1000 tc
USER tc

EXPOSE 8000

ENTRYPOINT ["tc"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
