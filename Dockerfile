FROM python:3.11-slim

ENV PYTHONUNBUFFERED=TRUE

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && apt-get clean

WORKDIR /app

COPY . /app

RUN pip3 install --upgrade pip &&  pip3 install -r ./requirements.txt --no-cache-dir

CMD ["sh", "-c", "daphne -e ssl:$PORT:privateKey=/app/certs/server.key:certKey=/app/certs/server.crt realtime.asgi:application"]
