"""
Logging Microservice
Centraliza los logs de todos los microservicios en archivos JSON locales (uno por día)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import json
import os
from pathlib import Path
import uuid
import logging
import sys

# ==================== Logging Configuration ====================
# Configurar logging de Python para ver errores en stdout
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Logging Service", version="1.0.0")

# Configuration
LOGS_DIR = os.getenv('LOGS_DIR', '/app/logs')
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)

logger.info(f"Logs directory: {LOGS_DIR}")
logger.info(f"Logs directory exists: {os.path.exists(LOGS_DIR)}")
logger.info(f"Logs directory writable: {os.access(LOGS_DIR, os.W_OK)}")


# ==================== Models ====================
class LogEntry(BaseModel):
    """Estructura de un log entry"""
    timestamp: Optional[str] = None  # ISO-8601
    module: str  # POKE_STATS, POKE_API, POKE_IMAGES, SEARCH_API
    api: str  # GET_STATS, GET_POKEMON, GET_IMAGES, GET_SEARCH, etc.
    function: str  # nombre de la función
    message: str
    level: str = "INFO"  # INFO, WARNING, ERROR, DEBUG
    latency_ms: Optional[float] = None
    request_id: Optional[str] = None


class LogResponse(BaseModel):
    """Respuesta al guardar un log"""
    success: bool
    message: str
    log_id: str
    date: str


# ==================== Helper Functions ====================
def get_current_date():
    """Obtiene la fecha actual en formato YYYY-MM-DD"""
    return date.today().strftime('%Y-%m-%d')


def get_logs_file_path(date_str: str = None):
    """Obtiene la ruta del archivo de logs para una fecha específica"""
    if date_str is None:
        date_str = get_current_date()
    return os.path.join(LOGS_DIR, f'logs_{date_str}.json')


def load_logs_for_date(date_str: str = None):
    """Carga los logs existentes para una fecha"""
    if date_str is None:
        date_str = get_current_date()

    file_path = get_logs_file_path(date_str)

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading logs: {e}")
            return []
    return []


def save_logs_for_date(logs: list, date_str: str = None):
    """Guarda los logs en el archivo correspondiente"""
    if date_str is None:
        date_str = get_current_date()

    file_path = get_logs_file_path(date_str)

    try:
        # Crear directorio si no existe
        os.makedirs(LOGS_DIR, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

        logger.info(f"Logs saved to {file_path} ({len(logs)} entries)")

    except IOError as e:
        logger.error(f"Error writing logs to {file_path}: {e}")
        raise Exception(f"Error writing logs: {e}")


def format_log_entry(log_data: LogEntry):
    """Formatea un log entry para almacenamiento"""
    now = datetime.utcnow().isoformat() + 'Z'
    request_id = str(uuid.uuid4())[:8]

    return {
        "timestamp": log_data.timestamp or now,
        "date": get_current_date(),
        "module": log_data.module,
        "api": log_data.api,
        "function": log_data.function,
        "message": log_data.message,
        "level": log_data.level,
        "latency_ms": log_data.latency_ms,
        "request_id": log_data.request_id or request_id
    }


# ==================== Endpoints ====================
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "logging_service",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "logs_directory": LOGS_DIR,
        "directory_writable": os.access(LOGS_DIR, os.W_OK)
    }


@app.post("/logs", response_model=LogResponse, tags=["Logs"])
async def create_log(log: LogEntry):
    """
    Crea un nuevo entry de log y lo guarda en el archivo del día

    Nomenclatura estándar: {Fecha}{Modulo}{API}{Funcion} Message

    Estructura JSON:
    {
        "timestamp": "ISO-8601",
        "module": "POKE_STATS",
        "api": "GET_STATS",
        "function": "query_pokemon_by_name",
        "message": "Pokémon encontrado",
        "level": "INFO",
        "latency_ms": 45
    }
    """
    try:
        current_date = get_current_date()

        # Validar campos requeridos
        if not log.module or not log.api or not log.function or not log.message:
            logger.warning(f"Missing required fields in log")
            raise HTTPException(
                status_code=400,
                detail="Fields 'module', 'api', 'function', and 'message' are required"
            )

        # Formatear el log
        formatted_log = format_log_entry(log)

        # Cargar logs existentes
        logs = load_logs_for_date(current_date)

        # Agregar nuevo log
        logs.append(formatted_log)

        # Guardar logs
        save_logs_for_date(logs, current_date)

        logger.info(f"Log created: {log.module}.{log.api}.{log.function}")

        return LogResponse(
            success=True,
            message="Log saved successfully",
            log_id=formatted_log['request_id'],
            date=current_date
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating log: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs/date/{date_str}", tags=["Logs"])
async def get_logs_by_date(date_str: str):
    """
    Obtiene todos los logs de una fecha específica (formato: YYYY-MM-DD)

    Ejemplo: GET /logs/date/2026-05-27
    """
    try:
        # Validar formato de fecha
        datetime.strptime(date_str, '%Y-%m-%d')

        logs = load_logs_for_date(date_str)

        return {
            "date": date_str,
            "count": len(logs),
            "logs": logs
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error retrieving logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs/today", tags=["Logs"])
async def get_logs_today():
    """Obtiene todos los logs del día actual"""
    try:
        current_date = get_current_date()
        logs = load_logs_for_date(current_date)

        logger.info(f"Retrieved {len(logs)} logs for today ({current_date})")

        return {
            "date": current_date,
            "count": len(logs),
            "logs": logs
        }

    except Exception as e:
        logger.error(f"Error retrieving logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs/latest/{limit}", tags=["Logs"])
async def get_latest_logs(limit: int = 100):
    """Obtiene los últimos N logs del día actual"""
    try:
        if limit <= 0:
            raise HTTPException(status_code=400, detail="Limit must be > 0")

        current_date = get_current_date()
        logs = load_logs_for_date(current_date)

        return {
            "date": current_date,
            "limit_requested": limit,
            "count": len(logs[-limit:]),
            "logs": logs[-limit:]
        }

    except Exception as e:
        logger.error(f"Error retrieving logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs/module/{module}", tags=["Logs"])
async def get_logs_by_module(module: str):
    """Obtiene todos los logs de un módulo específico del día actual"""
    try:
        current_date = get_current_date()
        logs = load_logs_for_date(current_date)

        filtered_logs = [log for log in logs if log['module'] == module.upper()]

        logger.info(f"Retrieved {len(filtered_logs)} logs for module {module}")

        return {
            "date": current_date,
            "module": module.upper(),
            "count": len(filtered_logs),
            "logs": filtered_logs
        }

    except Exception as e:
        logger.error(f"Error retrieving logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Evento ejecutado al iniciar la aplicación"""
    logger.info("=== Logging Service Started ===")
    logger.info(f"Logs directory: {LOGS_DIR}")
    logger.info(f"Directory exists: {os.path.exists(LOGS_DIR)}")
    logger.info(f"Directory writable: {os.access(LOGS_DIR, os.W_OK)}")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
