FROM python:3.11-slim

ENV PYTHONUNBUFFERED=TRUE

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && apt-get clean

WORKDIR /app

COPY . /app

RUN pip3 install --upgrade pip &&  pip3 install -r ./requirements.txt --no-cache-dir

CMD ["sh", "-c", "daphne -p $PORT -b 0.0.0.0 realtime.asgi:application"]
