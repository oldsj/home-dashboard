"""Pydantic models for cameras integration."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StreamType(str, Enum):
    """Supported stream types."""

    WEBRTC = "webrtc"
    MJPEG = "mjpeg"
    HLS = "hls"


class CamerasConfig(BaseSettings):
    """Configuration for cameras integration from credentials.yaml."""

    model_config = SettingsConfigDict(
        yaml_file="/app/config/credentials.yaml",
        extra="ignore",
    )

    unifi_host: str = Field(..., description="UniFi Protect host address")
    unifi_port: int = Field(default=443, description="UniFi Protect port")
    unifi_username: str = Field(..., description="UniFi Protect username")
    unifi_password: str = Field(..., description="UniFi Protect password")
    unifi_verify_ssl: bool = Field(default=False, description="Verify SSL certificate")

    go2rtc_url: str = Field(
        default="http://go2rtc:1984", description="Internal go2rtc URL"
    )
    go2rtc_external_url: str = Field(
        ..., description="External go2rtc URL for browser access"
    )
    default_stream_type: StreamType = Field(
        default=StreamType.WEBRTC, description="Default stream type"
    )


class CameraStatus(str, Enum):
    """Camera status."""

    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class MotionEvent(BaseModel):
    """Motion detection event."""

    camera_id: str
    camera_name: str
    timestamp: datetime
    thumbnail_url: Optional[str] = None
    score: Optional[float] = Field(
        default=None, ge=0.0, le=100.0
    )  # UniFi uses 0-100 scale


class CameraInfo(BaseModel):
    """Camera information with stream URLs."""

    id: str
    name: str
    status: CameraStatus
    is_recording: bool
    motion_detected: bool = False
    last_motion: Optional[datetime] = None

    # Stream URLs for different formats
    webrtc_url: Optional[str] = None
    mjpeg_url: Optional[str] = None
    hls_url: Optional[str] = None

    # Camera metadata
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    resolution: Optional[str] = None


class CamerasData(BaseModel):
    """Response data from cameras integration."""

    cameras: list[CameraInfo]
    recent_motion_events: list[MotionEvent] = Field(default_factory=list)
    default_stream_type: StreamType
    go2rtc_external_url: str
    timestamp: datetime = Field(default_factory=datetime.now)
