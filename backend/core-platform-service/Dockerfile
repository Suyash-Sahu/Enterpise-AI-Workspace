FROM python:3.13-slim

WORKDIR /app

# build-essential + libpq-dev: argon2-cffi/cryptography build from source when
# no prebuilt wheel matches this exact python:3.13-slim platform; psycopg2
# needs libpq to link against even though psycopg2-binary vendors most of it.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
