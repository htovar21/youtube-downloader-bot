# YouTube Downloader Bot para Telegram

## Descripción
Bot para descargar videos y audios de YouTube enviando un enlace.

## Cómo desplegar

1. Crear un bot en Telegram con BotFather y obtener el TOKEN.
2. Subir el proyecto a un repositorio GitHub.
3. Crear cuenta en Railway o Render.
4. Conectar el repo y desplegar.
5. En variables de entorno agregar `TOKEN=tu_token_aqui`.
6. Ejecutar.

## Limitaciones
- Telegram limita archivos enviados a 50 MB para bots.
- Solo acepta enlaces válidos de YouTube.

## Dependencias
- python-telegram-bot
- pytube
- validators
