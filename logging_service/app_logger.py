"""
Logger client para ser usado desde otros microservicios
Simplifica el envío de logs al Logging Service
"""

import httpx
import os
from datetime import datetime
from typing import Optional
import asyncio


class AppLogger:
    """Cliente para enviar logs al Logging Service"""

    def __init__(self, module: str, logging_service_url: Optional[str] = None):
        """
        Args:
            module: Nombre del módulo (POKE_STATS, POKE_API, POKE_IMAGES, SEARCH_API)
            logging_service_url: URL del servicio de logging (default: env variable)
        """
        self.module = module
        self.logging_service_url = logging_service_url or os.getenv(
            'LOGGING_SERVICE_URL', 'http://localhost:8004'
        )

    async def log(
        self,
        api: str,
        function: str,
        message: str,
        level: str = "INFO",
        latency_ms: Optional[float] = None,
        request_id: Optional[str] = None
    ):
        """
        Envía un log al servicio centralizado

        Args:
            api: Endpoint o API (GET_STATS, GET_POKEMON, etc.)
            function: Nombre de la función
            message: Mensaje del log
            level: INFO, WARNING, ERROR, DEBUG
            latency_ms: Latencia en milisegundos (opcional)
            request_id: ID de la solicitud (opcional)
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "module": self.module,
                    "api": api,
                    "function": function,
                    "message": message,
                    "level": level,
                    "latency_ms": latency_ms,
                    "request_id": request_id
                }

                response = await client.post(
                    f"{self.logging_service_url}/logs",
                    json=payload,
                    timeout=5.0
                )

                if response.status_code != 200:
                    print(f"Warning: Failed to send log. Status: {response.status_code}")

        except Exception as e:
            print(f"Error sending log: {e}")

    # Métodos de conveniencia
    async def info(self, api: str, function: str, message: str, latency_ms: Optional[float] = None):
        """Log de nivel INFO"""
        await self.log(api, function, message, "INFO", latency_ms)

    async def warning(self, api: str, function: str, message: str, latency_ms: Optional[float] = None):
        """Log de nivel WARNING"""
        await self.log(api, function, message, "WARNING", latency_ms)

    async def error(self, api: str, function: str, message: str, latency_ms: Optional[float] = None):
        """Log de nivel ERROR"""
        await self.log(api, function, message, "ERROR", latency_ms)

    async def debug(self, api: str, function: str, message: str, latency_ms: Optional[float] = None):
        """Log de nivel DEBUG"""
        await self.log(api, function, message, "DEBUG", latency_ms)


# Función auxiliar para logging síncrono (esperar el log sin bloquear)
def log_async(logger: AppLogger, api: str, function: str, message: str, level: str = "INFO", latency_ms: Optional[float] = None):
    """
    Envía un log sin bloquear la ejecución
    """
    try:
        asyncio.create_task(logger.log(api, function, message, level, latency_ms))
    except RuntimeError:
        # Si no hay event loop, crear uno nuevo
        asyncio.run(logger.log(api, function, message, level, latency_ms))
