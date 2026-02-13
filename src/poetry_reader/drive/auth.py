"""
Google Drive authentication module using PyDrive2.

Handles OAuth2 authentication flow and credential management.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.client import OAuth2Credentials


class DriveAuthError(Exception):
    """Raised when authentication with Google Drive fails."""

    pass


def authenticate(
    credentials_path: Optional[str] = None,
    client_secrets_path: Optional[str] = None,
    settings_file: Optional[str] = None,
) -> GoogleDrive:
    """
    Authenticate with Google Drive and return a GoogleDrive instance.

    Authentication flow:
    1. Try to load existing credentials from credentials_path
    2. If credentials don't exist or are invalid, start OAuth2 flow
    3. Save credentials for future use
    4. Return authenticated GoogleDrive instance

    Args:
        credentials_path: Path to save/load credentials.json (default: ./credentials/credentials.json)
        client_secrets_path: Path to client_secrets.json (default: ./credentials/client_secrets.json)
        settings_file: Path to PyDrive settings file (default: auto-generated)

    Returns:
        GoogleDrive: Authenticated GoogleDrive instance

    Raises:
        DriveAuthError: If authentication fails or client_secrets.json not found

    Example:
        >>> drive = authenticate()
        >>> files = drive.ListFile({'q': "'root' in parents"}).GetList()
    """
    # Default paths (convert to absolute)
    if credentials_path is None:
        credentials_path = "./credentials/credentials.json"
    if client_secrets_path is None:
        client_secrets_path = "./credentials/client_secrets.json"

    # Convert to absolute paths
    credentials_path = str(Path(credentials_path).resolve())
    client_secrets_path = str(Path(client_secrets_path).resolve())

    # Ensure credentials directory exists
    cred_dir = Path(credentials_path).parent
    cred_dir.mkdir(parents=True, exist_ok=True)

    # Check if client_secrets.json exists

    if not os.path.exists(client_secrets_path):
        raise DriveAuthError(
            f"client_secrets.json not found at: {client_secrets_path}\n\n"
            "To get started:\n"
            "1. Go to https://console.cloud.google.com/\n"
            "2. Create a new project or select existing one\n"
            "3. Enable Google Drive API\n"
            "4. Create OAuth 2.0 credentials (Desktop app)\n"
            "5. Download client_secrets.json\n"
            "6. Place it at: ./credentials/client_secrets.json"
        )

    # Create settings for PyDrive2
    if settings_file is None:
        # Generate temporary settings
        settings_file = str((cred_dir / "settings.yaml").resolve())
        _create_settings_file(settings_file, client_secrets_path, credentials_path)
    else:
        settings_file = str(Path(settings_file).resolve())

    try:
        # Initialize GoogleAuth
        gauth = GoogleAuth(settings_file=settings_file)

        # Load client configuration from client_secrets.json
        gauth.LoadClientConfigFile(client_secrets_path)

        # Try to load saved credentials
        gauth.LoadCredentialsFile(credentials_path)

        if gauth.credentials is None:
            # No credentials found, start OAuth flow
            print("[poetry-reader] Starting OAuth2 Authorization Code flow...")
            print()

            # Get client config
            client_id = gauth.client_config["client_id"]
            client_secret = gauth.client_config["client_secret"]
            scopes = [
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/drive.file",
            ]

            # Generate authorization URL
            import secrets

            state = secrets.token_urlsafe(32)

            auth_params = {
                "client_id": client_id,
                "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                "scope": " ".join(scopes),
                "response_type": "code",
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }

            auth_url = (
                "https://accounts.google.com/o/oauth2/v2/auth?"
                + urllib.parse.urlencode(auth_params)
            )

            # Show instructions
            print("=" * 70)
            print("AUTHENTICATION REQUIRED")
            print("=" * 70)
            print()
            print("Since this is a remote server, please follow these steps:")
            print()
            print("1. Copy this URL and open it in your local browser:")
            print(f"   {auth_url}")
            print()
            print("2. Sign in with your Google account and authorize the app")
            print()
            print("3. Google will show you an authorization code")
            print("   (starts with something like '4/...')")
            print()
            print("4. Copy that code and paste it below:")
            print("=" * 70)
            print()

            # Get authorization code from user
            auth_code = input("Enter authorization code: ").strip()

            if not auth_code:
                raise DriveAuthError("No authorization code provided")

            # Exchange code for tokens
            print("[poetry-reader] Exchanging code for tokens...")

            token_data = urllib.parse.urlencode(
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": auth_code,
                    "grant_type": "authorization_code",
                    "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                }
            ).encode("utf-8")

            token_req = urllib.request.Request(
                "https://oauth2.googleapis.com/token",
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )

            with urllib.request.urlopen(token_req) as response:
                token_response = json.loads(response.read().decode("utf-8"))

            # Success! Create OAuth2Credentials object
            import datetime

            token_expiry = datetime.datetime.utcnow() + datetime.timedelta(
                seconds=token_response["expires_in"]
            )

            gauth.credentials = OAuth2Credentials(
                access_token=token_response["access_token"],
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=token_response.get("refresh_token"),
                token_expiry=token_expiry,
                token_uri="https://oauth2.googleapis.com/token",
                user_agent="poetry-reader/1.0",
                scopes=scopes,
            )

            print("[poetry-reader] ✓ Authenticated successfully!")
        elif gauth.access_token_expired:
            # Credentials expired, refresh
            print("[poetry-reader] Refreshing expired access token...")
            gauth.Refresh()
        else:
            # Credentials valid, authorize
            gauth.Authorize()

        # Save credentials for next run
        gauth.SaveCredentialsFile(credentials_path)
        print(f"[poetry-reader] ✓ Authenticated successfully")

        # Create and return GoogleDrive instance
        drive = GoogleDrive(gauth)
        return drive

    except Exception as e:
        raise DriveAuthError(f"Authentication failed: {str(e)}") from e


def _create_settings_file(
    settings_path: str, client_secrets_path: str, credentials_path: str
) -> None:
    """
    Create a PyDrive2 settings.yaml file with OAuth2 configuration.

    Args:
        settings_path: Where to save settings.yaml
        client_secrets_path: Path to client_secrets.json
        credentials_path: Path where credentials will be saved
    """
    # Ensure absolute paths in settings file
    settings_path = str(Path(settings_path).resolve())
    client_secrets_path = str(Path(client_secrets_path).resolve())
    credentials_path = str(Path(credentials_path).resolve())

    settings_content = f"""client_config_backend: file
client_config_file: {client_secrets_path}

save_credentials: True
save_credentials_backend: file
save_credentials_file: {credentials_path}

get_refresh_token: True

oauth_scope:
  - https://www.googleapis.com/auth/drive
  - https://www.googleapis.com/auth/drive.file
"""

    with open(settings_path, "w") as f:
        f.write(settings_content)


def validate_authentication(drive: GoogleDrive) -> bool:
    """
    Test if the GoogleDrive instance is properly authenticated.

    Args:
        drive: GoogleDrive instance to validate

    Returns:
        bool: True if authentication is valid, False otherwise
    """
    try:
        # Try to list files in root (minimal API call)
        drive.ListFile({"q": "'root' in parents", "maxResults": 1}).GetList()
        return True
    except Exception:
        return False
