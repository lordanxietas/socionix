FROM python:3.9

#Перемещаемся в папку


ADD requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

ADD . /app

WORKDIR /app
#Выставляем Timezone
ENV TZ Europe/Moscow

#Запуск самой программы
CMD ["bash", "/app/start.sh"]
