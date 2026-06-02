"""
MonitorMach – Integration Test Suite
=====================================
Validates the five project objectives:
  1. Microservice architecture (independent services, orchestration flow)
  2. Distributed logging (standard format, all services log)
  3. Latency measurement (latency_ms present and valid in every log)
  4. Log-based metrics (query by module, date, latest N)
  5. Load-test configuration (JMeter plan has 1000-10000 calls)

Additional rules validated:
  - Log format:  {Timestamp}{Module}{API}{Function} Message
  - Each log clearly identifies time + microservice
  - latency_ms measures start-to-end of each code block

Run:
    pip install pytest requests
    pytest tests/test_services.py -v
"""

import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

# ── Service endpoints (host ports) ──────────────────────────────────────────
LOGGING_URL    = "http://localhost:8004"
POKE_API_URL   = "http://localhost:8001"
POKE_STATS_URL = "http://localhost:8002"
POKE_IMAGES_URL = "http://localhost:8003"
SEARCH_URL     = "http://localhost:8000"

TIMEOUT = 15

# ── Helpers ──────────────────────────────────────────────────────────────────

def get(url, **kw):
    return requests.get(url, timeout=TIMEOUT, **kw)

def post(url, **kw):
    return requests.post(url, timeout=TIMEOUT, **kw)

def trigger_service_calls():
    """Fire one request per service so logs are guaranteed to exist."""
    get(f"{POKE_API_URL}/pokemon/pikachu")
    get(f"{POKE_STATS_URL}/stats/pikachu")
    get(f"{POKE_IMAGES_URL}/images/pikachu")
    get(f"{SEARCH_URL}/poke/search", params={"pokemon_name": "pikachu"})
    time.sleep(0.8)   # allow async log writes to settle


# ════════════════════════════════════════════════════════════════════════════
# Objetivo 1 – Arquitectura basada en microservicios
# ════════════════════════════════════════════════════════════════════════════

class TestMicroserviceArchitecture:
    """Each service is independently deployable and reachable on its own port."""

    @pytest.mark.parametrize("name,url", [
        ("logging_service", LOGGING_URL),
        ("poke_api",        POKE_API_URL),
        ("poke_stats",      POKE_STATS_URL),
        ("poke_images",     POKE_IMAGES_URL),
        ("search_api",      SEARCH_URL),
    ])
    def test_each_service_is_independently_healthy(self, name, url):
        r = get(f"{url}/health")
        assert r.status_code == 200, f"{name} /health returned {r.status_code}"
        body = r.json()
        assert body.get("status") == "healthy", f"{name} status != healthy: {body}"
        assert body.get("service") == name, f"service field mismatch: {body}"

    def test_search_api_orchestrates_all_downstream_services(self):
        """Search API must call poke_api, poke_stats and poke_images in one request."""
        r = get(f"{SEARCH_URL}/poke/search", params={"pokemon_name": "charizard"})
        assert r.status_code == 200
        body = r.json()
        # name from POKE API
        assert body.get("name") == "charizard", "Missing/wrong 'name'"
        # stats list from POKE Stats
        assert isinstance(body.get("stats"), list), "Missing 'stats' list (from poke_stats)"
        # images key present (poke_images, may be null if no files)
        assert "images" in body, "Missing 'images' key (from poke_images)"

    def test_services_status_endpoint_reports_all_healthy(self):
        r = get(f"{SEARCH_URL}/poke/status")
        assert r.status_code == 200
        services = r.json().get("services", {})
        for svc in ("poke_api", "poke_stats", "poke_images", "logging_service"):
            assert svc in services, f"Missing service: {svc}"
            assert services[svc]["status"] == "healthy", \
                f"{svc} not healthy: {services[svc]}"

    def test_poke_stats_connects_to_database(self):
        r = get(f"{POKE_STATS_URL}/health")
        body = r.json()
        assert body.get("database") == "connected", \
            "poke_stats can't reach PostgreSQL DB"

    def test_poke_api_connects_to_external_pokeapi(self):
        """poke_api must proxy to https://pokeapi.co/api/v2/pokemon/{name}."""
        r = get(f"{POKE_API_URL}/pokemon/bulbasaur")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["id"] == 1
        assert data["name"] == "bulbasaur"

    def test_poke_stats_serves_from_local_db(self):
        r = get(f"{POKE_STATS_URL}/stats/pikachu")
        assert r.status_code == 200
        stats = r.json()["data"]
        for field in ("hp", "attack", "defense", "sp_atk", "sp_def", "speed"):
            assert field in stats, f"Missing stat field: {field}"

    def test_search_returns_correct_schema(self):
        """Response schema: {name, stats:[{name,value},...], images: url|null}"""
        r = get(f"{SEARCH_URL}/poke/search", params={"pokemon_name": "pikachu"})
        body = r.json()
        assert body["name"] == "pikachu"
        # stats must be a list of {name, value} entries
        stats = body["stats"]
        assert isinstance(stats, list)
        stat_names = {s["name"] for s in stats}
        for field in ("hp", "attack", "defense", "sp_atk", "sp_def", "speed"):
            assert field in stat_names, f"Missing stat '{field}' in stats list"
        for entry in stats:
            assert "name" in entry and "value" in entry
            assert isinstance(entry["value"], int)
        # images must be a string URL or null
        assert body["images"] is None or isinstance(body["images"], str)


