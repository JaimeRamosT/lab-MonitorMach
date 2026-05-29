# Checklist de Deployment - MonitorMach

## ✅ Verificación de Estructura

- [x] Archivo `.env` - Variables de entorno
- [x] `docker-compose.yml` - Orquestación
- [x] `Dockerfile` - Base para servicios
- [x] `requirements.txt` - Dependencias compartidas
- [x] `database/init.sql` - Script de BD
- [x] `database/import_csv.py` - Importador de datos
- [x] `database/Pokemon.csv` - Datos de Pokemon

## ✅ Microservicios Implementados

### Logging Service
- [x] `logging_service/Dockerfile`
- [x] `logging_service/requirements.txt`
- [x] `logging_service/main.py`
- [x] `logging_service/app_logger.py`
- [x] Directorio `logging_service/logs/`

### POKE API Service
- [x] `poke_api/Dockerfile`
- [x] `poke_api/requirements.txt`
- [x] `poke_api/main.py`

### POKE Stats Service
- [x] `poke_stats/Dockerfile`
- [x] `poke_stats/requirements.txt`
- [x] `poke_stats/main.py`

### POKE Images Service
- [x] `poke_images/Dockerfile`
- [x] `poke_images/requirements.txt`
- [x] `poke_images/main.py`
- [x] Directorios de ejemplo en `poke_images/images/`

### Search API Service (Orquestador)
- [x] `search_api/Dockerfile`
- [x] `search_api/requirements.txt`
- [x] `search_api/main.py`

## ✅ Testing y Herramientas

- [x] `jmeter/test_plan.jmx` - Plan de tests (1000-10000 llamadas)
- [x] `run.sh` - Script de ejecución
- [x] `setup_images.sh` - Script de setup de directorios
- [x] `README.md` - Documentación

## 🚀 Pasos para Iniciar

### 1. Verificar Requisitos
```bash
docker --version
docker-compose --version
```

### 2. Iniciar Servicios
```bash
./run.sh up
# O
docker-compose up -d
```

### 3. Esperar Setup (2-3 minutos)
```bash
docker-compose ps
```

### 4. Pruebas Básicas
```bash
# Búsqueda
curl "http://localhost:8000/poke/search?pokemon_name=pikachu"

# Estado
curl "http://localhost:8000/poke/status"

# Logs
curl "http://localhost:8004/logs/today"
```

### 5. Tests de Carga (JMeter)
```bash
cd jmeter
jmeter -n -t test_plan.jmx -l results.jtl -j jmeter.log
```

## 📊 Puertos en Uso

| Servicio | Puerto | Dirección |
|----------|--------|-----------|
| Search API | 8000 | http://localhost:8000 |
| POKE API | 8001 | http://localhost:8001 |
| POKE Stats | 8002 | http://localhost:8002 |
| POKE Images | 8003 | http://localhost:8003 |
| Logging Service | 8004 | http://localhost:8004 |
| PostgreSQL | 5432 | localhost:5432 |

## 🔧 Configuración Importante

### Base de Datos
- Usuario: `postgres`
- Contraseña: `monitormach_pass_2026`
- Base de datos: `monitormach_db`
- Tabla: `pokemon_stats` (HP, Attack, Defense, Sp.Atk, Sp.Def, Speed)

### Logging
- Formato: JSON
- Archivos: `logging_service/logs/logs_YYYY-MM-DD.json`
- Nomenclatura: `{Fecha}{Modulo}{API}{Funcion} Message`

### Imágenes
- Estructura: `poke_images/images/{pokemon_name}/`
- Extensiones: `.jpg`, `.png`, `.gif`, `.webp`

## 🧪 Tests de Carga

- **Herramienta**: JMeter
- **Rango**: 1,000 - 10,000 llamadas
- **Configuración**: `jmeter/test_plan.jmx`
- **Variables**:
  - THREAD_COUNT: 100 (default)
  - LOOP_COUNT: 100 (default)
  - Total: 10,000

## 📝 Notas

1. Los logs se generan automáticamente en JSON
2. La BD se inicializa automáticamente al iniciar
3. Los datos del CSV se pueden importar manualmente si es necesario
4. Todos los servicios tienen health checks
5. Los servicios se comunican por HTTP REST (síncronamente)

## 🆘 Troubleshooting

```bash
# Ver logs de un servicio
docker-compose logs -f [service_name]

# Reiniciar un servicio
docker-compose restart [service_name]

# Limpiar todo
docker-compose down -v

# Reconstruir imágenes
docker-compose up -d --build
```

---

**Estado**: ✅ LISTO PARA DEPLOYMENT
**Fecha**: 27 de Mayo, 2026
**Versión**: 1.0
