"""
Google Drive authentication module using PyDrive2.

Handles OAuth2 authentication flow and credential management.
"""

import os
from pathlib import Path
from typing import Optional
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive


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
        gauth.LoadClientConfigFile()

        # Try to load saved credentials
        gauth.LoadCredentialsFile(credentials_path)

        if gauth.credentials is None:
            # No credentials found, start OAuth flow
            print("[poetry-reader] Starting OAuth2 authentication flow...")
            print("[poetry-reader] A browser window will open for authorization.")
            gauth.LocalWebserverAuth()
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
