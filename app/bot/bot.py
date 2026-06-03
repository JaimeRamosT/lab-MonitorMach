#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MonitorMach Bot CLI
===================
Consulta los logs del logging_service y presenta metricas de latencia,
disponibilidad y rendimiento por modulo.

Uso:
  python bot.py CheckLatency   <Modulo> -<DD/MM> -<DD/MM>
  python bot.py CheckLatency   <Modulo> -LastXDays
  python bot.py CheckAvailability <Modulo> -LastXDays
  python bot.py RenderGraph    -Latency|-Availability -LastXDays [Modulo]
  python bot.py Stats          [<Modulo>] [-LastXDays]

Modulos validos: PokeStats | PokeAPI | PokeImage | SearchAPI
Flag especial:   --mock  (usa datos sinteticos, no requiere servicios activos)

Ejemplos:
  python bot.py CheckAvailability PokeStats -Last5Days
  python bot.py CheckLatency PokeImage -01/10 -03/10
  python bot.py RenderGraph -Latency -Last3Days
  python bot.py Stats
  python bot.py --mock Stats -Last3Days
"""

import sys
import re
import math
import statistics
import random as _random
import urllib.request
import urllib.error
import json
from datetime import date, datetime, timedelta
from collections import defaultdict
from typing import Optional, List

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LOGGING_URL = "http://localhost:8004"
MOCK_MODE   = "--mock" in sys.argv

# --logs-dir <path>: lee archivos JSON directamente desde el filesystem
# Evita problemas de zona horaria entre el contenedor (UTC) y el host local.
_logs_dir_arg = next(
    (sys.argv[i + 1] for i, a in enumerate(sys.argv)
     if a == "--logs-dir" and i + 1 < len(sys.argv)),
    None
)
LOGS_DIR_LOCAL = _logs_dir_arg  # None = usar API

MODULE_MAP = {
    "pokestats":  "POKE_STATS",
    "pokeapi":    "POKE_API",
    "pokeimage":  "POKE_IMAGES",
    "pokeimages": "POKE_IMAGES",
    "searchapi":  "SEARCH_API",
}

COLORS = {
    "header": "\033[1;34m",
    "ok":     "\033[0;32m",
    "warn":   "\033[0;33m",
    "err":    "\033[0;31m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}

def c(key: str, text: str) -> str:
    return COLORS[key] + str(text) + COLORS["reset"]


# ---------------------------------------------------------------------------
# Mock data (used when --mock flag is present)
# ---------------------------------------------------------------------------

def _mock_logs(module: str, d: date) -> list:
    """Synthetic logs for demo / testing without live services."""
    _random.seed(int(d.strftime("%Y%m%d")) + hash(module) % 1000)
    n = _random.randint(40, 120)
    base_lat = {"POKE_STATS": 300, "POKE_API": 1200, "POKE_IMAGES": 500, "SEARCH_API": 800}.get(module, 400)
    apis = {"POKE_STATS": "GET_STATS", "POKE_API": "GET_POKEMON",
            "POKE_IMAGES": "GET_IMAGES", "SEARCH_API": "GET_SEARCH"}
    logs = []
    for i in range(n):
        is_error = _random.random() < 0.05
        lat = max(1, round(_random.gauss(base_lat, base_lat * 0.3)))
        logs.append({
            "timestamp": "{}T{:02d}:{:02d}:{:02d}Z".format(
                d.isoformat(), _random.randint(0, 23),
                _random.randint(0, 59), _random.randint(0, 59)),
            "date": d.isoformat(),
            "module": module,
            "api": apis.get(module, "GET_UNKNOWN"),
            "function": "handler",
            "message": "error" if is_error else "ok",
            "level": "ERROR" if is_error else "INFO",
            "latency_ms": lat,
            "request_id": "mock-{:04d}".format(i),
        })
    return logs


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

def _fetch(path: str) -> dict:
    url = LOGGING_URL + path
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 400:
            return {"logs": [], "count": 0}
        raise
    except Exception as e:
        print(c("err", "  Error al conectar con el logging service ({}): {}".format(url, e)))
        print(c("warn", "  Tip: usa --mock para datos sinteticos sin servicios activos."))
        sys.exit(1)


def _logs_from_file(d: date) -> list:
    """Lee el archivo de logs local para una fecha dada.
    Busca tanto por fecha exacta como en todos los archivos disponibles
    filtrando por el campo 'date' interno."""
    import glob as _glob
    import os

    # Intento 1: archivo con nombre exacto logs_YYYY-MM-DD.json
    exact = os.path.join(LOGS_DIR_LOCAL, "logs_{}.json".format(d.strftime("%Y-%m-%d")))
    if os.path.exists(exact):
        try:
            with open(exact, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    # Intento 2: buscar en todos los archivos del directorio
    # filtrando por el campo 'date' del log (maneja diferencias de TZ)
    date_str = d.strftime("%Y-%m-%d")
    all_logs = []
    for filepath in _glob.glob(os.path.join(LOGS_DIR_LOCAL, "logs_*.json")):
        try:
            with open(filepath, encoding="utf-8") as f:
                entries = json.load(f)
            all_logs.extend(e for e in entries if e.get("date") == date_str)
        except Exception:
            continue
    return all_logs


def _all_local_logs() -> list:
    """Carga todos los archivos de log disponibles en LOGS_DIR_LOCAL."""
    import glob as _glob
    import os
    all_logs = []
    for filepath in sorted(_glob.glob(os.path.join(LOGS_DIR_LOCAL, "logs_*.json"))):
        try:
            with open(filepath, encoding="utf-8") as f:
                all_logs.extend(json.load(f))
        except Exception:
            continue
    return all_logs


def logs_for_date(d: date) -> list:
    if MOCK_MODE:
        all_logs = []
        for mod in set(MODULE_MAP.values()):
            all_logs.extend(_mock_logs(mod, d))
        return all_logs
    if LOGS_DIR_LOCAL:
        return _logs_from_file(d)
    return _fetch("/logs/date/{}".format(d.strftime("%Y-%m-%d"))).get("logs", [])


def logs_for_module_date(module: str, d: date) -> list:
    if MOCK_MODE:
        return _mock_logs(module, d)
    return [l for l in logs_for_date(d) if l.get("module") == module]


# ---------------------------------------------------------------------------
# Argument helpers
# ---------------------------------------------------------------------------

def resolve_module(raw: str) -> str:
    key = raw.lower().replace("-", "").replace("_", "")
    if key not in MODULE_MAP:
        print(c("err", "  Modulo desconocido: '{}'".format(raw)))
        print("  Validos: " + ", ".join(MODULE_MAP.keys()))
        sys.exit(1)
    return MODULE_MAP[key]


def parse_last_x_days(arg: str) -> Optional[int]:
    m = re.match(r"-[Ll]ast(\d+)[Dd]ays?$", arg)
    return int(m.group(1)) if m else None


def parse_dd_mm(arg: str) -> Optional[date]:
    m = re.match(r"-(\d{1,2})[/\-](\d{1,2})$", arg)
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    try:
        return date(date.today().year, month, day)
    except ValueError:
        return None


def date_range(start: date, end: date) -> list:
    days, cur = [], start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def last_n_days(n: int) -> list:
    today = date.today()
    return [today - timedelta(days=i) for i in range(n - 1, -1, -1)]


def fmt_date(d: date) -> str:
    return d.strftime("%d/%m")


# ---------------------------------------------------------------------------
# Metric calculations
# ---------------------------------------------------------------------------

def latencies_for(module: str, d: date) -> list:
    return [l["latency_ms"] for l in logs_for_module_date(module, d)
            if l.get("latency_ms") is not None]


def avg_latency(lats: list) -> Optional[float]:
    return round(statistics.mean(lats), 1) if lats else None


def p95(values: list) -> Optional[float]:
    if not values:
        return None
    sv = sorted(values)
    idx = max(0, math.ceil(0.95 * len(sv)) - 1)
    return round(sv[idx], 1)


def availability_for(module: str, d: date) -> Optional[float]:
    logs = logs_for_module_date(module, d)
    if not logs:
        return None
    success = sum(1 for l in logs if l.get("level") == "INFO")
    error   = sum(1 for l in logs if l.get("level") == "ERROR")
    total = success + error
    return round(success / total * 100, 1) if total else None


# ---------------------------------------------------------------------------
# ASCII line chart
# ---------------------------------------------------------------------------

def render_line_chart(days: list, values: list, label: str, unit: str = ""):
    valid = [(d, v) for d, v in zip(days, values) if v is not None]
    if not valid:
        print(c("warn", "  No hay datos para graficar."))
        return

    chart_dates, chart_vals = zip(*valid)
    min_v  = min(chart_vals)
    max_v  = max(chart_vals)
    rows   = 10
    col_w  = 12

    def row_for(v):
        if max_v == min_v:
            return rows // 2
        return round((max_v - v) / (max_v - min_v) * (rows - 1))

    print()
    print(c("bold", "  " + label))
    print()

    grid = [[" " * col_w for _ in range(len(chart_dates))] for _ in range(rows)]
    for ci, (d, v) in enumerate(zip(chart_dates, chart_vals)):
        ri = row_for(v)
        val_str = "**{}{}**".format(int(v), unit)
        grid[ri][ci] = val_str.center(col_w)

    for ri, row in enumerate(grid):
        y_val = max_v - (max_v - min_v) * ri / (rows - 1) if max_v != min_v else max_v
        y_label = "{:>6}{} |".format(int(y_val), unit)
        print("  " + y_label + "".join(row))

    print("  {:>8} +".format("") + "-" * (len(chart_dates) * col_w))
    date_row = "".join(fmt_date(d).center(col_w) for d in chart_dates)
    print("  {:>10}{}".format("", date_row))
    print()


# ---------------------------------------------------------------------------
# Command: CheckLatency
# ---------------------------------------------------------------------------

def cmd_check_latency(args: list):
    if len(args) < 2:
        print(c("err", "  Uso: CheckLatency <Modulo> -LastXDays  |  -DD/MM -DD/MM"))
        sys.exit(1)

    module = resolve_module(args[0])

    if len(args) == 2 and parse_last_x_days(args[1]) is not None:
        days = last_n_days(parse_last_x_days(args[1]))
    elif len(args) == 3:
        start, end = parse_dd_mm(args[1]), parse_dd_mm(args[2])
        if not start or not end:
            print(c("err", "  Formato de fecha invalido. Usa -DD/MM"))
            sys.exit(1)
        if start > end:
            start, end = end, start
        days = date_range(start, end)
    else:
        print(c("err", "  Uso: CheckLatency <Modulo> -LastXDays  |  -DD/MM -DD/MM"))
        sys.exit(1)

    print()
    print(c("header", "  [CheckLatency] " + module))
    print(c("header", "  " + "-" * 40))

    all_lats = []
    for d in days:
        lats = latencies_for(module, d)
        all_lats.extend(lats)
        avg  = avg_latency(lats)
        tag  = fmt_date(d)
        if avg is not None:
            color = "ok" if avg < 1000 else ("warn" if avg < 3000 else "err")
            print("  {}   {} ms  (n={})".format(tag, c(color, str(int(avg))), len(lats)))
        else:
            print("  {}   {}".format(tag, c("warn", "sin datos")))

    if all_lats:
        print()
        print("  Promedio total : " + c("bold", str(int(avg_latency(all_lats))) + " ms"))
        print("  P95            : " + c("bold", str(int(p95(all_lats))) + " ms"))
    print()


# ---------------------------------------------------------------------------
# Command: CheckAvailability
# ---------------------------------------------------------------------------

def cmd_check_availability(args: list):
    if len(args) < 2:
        print(c("err", "  Uso: CheckAvailability <Modulo> -LastXDays"))
        sys.exit(1)

    module = resolve_module(args[0])
    n = parse_last_x_days(args[1])
    if n is None:
        print(c("err", "  Formato invalido. Usa -LastXDays (ej: -Last5Days)"))
        sys.exit(1)

    days = last_n_days(n)

    print()
    print(c("header", "  [CheckAvailability] " + module))
    print(c("header", "  " + "-" * 40))
    print("  Disponibilidad = Exitos / (Exitos + Errores) x 100")
    print()

    all_success = all_error = 0
    for d in days:
        logs    = logs_for_module_date(module, d)
        success = sum(1 for l in logs if l.get("level") == "INFO")
        error   = sum(1 for l in logs if l.get("level") == "ERROR")
        total   = success + error
        all_success += success
        all_error   += error

        tag = fmt_date(d)
        if total == 0:
            print("  {}   {}".format(tag, c("warn", "sin datos")))
        else:
            avail = success / total * 100
            color = "ok" if avail >= 95 else ("warn" if avail >= 80 else "err")
            print("  {}   {}  ({} ok / {} err)".format(
                tag, c(color, "{:.1f}%".format(avail)), success, error))

    grand_total = all_success + all_error
    if grand_total > 0:
        grand = all_success / grand_total * 100
        color = "ok" if grand >= 95 else ("warn" if grand >= 80 else "err")
        print()
        print("  Disponibilidad total : " + c(color, "{:.1f}%".format(grand)))
    print()


# ---------------------------------------------------------------------------
# Command: RenderGraph
# ---------------------------------------------------------------------------

def cmd_render_graph(args: list):
    if len(args) < 2:
        print(c("err", "  Uso: RenderGraph -Latency|-Availability -LastXDays [Modulo]"))
        sys.exit(1)

    metric = args[0].lstrip("-").lower()
    if metric not in ("latency", "availability", "lat", "avail"):
        print(c("err", "  Metrica desconocida. Usa -Latency o -Availability"))
        sys.exit(1)
    is_latency = metric in ("latency", "lat")

    n = parse_last_x_days(args[1])
    if n is None:
        print(c("err", "  Formato invalido. Usa -LastXDays"))
        sys.exit(1)

    module = resolve_module(args[2]) if len(args) >= 3 else None
    days   = last_n_days(n)
    mods   = [module] if module else list(set(MODULE_MAP.values()))

    print()
    print(c("header", "  [RenderGraph] {} - Ultimos {} dias".format(
        "Latencia" if is_latency else "Disponibilidad", n)))

    for mod in sorted(mods):
        values = []
        for d in days:
            if is_latency:
                lats = latencies_for(mod, d)
                values.append(avg_latency(lats))
            else:
                values.append(availability_for(mod, d))
        unit  = "ms" if is_latency else "%"
        label = "{} - {}".format("Latencia" if is_latency else "Disponibilidad", mod)
        render_line_chart(days, values, label, unit)


# ---------------------------------------------------------------------------
# Command: Stats
# ---------------------------------------------------------------------------

def cmd_stats(args: list):
    module_filter = None
    n_days = 1

    for arg in args:
        x = parse_last_x_days(arg)
        if x is not None:
            n_days = x
        elif not arg.startswith("-"):
            module_filter = resolve_module(arg)

    days     = last_n_days(n_days)
    all_logs = []
    if LOGS_DIR_LOCAL and n_days >= 30:
        # Para ventanas grandes en modo local, carga todo de una vez
        all_logs = _all_local_logs()
    else:
        for d in days:
            all_logs.extend(logs_for_date(d))

    if module_filter:
        all_logs = [l for l in all_logs if l.get("module") == module_filter]

    if not all_logs:
        print(c("warn", "\n  No hay logs en el periodo solicitado.\n"))
        return

    title = "Stats | {} | Ultimos {} dia(s)".format(
        module_filter or "TODOS", n_days)
    print()
    print(c("header", "  [Stats] " + title))
    print(c("header", "  " + "-" * 50))

    latencies   = [l["latency_ms"] for l in all_logs if l.get("latency_ms") is not None]
    total_req   = len(all_logs)
    success_req = sum(1 for l in all_logs if l.get("level") == "INFO")
    error_req   = sum(1 for l in all_logs if l.get("level") == "ERROR")

    # Span in minutes
    timestamps = []
    for l in all_logs:
        try:
            timestamps.append(
                datetime.fromisoformat(l["timestamp"].replace("Z", "+00:00")))
        except Exception:
            pass
    span_min = max(1, (max(timestamps) - min(timestamps)).total_seconds() / 60) \
               if len(timestamps) >= 2 else 1

    req_per_min = round(total_req / span_min, 2)
    throughput  = round(total_req / max(1, span_min * 60), 4)
    error_ratio = round(error_req / total_req * 100, 2) if total_req else 0
    p95_lat     = p95(latencies)
    avg_lat     = avg_latency(latencies)

    # Top failing endpoint
    api_errors = defaultdict(int)
    api_totals = defaultdict(int)
    for l in all_logs:
        key = "{}.{}".format(l.get("module", "?"), l.get("api", "?"))
        api_totals[key] += 1
        if l.get("level") == "ERROR":
            api_errors[key] += 1

    top_fail     = max(api_errors, key=api_errors.get) if api_errors else "ninguno"
    top_fail_pct = round(api_errors[top_fail] / api_totals[top_fail] * 100, 1) \
                   if top_fail != "ninguno" else 0

    # Per-module breakdown
    mod_lats = defaultdict(list)
    mod_errs = defaultdict(int)
    mod_tots = defaultdict(int)
    for l in all_logs:
        mod = l.get("module", "?")
        if l.get("latency_ms") is not None:
            mod_lats[mod].append(l["latency_ms"])
        mod_tots[mod] += 1
        if l.get("level") == "ERROR":
            mod_errs[mod] += 1

    # Print general metrics
    print()
    W = 32
    print("  {:<{}} {}".format("Total requests", W, c("bold", str(total_req))))
    print("  {:<{}} {}".format("Requests / minuto", W, c("bold", str(req_per_min))))
    print("  {:<{}} {}".format("Throughput", W, c("bold", str(throughput) + " req/s")))
    print("  {:<{}} {}".format("Error ratio", W,
          c("err" if error_ratio > 5 else "ok", str(error_ratio) + "%")))
    print("  {:<{}} {}".format("Latencia promedio", W,
          c("bold", str(int(avg_lat)) + " ms") if avg_lat else "N/A"))
    print("  {:<{}} {}".format("P95 latencia", W,
          c("warn" if p95_lat and p95_lat > 2000 else "bold",
            str(int(p95_lat)) + " ms") if p95_lat else "N/A"))
    print("  {:<{}} {} ({:.1f}% error rate)".format(
          "Top failing endpoint", W, c("err", top_fail), top_fail_pct))

    # Per-module
    if not module_filter and mod_lats:
        print()
        print(c("header", "  Latencia por modulo:"))
        for mod in sorted(mod_lats):
            lats    = mod_lats[mod]
            err_pct = round(mod_errs[mod] / mod_tots[mod] * 100, 1) if mod_tots[mod] else 0
            color   = "err" if err_pct > 10 else ("warn" if err_pct > 2 else "ok")
            print("    {:<22} avg={:>5}ms  p95={:>5}ms  errors={}".format(
                mod, int(avg_latency(lats)), int(p95(lats)), c(color, str(err_pct) + "%")))

    # Analysis
    print()
    print(c("header", "  Analisis:"))

    # Bottleneck
    if mod_lats:
        bn_mod = max(mod_lats, key=lambda m: p95(mod_lats[m]) or 0)
        bn_p95 = int(p95(mod_lats[bn_mod]) or 0)
        reason = {
            "POKE_API":    "dependencia de red externa (pokeapi.co) — sin cache",
            "POKE_STATS":  "sin connection pooling en PostgreSQL",
            "POKE_IMAGES": "I/O en disco al listar archivos de imagen",
            "SEARCH_API":  "orquestacion sincronica de 3 servicios en paralelo",
        }.get(bn_mod, "carga alta")
        print()
        print("  [Bottleneck] " + c("err", bn_mod))
        print("    P95 = {} ms — {}".format(bn_p95, reason))

    # Retry
    retry_mods = [m for m in mod_errs
                  if mod_tots[m] and mod_errs[m] / mod_tots[m] > 0.02]
    print()
    print("  [Retry recomendado]")
    if retry_mods:
        for mod in retry_mods:
            pct = round(mod_errs[mod] / mod_tots[mod] * 100, 1)
            reason = "red externa inestable" if mod == "POKE_API" else "errores transitorios"
            print("    * {} ({:.1f}%) — {}".format(c("warn", mod), pct, reason))
    else:
        print("    * {} — error ratio < 2% en todos los modulos".format(
              c("ok", "Ninguno")))

    # Scale
    print()
    print("  [Debe escalar?]")
    scale_reasons = []
    if req_per_min > 50:
        scale_reasons.append("{:.1f} req/min > umbral 50".format(req_per_min))
    if p95_lat and p95_lat > 3000:
        scale_reasons.append("P95 {} ms > 3000 ms".format(int(p95_lat)))
    if error_ratio > 5:
        scale_reasons.append("error ratio {:.1f}% > 5%".format(error_ratio))
    if scale_reasons:
        print("    * " + c("warn", "Si") + " —")
        for r in scale_reasons:
            print("      - " + r)
    else:
        print("    * {} — carga y latencia dentro de rangos normales".format(
              c("ok", "No por ahora")))
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMANDS = {
    "checklatency":      cmd_check_latency,
    "checkavailability": cmd_check_availability,
    "rendergraph":       cmd_render_graph,
    "stats":             cmd_stats,
}

HELP = """
MonitorMach Bot CLI
===================

  CheckLatency   <Modulo> -LastXDays
  CheckLatency   <Modulo> -DD/MM -DD/MM
  CheckAvailability <Modulo> -LastXDays
  RenderGraph    -Latency|-Availability -LastXDays [Modulo]
  Stats          [Modulo] [-LastXDays]

