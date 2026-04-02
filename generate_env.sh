#!/usr/bin/env bash
set -Eeuo pipefail

OUT_FILE=".env"
GCP_SECRET_NAME="dev_video_api"

ensure_jq() {
  if command -v jq >/dev/null 2>&1; then return; fi

  # Detect Windows (Git Bash, MSYS, Cygwin)
  if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]] || [[ -n "${MSYSTEM:-}" ]]; then
    echo "Error: jq is not installed. Please install it manually:" >&2
    echo "  winget install jqlang.jq" >&2
    echo "  or: choco install jq" >&2
    echo "  or: scoop install jq" >&2
    exit 2
  fi

  # Detect Linux package managers (require sudo)
  if command -v apt-get >/dev/null 2>&1; then
    echo "jq not found; installing with apt-get (may require sudo)..." >&2
    sudo apt-get update -y >/dev/null
    DEBIAN_FRONTEND=noninteractive sudo apt-get install -y jq >/dev/null
  elif command -v apk >/dev/null 2>&1; then
    echo "jq not found; installing with apk..." >&2
    apk add --no-cache jq >/dev/null
  elif command -v yum >/dev/null 2>&1; then
    echo "jq not found; installing with yum (may require sudo)..." >&2
    sudo yum install -y -q jq >/dev/null
  else
    echo "No known package manager available to install jq. Please install manually:" >&2
    echo "  Windows : winget install jqlang.jq   (or: choco install jq / scoop install jq)" >&2
    echo "  macOS   : brew install jq" >&2
    echo "  Debian/Ubuntu: sudo apt-get update && sudo apt-get install -y jq" >&2
    exit 2
  fi
}

check_gcloud_login() {
  echo "Checking gcloud authentication..."
  
  # Check if gcloud is installed
  if ! command -v gcloud >/dev/null 2>&1; then
    echo "Error: gcloud CLI is not installed. Please install the Google Cloud SDK:" >&2
    echo "  https://cloud.google.com/sdk/docs/install" >&2
    exit 1
  fi
  
  # Check if user is logged in by trying to get the active account
  local ACTIVE_ACCOUNT
  ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null || true)
  
  if [ -z "$ACTIVE_ACCOUNT" ] || [ "$ACTIVE_ACCOUNT" = "(unset)" ]; then
    echo "Not logged in to GCP. Running gcloud auth login..."
    gcloud auth login
  else
    echo "✓ Already logged in as: $ACTIVE_ACCOUNT"
  fi
  
  # Verify login was successful
  ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null || true)
  if [ -z "$ACTIVE_ACCOUNT" ] || [ "$ACTIVE_ACCOUNT" = "(unset)" ]; then
    echo "Error: Failed to authenticate with gcloud." >&2
    exit 1
  fi
  
  # Ensure the correct project is set
  local CURRENT_PROJECT
  CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || true)
  
  if [ "$CURRENT_PROJECT" != "formedics-dev" ]; then
    echo "Setting gcloud project to formedics-dev..."
    gcloud config set project formedics-dev
  else
    echo "✓ Project already set to: formedics-dev"
  fi
}

process_secret() {
  local SECRET_NAME="$1"
  local DESCRIPTION="$2"
  local OPTIONAL="${3:-false}"

  echo "Fetching $SECRET_NAME from Secret Manager ($DESCRIPTION)..."

  # Try to fetch the secret, handle failure gracefully if optional
  if ! JSON="$(gcloud secrets versions access latest --secret="$SECRET_NAME" 2>&1)"; then
    if [ "$OPTIONAL" = "true" ]; then
      echo "$SECRET_NAME not found (skipping - not required for this environment)"
      return 0
    else
      echo "Failed to fetch required secret $SECRET_NAME" >&2
      echo "$JSON" >&2
      exit 1
    fi
  fi

  # Validate JSON early (will throw if invalid)
  if ! echo "$JSON" | jq -e type >/dev/null 2>&1; then
    echo "Invalid JSON in secret $SECRET_NAME" >&2
    exit 1
  fi

  # Iterate keys -> values and write to .env file
  # Format: key="value" (double-quoted values)
  while IFS=$'\t' read -r KEY RAW_VALUE; do
    # Strip possible CR
    VAL="${RAW_VALUE%$'\r'}"
    
    # Escape backslashes and quotes for proper .env formatting
    VAL_ESCAPED="$(printf '%s' "$VAL" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
    
    # Write key="value" to .env file
    printf '%s="%s"\n' "$KEY" "$VAL_ESCAPED" >> "$OUT_FILE"
  done < <(jq -r 'to_entries[] | "\(.key)\t\(.value|tostring)"' <<<"$JSON")

  echo "✓ $DESCRIPTION loaded"
}

add_static_values() {
  echo "" >> "$OUT_FILE"
  echo "# Static development values" >> "$OUT_FILE"
  
  cat >> "$OUT_FILE" << 'EOF'
MONGO_AMC_USER=""
MONGO_AMC_PASS=""
MONGO_AMC_URL=""
GENAI_API_KEY=""
ITB_FEED_ENV=""
FEED_SERVICE_ENV=""
WP_APP_USER=""
WP_APP_PW=""
MONGO_MASHUP_USER=""
MONGO_MASHUP_PASS=""
MONGO_MASHUP_URL=""
FM_API_SERVICES_KEYS="{\"internal\": {\"user1\": \"abcdef\"},\"external\": {},\"ai\": {},\"iterable\": {},\"backend\": {}}"
ELSEVIER_API_KEY=""
ITERABLE_API_KEY=""
EOF
}

main() {
  ensure_jq
  check_gcloud_login
  
  echo "# Build-time env vars" > "$OUT_FILE"
  echo "# Generated $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$OUT_FILE"

  # Fetch GCP video api keys (required)
  process_secret "$GCP_SECRET_NAME" "Video API config" "false"

  # Add static development values
  add_static_values

  echo "$OUT_FILE generated successfully."
}

main "$@"
