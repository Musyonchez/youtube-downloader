FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# requirements.lock (docs/16, 16-15) pins the full resolved dependency
# closure -- reproducible builds instead of "whatever's newest today" on
# every image rebuild. See requirements.lock's header for how to regenerate
# it after changing requirements.txt.
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
