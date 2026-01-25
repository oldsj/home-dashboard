"""Client for go2rtc streaming service."""

import logging
from typing import Optional
from urllib.parse import quote

import httpx

from .models import StreamType

logger = logging.getLogger(__name__)


class Go2RTCClient:
    """Client for interacting with go2rtc API."""

    def __init__(self, base_url: str, external_url: Optional[str] = None):
        """Initialize go2rtc client.

        Args:
            base_url: Internal go2rtc URL (e.g., http://go2rtc:1984)
            external_url: External go2rtc URL for browser access (defaults to http://localhost:1984)
        """
        self.base_url = base_url.rstrip("/")
        self.external_url = (external_url or "http://localhost:1984").rstrip("/")
        self.client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()

    async def register_stream(self, camera_name: str, rtsp_url: str) -> bool:
        """Register an RTSP stream with go2rtc.

        Args:
            camera_name: Unique camera identifier
            rtsp_url: RTSP stream URL

        Returns:
            True if registration successful, False otherwise
        """
        try:
            # go2rtc API: PATCH /api/config with streams configuration
            # Note: This may fail if go2rtc config is read-only or has issues
            # Streams can still work via direct RTSP URLs even if registration fails
            config = {"streams": {camera_name: [rtsp_url]}}

            response = await self.client.patch(
                f"{self.base_url}/api/config", json=config
            )
            response.raise_for_status()

            logger.info(f"Registered stream for camera: {camera_name}")
            return True

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"Could not register stream for {camera_name} (go2rtc config may be read-only): {e.response.status_code}"
            )
            return False
        except httpx.HTTPError as e:
            logger.warning(f"Failed to register stream for {camera_name}: {e}")
            return False

    async def get_stream_url(
        self, camera_name: str, stream_type: StreamType, rtsp_url: Optional[str] = None
    ) -> Optional[str]:
        """Get playback URL for a camera stream.

        Args:
            camera_name: Camera identifier (used if stream is pre-registered)
            stream_type: Type of stream (webrtc, mjpeg, hls)
            rtsp_url: Optional RTSP URL for direct proxying (if stream not registered)

        Returns:
            Stream URL or None if unavailable
        """
        # go2rtc can either use pre-registered streams or proxy directly from RTSP
        # If rtsp_url is provided, use direct proxying: ?src={rtsp_url}
        # Otherwise, use registered stream name: ?src={camera_name}

        src = rtsp_url if rtsp_url else camera_name
        # URL-encode the src parameter (RTSP URLs contain special characters)
        encoded_src = quote(src, safe="")

        # Convert http(s):// to ws(s):// for WebSocket URL
        ws_url = self.external_url.replace("https://", "wss://").replace(
            "http://", "ws://"
        )

        url_patterns = {
            StreamType.WEBRTC: f"{ws_url}/api/ws?src={encoded_src}",
            StreamType.MJPEG: f"{self.external_url}/api/stream.mjpeg?src={encoded_src}",
            StreamType.HLS: f"{self.external_url}/api/stream.m3u8?src={encoded_src}",
        }

        return url_patterns.get(stream_type)

    async def check_health(self) -> bool:
        """Check if go2rtc is healthy and responding.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/streams")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def restart(self) -> bool:
        """Restart go2rtc to apply config changes.

        Returns:
            True if restart triggered (connection drop is expected)
        """
        try:
            response = await self.client.post(f"{self.base_url}/api/restart")
            return response.status_code == 200
        except httpx.RemoteProtocolError:
            # Connection drop is expected when go2rtc restarts
            logger.info("go2rtc restart triggered (connection closed as expected)")
            return True
        except httpx.HTTPError as e:
            logger.warning(f"Failed to restart go2rtc: {e}")
            return False

    async def list_streams(self) -> dict[str, list[str]]:
        """List all registered streams.

        Returns:
            Dictionary mapping camera names to stream URLs
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/streams")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to list streams: {e}")
            return {}
