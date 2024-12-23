# Используем более стабильный образ python
FROM python:3.9-alpine

# Устанавливаем docker-compose через pip
RUN pip install docker-compose

# Копируем docker-compose.yml в контейнер
COPY docker-compose.yml /app/docker-compose.yml

WORKDIR /app

# Запускаем контейнеры с помощью docker-compose
CMD ["docker-compose", "up", "-d"]
