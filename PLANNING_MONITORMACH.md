# 📋 PLANNING - MonitorMach: Arquitectura de Microservicios

**Proyecto:** MonitorMach - Sistema de monitoreo basado en microservicios  
**Fecha:** 27 de Mayo, 2026  
**Stack:** Python + FastAPI + PostgreSQL + Docker Compose  
**Responsable:** Coconut

---

## 🎯 Objetivo General

Diseñar e implementar una arquitectura basada en **microservicios** que permita:
- Búsqueda de Pokémon con estadísticas
- Logging distribuido con nomenclatura estándar
- Medición de latencia y disponibilidad
- Generación de métricas mediante tests de carga (JMeter: 1000-10000 llamadas)

---

## 📐 Arquitectura General

```
┌─────────────┐
│ Search API  │ (Puerto 8000)
└──────┬──────┘
       │
       ├─→ POKE API (Puerto 8001) → PokeAPI externa
       ├─→ POKE Stats (Puerto 8002) → PostgreSQL + CSV
       ├─→ POKE Images (Puerto 8003) → File Server/S3
       │
       └─→ Logging Microservice (Puerto 8004) → JSON logs por día
```

---

## 🔧 Microservicios a Implementar

### 1. **Search API** (Orquestador)
- **Puerto:** 8000
- **Responsabilidad:** Orquestar búsquedas, coordinar llamadas a otros microservicios
- **Endpoint:** `GET /poke/search?pokemon_name={name}`
- **Respuesta:** 
  ```json
  {
    "name": "string",
    "stats": [],
    "image": "url"
  }
  ```
- **Dependencias:** Llama a POKE API, POKE Stats, POKE Images
- **Logs:** Registra cada búsqueda