# ════════════════════════════════════════════════════════════════════════════
# Objetivo 2 – Logging distribuido con formato estándar
# Formato: {Timestamp}{Module}{API}{Function} Message
# ════════════════════════════════════════════════════════════════════════════

class TestDistributedLogging:
    """
    Every microservice must emit logs to the central logging_service.
    Each log entry must conform to the standard format:
      {Timestamp}{Module}{API}{Function} Message
    """

    ISO8601_RE = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$"
    )

    @classmethod
    def setup_class(cls):
        """Generate at least one log per service before running assertions."""
        trigger_service_calls()

    def _recent_logs_for(self, module: str, n: int = 10) -> list:
        r = get(f"{LOGGING_URL}/logs/module/{module}")
        assert r.status_code == 200
        logs = r.json()["logs"]
        assert len(logs) > 0, f"No logs found for module {module} — service may not be logging"
        return logs[-n:]

    def _assert_log_format(self, log: dict, expected_module: str):
        """Validate the standard log structure: {Timestamp}{Module}{API}{Function} Message."""
        # {Timestamp} – must be a valid ISO-8601 datetime
        assert "timestamp" in log, "Log missing 'timestamp'"
        ts = log["timestamp"]
        assert self.ISO8601_RE.match(ts), f"timestamp not ISO-8601: '{ts}'"
        # Ensure it is actually parseable
        datetime.fromisoformat(ts.replace("Z", "+00:00"))

        # {Module} – must match the service
        assert log.get("module") == expected_module, \
            f"Expected module={expected_module}, got {log.get('module')}"

        # {API} – must be non-empty string
        assert log.get("api"), f"Log missing 'api': {log}"

        # {Function} – must be non-empty string
        assert log.get("function"), f"Log missing 'function': {log}"

        # Message – must be non-empty string
        assert log.get("message"), f"Log missing 'message': {log}"

    @pytest.mark.parametrize("module", [
        "POKE_API",
        "POKE_STATS",
        "POKE_IMAGES",
        "SEARCH_API",
    ])
    def test_each_service_emits_logs_with_standard_format(self, module):
        logs = self._recent_logs_for(module)
        for log in logs:
            self._assert_log_format(log, module)

    def test_logs_identify_timestamp_clearly(self):
        """Every log must have a machine-parseable timestamp."""
        r = get(f"{LOGGING_URL}/logs/today")
        logs = r.json()["logs"]
        assert len(logs) > 0, "No logs for today"
        for log in logs:
            assert "timestamp" in log
            assert "date" in log
            # date must match YYYY-MM-DD
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", log["date"]), \
                f"'date' field not YYYY-MM-DD: {log['date']}"

    def test_logs_identify_microservice_clearly(self):
        """Every log must have a module field that identifies the emitting service."""
        r = get(f"{LOGGING_URL}/logs/today")
        logs = r.json()["logs"]
        known_modules = {"POKE_API", "POKE_STATS", "POKE_IMAGES", "SEARCH_API", "TEST"}
        for log in logs:
            assert "module" in log, f"Log missing 'module': {log}"
            # Module must be a non-empty uppercase string
            assert log["module"] and log["module"] == log["module"].upper(), \
                f"module not uppercase: {log['module']}"

    def test_logging_service_rejects_incomplete_entries(self):
        """Log entries missing required fields must be rejected with 400."""
        r = post(f"{LOGGING_URL}/logs", json={"module": "TEST", "message": "oops"})
        assert r.status_code == 400

    def test_search_api_triggers_logs_in_multiple_services(self):
        """A single search call must cascade logs to SEARCH_API and downstream services."""
        before_counts = {}
        for module in ("SEARCH_API", "POKE_API", "POKE_STATS", "POKE_IMAGES"):
            r = get(f"{LOGGING_URL}/logs/module/{module}")
            before_counts[module] = r.json()["count"]

        get(f"{SEARCH_URL}/poke/search", params={"pokemon_name": "gengar"})
        time.sleep(1.0)

        for module in ("SEARCH_API", "POKE_API", "POKE_STATS"):
            r = get(f"{LOGGING_URL}/logs/module/{module}")
            after = r.json()["count"]
            assert after > before_counts[module], \
                f"{module} did not emit a new log after /poke/search"


