"""UniFi Protect client wrapper."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from uiprotect import ProtectApiClient
from uiprotect.data import Camera, Event, EventType

from .models import CameraInfo, CameraStatus, MotionEvent

logger = logging.getLogger(__name__)


class UniFiProtectClient:
    """Wrapper around uiprotect library for UniFi Protect API."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        verify_ssl: bool = False,
    ):
        """Initialize UniFi Protect client.

        Args:
            host: UniFi Protect host address
            port: UniFi Protect port
            username: Username for authentication
            password: Password for authentication
            verify_ssl: Whether to verify SSL certificate
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self._client: Optional[ProtectApiClient] = None

    async def connect(self) -> None:
        """Connect to UniFi Protect."""
        try:
            self._client = ProtectApiClient(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                verify_ssl=self.verify_ssl,
            )
            await self._client.update()
            logger.info(f"Connected to UniFi Protect at {self.host}")
        except Exception as e:
            logger.error(f"Failed to connect to UniFi Protect: {e}")
            raise

    async def close(self) -> None:
        """Close connection to UniFi Protect."""
        if self._client:
            await self._client.close()

    def _camera_to_info(self, camera: Camera) -> CameraInfo:
        """Convert uiprotect Camera to CameraInfo model.

        Args:
            camera: Camera object from uiprotect

        Returns:
            CameraInfo model
        """
        # Determine camera status
        status = CameraStatus.ONLINE if camera.is_connected else CameraStatus.OFFLINE

        # Get resolution string
        resolution = None
        if camera.channels and len(camera.channels) > 0:
            channel = camera.channels[0]
            resolution = f"{channel.width}x{channel.height}"

        return CameraInfo(
            id=camera.id,
            name=camera.name,
            status=status,
            is_recording=camera.is_recording,
            motion_detected=camera.is_motion_detected,
            last_motion=camera.last_motion,
            model=camera.type,
            firmware_version=camera.firmware_version,
            resolution=resolution,
        )

    async def get_cameras(self) -> list[CameraInfo]:
        """Get list of all cameras.

        Returns:
            List of CameraInfo objects
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        await self._client.update()
        cameras = self._client.bootstrap.cameras.values()

        return [self._camera_to_info(camera) for camera in cameras]

    async def get_camera_rtsp_url(
        self, camera_id: str, quality: str = "low"
    ) -> Optional[str]:
        """Get RTSP URL for a camera.

        Args:
            camera_id: Camera ID
            quality: Stream quality - "high" (4K H.265), "medium" (1080p H.264),
                     or "low" (720p H.264). Default "low" for Pi compatibility.

        Returns:
            RTSP URL or None if unavailable
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        camera = self._client.bootstrap.cameras.get(camera_id)
        if not camera:
            logger.warning(f"Camera {camera_id} not found")
            return None

        # Channel mapping: 0=high (4K H.265), 1=medium (1080p H.264), 2=low (720p H.264)
        quality_to_channel = {"high": 0, "medium": 1, "low": 2}
        channel_idx = quality_to_channel.get(quality, 1)

        if camera.channels and len(camera.channels) > channel_idx:
            channel = camera.channels[channel_idx]
            logger.info(
                f"Using {quality} quality stream for {camera.name}: "
                f"{channel.width}x{channel.height}"
            )
            return channel.rtsp_url
        elif camera.channels and len(camera.channels) > 0:
            # Fallback: prefer H.264 channels (1, 2) over H.265 (0) for Pi compatibility
            # Try channels in order: 1 (medium H.264), 2 (low H.264), then 0 (high H.265)
            fallback_order = [1, 2, 0]
            for fb_idx in fallback_order:
                if len(camera.channels) > fb_idx:
                    channel = camera.channels[fb_idx]
                    logger.warning(
                        f"Channel {channel_idx} not available for {camera.name}, "
                        f"falling back to channel {fb_idx}: {channel.width}x{channel.height}"
                    )
                    return channel.rtsp_url

        return None

    async def get_recent_motion_events(
        self, hours: int = 24, limit: int = 50
    ) -> list[MotionEvent]:
        """Get recent motion detection events.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of events to return

        Returns:
            List of MotionEvent objects
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        # Calculate start time
        start_time = datetime.now() - timedelta(hours=hours)

        try:
            # Fetch motion events
            # Try with event_types parameter first (older API)
            try:
                events = await self._client.get_events(
                    start=start_time, event_types=[EventType.MOTION]
                )
            except TypeError:
                # Fallback for newer API that doesn't accept event_types
                events = await self._client.get_events(start=start_time)
                # Filter for motion events manually
                events = [e for e in events if e.type == EventType.MOTION]

            motion_events: list[MotionEvent] = []
            for event in events[:limit]:
                if isinstance(event, Event) and event.camera:
                    # Safely get thumbnail_url (may not exist on all Event objects)
                    thumbnail_url = getattr(event, "thumbnail_url", None)
                    motion_event = MotionEvent(
                        camera_id=event.camera.id,
                        camera_name=event.camera.name,
                        timestamp=event.start,
                        thumbnail_url=thumbnail_url,
                        score=event.score,
                    )
                    motion_events.append(motion_event)

            return motion_events

        except Exception as e:
            logger.error(f"Failed to fetch motion events: {e}")
            return []

    async def check_health(self) -> bool:
        """Check if UniFi Protect connection is healthy.

        Returns:
            True if connected and responsive, False otherwise
        """
        try:
            if not self._client:
                return False
            await self._client.update()
            return True
        except Exception:
            return False
