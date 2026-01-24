#!/bin/bash
# Polls GitHub every minute, pulls and restarts on changes
# Includes health check - rolls back if deploy fails
set -e

DASHBOARD_DIR="${DASHBOARD_DIR:-${HOME}/dashboard}"
POLL_INTERVAL="${POLL_INTERVAL:-60}"
HEALTH_URL="http://localhost:9753/health"
HEALTH_RETRIES=5
HEALTH_DELAY=3

cd "${DASHBOARD_DIR}"

echo "Starting update loop (polling every ${POLL_INTERVAL}s)..."

while true; do
	# Fetch latest
	git fetch origin main --quiet 2>/dev/null || {
		echo "[$(date '+%H:%M:%S')] Failed to fetch, retrying in ${POLL_INTERVAL}s"
		sleep "${POLL_INTERVAL}"
		continue
	}

	LOCAL=$(git rev-parse HEAD)
	REMOTE=$(git rev-parse origin/main)

	if [[ ${LOCAL} != "${REMOTE}" ]]; then
		echo "[$(date '+%H:%M:%S')] Update found! Deploying..."

		# Save current working commit for rollback
		ROLLBACK_COMMIT="${LOCAL}"

		git pull origin main --quiet

		docker compose down --remove-orphans 2>/dev/null || true
		docker compose build --quiet
		docker compose up -d

		# Health check with retries
		HEALTHY=false
		for i in $(seq 1 "${HEALTH_RETRIES}"); do
			sleep "${HEALTH_DELAY}"
			RESPONSE=$(curl -sf "${HEALTH_URL}" 2>/dev/null) || RESPONSE=""
			if echo "${RESPONSE}" | grep -q '"status":"healthy"'; then
				HEALTHY=true
				break
			fi
			echo "[$(date '+%H:%M:%S')] Health check ${i}/${HEALTH_RETRIES} failed..."
			[[ -n ${RESPONSE} ]] && echo "  Response: ${RESPONSE}"
		done

		if [[ ${HEALTHY} == true ]]; then
			# Trigger browser refresh via WebSocket
			curl -s -X POST "http://localhost:9753/api/trigger-refresh" || true
			echo "[$(date '+%H:%M:%S')] Deploy complete: $(git log -1 --pretty='%s')"
		else
			echo "[$(date '+%H:%M:%S')] Deploy FAILED - rolling back to ${ROLLBACK_COMMIT}"

			git reset --hard "${ROLLBACK_COMMIT}"

			docker compose down --remove-orphans 2>/dev/null || true
			docker compose build --quiet
			docker compose up -d

			echo "[$(date '+%H:%M:%S')] Rolled back to: $(git log -1 --pretty='%s')"
		fi
	fi

	sleep "${POLL_INTERVAL}"
done