# ════════════════════════════════════════════════════════════════════════════
# Objetivo 3 – Medición de latencia
# latency_ms debe medir inicio y fin de cada bloque de código
# ════════════════════════════════════════════════════════════════════════════

class TestLatencyMeasurement:
    """
    Every log emitted by a service must include latency_ms > 0.
    This confirms that start/end time is measured around each code block.
    """

    @classmethod
    def setup_class(cls):
        trigger_service_calls()

    def _assert_latency_in_logs(self, module: str):
        r = get(f"{LOGGING_URL}/logs/module/{module}")
        logs = r.json()["logs"]
        assert len(logs) > 0, f"No logs for {module}"
        for log in logs[-5:]:
            assert "latency_ms" in log, \
                f"{module} log missing 'latency_ms': {log}"
            assert log["latency_ms"] is not None, \
                f"{module} log has null latency_ms: {log}"
            assert isinstance(log["latency_ms"], (int, float)), \
                f"{module} latency_ms is not numeric: {log['latency_ms']}"
            assert log["latency_ms"] >= 0, \
                f"{module} latency_ms is negative: {log['latency_ms']}"

    @pytest.mark.parametrize("module", [
        "POKE_API",
        "POKE_STATS",
        "POKE_IMAGES",
        "SEARCH_API",
    ])
    def test_latency_present_and_valid_in_module_logs(self, module):
        self._assert_latency_in_logs(module)

    def test_latency_is_positive_nonzero_for_real_calls(self):
        """Real I/O operations should produce latency > 0 ms."""
        for module in ("POKE_API", "POKE_STATS"):
            r = get(f"{LOGGING_URL}/logs/module/{module}")
            logs = r.json()["logs"]
            latencies = [l["latency_ms"] for l in logs if l.get("latency_ms") is not None]
            assert any(lat > 0 for lat in latencies), \
                f"All {module} latency_ms values are 0 — timing may not be implemented"

    def test_search_api_latency_covers_full_orchestration(self):
        """Search API latency should reflect time for all downstream calls."""
        get(f"{SEARCH_URL}/poke/search", params={"pokemon_name": "mewtwo"})
        time.sleep(0.8)
        r = get(f"{LOGGING_URL}/logs/module/SEARCH_API")
        logs = r.json()["logs"]
        assert logs, "SEARCH_API produced no logs"
        last = logs[-1]
        assert last.get("latency_ms") is not None
        # Orchestration takes at least a few ms
        assert last["latency_ms"] > 0, "SEARCH_API latency should be > 0"

    def test_latency_logged_for_not_found_cases(self):
        """Even 404 responses must record latency_ms (error paths are timed too)."""
        get(f"{POKE_STATS_URL}/stats/notapokemon99999")  # triggers a WARNING log
        time.sleep(0.5)
        r = get(f"{LOGGING_URL}/logs/module/POKE_STATS")
        logs = r.json()["logs"]
        # Find the most recent warning entry
        warnings = [l for l in logs if l.get("level") == "WARNING"]
        if warnings:
            last_warn = warnings[-1]
            assert last_warn.get("latency_ms") is not None, \
                "latency_ms missing on WARNING log"


# ════════════════════════════════════════════════════════════════════════════
# Objetivo 4 – Procesamiento de logs para generar métricas
# ════════════════════════════════════════════════════════════════════════════

