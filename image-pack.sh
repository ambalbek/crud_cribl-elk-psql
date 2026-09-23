#!/usr/bin/env bash
set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────
COMPOSE_FILE="docker-compose_dev.yml"
PLATFORM="linux/amd64"
TAG="1.0.0"
SPLIT_SIZE="25m"
OUT_DIR="image-pack"
TAR_FILE="$OUT_DIR/cribl-images-$TAG.tar"

# ── Usage ────────────────────────────────────────────────────────────────────
usage() {
  echo "Usage:"
  echo "  bash image-pack.sh          Build, save, and split images"
  echo "  bash image-pack.sh --load   Reassemble and load images"
  exit 1
}

# ═══════════════════════════════════════════════════════════════════════════════
#  --load: reassemble split parts and load into Docker
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "${1:-}" == "--load" ]]; then
  PARTS=("${TAR_FILE}".part*)

  if [[ ${#PARTS[@]} -eq 0 || ! -f "${PARTS[0]}" ]]; then
    echo "ERROR: No part files found at ${TAR_FILE}.part*"
    exit 1
  fi

  echo "==> Found ${#PARTS[@]} part(s):"
  for f in "${PARTS[@]}"; do
    echo "    $f"
  done

  echo ""
  echo "==> Reassembling into $TAR_FILE"
  cat "${PARTS[@]}" > "$TAR_FILE"

  TAR_SIZE=$(du -h "$TAR_FILE" | cut -f1)
  echo "    Size: $TAR_SIZE"

  echo ""
  echo "==> Loading images into Docker"
  docker load -i "$TAR_FILE"

  echo ""
  echo "==> Cleaning up tar"
  rm "$TAR_FILE"

  echo ""
  echo "==> Done. Loaded images:"
  docker images --format "    {{.Repository}}:{{.Tag}}  ({{.Size}})" | grep -E "cribl-framework|etn-onboarding|cribl-service|ece-service|postgres" || true
  exit 0
fi

# ═══════════════════════════════════════════════════════════════════════════════
#  Default: build, save, split
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "${1:-}" != "" ]]; then
  usage
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: $COMPOSE_FILE not found in $(pwd)"
  exit 1
fi

echo "==> Found $COMPOSE_FILE"
echo ""

# ── Build images ────────────────────────────────────────────────────────────
declare -a NAMES=("cribl-framework" "etn-onboarding" "cribl-service" "ece-service")
declare -a CMDS=(
  "docker build --platform $PLATFORM -t cribl-framework:$TAG ."
  "docker build --platform $PLATFORM -t etn-onboarding:$TAG ./etn_onboarding"
  "docker build --platform $PLATFORM -t cribl-service:$TAG -f cribl_service/Dockerfile ."
  "docker build --platform $PLATFORM -t ece-service:$TAG -f ece_service/Dockerfile ."
)

IMAGE_TAGS=()
for i in "${!NAMES[@]}"; do
  echo "==> Building ${NAMES[$i]}:$TAG ($PLATFORM)"
  eval "${CMDS[$i]}"
  IMAGE_TAGS+=("${NAMES[$i]}:$TAG")
  echo ""
done

# ── Pull stock images ───────────────────────────────────────────────────────
PULL_IMAGES=("postgres:16")
for img in "${PULL_IMAGES[@]}"; do
  echo "==> Pulling $img ($PLATFORM)"
  docker pull --platform "$PLATFORM" "$img"
  IMAGE_TAGS+=("$img")
  echo ""
done

# ── Save all images into a single tar ───────────────────────────────────────
mkdir -p "$OUT_DIR"

echo "==> Saving ${#IMAGE_TAGS[@]} images to $TAR_FILE"
docker save -o "$TAR_FILE" "${IMAGE_TAGS[@]}"

TAR_SIZE=$(du -h "$TAR_FILE" | cut -f1)
echo "    Size: $TAR_SIZE"
echo ""

# ── Split into chunks ──────────────────────────────────────────────────────
echo "==> Splitting into ${SPLIT_SIZE}B chunks"
split -b "$SPLIT_SIZE" -d "$TAR_FILE" "${TAR_FILE}.part"

rm "$TAR_FILE"

echo ""
echo "==> Created files:"
for f in "${TAR_FILE}".part*; do
  SIZE=$(du -h "$f" | cut -f1)
  echo "    $f  ($SIZE)"
done

echo ""
echo "==> Done. To load on the target machine:"
echo "    1. Copy the $OUT_DIR/ folder"
echo "    2. Run: bash image-pack.sh --load"
