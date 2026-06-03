# MonitorMach - Arquitectura de Microservicios

Sistema de monitoreo basado en microservicios que implementa búsqueda de Pokémon con logging distribuido, medición de latencia y pruebas de carga.

## Arquitectura

```
┌─────────────────┐
│   Search API    │ (8000)
└────────┬────────┘
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│ POKE   │ │ POKE   │ │ POKE   │ │ Logging  │
│  API   │ │ Stats  │ │ Images │ │ Service  │
│(8001)  │ │(8002)  │ │(8003)  │ │ (8004)   │
└────────┘ └───┬────┘ └────────┘ └──────────┘
               │
         ┌─────▼─────┐
         │PostgreSQL │
         │ (5432)    │
         └───────────┘
```

**Response de `/poke/search`:**
```json
{
  "name": "pikachu",
  "stats": [
    {"name": "hp", "value": 35},
    {"name": "attack", "value": 55},
    {"name": "defense", "value": 40},
    {"name": "sp_atk", "value": 50},
    {"name": "sp_def", "value": 50},
    {"name": "speed", "value": 90}
  ],
  "images": "http://localhost:8003/static/pikachu/0.jpg"
}
```

## Ejecución rápida

```bash
# 1. Iniciar servicios
docker-compose up -d

# 2. Inicializar base de datos (primera vez)
bash init_db.sh

# 3. Prueba rápida
curl "http://localhost:8000/poke/search?pokemon_name=pikachu"

# Detener
docker-compose down
```

## API Endpoints

| Servicio | Puerto | Endpoints principales |
|---|---|---|
| Search API | 8000 | `GET /poke/search?pokemon_name=` · `GET /poke/status` |
| Poke API | 8001 | `GET /pokemon/{name}` · `GET /pokemon/{name}/raw` |
| Poke Stats | 8002 | `GET /stats/{name}` · `GET /stats?limit=N` |
| Poke Images | 8003 | `GET /images/{name}` · `GET /images` |
| Logging | 8004 | `GET /logs/today` · `GET /logs/module/{MOD}` · `GET /logs/date/{YYYY-MM-DD}` |

## Bot CLI

El bot consulta los logs generados por los microservicios y presenta métricas de latencia, disponibilidad y rendimiento directamente en consola.

```bash
cd app/bot
python bot.py <comando> [opciones]
```

### Flags globales

| Flag | Descripción |
|---|---|
| `--logs-dir <ruta>` | Lee los archivos JSON de logs directamente (recomendado, evita problemas de zona horaria) |
| `--mock` | Genera datos sintéticos para demo sin necesidad de servicios activos |

### Módulos válidos

`PokeStats` · `PokeAPI` · `PokeImage` · `SearchAPI`

---

### CheckLatency

Muestra la latencia promedio de un módulo día a día, más el promedio total y P95.

```bash
# Rango de días
python bot.py --logs-dir ../logs CheckLatency PokeStats -Last5Days

# Rango de fechas específico
python bot.py --logs-dir ../logs CheckLatency PokeImage -01/10 -03/10
```

**Salida de ejemplo:**
```
  [CheckLatency] POKE_IMAGES
  ----------------------------------------
  01/10   503 ms  (n=71)
  02/10   529 ms  (n=60)
  03/10   513 ms  (n=110)

  Promedio total : 514 ms
  P95            : 755 ms
```

---

### CheckAvailability

Muestra la disponibilidad diaria de un módulo.

```
Disponibilidad = Exitos / (Exitos + Errores) x 100
```
- Éxito = log con level `INFO`
- Error = log con level `ERROR`

```bash
python bot.py --logs-dir ../logs CheckAvailability PokeStats -Last5Days
```

**Salida de ejemplo:**
```
  [CheckAvailability] POKE_STATS
  ----------------------------------------
  01/10   99.9%  (500 ok / 0 err)
  02/10   89.9%  (440 ok / 49 err)
  03/10   94.2%  (480 ok / 29 err)

  Disponibilidad total : 94.6%
```

---

