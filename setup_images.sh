#!/bin/bash

# Script para crear estructura de directorios de imágenes de Pokemon

IMAGES_DIR="poke_images/images"

# Pokemon populares para crear directorios de ejemplo
POKEMONS=(
    "pikachu"
    "charizard"
    "blastoise"
    "venusaur"
    "arcanine"
    "lapras"
    "machamp"
    "gengar"
    "golem"
    "alakazam"
)

echo "Creando estructura de directorios para imágenes de Pokemon..."

mkdir -p "$IMAGES_DIR"

for pokemon in "${POKEMONS[@]}"; do
    dir="$IMAGES_DIR/$pokemon"
    mkdir -p "$dir"
    echo "✓ Creado directorio: $dir"
done

echo ""
echo "Estructura de directorios creada exitosamente."
echo ""
echo "Ahora puedes copiar imágenes en los directorios:"
echo "  poke_images/images/pikachu/image1.jpg"
echo "  poke_images/images/pikachu/image2.png"
echo "  etc..."