Modulos: PokeStats | PokeAPI | PokeImage | SearchAPI

Opciones:
  --mock              Usa datos sinteticos (no requiere servicios activos)
  --logs-dir <path>   Lee archivos JSON directamente (evita problemas de TZ)
                      Ejemplo: --logs-dir ../logs

Ejemplos:
  python bot.py CheckAvailability PokeStats -Last5Days
  python bot.py CheckLatency PokeImage -01/10 -03/10
  python bot.py RenderGraph -Latency -Last3Days
  python bot.py RenderGraph -Availability -Last7Days PokeStats
  python bot.py Stats
  python bot.py Stats PokeAPI -Last3Days
  python bot.py --mock Stats -Last3Days
"""


def main():
    # Strip meta-flags before dispatching
    skip_next = False
    argv = []
    for a in sys.argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if a in ("--mock",):
            continue
        if a == "--logs-dir":
            skip_next = True
            continue
        argv.append(a)
    if not argv or argv[0].lower() in ("-h", "--help", "help"):
        print(HELP)
        return

    cmd_key = argv[0].lower()
    if cmd_key not in COMMANDS:
        print(c("err", "\n  Comando desconocido: '{}'".format(argv[0])))
        print(HELP)
        sys.exit(1)

    COMMANDS[cmd_key](argv[1:])


if __name__ == "__main__":
    main()
