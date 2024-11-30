# Запуск проекта через Docker

## Предварительные требования
Для запуска проекта убедитесь, что у вас установлены:
- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Запуск проекта
1. Склонируйте репозиторий и перейдите в папку проекта:
   ```bash
   git clone https://github.com/bmstu-secret-chat/secret_chat-realtime.git && cd secret_chat-realtime/
   ```
   
2. Запустите проект с помощью Docker Compose:
   ```bash
   docker-compose up -d
   ```
   Команда запускает контейнеры в фоновом режиме.

## Обновление проекта
Если вы вносите изменения в код (например, обновляете зависимости или изменяете Dockerfile), выполните команду для пересборки контейнеров:
   ```bash
   docker-compose up -d --build
   ```
Эта команда пересобирает образы и перезапускает контейнеры.

## Остановка проекта
Чтобы остановить запущенные контейнеры, выполните:
   ```bash
   docker-compose down
   ```
