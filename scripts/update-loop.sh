#!/bin/bash
# Polls GitHub and pulls changes - watch mode handles sync/restart
# Includes health check - rolls back if deploy fails
set -e

DASHBOARD_DIR="${DASHBOARD_DIR:-${HOME}/dashboard}"
BRANCH="${BRANCH:-dev}"
POLL_INTERVAL="${POLL_INTERVAL:-60}"
HEALTH_URL="http://localhost:9753/health"
HEALTH_RETRIES=15
HEALTH_DELAY=4
# Initial delay after pull to let watch mode sync files and restart containers
SYNC_DELAY=10

cd "${DASHBOARD_DIR}"

echo "Starting update loop (polling every ${POLL_INTERVAL}s, watch mode)..."

while true; do
	# Fetch latest
	git fetch origin "${BRANCH}" --quiet 2>/dev/null || {
		echo "[$(date '+%H:%M:%S')] Failed to fetch, retrying in ${POLL_INTERVAL}s"
		sleep "${POLL_INTERVAL}"
		continue
	}

	LOCAL=$(git rev-parse HEAD)
	REMOTE=$(git rev-parse origin/"${BRANCH}")

	if [[ ${LOCAL} != "${REMOTE}" ]]; then
		echo "[$(date '+%H:%M:%S')] Update found! Pulling..."

		# Save current working commit for rollback
		ROLLBACK_COMMIT="${LOCAL}"

		git reset --hard origin/"${BRANCH}"

		# Watch mode detects file changes and syncs/restarts automatically
		# Wait for sync to complete before health checking
		echo "[$(date '+%H:%M:%S')] Waiting for watch mode to sync..."
		sleep "${SYNC_DELAY}"

		# Health check with retries
		HEALTHY=false
		for i in $(seq 1 "${HEALTH_RETRIES}"); do
			RESPONSE=$(curl -sf "${HEALTH_URL}" 2>/dev/null) || RESPONSE=""
			if echo "${RESPONSE}" | grep -q '"status":"healthy"'; then
				HEALTHY=true
				break
			fi
			echo "[$(date '+%H:%M:%S')] Health check ${i}/${HEALTH_RETRIES} waiting..."
			sleep "${HEALTH_DELAY}"
		done

		if [[ ${HEALTHY} == true ]]; then
			# Trigger browser refresh via WebSocket
			curl -s -X POST "http://localhost:9753/api/trigger-refresh" || true
			echo "[$(date '+%H:%M:%S')] Deploy complete: $(git log -1 --pretty='%s')"
		else
			echo "[$(date '+%H:%M:%S')] Deploy FAILED - rolling back to ${ROLLBACK_COMMIT}"

			# Reset git - watch mode will sync the reverted files
			git reset --hard "${ROLLBACK_COMMIT}"

			echo "[$(date '+%H:%M:%S')] Waiting for rollback sync..."
			sleep "${SYNC_DELAY}"

			echo "[$(date '+%H:%M:%S')] Rolled back to: $(git log -1 --pretty='%s')"
		fi
	fi

	sleep "${POLL_INTERVAL}"
done
