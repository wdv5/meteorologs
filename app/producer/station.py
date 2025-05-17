import pika
import json
import random
import time
import os
from datetime import datetime, timezone

def connect_rabbitmq():
    """Establece conexión con RabbitMQ con credenciales y parámetros configurados"""
    credentials = pika.PlainCredentials(
        os.getenv('RABBITMQ_USER', 'user'),
        os.getenv('RABBITMQ_PASSWORD', 'password')
    )
    parameters = pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST', 'rabbitmq'),
        port=5672,
        credentials=credentials
    )
    return pika.BlockingConnection(parameters)

def generar_datos_en_tiempo_real():
    """Genera y publica datos meteorológicos simulados en tiempo real"""
    with connect_rabbitmq() as connection:
        channel = connection.channel()
        
        # Configurar exchange durable
        channel.exchange_declare(
            exchange='weather_data',
            exchange_type='direct',
            durable=True
        )
        
        # Valores iniciales
        temperatura = 20.0
        humedad = 50.0
        irradianza = 0.0

        # Variaciones máximas por ciclo
        delta_temp = 0.2
        delta_humedad = 1.5
        delta_irradianza = 15.0

        try:
            while True:
                # Calcular hora actual para simulación realista
                now = datetime.now(timezone.utc)
                hora = now.hour
                
                # Simulación mejorada de irradianza (base + variación)
                irradianza_base = max(0, 100 * (1 - abs(12 - hora)/6))  # Máximo al mediodía
                irradianza = irradianza_base + random.uniform(-delta_irradianza, delta_irradianza)
                
                # Actualizar valores con variaciones
                temperatura += random.uniform(-delta_temp, delta_temp)
                humedad += random.uniform(-delta_humedad, delta_humedad)
                
                # Aplicar límites físicos
                temperatura = min(max(temperatura, -10.0), 40.0)
                humedad = min(max(humedad, 0.0), 100.0)
                irradianza = max(irradianza, 0.0)

                # Construir payload
                datos = {
                    "timestamp": now.isoformat(),
                    "temperatura": round(temperatura, 2),    
                    "humedad": round(humedad, 2),           
                    "irradiance": round(irradianza, 2)       
                }

                # Publicar mensaje
                channel.basic_publish(
                    exchange='weather_data',
                    routing_key='raw_data',
                    body=json.dumps(datos),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Mensaje persistente
                        content_type='application/json',
                        timestamp=int(now.timestamp())
                    )
                )
                
                time.sleep(1)  # Intervalo de 1 segundo
                
        except KeyboardInterrupt:
            print("\nProducer detenido de forma segura")

if __name__ == "__main__":
    generar_datos_en_tiempo_real()