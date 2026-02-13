"""
YouTube video uploader module.

Provides functionality to upload videos to YouTube with metadata.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build

from .auth import authenticate, YouTubeAuthError


class YouTubeUploadError(Exception):
    """Raised when video upload to YouTube fails."""

    pass


class YouTubeUploader:
    """
    YouTube video uploader class.

    Handles authentication and video uploads to YouTube.

    Example:
        >>> uploader = YouTubeUploader()
        >>> uploader.upload_video(
        ...     video_path="/path/to/video.mp4",
        ...     title="My Video Title",
        ...     description="Video description",
        ...     tags=["tag1", "tag2"],
        ...     category_id="22"
        ... )
    """

    # Video category IDs (YouTube standard categories)
    CATEGORIES = {
        "1": "Film & Animation",
        "2": "Autos & Vehicles",
        "10": "Music",
        "15": "Pets & Animals",
        "17": "Sports",
        "19": "Travel & Events",
        "20": "Gaming",
        "22": "People & Blogs",
        "23": "Comedy",
        "24": "Entertainment",
        "25": "News & Politics",
        "26": "Howto & Style",
        "27": "Education",
        "28": "Science & Technology",
        "29": "Nonprofits & Activism",
    }

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        client_secrets_path: Optional[str] = None,
    ):
        """
        Initialize the YouTube uploader.

        Args:
            credentials_path: Path to saved credentials
            client_secrets_path: Path to OAuth client secrets
        """
        self.credentials_path = credentials_path
        self.client_secrets_path = client_secrets_path
        self.youtube = None

    def authenticate(self) -> build:
        """
        Authenticate with YouTube API.

        Returns:
            googleapiclient.discovery.Resource: Authenticated YouTube service

        Raises:
            YouTubeAuthError: If authentication fails
        """
        self.youtube = authenticate(
            credentials_path=self.credentials_path,
            client_secrets_path=self.client_secrets_path,
        )
        return self.youtube

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: Optional[list] = None,
        category_id: str = "27",  # Default: Education
        privacy_status: str = "private",
        notify_subscribers: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Upload a video to YouTube.

        Args:
            video_path: Path to the video file to upload
            title: Video title (max 100 characters)
            description: Video description (max 5000 characters)
            tags: List of tags for the video
            category_id: YouTube category ID (default: 27 - Education)
            privacy_status: 'private', 'public', or 'unlisted'
            notify_subscribers: Whether to notify subscribers
            progress_callback: Optional callback function(bytes_sent, total_bytes)

        Returns:
            dict: API response containing video ID and other metadata

        Raises:
            YouTubeUploadError: If upload fails
            FileNotFoundError: If video file doesn't exist
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Ensure authenticated
        if self.youtube is None:
            self.authenticate()

        # Prepare video metadata
        body = {
            "snippet": {
                "title": title[:100],  # YouTube limit
                "description": description[:5000],  # YouTube limit
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
            },
        }

        if tags:
            body["snippet"]["tags"] = tags

        # Create media upload object
        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)

        # Create upload request
        insert_request = self.youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
            notifySubscribers=notify_subscribers,
        )

        # Execute upload with resumable support
        print(f"[youtube] Starting upload: {title}")
        print(f"[youtube] File: {video_path}")
        print(f"[youtube] Privacy: {privacy_status}")

        response = None
        error = None
        retry = 0
        max_retries = 10

        while response is None:
            try:
                print("[youtube] Uploading...", end="\r")
                status, response = insert_request.next_chunk()

                if status:
                    percent = int(status.progress() * 100)
                    print(f"[youtube] Uploading... {percent}%", end="\r")
                    if progress_callback:
                        progress_callback(status.resumable_progress, status.total_size)

            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    # Server error, retry
                    retry += 1
                    if retry > max_retries:
                        raise YouTubeUploadError(
                            f"Upload failed after {max_retries} retries: {str(e)}"
                        )
                    print(
                        f"[youtube] Server error, retrying ({retry}/{max_retries})..."
                    )
                    time.sleep(2**retry)  # Exponential backoff
                else:
                    raise YouTubeUploadError(f"Upload failed: {str(e)}")
            except Exception as e:
                raise YouTubeUploadError(f"Upload failed: {str(e)}")

        print()  # New line after progress

        if response is None:
            raise YouTubeUploadError("Upload failed: No response from YouTube")

        video_id = response.get("id")
        print(f"[youtube] Upload complete! Video ID: {video_id}")
        print(f"[youtube] URL: https://youtu.be/{video_id}")

        return response

    def upload_with_defaults(
        self,
        video_path: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Upload a video with automatic title/description generation from filename.

        Args:
            video_path: Path to the video file
            title: Optional title (uses filename if not provided)
            description: Optional description
            **kwargs: Additional arguments passed to upload_video()

        Returns:
            dict: API response
        """
        video_path = Path(video_path)

        if title is None:
            # Generate title from filename (remove extension, replace underscores/hyphens)
            title = video_path.stem.replace("_", " ").replace("-", " ").title()

        if description is None:
            description = f"Uploaded from {video_path.name}"

        return self.upload_video(
            video_path=str(video_path), title=title, description=description, **kwargs
        )


def upload_video(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[list] = None,
    category_id: str = "27",
    privacy_status: str = "private",
    credentials_path: Optional[str] = None,
    client_secrets_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to upload a video to YouTube.

    This is a simple wrapper around YouTubeUploader for one-off uploads.

    Args:
        video_path: Path to the video file
        title: Video title
        description: Video description
        tags: List of tags
        category_id: YouTube category ID
        privacy_status: 'private', 'public', or 'unlisted'
        credentials_path: Path to credentials file
        client_secrets_path: Path to client secrets file

    Returns:
        dict: API response with video metadata

    Example:
        >>> response = upload_video(
        ...     "/path/to/video.mp4",
        ...     title="My Video",
        ...     description="A description",
        ...     privacy_status="unlisted"
        ... )
        >>> print(f"Video URL: https://youtu.be/{response['id']}")
    """
    uploader = YouTubeUploader(
        credentials_path=credentials_path,
        client_secrets_path=client_secrets_path,
    )

    return uploader.upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        category_id=category_id,
        privacy_status=privacy_status,
    )
