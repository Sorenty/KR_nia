name: Build and Deploy Docker image

on:
  push:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      # Шаг 1: Клонируем репозиторий
      - name: Checkout repository
        uses: actions/checkout@v2

      # Шаг 2: Устанавливаем Docker (если требуется, Docker обычно уже есть на ubuntu-latest)
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      # Шаг 3: Логинимся в Docker Hub
      - name: Log in to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      # Шаг 4: Собираем Docker образ
      - name: Build Docker image
        run: docker build -t sorenty/order-managment-backend:latest ./backend

      # Шаг 5: Пушим образ в Docker Hub
      - name: Push Docker image to Docker Hub
        run: docker push sorenty/order-managment-backend:latest

      # Шаг 6: (Опционально) Деплой или другие действия с контейнером
      - name: Deploy or test with Docker image
        run: |
          # Ваши действия с контейнером
          docker run sorenty/order-managment-backend:latest
