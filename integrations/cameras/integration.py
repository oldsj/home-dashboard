"""
Cameras integration - UniFi Protect camera feeds with go2rtc streaming.

Connects to UniFi Protect, registers camera streams with go2rtc,
and provides camera info and motion events to the dashboard.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

from dashboard_integration_base import BaseIntegration, IntegrationConfig
from pydantic import Field, field_validator

from .src.go2rtc_client import Go2RTCClient
from .src.models import MotionEvent, StreamType
from .src.unifi_protect import UniFiProtectClient

logger = logging.getLogger(__name__)


class UniFiProtectConfig(IntegrationConfig):
    """Configuration model for UniFi Protect integration."""

    host: str = Field(
        ..., description="UniFi Protect host URL (e.g., https://unifi.example.com)"
    )
    username: str = Field(
        ...,
        description="UniFi Protect username",
        json_schema_extra={"secret": True},  # nosec
    )
    password: str = Field(
        ...,
        description="UniFi Protect password",
        json_schema_extra={"secret": True},  # nosec
    )
    api_key: Optional[str] = Field(
        default=None,
        description="UniFi Protect API key (optional)",
        json_schema_extra={"secret": True},  # nosec
    )
    verify_ssl: bool = Field(default=False, description="Verify SSL certificate")

    go2rtc_url: str = Field(
        default="http://go2rtc:1984", description="Internal go2rtc URL"
    )
    go2rtc_external_url: Optional[str] = Field(
        default=None,
        description="External go2rtc URL for browser access (defaults to http://localhost:1984)",
    )
    default_stream_type: str = Field(
        default="webrtc", description="Default stream type"
    )

    @field_validator("go2rtc_external_url", mode="before")
    @classmethod
    def set_default_external_url(cls, v: Optional[str]) -> str:
        """Set default external URL if not provided."""
        if v is None:
            return "http://localhost:1984"
        return v


class UniFiProtectIntegration(BaseIntegration):
    """
    UniFi Protect cameras integration with go2rtc streaming.

    Fetches camera info and motion events from UniFi Protect,
    registers RTSP streams with go2rtc for web playback.
    """

    name = "unifi_protect"
    display_name = "Cameras"
    refresh_interval = (
        30  # Update every 30 seconds (video is live, only need status updates)
    )

    ConfigModel = UniFiProtectConfig

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize UniFi Protect integration."""
        super().__init__(*args, **kwargs)
        self._unifi_client: Optional[UniFiProtectClient] = None
        self._go2rtc_client: Optional[Go2RTCClient] = None
        self._initialized = False
        self._recent_motion_events: list[MotionEvent] = (
            []
        )  # Cache from WebSocket events

    async def _initialize_clients(self) -> None:
        """Initialize UniFi Protect and go2rtc clients."""
        if self._initialized:
            return

        # Parse host URL to extract hostname and port
        host_url = self.get_config_value("host")
        parsed = urlparse(host_url)
        hostname = parsed.hostname or parsed.path.split(":")[0]
        port = parsed.port or 443

        # Initialize clients
        self._unifi_client = UniFiProtectClient(
            host=hostname,
            port=port,
            username=self.get_config_value("username"),
            password=self.get_config_value("password"),
            verify_ssl=self.get_config_value("verify_ssl", False),
        )

        self._go2rtc_client = Go2RTCClient(
            base_url=self.get_config_value("go2rtc_url", "http://go2rtc:1984"),
            external_url=self.get_config_value("go2rtc_external_url"),
        )

        # Connect to UniFi Protect
        try:
            await self._unifi_client.connect()
            logger.info("Connected to UniFi Protect")
        except Exception as e:
            logger.error(f"Failed to connect to UniFi Protect: {e}")
            raise

        # Wait for go2rtc to be ready
        max_retries = 10
        for i in range(max_retries):
            if await self._go2rtc_client.check_health():
                logger.info("go2rtc is ready")
                break
            logger.info(f"Waiting for go2rtc... ({i + 1}/{max_retries})")
            await asyncio.sleep(2)
        else:
            logger.warning("go2rtc health check failed, continuing anyway")

        # Register camera streams
        await self._register_camera_streams()

        self._initialized = True

    async def _register_camera_streams(self) -> None:
        """Register all camera streams with go2rtc.

        Note: Stream registration may fail if go2rtc config is read-only.
        Cameras will still work using direct RTSP proxying.
        """
        if not self._unifi_client or not self._go2rtc_client:
            return

        try:
            cameras = await self._unifi_client.get_cameras()
            logger.info(f"Found {len(cameras)} cameras")

            registered = 0
            for camera_info in cameras:
                rtsp_url = await self._unifi_client.get_camera_rtsp_url(camera_info.id)
                if rtsp_url:
                    # Use camera name as stream identifier (sanitized)
                    stream_name = camera_info.name.lower().replace(" ", "_")
                    if await self._go2rtc_client.register_stream(stream_name, rtsp_url):
                        registered += 1
                else:
                    logger.warning(f"No RTSP URL for camera {camera_info.name}")

            if registered > 0:
                logger.info(
                    f"Successfully registered {registered}/{len(cameras)} camera streams"
                )
            else:
                logger.info(
                    "No streams registered with go2rtc (will use direct RTSP proxying)"
                )

        except Exception as e:
            logger.warning(
                f"Stream registration failed, will use direct RTSP proxying: {e}"
            )

    async def fetch_data(self) -> dict[str, Any]:
        """
        Fetch camera data from UniFi Protect and generate stream URLs.

        Returns:
            Dict with cameras list, motion events, and stream configuration
        """
        # Initialize clients on first call
        if not self._initialized:
            await self._initialize_clients()

        if not self._unifi_client or not self._go2rtc_client:
            raise RuntimeError("Clients not initialized")

        try:
            # Fetch cameras from UniFi Protect
            cameras = await self._unifi_client.get_cameras()

            # Add stream URLs for each camera
            cameras_data = []
            for camera_info in cameras:
                # Stream name must match go2rtc.yaml config (lowercase, underscores)
                stream_name = camera_info.name.lower().replace(" ", "_")

                # Generate stream URLs using pre-registered stream names from go2rtc.yaml
                # (don't pass RTSP URL - use the configured stream names directly)
                webrtc_url = await self._go2rtc_client.get_stream_url(
                    stream_name, StreamType.WEBRTC
                )
                mjpeg_url = await self._go2rtc_client.get_stream_url(
                    stream_name, StreamType.MJPEG
                )
                hls_url = await self._go2rtc_client.get_stream_url(
                    stream_name, StreamType.HLS
                )

                cameras_data.append(
                    {
                        "id": camera_info.id,
                        "name": camera_info.name,
                        "status": camera_info.status.value,
                        "is_recording": camera_info.is_recording,
                        "motion_detected": camera_info.motion_detected,
                        "last_motion": (
                            camera_info.last_motion.isoformat()
                            if camera_info.last_motion
                            else None
                        ),
                        "model": camera_info.model,
                        "firmware_version": camera_info.firmware_version,
                        "resolution": camera_info.resolution,
                        "webrtc_url": webrtc_url,
                        "mjpeg_url": mjpeg_url,
                        "hls_url": hls_url,
                    }
                )

            # Use cached events from WebSocket if available, otherwise fetch from API
            if not self._recent_motion_events:
                # Initial load - fetch historical events from API
                motion_events = await self._unifi_client.get_recent_motion_events(
                    hours=6, limit=20
                )
                self._recent_motion_events = motion_events
            else:
                # Use real-time cached events from WebSocket
                motion_events = self._recent_motion_events

            motion_events_data = [
                {
                    "camera_id": event.camera_id,
                    "camera_name": event.camera_name,
                    "timestamp": event.timestamp,  # Keep as datetime for template
                    "thumbnail_url": event.thumbnail_url,
                    "score": event.score,
                }
                for event in motion_events
            ]

            return {
                "cameras": cameras_data,
                "recent_motion_events": motion_events_data,
                "default_stream_type": self.get_config_value(
                    "default_stream_type", "webrtc"
                ),
                "go2rtc_external_url": self.get_config_value("go2rtc_external_url"),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error fetching camera data: {e}")
            raise

    async def start_event_stream(self) -> AsyncIterator[dict[str, Any]]:
        """
        Stream camera events from UniFi Protect WebSocket.

        Yields widget data whenever camera status changes or motion is detected.
        """
        # Initialize clients
        if not self._initialized:
            await self._initialize_clients()

        if not self._unifi_client or not self._unifi_client._client:
            raise RuntimeError("Clients not initialized")

        # Yield initial state
        yield await self.fetch_data()

        # Set up event queue for WebSocket messages  # pragma: no cover
        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()  # pragma: no cover

        def websocket_callback(msg: Any) -> None:  # pragma: no cover
            """Handle WebSocket messages from UniFi Protect."""
            # Queue the message for async processing
            try:  # pragma: no cover
                asyncio.create_task(event_queue.put(msg))  # pragma: no cover
            except RuntimeError:  # pragma: no cover
                # Event loop might be closed, ignore
                pass  # pragma: no cover

        # Subscribe to WebSocket updates  # pragma: no cover
        unsubscribe = self._unifi_client._client.subscribe_websocket(
            websocket_callback
        )  # pragma: no cover

        try:  # pragma: no cover - background task infinite loop block
            # Stream events as they arrive (no polling, pure event-driven)
            while True:  # pragma: no cover
                msg = await event_queue.get()

                if not msg:  # pragma: no cover
                    continue

                # Skip heartbeats/pings - no need to re-render
                action = getattr(msg, "action", None)
                if action in ("ping", "heartbeat"):  # pragma: no cover
                    continue

                # Extract the updated object from WebSocket message
                new_obj = getattr(msg, "new_obj", None)
                obj_type = type(new_obj).__name__ if new_obj else None

                # If this is a motion event, add it to our cache
                if obj_type == "Event" and new_obj:  # pragma: no cover
                    # Check if it's a motion event
                    from uiprotect.data.types import EventType

                    if (  # pragma: no cover
                        hasattr(new_obj, "type")
                        and new_obj.type == EventType.MOTION
                        and hasattr(new_obj, "camera")
                        and new_obj.camera
                    ):
                        # Create MotionEvent from the WebSocket event
                        motion_event = MotionEvent(
                            camera_id=new_obj.camera.id,
                            camera_name=new_obj.camera.name,
                            timestamp=new_obj.start,
                            thumbnail_url=getattr(new_obj, "thumbnail_url", None),
                            score=new_obj.score,
                        )

                        # Add to cache, keeping most recent 20 events
                        self._recent_motion_events.insert(0, motion_event)
                        self._recent_motion_events = self._recent_motion_events[:20]

                        logger.info(
                            f"Motion event captured: {motion_event.camera_name} "
                            f"at {motion_event.timestamp.strftime('%I:%M:%S %p')}"
                        )

                # Only update if this was a Camera or Event change (not NVR/Bridge updates)
                if obj_type in ("Camera", "Event"):  # pragma: no cover
                    yield await self.fetch_data()

        finally:  # pragma: no cover
            # Clean up subscription
            unsubscribe()
