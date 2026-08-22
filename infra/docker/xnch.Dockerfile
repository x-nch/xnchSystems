FROM python:3.13-slim

WORKDIR /app

COPY xnch/ /app/xnch/
COPY xnch/pyproject.toml /app/
COPY xnch/uv.lock /app/
COPY xnch/litellm_config.yaml /app/litellm_config.yaml
COPY scraper/ /app/scraper/

RUN pip install --no-cache-dir -e /app

EXPOSE 8001

CMD ["uvicorn", "xnch.main:app", "--host", "0.0.0.0", "--port", "8001"]
