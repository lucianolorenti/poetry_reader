"""
YouTube module for poetry-reader.

Provides functionality to upload videos to YouTube.

Example usage:
    >>> from poetry_reader.youtube import YouTubeUploader, upload_video
    >>>
    >>> # Method 1: Using the uploader class
    >>> uploader = YouTubeUploader()
    >>> response = uploader.upload_video(
    ...     video_path="/path/to/video.mp4",
    ...     title="My Video",
    ...     description="A description",
    ...     privacy_status="private"
    ... )
    >>>
    >>> # Method 2: Using the convenience function
    >>> response = upload_video(
    ...     "/path/to/video.mp4",
    ...     title="My Video",
    ...     privacy_status="unlisted"
    ... )

Required setup:
    1. Create a project at https://console.cloud.google.com/
    2. Enable YouTube Data API v3
    3. Create OAuth 2.0 credentials (Desktop app)
    4. Download client_secrets.json and save as:
       ./credentials/youtube_client_secrets.json
    5. Run the upload - it will authenticate on first run

Note:
    Videos are uploaded as 'private' by default for safety.
    Change privacy_status to 'public' or 'unlisted' as needed.
"""

from .auth import authenticate, YouTubeAuthError, validate_authentication
from .uploader import (
    YouTubeUploader,
    YouTubeUploadError,
    upload_video,
)

__all__ = [
    # Authentication
    "authenticate",
    "YouTubeAuthError",
    "validate_authentication",
    # Uploading
    "YouTubeUploader",
    "YouTubeUploadError",
    "upload_video",
]
