#!/usr/bin/env bash
# Compile the Unity Catalog server extensions in config/unity-catalog/ext/ into jars/uc-ext/.
# Uses the UC image itself as the toolchain (javac 17 + the server classpath), so the classes
# always match the pinned server version. The compose file mounts jars/uc-ext at /opt/uc-ext
# and prepends it to the server classpath. Re-run after bumping the UC image.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
UC_IMAGE="${UC_IMAGE:-$(grep -oE 'image: unitycatalog/unitycatalog:[^ ]+' "$ROOT/docker-compose-unity-catalog.yml" | head -1 | cut -d' ' -f2)}"
SRC="$ROOT/config/unity-catalog/ext"
OUT="$ROOT/jars/uc-ext"

mkdir -p "$OUT"
# Compile inside the container and stream the classes out as a tar: avoids uid-mapping
# trouble writing to a bind mount from a rootless container.
docker run --rm -i \
    -v "$SRC:/src:ro,z" \
    "$UC_IMAGE" \
    sh -c 'javac -cp "$(cat server/target/classpath)" -d /tmp/out /src/*.java && tar -C /tmp/out -cf - .' \
    | tar -C "$OUT" -xf -
echo "compiled into $OUT:"
find "$OUT" -name '*.class'
