#!/bin/bash

# Директория для хранения сертификатов
CERT_DIR="./certs"
CERT_FILE="${CERT_DIR}/server.crt"
KEY_FILE="${CERT_DIR}/server.key"

# Проверяем, существуют ли сертификаты
if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo "Сертификаты уже существуют. Пропускаем генерацию."
    exit 0
fi

# Создаём директорию для сертификатов, если она не существует
mkdir -p "$CERT_DIR"

# Генерация самоподписанного сертификата с параметрами
echo "Генерация самоподписанного сертификата..."

openssl req -x509 -sha256 -nodes \
    -subj "/C=RU/ST=Moscow/L=Moscow/O=secret_chat/CN=localhost" \
    -newkey rsa:2048 \
    -days 365 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE"

echo "Сертификаты созданы и сохранены в директории $CERT_DIR."