### 2. **POKE API** (Consumidor de API externa)
- **Puerto:** 8001
- **Responsabilidad:** Consumir PokeAPI (https://pokeapi.co/api/v2/pokemon/{id or name}/)
- **Endpoint:** `GET /pokemon/{name_or_id}`
- **Respuesta:** Datos crudos del Pokémon
- **Logs:** Registra latencia de llamadas externas

### 3. **POKE Stats** (Microservicio de datos)
- **Puerto:** 8002
- **Responsabilidad:** Consultar estadísticas desde PostgreSQL (basado en CSV)
- **Endpoint:** `GET /stats/{pokemon_name}`
- **Respuesta:** Stats del CSV (HP, Attack, Defense, Speed, etc.)
- **Base de datos:** PostgreSQL
  - Tabla: `pokemon_stats`
  - Columnas: `#, Name, Type1, Type2, Total, HP, Attack, Defense, Sp.Atk, Sp.Def, Speed, Generation, Legendary`
  - Datos: Importados del CSV adjunto
- **Logs:** Registra consultas a BD, tiempo de respuesta

### 4. **POKE Images** (Gestor de imágenes)
- **Puerto:** 8003
- **Responsabilidad:** Gestionar URLs de imágenes de Pokémon
- **Endpoint:** `GET /images/{pokemon_name}`
- **Respuesta:** URL de imagen
- **Storage:** File Server local o S3
- **Logs:** Registra accesos a imágenes

### 5. **Logging Microservice** (Centralizador de logs) ⭐ *NUEVO*
- **Puerto:** 8004
- **Responsabilidad:** Recibir, procesar y almacenar logs de todos los servicios
- **Endpoint:** `POST /logs` (recibe logs de otros servicios)
- **Storage:** Archivos JSON locales, un archivo por día
- **Formato de log:**
  ```json
  {
    "timestamp": "2026-05-27T14:30:45.123Z",
    "module": "POKE_STATS",
    "api": "GET_STATS",
    "function": "query_pokemon_by_name",
    "message": "Pokémon encontrado: Pikachu",
    "level": "INFO",
    "latency_ms": 45
  }
  ```
- **Nomenclatura de archivo:** `logs_YYYY-MM-DD.json`

---

## 📦 Estructura del Proyecto

```
monitormach/
├── docker-compose.yml
├── .env
├── README.md
│
├── search_api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── logger.py
│   └── tests/
│
├── poke_api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── logger.py
│   └── tests/
│
├── poke_stats/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── logger.py
│   │   ├── db.py (conexión a PostgreSQL)
│   │   └── models.py
│   ├── data/
│   │   └── Pokemon.csv
│   └── tests/
│
├── poke_images/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── logger.py
│   └── tests/
│
├── logging_service/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── log_manager.py
│   └── logs/
│       └── logs_YYYY-MM-DD.json
│
├── jmeter/
│   └── test_plan.jmx (1000-10000 llamadas)
│
└── database/
    └── init.sql (schema de PostgreSQL)
```

---

## 🚀 Fases de Implementación

### **FASE 0: Preparación y Setup Inicial** (1-2 días)
**Objetivo:** Preparar el ambiente y estructura base

**Deliverables:**
1. Crear estructura de carpetas del proyecto
2. Crear archivo `docker-compose.yml` con servicios base
3. Crear archivo `.env` con variables de entorno
4. Crear `Dockerfile` base para servicios Python
5. Crear `requirements.txt` compartido (FastAPI, psycopg2, requests, etc.)
6. Crear archivo `database/init.sql` para crear tabla `pokemon_stats`
7. Script para importar datos del CSV a PostgreSQL

**Consideraciones:**
- Variables de entorno: DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, etc.
- Networks en Docker Compose para comunicación entre servicios
- Volumes para persistencia de BD y logs

---

### **FASE 1: Implementar Microservicios Core** (3-5 días)

#### **1.1 - POKE Stats (Crítico)**
**Por qué primero:** Es el único que requiere BD y datos del CSV

**Deliverables:**
- [ ] Setup de PostgreSQL en Docker
- [ ] Migración de CSV a tabla PostgreSQL
- [ ] Conexión a BD desde FastAPI
- [ ] Endpoint `GET /stats/{pokemon_name}`
- [ ] Implementar logger local
- [ ] Tests unitarios
- [ ] Documentación OpenAPI (Swagger)

**Especificaciones técnicas:**
```python
# Tabla en PostgreSQL (solo columnas requeridas)
CREATE TABLE pokemon_stats (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE,
    hp INT,
    attack INT,
    defense INT,
    sp_atk INT,
    sp_def INT,
    speed INT
);
```

#### **1.2 - POKE API**
**Deliverables:**
- [ ] Endpoint `GET /pokemon/{name_or_id}`
- [ ] Integración con PokeAPI externa
- [ ] Manejo de errores (Pokémon no encontrado)
- [ ] Implementar logger
- [ ] Tests unitarios

#### **1.3 - POKE Images**
**Deliverables:**
- [ ] Endpoint `GET /images/{pokemon_name}`
- [ ] Lógica para obtener imágenes desde directorio local
- [ ] Estructura: `pokemon_images/{pokemon_name}/` (carpeta por Pokémon)
- [ ] Retornar lista de rutas de imágenes disponibles
- [ ] Implementar logger

#### **1.4 - Search API** (Orquestador)
**Deliverables:**
- [ ] Endpoint `GET /poke/search?pokemon_name={name}`
- [ ] Lógica para llamar a POKE API, POKE Stats, POKE Images en paralelo/secuencial
- [ ] Agregación de respuestas
- [ ] Implementar logger
- [ ] Tests de integración

---

### **FASE 2: Microservicio de Logging** (2-3 días)

**Objetivo:** Centralizar logging de todos los servicios

**Deliverables:**
- [ ] Crear servicio Logging en puerto 8004
- [ ] Endpoint `POST /logs` que reciba logs JSON
- [ ] Validación de estructura de logs
- [ ] Almacenamiento diario en archivos JSON (logs_YYYY-MM-DD.json)
- [ ] Lógica de rotación de archivos (cambio de día)
- [ ] Implementar cliente Logger en cada microservicio para enviar logs

**Especificaciones técnicas:**

Estructura de log que recibirá:
```json
{
  "timestamp": "ISO-8601",
  "module": "POKE_STATS|POKE_API|POKE_IMAGES|SEARCH_API",
  "api": "GET_STATS|GET_POKEMON|GET_IMAGES|GET_SEARCH",
  "function": "nombre_función",
  "message": "descripción",
  "level": "INFO|WARNING|ERROR|DEBUG",
  "latency_ms": 123,
  "request_id": "uuid"
}
```

Archivo generado:
```
logging_service/logs/logs_2026-05-27.json
[
  { log1 },
  { log2 },
  ...
]
```

**Integración:**
- Cada microservicio tendrá cliente que envía logs a `http://logging_service:8004/logs`

---

### **FASE 3: Configuración Docker Compose** (1-2 días)

**Deliverables:**
- [ ] `docker-compose.yml` completo con todos los servicios
- [ ] Servicio PostgreSQL con volumen persistente
- [ ] Servicios de Python con dependencias correctas
- [ ] Variables de entorno (.env)
- [ ] Network para comunicación interna
- [ ] Volúmenes para logs y datos
- [ ] Health checks para servicios
- [ ] Comando para inicializar BD automáticamente

**docker-compose.yml básico:**
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - monitormach_network

  poke_stats:
    build: ./poke_stats
    ports:
      - "8002:8000"
    environment:
      DB_HOST: postgres
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      DB_NAME: ${DB_NAME}
    depends_on:
      - postgres
      - logging_service
    networks:
      - monitormach_network

  poke_api:
    build: ./poke_api
    ports:
      - "8001:8000"
    depends_on:
      - logging_service
    networks:
      - monitormach_network

  poke_images:
    build: ./poke_images
    ports:
      - "8003:8000"
    depends_on:
      - logging_service
    networks:
      - monitormach_network

  search_api:
    build: ./search_api
    ports:
      - "8000:8000"
    depends_on:
      - poke_api
      - poke_stats
      - poke_images
      - logging_service
    networks:
      - monitormach_network

  logging_service:
    build: ./logging_service
    ports:
      - "8004:8000"
    volumes:
      - ./logging_service/logs:/app/logs
    networks:
      - monitormach_network

volumes:
  postgres_data:

networks:
  monitormach_network:
    driver: bridge
```

---

### **FASE 4: Tests de Carga con JMeter** (2-3 días)

**Objetivo:** Generar carga y métricas de latencia/disponibilidad

**Deliverables:**
- [ ] Plan de test JMeter (test_plan.jmx)
- [ ] Configurar Thread Group: 1000-10000 llamadas
- [ ] Endpoints a testear:
  - `GET /poke/search?pokemon_name=pikachu`
  - `GET /stats/pikachu`
  - `GET /pokemon/pikachu`
  - `GET /images/pikachu`
- [ ] Metrics de JMeter:
  - Response Time (promedio, min, max, percentiles p95, p99)
  - Throughput (req/sec)
  - Error Rate
  - Availability
- [ ] Generar reportes HTML
- [ ] Almacenar logs de tests en `logs_TEST_YYYY-MM-DD.json`

**Especificaciones técnicas:**

- **Thread Group:** Ramp-up time, Hold-time, Number of threads configurables
- **Sampler:** HTTP Request a cada endpoint
- **Listeners:** View Results Tree, Summary Report, Response Time Graph
- **Assertions:** HTTP Response codes (200)
- **Parametrización:** Nombres de Pokémon del CSV

---

### **FASE 5: Verificación e Integración** (1-2 días)

**Deliverables:**
- [ ] Verificar comunicación entre servicios
- [ ] Validar estructura de logs generados
- [ ] Crear script para ejecutar todo (`./run.sh`)
- [ ] Crear script para detener servicios (`./stop.sh`)
- [ ] Documentación README con instrucciones
- [ ] Verificar que JMeter genere logs correctamente
- [ ] Realizar test de carga inicial
- [ ] Análisis de latencia y disponibilidad

**Comandos esperados:**
```bash
# Iniciar
docker-compose up -d

# Ver logs en vivo
docker-compose logs -f

# Detener
docker-compose down

# Ejecutar JMeter
jmeter -n -t jmeter/test_plan.jmx -l results.jtl
```

---

## 📊 Formato de Logs (Especificaciones Finales)

**Nomenclatura estándar:**
```
{Fecha}{Modulo}{API}{Funcion} Message
```

**Ejemplo:**
```
2026-05-27 14:30:45.123 | POKE_STATS | GET_STATS | query_pokemon_by_name | Pokémon encontrado: Pikachu | latency: 45ms
```

**Archivo JSON (logs_YYYY-MM-DD.json):**
```json
[
  {
    "timestamp": "2026-05-27T14:30:45.123Z",
    "date": "2026-05-27",
    "module": "POKE_STATS",
    "api": "GET_STATS",
    "function": "query_pokemon_by_name",
    "message": "Pokémon encontrado: Pikachu",
    "level": "INFO",
    "latency_ms": 45,
    "request_id": "abc-123-def"
  }
]
```

---

## 🔄 Comunicación entre Servicios

**Protocolo:** HTTP REST  
**Tipo:** Síncrono  
**Puertos internos:** Cada servicio en puerto 8000 (dentro del contenedor)

**Ejemplo de flujo:**
```
1. Cliente → Search API (8000): GET /poke/search?pokemon_name=pikachu
2. Search API → POKE API (8001): GET /pokemon/pikachu
3. Search API → POKE Stats (8002): GET /stats/pikachu
4. Search API → POKE Images (8003): GET /images/pikachu
5. Cada servicio → Logging Service (8004): POST /logs
6. Search API → Cliente: { name, stats, image }
```

---

## 📋 Checklist de Implementación

- [ ] **FASE 0:** Setup inicial (docker-compose.yml, .env, estructura)
- [ ] **FASE 1.1:** POKE Stats (BD + endpoint)
- [ ] **FASE 1.2:** POKE API (PokeAPI externa)
- [ ] **FASE 1.3:** POKE Images (gestión de imágenes)
- [ ] **FASE 1.4:** Search API (orquestador)
- [ ] **FASE 2:** Logging Service (centralización de logs)
- [ ] **FASE 3:** Docker Compose (integración total)
- [ ] **FASE 4:** JMeter Tests (1000-10000 llamadas)
- [ ] **FASE 5:** Verificación e integración

---

## ⚠️ Dudas/Decisiones Pendientes

1. ¿Existen nombres específicos de Pokémon para testear? (usar del CSV)
2. ¿Timeout máximo entre servicios? (por definir)
3. ¿Almacenamiento de imágenes: File Server local o URL externa?
4. ¿Formato exacto de respuesta en Search API cuando falte un dato?
5. ¿Reintentos automáticos si una llamada falla?

---

## 📞 Próximos Pasos

1. **Confirmar este planning**
2. **Iniciar FASE 0:** Crear estructura base
3. **Cualquier ajuste al planning** será notificado

---

**Última actualización:** 27 de Mayo, 2026
