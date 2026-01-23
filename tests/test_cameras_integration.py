"""Tests for cameras integration."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from pydantic import ValidationError

from integrations.cameras.integration import (
    UniFiProtectIntegration,
    UniFiProtectConfig,
)
from integrations.cameras.src.go2rtc_client import Go2RTCClient
from integrations.cameras.src.unifi_protect import UniFiProtectClient
from integrations.cameras.src.models import (
    StreamType,
    CameraInfo,
    CameraStatus,
    MotionEvent,
)
import httpx


class TestUniFiProtectConfig:
    """Tests for UniFiProtectConfig validation."""

    def test_valid_config(self):
        """Test creating valid config."""
        config = UniFiProtectConfig(
            host="https://unifi.example.com",
            username="admin",
            password="password",
        )
        assert config.host == "https://unifi.example.com"
        assert config.username == "admin"
        assert config.password == "password"
        assert config.verify_ssl is False
        assert config.go2rtc_url == "http://go2rtc:1984"
        # go2rtc_external_url defaults to None until validator runs
        assert config.default_stream_type == "webrtc"

    def test_default_external_url_set(self):
        """Test that default external URL is set when None."""
        config = UniFiProtectConfig(
            host="https://unifi.example.com",
            username="admin",
            password="password",
            go2rtc_external_url=None,
        )
        assert config.go2rtc_external_url == "http://localhost:1984"

    def test_custom_external_url_preserved(self):
        """Test that custom external URL is preserved."""
        config = UniFiProtectConfig(
            host="https://unifi.example.com",
            username="admin",
            password="password",
            go2rtc_external_url="https://streaming.example.com",
        )
        assert config.go2rtc_external_url == "https://streaming.example.com"

    def test_missing_required_field(self):
        """Test validation error for missing required field."""
        with pytest.raises(ValidationError):
            UniFiProtectConfig(host="https://unifi.example.com", username="admin")

    def test_api_key_optional(self):
        """Test that API key is optional."""
        config = UniFiProtectConfig(
            host="https://unifi.example.com",
            username="admin",
            password="password",
            api_key=None,
        )
        assert config.api_key is None


class TestGo2RTCClient:
    """Tests for Go2RTCClient."""

    def test_init(self):
        """Test client initialization."""
        client = Go2RTCClient("http://go2rtc:1984", "http://localhost:1984")
        assert client.base_url == "http://go2rtc:1984"
        assert client.external_url == "http://localhost:1984"

    def test_init_strips_trailing_slash(self):
        """Test that trailing slashes are stripped from URLs."""
        client = Go2RTCClient("http://go2rtc:1984/", "http://localhost:1984/")
        assert client.base_url == "http://go2rtc:1984"
        assert client.external_url == "http://localhost:1984"

    def test_init_default_external_url(self):
        """Test default external URL when not provided."""
        client = Go2RTCClient("http://go2rtc:1984")
        assert client.external_url == "http://localhost:1984"

    async def test_close(self):
        """Test client cleanup."""
        client = Go2RTCClient("http://go2rtc:1984")
        with patch.object(client.client, "aclose", new_callable=AsyncMock):
            await client.close()
            client.client.aclose.assert_called_once()

    async def test_register_stream_success(self):
        """Test successful stream registration."""
        client = Go2RTCClient("http://go2rtc:1984")

        with patch.object(
            client.client, "patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_patch.return_value = mock_response

            result = await client.register_stream("camera1", "rtsp://camera.local/stream")

            assert result is True
            mock_patch.assert_called_once_with(
                "http://go2rtc:1984/api/config",
                json={"streams": {"camera1": ["rtsp://camera.local/stream"]}},
            )

    async def test_register_stream_http_status_error(self):
        """Test stream registration with HTTP status error."""
        client = Go2RTCClient("http://go2rtc:1984")

        with patch.object(
            client.client, "patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_patch.side_effect = httpx.HTTPStatusError(
                "Forbidden", request=MagicMock(), response=mock_response
            )

            result = await client.register_stream("camera1", "rtsp://camera.local/stream")

            assert result is False

    async def test_register_stream_http_error(self):
        """Test stream registration with HTTP error."""
        client = Go2RTCClient("http://go2rtc:1984")

        with patch.object(
            client.client, "patch", new_callable=AsyncMock
        ) as mock_patch:
            mock_patch.side_effect = httpx.ConnectError("Connection failed")

            result = await client.register_stream("camera1", "rtsp://camera.local/stream")

            assert result is False

    async def test_get_stream_url_webrtc(self):
        """Test getting WebRTC stream URL."""
        client = Go2RTCClient("http://go2rtc:1984", "http://localhost:1984")

        url = await client.get_stream_url("camera1", StreamType.WEBRTC)

        assert "ws://localhost:1984/api/ws" in url
        assert "src=camera1" in url

    async def test_get_stream_url_mjpeg(self):
        """Test getting MJPEG stream URL."""
        client = Go2RTCClient("http://go2rtc:1984", "http://localhost:1984")

        url = await client.get_stream_url("camera1", StreamType.MJPEG)

        assert "http://localhost:1984/api/stream.mjpeg" in url
        assert "src=camera1" in url

    async def test_get_stream_url_hls(self):
        """Test getting HLS stream URL."""
        client = Go2RTCClient("http://go2rtc:1984", "http://localhost:1984")

        url = await client.get_stream_url("camera1", StreamType.HLS)

        assert "http://localhost:1984/api/stream.m3u8" in url
        assert "src=camera1" in url

    async def test_get_stream_url_with_rtsp_url(self):
        """Test getting stream URL with RTSP URL for direct proxying."""
        client = Go2RTCClient("http://go2rtc:1984", "http://localhost:1984")

        rtsp_url = "rtsp://camera.local/stream"
        url = await client.get_stream_url("camera1", StreamType.WEBRTC, rtsp_url)

        assert "src=" in url
        # RTSP URL should be URL-encoded
        assert "rtsp%3A%2F%2F" in url

    async def test_get_stream_url_https_to_wss(self):
        """Test that HTTPS URLs are converted to WSS for WebRTC."""
        client = Go2RTCClient("http://go2rtc:1984", "https://localhost:1984")

        url = await client.get_stream_url("camera1", StreamType.WEBRTC)

        assert "wss://localhost:1984" in url

    async def test_check_health_success(self):
        """Test health check when go2rtc is healthy."""
        client = Go2RTCClient("http://go2rtc:1984")

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = await client.check_health()

            assert result is True

    async def test_check_health_failure(self):
        """Test health check when go2rtc is down."""
        client = Go2RTCClient("http://go2rtc:1984")

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection failed")

            result = await client.check_health()

            assert result is False

    async def test_list_streams_success(self):
        """Test listing streams successfully."""
        client = Go2RTCClient("http://go2rtc:1984")

        expected_streams = {"camera1": ["rtsp://url1"], "camera2": ["rtsp://url2"]}

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = expected_streams
            mock_get.return_value = mock_response

            result = await client.list_streams()

            assert result == expected_streams

    async def test_list_streams_error(self):
        """Test list_streams returns empty dict on error."""
        client = Go2RTCClient("http://go2rtc:1984")

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection failed")

            result = await client.list_streams()

            assert result == {}


class TestUniFiProtectClient:
    """Tests for UniFiProtectClient."""

    def test_init(self):
        """Test client initialization."""
        client = UniFiProtectClient(
            host="unifi.local",
            port=443,
            username="admin",
            password="password",
            verify_ssl=True,
        )
        assert client.host == "unifi.local"
        assert client.port == 443
        assert client.username == "admin"
        assert client.password == "password"
        assert client.verify_ssl is True
        assert client._client is None

    async def test_connect_success(self):
        """Test successful connection to UniFi Protect."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_api_client = AsyncMock()
        mock_api_client.update = AsyncMock()

        with patch("integrations.cameras.src.unifi_protect.ProtectApiClient") as mock_class:
            mock_class.return_value = mock_api_client
            await client.connect()

            mock_class.assert_called_once_with(
                host="unifi.local",
                port=443,
                username="admin",
                password="password",
                verify_ssl=False,
            )
            mock_api_client.update.assert_called_once()
            assert client._client is mock_api_client

    async def test_connect_failure(self):
        """Test connection failure."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        with patch("integrations.cameras.src.unifi_protect.ProtectApiClient") as mock_class:
            mock_class.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await client.connect()

    async def test_close(self):
        """Test closing connection."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )
        mock_api_client = AsyncMock()
        client._client = mock_api_client

        await client.close()

        mock_api_client.close.assert_called_once()

    async def test_close_without_client(self):
        """Test close when client is None."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )
        # Should not raise error
        await client.close()

    def test_camera_to_info(self):
        """Test converting camera to CameraInfo."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_channel = MagicMock()
        mock_channel.width = 1920
        mock_channel.height = 1080
        mock_channel.rtsp_url = "rtsp://camera.local/stream"

        mock_camera = MagicMock()
        mock_camera.id = "camera-1"
        mock_camera.name = "Front Door"
        mock_camera.is_connected = True
        mock_camera.is_recording = True
        mock_camera.is_motion_detected = False
        mock_camera.last_motion = datetime(2024, 1, 1, 12, 0, 0)
        mock_camera.type = "UVC G3"
        mock_camera.firmware_version = "1.2.3"
        mock_camera.channels = [mock_channel]

        info = client._camera_to_info(mock_camera)

        assert info.id == "camera-1"
        assert info.name == "Front Door"
        assert info.status == CameraStatus.ONLINE
        assert info.is_recording is True
        assert info.motion_detected is False
        assert info.last_motion == datetime(2024, 1, 1, 12, 0, 0)
        assert info.model == "UVC G3"
        assert info.firmware_version == "1.2.3"
        assert info.resolution == "1920x1080"

    def test_camera_to_info_offline(self):
        """Test camera status when offline."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_camera = MagicMock()
        mock_camera.id = "camera-1"
        mock_camera.name = "Offline Camera"
        mock_camera.is_connected = False
        mock_camera.is_recording = False
        mock_camera.is_motion_detected = False
        mock_camera.last_motion = None
        mock_camera.type = "UVC G3"
        mock_camera.firmware_version = "1.2.3"
        mock_camera.channels = []

        info = client._camera_to_info(mock_camera)

        assert info.status == CameraStatus.OFFLINE
        assert info.resolution is None

    async def test_get_cameras(self):
        """Test getting list of cameras."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_channel = MagicMock()
        mock_channel.width = 1920
        mock_channel.height = 1080

        mock_camera = MagicMock()
        mock_camera.id = "camera-1"
        mock_camera.name = "Front Door"
        mock_camera.is_connected = True
        mock_camera.is_recording = True
        mock_camera.is_motion_detected = False
        mock_camera.last_motion = None
        mock_camera.type = "UVC G3"
        mock_camera.firmware_version = "1.2.3"
        mock_camera.channels = [mock_channel]

        mock_api_client = MagicMock()
        mock_api_client.update = AsyncMock()
        mock_api_client.bootstrap.cameras.values.return_value = [mock_camera]
        client._client = mock_api_client

        cameras = await client.get_cameras()

        assert len(cameras) == 1
        assert cameras[0].id == "camera-1"
        assert cameras[0].name == "Front Door"

    async def test_get_cameras_not_connected(self):
        """Test get_cameras raises error when not connected."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.get_cameras()

    async def test_get_camera_rtsp_url(self):
        """Test getting RTSP URL for a camera."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_channel = MagicMock()
        mock_channel.rtsp_url = "rtsp://camera.local/stream"

        mock_camera = MagicMock()
        mock_camera.channels = [mock_channel]

        mock_api_client = MagicMock()
        mock_api_client.bootstrap.cameras.get.return_value = mock_camera
        client._client = mock_api_client

        rtsp_url = await client.get_camera_rtsp_url("camera-1")

        assert rtsp_url == "rtsp://camera.local/stream"
        mock_api_client.bootstrap.cameras.get.assert_called_once_with("camera-1")

    async def test_get_camera_rtsp_url_not_found(self):
        """Test getting RTSP URL for non-existent camera."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_api_client = MagicMock()
        mock_api_client.bootstrap.cameras.get.return_value = None
        client._client = mock_api_client

        rtsp_url = await client.get_camera_rtsp_url("nonexistent")

        assert rtsp_url is None

    async def test_get_camera_rtsp_url_no_channels(self):
        """Test getting RTSP URL when camera has no channels."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_camera = MagicMock()
        mock_camera.channels = []

        mock_api_client = MagicMock()
        mock_api_client.bootstrap.cameras.get.return_value = mock_camera
        client._client = mock_api_client

        rtsp_url = await client.get_camera_rtsp_url("camera-1")

        assert rtsp_url is None

    async def test_get_camera_rtsp_url_not_connected(self):
        """Test get_camera_rtsp_url raises error when not connected."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.get_camera_rtsp_url("camera-1")

    async def test_get_recent_motion_events_with_event_types(self):
        """Test getting recent motion events (older API)."""
        from uiprotect.data import Event

        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_camera = MagicMock()
        mock_camera.id = "camera-1"
        mock_camera.name = "Front Door"

        mock_event = MagicMock(spec=Event)
        mock_event.camera = mock_camera
        mock_event.start = datetime(2024, 1, 1, 12, 0, 0)
        mock_event.thumbnail_url = "https://example.com/thumb.jpg"
        mock_event.score = 85

        mock_api_client = MagicMock()
        mock_api_client.get_events = AsyncMock(return_value=[mock_event])
        client._client = mock_api_client

        with patch("integrations.cameras.src.unifi_protect.isinstance", lambda obj, cls: True if cls.__name__ == "Event" or obj is mock_event else isinstance(obj, cls)):
            events = await client.get_recent_motion_events(hours=6, limit=20)

        assert len(events) == 1
        assert events[0].camera_id == "camera-1"
        assert events[0].camera_name == "Front Door"
        assert events[0].timestamp == datetime(2024, 1, 1, 12, 0, 0)
        assert events[0].thumbnail_url == "https://example.com/thumb.jpg"
        assert events[0].score == 85

    async def test_get_recent_motion_events_fallback_api(self):
        """Test getting recent motion events with fallback API."""
        from uiprotect.data import EventType, Event

        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_camera = MagicMock()
        mock_camera.id = "camera-1"
        mock_camera.name = "Front Door"

        mock_event = MagicMock(spec=Event)
        mock_event.camera = mock_camera
        mock_event.start = datetime(2024, 1, 1, 12, 0, 0)
        mock_event.type = EventType.MOTION
        mock_event.thumbnail_url = "https://example.com/thumb.jpg"
        mock_event.score = 85

        # First call raises TypeError, second call returns events
        mock_api_client = MagicMock()
        mock_api_client.get_events = AsyncMock(
            side_effect=[TypeError("unexpected keyword argument"), [mock_event]]
        )
        client._client = mock_api_client

        with patch("integrations.cameras.src.unifi_protect.isinstance", lambda obj, cls: True if cls.__name__ == "Event" or obj is mock_event else isinstance(obj, cls)):
            events = await client.get_recent_motion_events(hours=6, limit=20)

        assert len(events) == 1

    async def test_get_recent_motion_events_event_without_camera(self):
        """Test that events without camera are filtered out."""
        from uiprotect.data import Event

        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        # Event with no camera
        mock_event = MagicMock(spec=Event)
        mock_event.camera = None
        mock_event.start = datetime(2024, 1, 1, 12, 0, 0)
        mock_event.thumbnail_url = None
        mock_event.score = 0

        mock_api_client = MagicMock()
        mock_api_client.get_events = AsyncMock(return_value=[mock_event])
        client._client = mock_api_client

        with patch("integrations.cameras.src.unifi_protect.isinstance", lambda obj, cls: True if cls.__name__ == "Event" or obj is mock_event else isinstance(obj, cls)):
            events = await client.get_recent_motion_events(hours=6, limit=20)

        # Should be empty since event has no camera
        assert len(events) == 0

    async def test_get_recent_motion_events_error(self):
        """Test get_recent_motion_events returns empty list on error."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_api_client = AsyncMock()
        mock_api_client.get_events = AsyncMock(side_effect=Exception("API Error"))
        client._client = mock_api_client

        events = await client.get_recent_motion_events(hours=6, limit=20)

        assert events == []

    async def test_get_recent_motion_events_not_connected(self):
        """Test get_recent_motion_events raises error when not connected."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.get_recent_motion_events()

    async def test_check_health_success(self):
        """Test health check when UniFi Protect is healthy."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_api_client = AsyncMock()
        mock_api_client.update = AsyncMock()
        client._client = mock_api_client

        result = await client.check_health()

        assert result is True

    async def test_check_health_no_client(self):
        """Test health check returns False when client is None."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        result = await client.check_health()

        assert result is False

    async def test_check_health_error(self):
        """Test health check returns False on error."""
        client = UniFiProtectClient(
            host="unifi.local", port=443, username="admin", password="password"
        )

        mock_api_client = AsyncMock()
        mock_api_client.update = AsyncMock(side_effect=Exception("Update failed"))
        client._client = mock_api_client

        result = await client.check_health()

        assert result is False


class TestUniFiProtectIntegration:
    """Tests for UniFiProtectIntegration."""

    def test_init(self):
        """Test integration initialization."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)

        assert integration.name == "unifi_protect"
        assert integration.display_name == "Cameras"
        assert integration.refresh_interval == 5
        assert integration._unifi_client is None
        assert integration._go2rtc_client is None
        assert integration._initialized is False

    async def test_initialize_clients_success(self):
        """Test successful client initialization."""
        config = {
            "host": "https://unifi.local:443",
            "username": "admin",
            "password": "password",
            "verify_ssl": False,
        }
        integration = UniFiProtectIntegration(config)

        mock_unifi_client = AsyncMock()
        mock_unifi_client.connect = AsyncMock()
        mock_unifi_client.get_cameras = AsyncMock(return_value=[])

        mock_go2rtc_client = AsyncMock()
        mock_go2rtc_client.check_health = AsyncMock(return_value=True)
        mock_go2rtc_client.get_stream_url = AsyncMock(return_value="ws://localhost/stream")

        with patch.object(
            integration, "_UniFiProtectIntegration__unifi_client", mock_unifi_client, create=True
        ):
            with patch("integrations.cameras.integration.UniFiProtectClient") as mock_unifi_class:
                with patch("integrations.cameras.integration.Go2RTCClient") as mock_go2rtc_class:
                    mock_unifi_class.return_value = mock_unifi_client
                    mock_go2rtc_class.return_value = mock_go2rtc_client

                    await integration._initialize_clients()

        assert integration._initialized is True
        mock_unifi_client.connect.assert_called_once()

    async def test_initialize_clients_idempotent(self):
        """Test that initialize_clients doesn't reinitialize."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)
        integration._initialized = True

        mock_unifi = MagicMock()
        integration._unifi_client = mock_unifi

        await integration._initialize_clients()

        # Should return early without reinitializing
        assert integration._unifi_client is mock_unifi

    async def test_register_camera_streams_success(self):
        """Test successful stream registration."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)

        mock_camera = MagicMock()
        mock_camera.id = "camera-1"
        mock_camera.name = "Front Door"

        mock_unifi_client = AsyncMock()
        mock_unifi_client.get_cameras = AsyncMock(return_value=[mock_camera])
        mock_unifi_client.get_camera_rtsp_url = AsyncMock(
            return_value="rtsp://camera.local/stream"
        )

        mock_go2rtc_client = AsyncMock()
        mock_go2rtc_client.register_stream = AsyncMock(return_value=True)

        integration._unifi_client = mock_unifi_client
        integration._go2rtc_client = mock_go2rtc_client

        await integration._register_camera_streams()

        mock_go2rtc_client.register_stream.assert_called_once_with(
            "front_door", "rtsp://camera.local/stream"
        )

    async def test_register_camera_streams_no_rtsp_url(self):
        """Test stream registration when RTSP URL is unavailable."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)

        mock_camera = MagicMock()
        mock_camera.id = "camera-1"
        mock_camera.name = "Offline Camera"

        mock_unifi_client = AsyncMock()
        mock_unifi_client.get_cameras = AsyncMock(return_value=[mock_camera])
        mock_unifi_client.get_camera_rtsp_url = AsyncMock(return_value=None)

        mock_go2rtc_client = AsyncMock()
        mock_go2rtc_client.register_stream = AsyncMock()

        integration._unifi_client = mock_unifi_client
        integration._go2rtc_client = mock_go2rtc_client

        await integration._register_camera_streams()

        mock_go2rtc_client.register_stream.assert_not_called()

    async def test_register_camera_streams_registration_failure(self):
        """Test stream registration when go2rtc registration fails."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)

        mock_camera = MagicMock()
        mock_camera.id = "camera-1"
        mock_camera.name = "Front Door"

        mock_unifi_client = AsyncMock()
        mock_unifi_client.get_cameras = AsyncMock(return_value=[mock_camera])
        mock_unifi_client.get_camera_rtsp_url = AsyncMock(
            return_value="rtsp://camera.local/stream"
        )

        mock_go2rtc_client = AsyncMock()
        mock_go2rtc_client.register_stream = AsyncMock(return_value=False)

        integration._unifi_client = mock_unifi_client
        integration._go2rtc_client = mock_go2rtc_client

        await integration._register_camera_streams()

        # Should not raise, just log warning

    async def test_register_camera_streams_error(self):
        """Test stream registration handles exceptions."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)

        mock_unifi_client = AsyncMock()
        mock_unifi_client.get_cameras = AsyncMock(side_effect=Exception("API Error"))

        integration._unifi_client = mock_unifi_client
        integration._go2rtc_client = AsyncMock()

        await integration._register_camera_streams()

        # Should not raise, just log

    async def test_register_camera_streams_no_clients(self):
        """Test register_camera_streams returns early if no clients."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)

        await integration._register_camera_streams()

        # Should return early without error

    async def test_fetch_data_success(self):
        """Test successful data fetch."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
            "default_stream_type": "webrtc",
        }
        integration = UniFiProtectIntegration(config)

        mock_camera_info = MagicMock()
        mock_camera_info.id = "camera-1"
        mock_camera_info.name = "Front Door"
        mock_camera_info.status.value = "online"
        mock_camera_info.is_recording = True
        mock_camera_info.motion_detected = False
        mock_camera_info.last_motion = None
        mock_camera_info.model = "UVC G3"
        mock_camera_info.firmware_version = "1.2.3"
        mock_camera_info.resolution = "1920x1080"

        mock_unifi_client = AsyncMock()
        mock_unifi_client.get_cameras = AsyncMock(return_value=[mock_camera_info])
        mock_unifi_client.get_recent_motion_events = AsyncMock(return_value=[])

        mock_go2rtc_client = AsyncMock()
        mock_go2rtc_client.get_stream_url = AsyncMock(
            return_value="ws://localhost/stream"
        )

        integration._unifi_client = mock_unifi_client
        integration._go2rtc_client = mock_go2rtc_client
        integration._initialized = True

        data = await integration.fetch_data()

        assert "cameras" in data
        assert "recent_motion_events" in data
        assert len(data["cameras"]) == 1
        assert data["cameras"][0]["name"] == "Front Door"

    async def test_fetch_data_with_motion_events(self):
        """Test fetch_data includes motion events."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)

        mock_camera_info = MagicMock()
        mock_camera_info.id = "camera-1"
        mock_camera_info.name = "Front Door"
        mock_camera_info.status.value = "online"
        mock_camera_info.is_recording = True
        mock_camera_info.motion_detected = True
        mock_camera_info.last_motion = datetime(2024, 1, 1, 12, 0, 0)
        mock_camera_info.model = "UVC G3"
        mock_camera_info.firmware_version = "1.2.3"
        mock_camera_info.resolution = "1920x1080"

        mock_motion_event = MotionEvent(
            camera_id="camera-1",
            camera_name="Front Door",
            timestamp="2024-01-01T12:00:00",
            thumbnail_url="https://example.com/thumb.jpg",
            score=85,
        )

        mock_unifi_client = AsyncMock()
        mock_unifi_client.get_cameras = AsyncMock(return_value=[mock_camera_info])
        mock_unifi_client.get_recent_motion_events = AsyncMock(
            return_value=[mock_motion_event]
        )

        mock_go2rtc_client = AsyncMock()
        mock_go2rtc_client.get_stream_url = AsyncMock(
            return_value="ws://localhost/stream"
        )

        integration._unifi_client = mock_unifi_client
        integration._go2rtc_client = mock_go2rtc_client
        integration._initialized = True

        data = await integration.fetch_data()

        assert len(data["recent_motion_events"]) == 1

    async def test_fetch_data_error(self):
        """Test fetch_data handles errors gracefully."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)

        mock_unifi_client = AsyncMock()
        mock_unifi_client.get_cameras = AsyncMock(side_effect=Exception("API Error"))

        integration._unifi_client = mock_unifi_client
        integration._go2rtc_client = AsyncMock()
        integration._initialized = True

        with pytest.raises(Exception, match="API Error"):
            await integration.fetch_data()

    async def test_fetch_data_clients_not_initialized(self):
        """Test fetch_data raises error if clients not initialized."""
        config = {
            "host": "https://unifi.local",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)
        integration._initialized = True

        # Simulate clients failed to initialize
        integration._unifi_client = None
        integration._go2rtc_client = AsyncMock()

        with pytest.raises(RuntimeError, match="Clients not initialized"):
            await integration.fetch_data()

    async def test_initialize_clients_go2rtc_health_check_failure(self):
        """Test initialization when go2rtc health check fails but continues."""
        import asyncio

        config = {
            "host": "https://unifi.local:443",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)

        mock_unifi_client = AsyncMock()
        mock_unifi_client.connect = AsyncMock()
        mock_unifi_client.get_cameras = AsyncMock(return_value=[])

        mock_go2rtc_client = AsyncMock()
        mock_go2rtc_client.check_health = AsyncMock(return_value=False)

        with patch("integrations.cameras.integration.UniFiProtectClient") as mock_unifi_class:
            with patch("integrations.cameras.integration.Go2RTCClient") as mock_go2rtc_class:
                mock_unifi_class.return_value = mock_unifi_client
                mock_go2rtc_class.return_value = mock_go2rtc_client

                await integration._initialize_clients()

        assert integration._initialized is True

    async def test_initialize_clients_unifi_connect_failure(self):
        """Test initialization fails if UniFi Protect connection fails."""
        config = {
            "host": "https://unifi.local:443",
            "username": "admin",
            "password": "password",
        }
        integration = UniFiProtectIntegration(config)

        mock_unifi_client = AsyncMock()
        mock_unifi_client.connect = AsyncMock(side_effect=Exception("Connection failed"))

        with patch("integrations.cameras.integration.UniFiProtectClient") as mock_unifi_class:
            mock_unifi_class.return_value = mock_unifi_client

            with pytest.raises(Exception, match="Connection failed"):
                await integration._initialize_clients()