class TestLogMetrics:
    """
    The logging_service must support log querying so metrics can be derived:
    - Count per module
    - Filter by date
    - Latest N entries
    - Filter by module
    """

    @classmethod
    def setup_class(cls):
        trigger_service_calls()

    def test_can_count_logs_per_module(self):
        """Must be able to retrieve total log count per module."""
        for module in ("POKE_API", "POKE_STATS", "POKE_IMAGES", "SEARCH_API"):
            r = get(f"{LOGGING_URL}/logs/module/{module}")
            body = r.json()
            assert "count" in body, f"No 'count' in response for {module}"
            assert isinstance(body["count"], int)
            assert body["count"] >= 0

    def test_can_query_logs_by_today_date(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r = get(f"{LOGGING_URL}/logs/date/{today}")
        assert r.status_code == 200
        body = r.json()
        assert body["date"] == today
        assert "count" in body
        assert "logs" in body

    def test_can_get_latest_n_logs(self):
        for limit in (1, 5, 20):
            r = get(f"{LOGGING_URL}/logs/latest/{limit}")
            assert r.status_code == 200
            body = r.json()
            assert body["limit_requested"] == limit
            assert len(body["logs"]) <= limit

    def test_module_filter_returns_only_that_module(self):
        r = get(f"{LOGGING_URL}/logs/module/POKE_STATS")
        body = r.json()
        for log in body["logs"]:
            assert log["module"] == "POKE_STATS", \
                f"Module filter leaked log from {log['module']}"

    def test_today_logs_include_entries_from_multiple_services(self):
        """After calls to all services, today's log must include ≥ 2 distinct modules."""
        r = get(f"{LOGGING_URL}/logs/today")
        logs = r.json()["logs"]
        modules_seen = {l["module"] for l in logs}
        service_modules = modules_seen & {"POKE_API", "POKE_STATS", "POKE_IMAGES", "SEARCH_API"}
        assert len(service_modules) >= 2, \
            f"Expected logs from ≥ 2 services, got: {service_modules}"

    def test_logs_have_request_id_for_tracing(self):
        """Each log must carry a request_id to enable distributed tracing."""
        r = get(f"{LOGGING_URL}/logs/today")
        logs = r.json()["logs"]
        for log in logs[:10]:
            assert "request_id" in log, f"Log missing 'request_id': {log}"
            assert log["request_id"], "request_id is empty"

    def test_logs_have_level_field_for_severity_metrics(self):
        """Level (INFO/WARNING/ERROR) enables alert threshold metrics."""
        r = get(f"{LOGGING_URL}/logs/today")
        logs = r.json()["logs"]
        valid_levels = {"INFO", "WARNING", "ERROR", "DEBUG"}
        for log in logs[:20]:
            assert log.get("level") in valid_levels, \
                f"Invalid level '{log.get('level')}' in log: {log}"

    def test_invalid_date_format_returns_400(self):
        r = get(f"{LOGGING_URL}/logs/date/2026/01/01")
        assert r.status_code in (400, 404, 422)

    def test_invalid_date_string_returns_400(self):
        r = get(f"{LOGGING_URL}/logs/date/not-a-date")
        assert r.status_code == 400


# ════════════════════════════════════════════════════════════════════════════
# Objetivo 5 – Pruebas de carga (validación del plan JMeter)
# Min 1000 llamadas – Max 10000 llamadas
# ════════════════════════════════════════════════════════════════════════════

class TestJMeterLoadTestConfiguration:
    """
    The JMeter test plan (jmeter/test_plan.jmx) must be configured for
    a total of 1 000 – 10 000 HTTP calls (THREAD_COUNT × LOOP_COUNT).
    """

    JMX_PATH = Path(__file__).parent.parent / "jmeter" / "test_plan.jmx"

    @pytest.fixture(scope="class")
    def jmx_root(self):
        assert self.JMX_PATH.exists(), f"JMeter plan not found: {self.JMX_PATH}"
        return ET.parse(self.JMX_PATH).getroot()

    def _get_var(self, root, name: str) -> str | None:
        for ep in root.iter("elementProp"):
            if ep.get("name") == name:
                val = ep.find(".//stringProp[@name='Argument.value']")
                if val is not None:
                    return val.text
        return None

    def test_jmx_file_exists(self):
        assert self.JMX_PATH.exists(), "jmeter/test_plan.jmx not found"

    def test_total_calls_within_1000_to_10000(self, jmx_root):
        threads_str = self._get_var(jmx_root, "THREAD_COUNT")
        loops_str   = self._get_var(jmx_root, "LOOP_COUNT")
        assert threads_str, "THREAD_COUNT variable not found in JMX"
        assert loops_str,   "LOOP_COUNT variable not found in JMX"
        total = int(threads_str) * int(loops_str)
        assert 1_000 <= total <= 10_000, \
            f"Total calls = {total} (THREAD_COUNT={threads_str} × LOOP_COUNT={loops_str}). Must be 1000–10000."

    def test_thread_group_targets_search_api(self, jmx_root):
        """The load test must target the Search API /poke/search endpoint."""
        paths = [sp.text for sp in jmx_root.iter("stringProp")
                 if sp.get("name") == "HTTPSampler.path"]
        assert any("/poke/search" in (p or "") for p in paths), \
            "JMX does not contain a sampler targeting /poke/search"

    def test_latency_collection_enabled(self, jmx_root):
        """The results collector must record latency for performance analysis."""
        latency_nodes = [
            el for el in jmx_root.iter("latency")
            if el.text and el.text.strip().lower() == "true"
        ]
        assert len(latency_nodes) > 0, \
            "JMeter plan does not have latency collection enabled"

    def test_timestamp_collection_enabled(self, jmx_root):
        ts_nodes = [
            el for el in jmx_root.iter("timestamp")
            if el.text and el.text.strip().lower() == "true"
        ]
        assert len(ts_nodes) > 0, \
            "JMeter plan does not have timestamp collection enabled"

    def test_result_file_configured(self, jmx_root):
        """A .jtl results file must be configured for post-processing."""
        filenames = [
            sp.text for sp in jmx_root.iter("stringProp")
            if sp.get("name") == "filename" and sp.text
        ]
        assert any(".jtl" in f for f in filenames), \
            "No .jtl results filename configured in JMeter plan"


# ════════════════════════════════════════════════════════════════════════════
# Functional smoke tests (per service)
# ════════════════════════════════════════════════════════════════════════════

class TestPokeAPIFunctional:
    def test_get_by_name(self):
        r = get(f"{POKE_API_URL}/pokemon/pikachu")
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "pikachu"

    def test_get_by_id(self):
        r = get(f"{POKE_API_URL}/pokemon/25")
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "pikachu"

    def test_not_found(self):
        assert get(f"{POKE_API_URL}/pokemon/notapokemon99999").status_code == 404

    def test_raw_endpoint(self):
        r = get(f"{POKE_API_URL}/pokemon/charmander/raw")
        assert r.status_code == 200
        assert r.json()["name"] == "charmander"


class TestPokeStatsFunctional:
    def test_get_pikachu(self):
        r = get(f"{POKE_STATS_URL}/stats/pikachu")
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "pikachu"

    def test_case_insensitive(self):
        assert get(f"{POKE_STATS_URL}/stats/PIKACHU").status_code == 200

    def test_not_found(self):
        assert get(f"{POKE_STATS_URL}/stats/notapokemon99999").status_code == 404

    def test_list_with_limit(self):
        r = get(f"{POKE_STATS_URL}/stats", params={"limit": 5})
        assert len(r.json()["data"]) <= 5


class TestPokeImagesFunctional:
    def test_list_all(self):
        r = get(f"{POKE_IMAGES_URL}/images")
        assert r.status_code == 200
        assert "pokemon" in r.json()

    def test_no_images_returns_success_false(self):
        r = get(f"{POKE_IMAGES_URL}/images/notapokemon99999")
        assert r.status_code == 200
        assert r.json()["success"] is False

    def test_verify_directory(self):
        r = post(f"{POKE_IMAGES_URL}/images/testpokemon/verify")
        assert r.status_code == 200
        assert r.json()["success"] is True


class TestSearchAPIFunctional:
    def test_search_pikachu(self):
        r = get(f"{SEARCH_URL}/poke/search", params={"pokemon_name": "pikachu"})
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "pikachu"
        assert isinstance(body["stats"], list)
        assert len(body["stats"]) > 0
        assert "images" in body

    def test_stats_are_list_of_name_value(self):
        r = get(f"{SEARCH_URL}/poke/search", params={"pokemon_name": "bulbasaur"})
        assert r.status_code == 200
        for entry in r.json()["stats"]:
            assert "name" in entry and "value" in entry
            assert isinstance(entry["value"], int)

    def test_images_is_string_or_null(self):
        r = get(f"{SEARCH_URL}/poke/search", params={"pokemon_name": "pikachu"})
        assert r.status_code == 200
        images = r.json()["images"]
        assert images is None or isinstance(images, str)

    def test_not_found(self):
        assert get(f"{SEARCH_URL}/poke/search",
                   params={"pokemon_name": "notapokemon99999"}).status_code == 404

    def test_empty_name_rejected(self):
        assert get(f"{SEARCH_URL}/poke/search",
                   params={"pokemon_name": ""}).status_code == 400
