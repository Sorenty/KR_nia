# Используем базовый образ docker:latest
FROM docker:latest

# Устанавливаем docker-compose через официальный скрипт
RUN curl -L https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose \
    && chmod +x /usr/local/bin/docker-compose

# Копируем docker-compose.yml в контейнер
COPY docker-compose.yml /app/docker-compose.yml

WORKDIR /app

# Запускаем контейнеры с помощью docker-compose
CMD ["docker-compose", "up", "-d"]
