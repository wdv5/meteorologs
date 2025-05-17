# Sistema de Gestión de Logs Meteorológicos
Un sistema distribuido para procesar y almacenar datos meteorológicos simulados usando RabbitMQ, PostgreSQL y Docker. Diseñado para garantizar persistencia, escalabilidad y manejo robusto de errores.

## Requisitos
- Docker
- Docker Compose
- Python 

  
## Características Principales
- Producer: Genera datos simulados de temperatura, humedad e irradianza en tiempo real.
- RabbitMQ: Broker de mensajería con colas durables y mensajes persistentes.
- Consumer: Procesa mensajes, valida datos y los almacena en PostgreSQL.
- PostgreSQL: Base de datos con esquema optimizado y restricciones de integridad.
- Docker Compose: Orquestación automática de contenedores con reinicios y volúmenes persistentes.

## Configuración
1. Clona el repositorio:
   ```bash
   git clone https://github.com/wdv5/meteorologs.git

Ejecución del sistema

Clonación del repositorio:
# Clonar repositorio
git clone https://github.com/wdv5/meteorologs.git
cd weather-system
Iniciar los contenedores:
docker-compose up --build

Verificación de servicios

PostgresSQL: conectarse vía psql
docker exec -it postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}
Consultar datos:
SELECT * FROM weather_logs LIMIT 10;
RabbitMQ:
- Acceder al dashboard: http://localhost:15672 (usuario: user, contraseña: password)
- Verificar cola: weather_queue

Pruebas de validación
Caso 1: Datos válidos
• El producer envía datos cada 1 segundo
• Verificar los logs del consumer
docker logs -f consumer
 Salida esperada:
Dato insertado: {'timestamp': '2025-05-17T04:21:09.957Z', 'temperatura': 2
2.5, 'humedad': 45.0}
Caso 2: Datos inválidos
• Simular un mensaje con temperatura = 150°C:
datos = {"timestamp": "2025-05-17T00:00:00Z", "temperatura": 150.0,
"humedad": 50.0}
Salida esperada en logs:
 Error de validación: Temperatura fuera de rango: 150.0

Pruebas de Recuperación de Fallos
1. Reinicio de PostgresSQl
docker restart postgres
El consumer debe reconectarse auticamente
2. Caída de RabbitMQ:
docker stop rabbitmq && docker start rabbitmq
El producer reintenta enviar mensajes
