#!/usr/bin/env bash
# Run on backend-agent: bash infra/jenkins/deploy-backend.sh "$APP_IMAGE"
# Requires the existing keyfin-prod app and its read-only deployment configuration.
set +x
set -Eeuo pipefail
umask 077

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ $# -eq 1 ]] || fail 'Usage: deploy-backend.sh keyfin-backend:ci-BUILD-COMMIT'
new_image="$1"
[[ "$new_image" =~ ^keyfin-backend:ci-[0-9]+-[0-9a-f]{12,40}$ ]] || fail 'Invalid deployment image tag.'

# Overrides allow isolated verification without using the production directories.
config_dir="${KEYFIN_DEPLOY_CONFIG_DIR:-/home/ubuntu/keyfin-deploy}"
state_root="${KEYFIN_DEPLOY_STATE_ROOT:-/home/jenkins/agent/deploy-state/keyfin-prod}"
env_file="$config_dir/.env"

test -r "$env_file" || fail 'Deployment environment file is not readable.'
test -r "$config_dir/compose.prod.yml" || fail 'Deployment Compose file is not readable.'
expected_id="$(docker image inspect --format '{{.Id}}' "$new_image")"
[[ -n "$expected_id" ]] || fail 'Deployment image was not found locally.'

old_container="$(docker ps -aq \
  --filter label=com.docker.compose.project=keyfin-prod \
  --filter label=com.docker.compose.service=app)"
[[ -n "$old_container" && "$old_container" != *$'\n'* ]] || fail 'Expected exactly one existing app container.'

old_status="$(docker inspect --format '{{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$old_container")"
[[ "$old_status" == 'true healthy' ]] || fail 'Existing app must be running and healthy before deployment.'
old_id="$(docker inspect --format '{{.Image}}' "$old_container")"
[[ -n "$old_id" ]] || fail 'Existing app image could not be identified.'

mkdir -p "$state_root"
state_dir="$state_root/${new_image##*:}"
# Reserve the directory before tagging, so a retry cannot overwrite its rollback image.
mkdir "$state_dir" || fail 'Recovery state already exists; use a new Jenkins build number.'
cp "$config_dir/compose.prod.yml" "$state_dir/base.yml"

rollback_image="keyfin-backend:rollback-${new_image##*:}"
docker image tag "$old_id" "$rollback_image"
printf '%s\n' "$rollback_image" > "$state_dir/rollback-image.txt"
printf '%s\n' "$old_id" > "$state_dir/rollback-image-id.txt"

# Escape dollar signs for Compose to preserve the original container's shell commands.
docker inspect --format '{
  "services": {
    "app": {
      "healthcheck": {
        "test": {{json .Config.Healthcheck.Test}},
        "interval": "{{json .Config.Healthcheck.Interval}}ns",
        "timeout": "{{json .Config.Healthcheck.Timeout}}ns",
        "start_period": "{{json .Config.Healthcheck.StartPeriod}}ns",
        "retries": {{json .Config.Healthcheck.Retries}}
      }
    }
  }
}' "$old_container" | sed 's/\$/$$/g' > "$state_dir/rollback.json"

cat > "$state_dir/candidate.yml" <<'YAML'
services:
  app:
    healthcheck:
      test: ["CMD", "curl", "--fail", "--silent", "--show-error",
             "--max-time", "5", "--output", "/dev/null",
             "http://127.0.0.1:8080/actuator/health/readiness"]
YAML

compose_with() {
  local selected_image="$1"
  local override_file="$2"
  shift 2

  APP_IMAGE="$selected_image" timeout 240s docker compose \
    -p keyfin-prod \
    --env-file "$env_file" \
    -f "$state_dir/base.yml" \
    -f "$override_file" "$@"
}

compose_with "$new_image" "$state_dir/candidate.yml" config --quiet
compose_with "$rollback_image" "$state_dir/rollback.json" config --quiet
echo "Recovery state: $state_dir"

rollback_needed=0
finish() {
  local result=$?
  local restored_container
  trap - EXIT INT TERM

  if [[ "$rollback_needed" -eq 1 ]]; then
    [[ "$result" -ne 0 ]] || result=1
    echo 'Deployment failed. Restoring previous image and health check.'

    if compose_with "$rollback_image" "$state_dir/rollback.json" \
      up -d --no-deps --no-build --pull never --wait --wait-timeout 180 app \
      && restored_container="$(compose_with "$rollback_image" "$state_dir/rollback.json" ps -q app)" \
      && [[ -n "$restored_container" && "$restored_container" != *$'\n'* ]] \
      && [[ "$(docker inspect --format '{{.Image}}' "$restored_container")" == "$old_id" ]]; then
      echo 'ROLLBACK_COMPLETED'
    else
      echo "ROLLBACK_FAILED: manual recovery is required. Recovery state: $state_dir" >&2
    fi
  fi

  exit "$result"
}

trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

rollback_needed=1
compose_with "$new_image" "$state_dir/candidate.yml" \
  up -d --no-deps --no-build --pull never --wait --wait-timeout 180 app

new_container="$(compose_with "$new_image" "$state_dir/candidate.yml" ps -q app)"
[[ -n "$new_container" && "$new_container" != *$'\n'* ]] || fail 'New app container could not be identified.'
[[ "$(docker inspect --format '{{.Image}}' "$new_container")" == "$expected_id" ]] || fail 'Running app does not match the requested image.'

response="$(timeout 15s docker exec "$new_container" curl \
  --fail --silent --show-error --max-time 5 \
  --write-out '\n%{http_code}' \
  http://127.0.0.1:8080/actuator/health/readiness)"
status_code="${response##*$'\n'}"
response_body="${response%$'\n'*}"
compact_body="$(printf '%s' "$response_body" | tr -d '[:space:]')"
# show-details/show-components=never makes the expected body a single status field.
[[ "$status_code" == 200 && "$compact_body" == '{"status":"UP"}' ]] || fail 'Readiness did not return HTTP 200 with status UP.'

printf '%s\n' "$new_image" > "$state_dir/success-image.txt"
rollback_needed=0
echo "DEPLOY_SUCCESS: $new_image"
