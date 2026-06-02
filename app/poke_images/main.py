"""
POKE Images Microservice
Gestiona acceso a imágenes de Pokemon desde directorio local
Estructura: images/{pokemon_name}/*.jpg|png
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import os
from pathlib import Path
from datetime import datetime
import time
import httpx
import logging
import sys

# Configurar logging
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

app = FastAPI(title="POKE Images Service", version="1.0.0")

# Configuration
IMAGES_DIR = os.getenv('IMAGES_DIR', '/app/images')
LOGGING_SERVICE_URL = os.getenv('LOGGING_SERVICE_URL', 'http://localhost:8004')

# Crear directorio de imágenes si no existe
Path(IMAGES_DIR).mkdir(parents=True, exist_ok=True)

# Servir imágenes estáticas
try:
    app.mount("/static", StaticFiles(directory=IMAGES_DIR), name="static")
except Exception as e:
    print(f"Warning: Could not mount static files: {e}")


# ==================== Models ====================
class ImageInfo(BaseModel):
    """Información de una imagen"""
    filename: str
    path: str
    pokemon_name: str


class ImagesResponse(BaseModel):
    """Respuesta con información de imágenes"""
    success: bool
    pokemon_name: str
    count: int
    images: List[ImageInfo] = []
    message: str


# ==================== Logging Helper ====================
async def send_log(api: str, function: str, message: str, level: str = "INFO", latency_ms: float = None):
    """Envía un log al servicio centralizado"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "module": "POKE_IMAGES",
                "api": api,
                "function": function,
                "message": message,
                "level": level,
                "latency_ms": latency_ms
            }
            response = await client.post(f"{LOGGING_SERVICE_URL}/logs", json=payload, timeout=5.0)

            if response.status_code == 200:
                logger.info(f"Log sent: {api}.{function}")
            else:
                logger.warning(f"Log send failed with status {response.status_code}")

    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to logging service: {e}")
    except httpx.TimeoutException as e:
        logger.error(f"Timeout sending log: {e}")
    except Exception as e:
        logger.error(f"Error sending log: {e}", exc_info=True)


# ==================== Helper Functions ====================
def get_images_for_pokemon(pokemon_name: str) -> List[ImageInfo]:
    """
    Obtiene la lista de imágenes para un Pokemon

    Estructura esperada: {IMAGES_DIR}/{pokemon_name}/*.jpg|png
    """
    pokemon_dir = os.path.join(IMAGES_DIR, pokemon_name.lower())

    if not os.path.exists(pokemon_dir):
        return []

    images = []
    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

    try:
        for filename in os.listdir(pokemon_dir):
            if os.path.isfile(os.path.join(pokemon_dir, filename)):
                ext = os.path.splitext(filename)[1].lower()
                if ext in valid_extensions:
                    image_path = f"/static/{pokemon_name.lower()}/{filename}"
                    images.append(
                        ImageInfo(
                            filename=filename,
                            path=image_path,
                            pokemon_name=pokemon_name
                        )
                    )
    except Exception as e:
        print(f"Error reading images for {pokemon_name}: {e}")

    return images


# ==================== Endpoints ====================
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "poke_images",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "images_directory": IMAGES_DIR,
        "directory_exists": os.path.exists(IMAGES_DIR)
    }


@app.get("/images/{pokemon_name}", response_model=ImagesResponse, tags=["Images"])
async def get_pokemon_images(pokemon_name: str):
    """
    Obtiene la lista de imágenes disponibles para un Pokemon

    La estructura esperada de directorios es:
    /app/images/{pokemon_name}/
    ├── image1.jpg
    ├── image2.png
    └── image3.jpg

    Ejemplo: GET /images/pikachu
    """
    start_time = time.time()

    try:
        images = get_images_for_pokemon(pokemon_name)
        latency_ms = (time.time() - start_time) * 1000

        if images:
            # Log éxito
            await send_log(
                api="GET_IMAGES",
                function="get_pokemon_images",
                message=f"Found {len(images)} images for {pokemon_name}",
                level="INFO",
                latency_ms=latency_ms
            )

            return ImagesResponse(
                success=True,
                pokemon_name=pokemon_name,
                count=len(images),
                images=images,
                message=f"Found {len(images)} image(s)"
            )
        else:
            # Log advertencia
            await send_log(
                api="GET_IMAGES",
                function="get_pokemon_images",
                message=f"No images found for {pokemon_name}",
                level="WARNING",
                latency_ms=latency_ms
            )

            return ImagesResponse(
                success=False,
                pokemon_name=pokemon_name,
                count=0,
                images=[],
                message=f"No images found for {pokemon_name}"
            )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        await send_log(
            api="GET_IMAGES",
            function="get_pokemon_images",
            message=f"Error retrieving images: {str(e)}",
            level="ERROR",
            latency_ms=latency_ms
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/images", response_model=dict, tags=["Images"])
async def list_all_pokemon_with_images():
    """
    Lista todos los Pokemon que tienen imágenes disponibles

    Ejemplo: GET /images
    """
    start_time = time.time()

    try:
        pokemon_dirs = []

        if os.path.exists(IMAGES_DIR):
            for item in os.listdir(IMAGES_DIR):
                item_path = os.path.join(IMAGES_DIR, item)
                if os.path.isdir(item_path):
                    # Verificar si hay imágenes en el directorio
                    images = get_images_for_pokemon(item)
                    if images:
                        pokemon_dirs.append({
                            "pokemon_name": item,
                            "image_count": len(images)
                        })

        latency_ms = (time.time() - start_time) * 1000

        await send_log(
            api="LIST_IMAGES",
            function="list_all_pokemon_with_images",
            message=f"Listed {len(pokemon_dirs)} Pokemon with images",
            level="INFO",
            latency_ms=latency_ms
        )

        return {
            "success": True,
            "count": len(pokemon_dirs),
            "pokemon": pokemon_dirs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/images/{pokemon_name}/verify", tags=["Images"])
async def verify_pokemon_directory(pokemon_name: str):
    """
    Verifica si existe un directorio para un Pokemon y crea si es necesario

    Útil para setup inicial del proyecto

    Ejemplo: POST /images/pikachu/verify
    """
    start_time = time.time()

    try:
        pokemon_dir = os.path.join(IMAGES_DIR, pokemon_name.lower())

        if not os.path.exists(pokemon_dir):
            os.makedirs(pokemon_dir, exist_ok=True)
            created = True
        else:
            created = False

        latency_ms = (time.time() - start_time) * 1000

        message = f"Directory created for {pokemon_name}" if created else f"Directory already exists for {pokemon_name}"

        await send_log(
            api="VERIFY_DIRECTORY",
            function="verify_pokemon_directory",
            message=message,
            level="INFO",
            latency_ms=latency_ms
        )

        return {
            "success": True,
            "pokemon_name": pokemon_name,
            "directory_path": pokemon_dir,
            "created": created,
            "message": message
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        await send_log(
            api="VERIFY_DIRECTORY",
            function="verify_pokemon_directory",
            message=f"Error verifying directory: {str(e)}",
            level="ERROR",
            latency_ms=latency_ms
        )
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
