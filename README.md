Socionix bot - бот-тестирование по соционике.

Для оркестрования используется docker-compose

1. Перед тем как начинать работу, нужно создать домен, сертификаты https через certbot, и перенаправить на порт, указанный в nginx/Dockerfile
2. Сконфигурировать docker-compose.yaml: установить локальную папку для сохранения данных postgresql, адрес webhook, и token бота


