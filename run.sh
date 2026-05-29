#!/bin/bash

# Script para facilitar la ejecución del proyecto MonitorMach

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}======================================${NC}"
}

case "$1" in
    "up")
        print_header "Iniciando servicios..."
        docker-compose up -d
        echo -e "${GREEN}✓ Servicios iniciados${NC}"
        echo -e "Esperando 30 segundos para que estén listos..."
        sleep 30
        echo -e "${GREEN}✓ Ejecuta: docker-compose logs -f${NC}"
        ;;

    "down")
        print_header "Deteniendo servicios..."
        docker-compose down
        echo -e "${GREEN}✓ Servicios detenidos${NC}"
        ;;

    "restart")
        print_header "Reiniciando servicios..."
        docker-compose restart
        echo -e "${GREEN}✓ Servicios reiniciados${NC}"
        ;;

    "clean")
        print_header "Limpiando volúmenes..."
        docker-compose down -v
        echo -e "${GREEN}✓ Volúmenes eliminados${NC}"
        ;;

    "logs")
        print_header "Mostrando logs..."
        docker-compose logs -f
        ;;

    "logs-search")
        docker-compose logs -f search_api
        ;;

    "logs-stats")
        docker-compose logs -f poke_stats
        ;;

    "logs-logging")
        docker-compose logs -f logging_service
        ;;

    "status")
        print_header "Estado de servicios..."
        docker-compose ps
        ;;

    "test-search")
        print_header "Probando búsqueda..."
        curl "http://localhost:8000/poke/search?pokemon_name=pikachu" | jq '.'
        ;;

    "test-status")
        print_header "Estado de microservicios..."
        curl "http://localhost:8000/poke/status" | jq '.'
        ;;

    "test-logs")
        print_header "Logs del día..."
        curl "http://localhost:8004/logs/today" | jq '.logs | length'
        ;;

    "rebuild")
        print_header "Reconstruyendo imágenes..."
        docker-compose down
        docker-compose up -d --build
        echo -e "${GREEN}✓ Reconstrucción completada${NC}"
        ;;

    *)
        echo "Uso: ./run.sh [COMANDO]"
        echo ""
        echo "Comandos disponibles:"
        echo "  up              - Iniciar servicios"
        echo "  down            - Detener servicios"
        echo "  restart         - Reiniciar servicios"
        echo "  clean           - Limpiar volúmenes"
        echo "  logs            - Ver todos los logs"
        echo "  logs-search     - Ver logs de Search API"
        echo "  logs-stats      - Ver logs de POKE Stats"
        echo "  logs-logging    - Ver logs de Logging Service"
        echo "  status          - Ver estado de servicios"
        echo "  test-search     - Probar endpoint de búsqueda"
        echo "  test-status     - Probar endpoint de estado"
        echo "  test-logs       - Ver cantidad de logs"
        echo "  rebuild         - Reconstruir imágenes"
        ;;
esac
