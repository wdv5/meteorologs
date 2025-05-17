rabbitmqadmin -u user -p password declare queue name=weather_queue durable=true arguments='{"x-queue-mode":"lazy"}'
exit
