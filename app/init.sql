CREATE TABLE IF NOT EXISTS weather_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    temperatura DECIMAL(5,2) NOT NULL CHECK (temperatura BETWEEN -50 AND 60),
    humedad DECIMAL(5,2) NOT NULL CHECK (humedad BETWEEN 0 AND 100)
);