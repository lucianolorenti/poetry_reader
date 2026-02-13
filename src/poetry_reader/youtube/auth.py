"""
YouTube upload module using Google YouTube Data API v3.

Handles OAuth2 authentication and video uploads to YouTube.
"""

import os
import sys
import json
import httplib2
from pathlib import Path
from typing import Optional, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow


class YouTubeAuthError(Exception):
    """Raised when authentication with YouTube fails."""

    pass


class YouTubeUploadError(Exception):
    """Raised when video upload to YouTube fails."""

    pass


# OAuth2 scopes required for YouTube upload
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"


def authenticate(
    credentials_path: Optional[str] = None,
    client_secrets_path: Optional[str] = None,
) -> build:
    """
    Authenticate with YouTube and return a YouTube API service instance.

    Authentication flow:
    1. Try to load existing credentials from credentials_path
    2. If credentials don't exist or are invalid, start OAuth2 flow
    3. Save credentials for future use
    4. Return authenticated YouTube API service

    Args:
        credentials_path: Path to save/load youtube_credentials.json
                         (default: ./credentials/youtube_credentials.json)
        client_secrets_path: Path to client_secrets.json
                            (default: ./credentials/youtube_client_secrets.json)

    Returns:
        googleapiclient.discovery.Resource: Authenticated YouTube API service

    Raises:
        YouTubeAuthError: If authentication fails or client_secrets.json not found

    Example:
        >>> youtube = authenticate()
        >>> response = youtube.videos().insert(...).execute()
    """
    # Default paths (convert to absolute)
    if credentials_path is None:
        credentials_path = "./credentials/youtube_credentials.json"
    if client_secrets_path is None:
        client_secrets_path = "./credentials/youtube_client_secrets.json"

    # Convert to absolute paths
    credentials_path = str(Path(credentials_path).resolve())
    client_secrets_path = str(Path(client_secrets_path).resolve())

    # Ensure credentials directory exists
    cred_dir = Path(credentials_path).parent
    cred_dir.mkdir(parents=True, exist_ok=True)

    # Check if client_secrets.json exists
    if not os.path.exists(client_secrets_path):
        raise YouTubeAuthError(
            f"youtube_client_secrets.json not found at: {client_secrets_path}\n\n"
            "To get started:\n"
            "1. Go to https://console.cloud.google.com/\n"
            "2. Create a new project or select existing one\n"
            "3. Enable YouTube Data API v3\n"
            "4. Create OAuth 2.0 credentials (Desktop app)\n"
            "5. Download client_secrets.json\n"
            "6. Place it at: ./credentials/youtube_client_secrets.json"
        )

    creds = None

    # Load existing credentials if available
    if os.path.exists(credentials_path):
        try:
            creds = Credentials.from_authorized_user_file(
                credentials_path, [YOUTUBE_UPLOAD_SCOPE, YOUTUBE_READONLY_SCOPE]
            )
        except Exception as e:
            print(f"[youtube] Warning: Could not load credentials: {e}")

    # If no valid credentials, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[youtube] Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("[youtube] Starting OAuth2 flow...")
            print()
            print("=" * 70)
            print("YOUTUBE AUTHENTICATION REQUIRED")
            print("=" * 70)
            print()
            print("A browser window will open for you to authorize the application.")
            print("If running on a remote server, you may need to copy the URL")
            print("and open it locally.")
            print()

            try:
                flow = Flow.from_client_secrets_file(
                    client_secrets_path,
                    scopes=[YOUTUBE_UPLOAD_SCOPE, YOUTUBE_READONLY_SCOPE],
                )

                # For desktop app, use local server
                flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

                # Run console flow for remote servers
                auth_url, _ = flow.authorization_url(
                    prompt="consent", access_type="offline"
                )

                print("Please visit this URL to authorize this application:")
                print(f"  {auth_url}")
                print()

                # Get authorization code from user
                code = input("Enter the authorization code: ").strip()

                if not code:
                    raise YouTubeAuthError("No authorization code provided")

                flow.fetch_token(code=code)
                creds = flow.credentials

            except Exception as e:
                raise YouTubeAuthError(f"OAuth flow failed: {str(e)}") from e

        # Save credentials for next run
        if creds:
            creds_data = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes,
            }
            with open(credentials_path, "w") as f:
                json.dump(creds_data, f)
            print(f"[youtube] Credentials saved to {credentials_path}")

    # Build and return YouTube service
    try:
        youtube = build("youtube", "v3", credentials=creds)
        print("[youtube] Successfully authenticated with YouTube API")
        return youtube
    except Exception as e:
        raise YouTubeAuthError(f"Failed to build YouTube service: {str(e)}") from e


def validate_authentication(youtube: build) -> bool:
    """
    Test if the YouTube service is properly authenticated.

    Args:
        youtube: YouTube API service instance to validate

    Returns:
        bool: True if authentication is valid, False otherwise
    """
    try:
        # Try to get channel info (minimal API call)
        youtube.channels().list(part="snippet", mine=True).execute()
        return True
    except Exception:
        return False
