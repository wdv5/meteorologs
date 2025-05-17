# Sistema de Gestión de Logs Meteorológicos

## Requisitos
- Docker
- Docker Compose
  
## Descripción de meteorologs
Producer: Envía datos simulados a RabbitMQ.

RabbitMQ: Broker con exchange weather_data y cola durable weather_queue.

Consumer: Procesa mensajes y persiste en PostgreSQL.

PostgreSQL: Almacena datos en la tabla weather_logs.

## Configuración
1. Clona el repositorio:
   ```bash
   git clone https://github.com/wdv5/meteorologs.git