### RenderGraph

Renderiza un gráfico ASCII de líneas con la tendencia de latencia o disponibilidad.

```bash
# Latencia de todos los módulos
python bot.py --logs-dir ../logs RenderGraph -Latency -Last3Days

# Disponibilidad de un módulo específico
python bot.py --logs-dir ../logs RenderGraph -Availability -Last7Days PokeStats
```

**Salida de ejemplo:**
```
  [RenderGraph] Latencia - Ultimos 3 dias

  Latencia - POKE_API

    1192ms |             **1192ms**
    1179ms | **1179ms**
    1154ms |                         **1154ms**
           +------------------------------------
               01/10       02/10       03/10
```

---

### Stats

Muestra métricas generales del sistema e incluye análisis automático de bottleneck, puntos de retry y recomendación de escalado.

```bash
# Todos los módulos, último día
python bot.py --logs-dir ../logs Stats

# Módulo específico, últimos 3 días
python bot.py --logs-dir ../logs Stats PokeAPI -Last3Days
```

**Métricas reportadas:**
- Total requests · Requests/minuto · Throughput (req/s)
- Error ratio · Latencia promedio · P95 latencia
- Top failing endpoint
- Latencia y error rate por módulo

**Análisis automático:**
- **Bottleneck**: módulo con mayor P95 y causa probable
- **Retry recomendado**: módulos con error ratio > 2%
- **¿Debe escalar?**: basado en req/min, P95 y error ratio

**Salida de ejemplo:**
```
  [Stats] Stats | TODOS | Ultimos 1 dia(s)

  Total requests                   7143
  Requests / minuto                58.27
  Throughput                       0.97 req/s
  Error ratio                      0.0%
  Latencia promedio                3441 ms
  P95 latencia                     10822 ms
  Top failing endpoint             ninguno

  Latencia por modulo:
    POKE_API        avg=  555ms  p95=  565ms  errors=0.0%
    POKE_IMAGES     avg=   35ms  p95=   80ms  errors=0.0%
    POKE_STATS      avg=   19ms  p95=   39ms  errors=0.0%
    SEARCH_API      avg=10448ms  p95=12154ms  errors=0.0%

  [Bottleneck] SEARCH_API
    P95 = 12154 ms — orquestacion sincronica de 3 servicios en paralelo

  [Retry recomendado]
    * Ninguno — error ratio < 2% en todos los modulos

  [Debe escalar?]
    * Si — 58.3 req/min > umbral 50 / P95 10822 ms > 3000 ms
```

## Tests de integración

```bash
pip install pytest requests
pytest tests/test_services.py -v
```

Cubre los 5 objetivos del proyecto: arquitectura, logging distribuido, medición de latencia, métricas desde logs y configuración de prueba de carga.

## Tests de carga (JMeter)

```bash
cd jmeter

# 1000 llamadas (mínimo)
jmeter -n -t test_plan.jmx -JTHREAD_COUNT=10 -JLOOP_COUNT=100 -l results.jtl -e -o report/

# 10000 llamadas (máximo)
jmeter -n -t test_plan.jmx -JTHREAD_COUNT=100 -JLOOP_COUNT=100 -l results.jtl -e -o report/

# Generar reporte HTML desde resultados existentes
jmeter -g results.jtl -o report/
```

Resultados: `jmeter/results.jtl` · Reporte HTML: `jmeter/report/index.html`

## Logging distribuido

Archivos JSON diarios en `app/logs/logs_YYYY-MM-DD.json`.

**Formato estándar:** `{Timestamp}{Modulo}{API}{Funcion} Message`

```json
{
  "timestamp": "2026-06-03T00:26:11Z",
  "date": "2026-06-03",
  "module": "POKE_STATS",
  "api": "GET_STATS",
  "function": "get_pokemon_stats",
  "message": "Pokemon encontrado: pikachu",
  "level": "INFO",
  "latency_ms": 18.4,
  "request_id": "bcc83971"
}
```

---

**MonitorMach v2.0** | Actualizado: Junio 2026
