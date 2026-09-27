#!/usr/bin/env bash
# Run on backend-agent: bash infra/jenkins/deploy-keyfin-pay.sh "$KEYFIN_PAY_IMAGE"
# Replaces only the keyfin-pay service of the existing keyfin-prod stack.
set +x
set -Eeuo pipefail
umask 077

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ $# -eq 1 ]] || fail 'Usage: deploy-keyfin-pay.sh keyfin-pay:ci-BUILD-COMMIT'
new_image="$1"
[[ "$new_image" =~ ^keyfin-pay:ci-[0-9]+-[0-9a-f]{12,40}$ ]] || fail 'Invalid deployment image tag.'

config_dir="${KEYFIN_DEPLOY_CONFIG_DIR:-/home/ubuntu/keyfin-deploy}"
state_root="${KEYFIN_DEPLOY_STATE_ROOT:-/home/jenkins/agent/deploy-state/keyfin-pay}"
env_file="$config_dir/.env"

test -r "$env_file" || fail 'Deployment environment file is not readable.'
test -r "$config_dir/compose.prod.yml" || fail 'Deployment Compose file is not readable.'
expected_id="$(docker image inspect --format '{{.Id}}' "$new_image")"
[[ -n "$expected_id" ]] || fail 'Deployment image was not found locally.'

mkdir -p "$state_root"
state_dir="$state_root/${new_image##*:}"
# Reserve the directory before tagging, so a retry cannot overwrite its rollback image.
mkdir "$state_dir" || fail 'Recovery state already exists; use a new Jenkins build number.'
cp "$config_dir/compose.prod.yml" "$state_dir/base.yml"

# Compose interpolates every service, so the backend's required variable needs a value even
# though this deployment only acts on keyfin-pay. Reuse whatever the app container runs now.
app_container="$(docker ps -q \
  --filter label=com.docker.compose.project=keyfin-prod \
  --filter label=com.docker.compose.service=app)"
current_app_image=''
if [[ -n "$app_container" && "$app_container" != *$'\n'* ]]; then
  current_app_image="$(docker inspect --format '{{.Config.Image}}' "$app_container")"
fi
[[ -n "$current_app_image" ]] || fail 'Running backend app image could not be identified.'

compose_with() {
  local selected_image="$1"
  shift

  APP_IMAGE="$current_app_image" KEYFIN_PAY_IMAGE="$selected_image" timeout 240s docker compose \
    -p keyfin-prod \
    --env-file "$env_file" \
    -f "$state_dir/base.yml" "$@"
}

# The previous container is optional: the first deployment has nothing to roll back to.
old_container="$(docker ps -aq \
  --filter label=com.docker.compose.project=keyfin-prod \
  --filter label=com.docker.compose.service=keyfin-pay)"
[[ "$old_container" != *$'\n'* ]] || fail 'Expected at most one existing keyfin-pay container.'

rollback_image=''
if [[ -n "$old_container" ]]; then
  old_id="$(docker inspect --format '{{.Image}}' "$old_container")"
  [[ -n "$old_id" ]] || fail 'Existing keyfin-pay image could not be identified.'
  rollback_image="keyfin-pay:rollback-${new_image##*:}"
  docker image tag "$old_id" "$rollback_image"
  printf '%s\n' "$rollback_image" > "$state_dir/rollback-image.txt"
  printf '%s\n' "$old_id" > "$state_dir/rollback-image-id.txt"
  compose_with "$rollback_image" config --quiet
else
  echo 'No existing keyfin-pay container; deploying without a rollback target.'
fi

compose_with "$new_image" config --quiet
echo "Recovery state: $state_dir"

rollback_needed=0
finish() {
  local result=$?
  local restored_container
  trap - EXIT INT TERM

  if [[ "$rollback_needed" -eq 1 ]]; then
    [[ "$result" -ne 0 ]] || result=1

    if [[ -z "$rollback_image" ]]; then
      echo "Deployment failed and no rollback target exists. Recovery state: $state_dir" >&2
      exit "$result"
    fi

    echo 'Deployment failed. Restoring the previous image.'
    if compose_with "$rollback_image" \
      up -d --no-deps --no-build --pull never --wait --wait-timeout 120 keyfin-pay \
      && restored_container="$(compose_with "$rollback_image" ps -q keyfin-pay)" \
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
compose_with "$new_image" \
  up -d --no-deps --no-build --pull never --wait --wait-timeout 120 keyfin-pay

new_container="$(compose_with "$new_image" ps -q keyfin-pay)"
[[ -n "$new_container" && "$new_container" != *$'\n'* ]] || fail 'New keyfin-pay container could not be identified.'
[[ "$(docker inspect --format '{{.Image}}' "$new_container")" == "$expected_id" ]] || fail 'Running keyfin-pay does not match the requested image.'

# busybox wget: node:22-alpine ships no curl.
response="$(timeout 15s docker exec "$new_container" \
  wget -q -O - -T 5 http://127.0.0.1:4100/healthz)"
[[ "$(printf '%s' "$response" | tr -d '[:space:]')" == '{"status":"UP"}' ]] \
  || fail 'Health check did not return status UP.'

printf '%s\n' "$new_image" > "$state_dir/success-image.txt"
rollback_needed=0
echo "DEPLOY_SUCCESS: $new_image"
