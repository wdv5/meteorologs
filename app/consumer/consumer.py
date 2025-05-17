import json
import logging
import os
import time
from datetime import datetime

import pika
import psycopg2
from psycopg2 import OperationalError
from psycopg2.extensions import connection

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WeatherConsumer:
    def __init__(self):
        self.pg_conn = self._connect_postgres_with_retry()
        self.rabbit_conn = self._connect_rabbitmq_with_retry()
        self._setup_infrastructure()
        
    def _connect_postgres_with_retry(self, max_retries: int = 5, delay: int = 5) -> connection:
        """Establece conexión con PostgreSQL con sistema de reintentos"""
        for attempt in range(1, max_retries + 1):
            try:
                conn = psycopg2.connect(
                    dbname=os.getenv('POSTGRES_DB'),
                    user=os.getenv('POSTGRES_USER'),
                    password=os.getenv('POSTGRES_PASSWORD'),
                    host=os.getenv('POSTGRES_HOST'),
                    connect_timeout=10
                )
                logger.info("Conexión a PostgreSQL establecida exitosamente")
                return conn
            except OperationalError as e:
                logger.error(f"Intento {attempt}/{max_retries} fallido: {str(e)}")
                if attempt < max_retries:
                    time.sleep(delay)
        
        raise RuntimeError("No se pudo conectar a PostgreSQL después de varios intentos")

    def _connect_rabbitmq_with_retry(self, max_retries: int = 5, delay: int = 5) -> pika.BlockingConnection:
        """Establece conexión con RabbitMQ con sistema de reintentos"""
        credentials = pika.PlainCredentials(
            os.getenv('RABBITMQ_USER', 'user'),
            os.getenv('RABBITMQ_PASSWORD', 'password')
        )
        
        parameters = pika.ConnectionParameters(
            host=os.getenv('RABBITMQ_HOST', 'rabbitmq'),
            credentials=credentials,
            connection_attempts=max_retries,
            retry_delay=delay,
            socket_timeout=10
        )
        
        for attempt in range(1, max_retries + 1):
            try:
                conn = pika.BlockingConnection(parameters)
                logger.info("Conexión a RabbitMQ establecida exitosamente")
                return conn
            except pika.exceptions.AMQPConnectionError as e:
                logger.error(f"Intento {attempt}/{max_retries} fallido: {str(e)}")
                if attempt < max_retries:
                    time.sleep(delay)
        
        raise RuntimeError("No se pudo conectar a RabbitMQ después de varios intentos")

    def _setup_infrastructure(self):
        """Configura los elementos necesarios en RabbitMQ y PostgreSQL"""
        self._setup_rabbitmq()
        self._setup_postgres()

    def _setup_rabbitmq(self):
        """Configura exchange, cola y bindings en RabbitMQ"""
        self.channel = self.rabbit_conn.channel()
        
        # Exchange durable
        self.channel.exchange_declare(
            exchange='weather_data',
            exchange_type='direct',
            durable=True
        )
        
        # Cola durable con política Lazy
        self.channel.queue_declare(
            queue='weather_queue',
            durable=True,
            arguments={'x-queue-mode': 'lazy'}
        )
        
        self.channel.queue_bind(
            exchange='weather_data',
            queue='weather_queue',
            routing_key='raw_data'
        )
        
        # Configurar calidad de servicio
        self.channel.basic_qos(prefetch_count=1)

    def _setup_postgres(self):
        """Verifica y prepara la estructura de la base de datos"""
        with self.pg_conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weather_logs (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    temperature DECIMAL(5,2) NOT NULL CHECK (temperature BETWEEN -50 AND 60),
                    humidity DECIMAL(5,2) NOT NULL CHECK (humidity BETWEEN 0 AND 100),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_timestamp ON weather_logs(timestamp);
            """)
            self.pg_conn.commit()

    def _validate_message(self, data: dict) -> bool:
        """Valida la estructura y valores del mensaje recibido"""
        required_fields = {'timestamp', 'temperatura', 'humedad'} 
        
        # Validar campos obligatorios
        if not required_fields.issubset(data.keys()):
            missing = required_fields - data.keys()
            raise ValueError(f"Campos obligatorios faltantes: {', '.join(missing)}")
        
        # Validar tipos de datos
        if not isinstance(data['temperatura'], (int, float)):
            raise ValueError("Temperatura debe ser numérica")
            
        if not isinstance(data['humedad'], (int, float)):
            raise ValueError("Humedad debe ser numérica")
        
        # Validar rangos
        if not (-50 <= data['temperatura'] <= 60):
            raise ValueError(f"Temperatura fuera de rango: {data['temperature']}")
            
        if not (0 <= data['humedad'] <= 100):
            raise ValueError(f"Humedad fuera de rango: {data['humidity']}")
        
        # Validar formato de timestamp
        try:
            datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        except ValueError:
            raise ValueError("Formato de timestamp inválido, usar ISO 8601")
        
        return True

    def _process_message(self, ch: pika.channel.Channel, method: pika.spec.Basic.Deliver, properties: pika.spec.BasicProperties, body: bytes):
        """Procesa un mensaje recibido de RabbitMQ"""
        try:
            data = json.loads(body)
            self._validate_message(data)
            
            # Convertir timestamp
            timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            
            # Insertar en PostgreSQL
            with self.pg_conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO weather_logs 
                    (timestamp, temperatura, humedad)
                    VALUES (%s, %s, %s)
                """, (timestamp, data['temperatura'], data['humedad']))
                self.pg_conn.commit()
            
            logger.info(f"Dato insertado: {data}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error deserializando JSON: {str(e)} - Mensaje: {body.decode()}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
        except ValueError as e:
            logger.error(f"Error de validación: {str(e)} - Mensaje: {body.decode()}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
        except OperationalError as e:
            logger.critical(f"Error de base de datos: {str(e)}")
            self._reconnect_postgres()
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
        except Exception as e:
            logger.error(f"Error inesperado: {str(e)}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def _reconnect_postgres(self):
        """Reconexión a PostgreSQL con manejo de errores"""
        try:
            self.pg_conn.close()
        except Exception:
            pass
            
        self.pg_conn = self._connect_postgres_with_retry()
        self._setup_postgres()

    def start_consuming(self):
        """Inicia el consumo de mensajes de RabbitMQ"""
        self.channel.basic_consume(
            queue='weather_queue',
            on_message_callback=self._process_message,
            auto_ack=False
        )
        
        logger.info("Iniciando consumo de mensajes...")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.stop()
            
    def stop(self):
        """Detiene el consumer y cierra conexiones"""
        logger.info("Deteniendo consumer...")
        try:
            self.channel.close()
            self.rabbit_conn.close()
            self.pg_conn.close()
        except Exception as e:
            logger.error(f"Error al cerrar conexiones: {str(e)}")

if __name__ == "__main__":
    consumer = None
    try:
        consumer = WeatherConsumer()
        consumer.start_consuming()
    except Exception as e:
        logger.critical(f"Error crítico: {str(e)}")
        if consumer:
            consumer.stop()
        raise