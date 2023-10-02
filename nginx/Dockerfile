FROM nginx:latest

EXPOSE 80
RUN mkdir /etc/nginx/sites-enabled/
RUN mkdir /etc/nginx/certs/
RUN mkdir /etc/nginx/certs/anxietas-facing.ru/
COPY nginx.conf /etc/nginx/sites-enabled/
COPY nginx.conf /etc/nginx/conf.d/
CMD ["nginx", "-g", "daemon off;"]