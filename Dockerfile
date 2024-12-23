FROM docker:latest

# Устанавливаем docker-compose
RUN apk add --no-cache python3 py3-pip && \
    pip3 install docker-compose

# Копируем docker-compose.yml в контейнер
COPY docker-compose.yml /app/docker-compose.yml

WORKDIR /app

CMD ["docker-compose", "up", "-d"]