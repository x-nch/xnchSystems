FROM python:3.13-slim

WORKDIR /app

COPY nexi/pyproject.toml /app/nexi/
COPY nexi/ /app/nexi/
COPY xnch/pyproject.toml /app/xnch/
COPY xnch/ /app/xnch/
COPY scraper/ /app/scraper/

RUN pip install --no-cache-dir -e /app/nexi -e /app/xnch

EXPOSE 8000

CMD ["uvicorn", "nexi.main:app", "--host", "0.0.0.0", "--port", "8000"]
