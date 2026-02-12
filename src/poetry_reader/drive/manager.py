"""
Google Drive file management module.

Handles downloading, uploading, and file operations with Google Drive.
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pydrive2.drive import GoogleDrive
from pydrive2.files import GoogleDriveFile


@dataclass
class FileInfo:
    """Information about a file in Google Drive."""

    id: str
    title: str
    mimeType: str
    size: Optional[int] = None
    modifiedDate: Optional[str] = None
    webViewLink: Optional[str] = None


class DriveManagerError(Exception):
    """Raised when Drive operations fail."""

    pass


class DriveManager:
    """
    Manager for Google Drive file operations.

    Handles downloading, uploading, listing, and file management
    with automatic retry logic and error handling.
    """

    def __init__(
        self, drive: GoogleDrive, max_retries: int = 3, retry_delay: float = 5.0
    ):
        """
        Initialize DriveManager.

        Args:
            drive: Authenticated GoogleDrive instance
            max_retries: Maximum number of retry attempts for failed operations
            retry_delay: Delay in seconds between retries
        """
        self.drive = drive
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def list_files_in_folder(
        self,
        folder_id: str,
        mime_type: Optional[str] = None,
        file_extension: Optional[str] = None,
    ) -> List[FileInfo]:
        """
        List all files in a Google Drive folder.

        Args:
            folder_id: Google Drive folder ID
            mime_type: Filter by MIME type (e.g., 'text/markdown')
            file_extension: Filter by file extension (e.g., '.md')

        Returns:
            List of FileInfo objects

        Raises:
            DriveManagerError: If listing fails after retries
        """
        query = f"'{folder_id}' in parents and trashed=false"
        if mime_type:
            query += f" and mimeType='{mime_type}'"

        for attempt in range(self.max_retries):
            try:
                file_list = self.drive.ListFile({"q": query}).GetList()

                files = []
                for f in file_list:
                    # Apply extension filter if specified
                    if file_extension and not f["title"].endswith(file_extension):
                        continue

                    files.append(
                        FileInfo(
                            id=f["id"],
                            title=f["title"],
                            mimeType=f.get("mimeType", "unknown"),
                            size=int(f.get("fileSize", 0)) if "fileSize" in f else None,
                            modifiedDate=f.get("modifiedDate"),
                            webViewLink=f.get("webViewLink"),
                        )
                    )

                return files

            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(
                        f"[poetry-reader] Retry {attempt + 1}/{self.max_retries} after error: {e}"
                    )
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise DriveManagerError(f"Failed to list files: {str(e)}") from e

        return []

    def find_file_by_name(self, folder_id: str, filename: str) -> Optional[FileInfo]:
        """
        Find a file by name in a specific folder.

        Args:
            folder_id: Google Drive folder ID
            filename: Name of the file to find

        Returns:
            FileInfo if found, None otherwise
        """
        try:
            files = self.list_files_in_folder(folder_id)
            for file_info in files:
                if file_info.title == filename:
                    return file_info
            return None
        except Exception:
            return None

    def download_file(self, file_id: str, local_path: str) -> bool:
        """
        Download a file from Google Drive.

        Args:
            file_id: Google Drive file ID
            local_path: Local path where file will be saved

        Returns:
            bool: True if download successful, False otherwise

        Raises:
            DriveManagerError: If download fails after retries
        """
        # Ensure parent directory exists
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(self.max_retries):
            try:
                file = self.drive.CreateFile({"id": file_id})
                file.GetContentFile(local_path)
                print(f"[poetry-reader] ✓ Downloaded: {Path(local_path).name}")
                return True

            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(
                        f"[poetry-reader] Retry {attempt + 1}/{self.max_retries} downloading {file_id}"
                    )
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise DriveManagerError(
                        f"Failed to download file {file_id}: {str(e)}"
                    ) from e

        return False

    def upload_file(
        self, local_path: str, drive_folder_id: str, filename: Optional[str] = None
    ) -> str:
        """
        Upload a file to Google Drive.

        Args:
            local_path: Path to local file to upload
            drive_folder_id: Google Drive folder ID where file will be uploaded
            filename: Optional custom filename (default: use local filename)

        Returns:
            str: Google Drive file ID of uploaded file

        Raises:
            DriveManagerError: If upload fails after retries
        """
        if not os.path.exists(local_path):
            raise DriveManagerError(f"Local file not found: {local_path}")

        if filename is None:
            filename = Path(local_path).name

        for attempt in range(self.max_retries):
            try:
                file = self.drive.CreateFile(
                    {"title": filename, "parents": [{"id": drive_folder_id}]}
                )
                file.SetContentFile(local_path)
                file.Upload()

                file_id = file["id"]
                print(f"[poetry-reader] ✓ Uploaded: {filename} (ID: {file_id})")
                return file_id

            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(
                        f"[poetry-reader] Retry {attempt + 1}/{self.max_retries} uploading {filename}"
                    )
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise DriveManagerError(
                        f"Failed to upload {filename}: {str(e)}"
                    ) from e

        raise DriveManagerError(f"Upload failed after {self.max_retries} attempts")

    def update_file(self, file_id: str, local_path: str) -> bool:
        """
        Update an existing file in Google Drive (replace content).

        Args:
            file_id: Google Drive file ID to update
            local_path: Path to new content

        Returns:
            bool: True if update successful

        Raises:
            DriveManagerError: If update fails after retries
        """
        if not os.path.exists(local_path):
            raise DriveManagerError(f"Local file not found: {local_path}")

        for attempt in range(self.max_retries):
            try:
                file = self.drive.CreateFile({"id": file_id})
                file.SetContentFile(local_path)
                file.Upload()
                print(
                    f"[poetry-reader] ✓ Updated file: {file['title']} (ID: {file_id})"
                )
                return True

            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(
                        f"[poetry-reader] Retry {attempt + 1}/{self.max_retries} updating {file_id}"
                    )
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise DriveManagerError(
                        f"Failed to update file {file_id}: {str(e)}"
                    ) from e

        return False

    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """
        Get metadata for a file in Google Drive.

        Args:
            file_id: Google Drive file ID

        Returns:
            Dict with file metadata

        Raises:
            DriveManagerError: If operation fails
        """
        try:
            file = self.drive.CreateFile({"id": file_id})
            file.FetchMetadata()
            return dict(file)
        except Exception as e:
            raise DriveManagerError(
                f"Failed to get metadata for {file_id}: {str(e)}"
            ) from e

    def file_exists_locally(self, filename: str, local_dir: str) -> bool:
        """
        Check if a file exists locally.

        Args:
            filename: Name of the file
            local_dir: Directory to check

        Returns:
            bool: True if file exists locally
        """
        local_path = Path(local_dir) / filename
        return local_path.exists()

    def get_shareable_link(self, file_id: str) -> str:
        """
        Get a shareable link for a file.

        Args:
            file_id: Google Drive file ID

        Returns:
            str: Shareable link URL

        Raises:
            DriveManagerError: If operation fails
        """
        try:
            file = self.drive.CreateFile({"id": file_id})
            file.FetchMetadata()

            # Make file shareable (anyone with link can view)
            permission = file.InsertPermission(
                {"type": "anyone", "value": "anyone", "role": "reader"}
            )

            return file.get("webViewLink", f"https://drive.google.com/file/d/{file_id}")

        except Exception as e:
            raise DriveManagerError(
                f"Failed to get shareable link for {file_id}: {str(e)}"
            ) from e

    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from Google Drive (move to trash).

        Args:
            file_id: Google Drive file ID

        Returns:
            bool: True if deletion successful

        Raises:
            DriveManagerError: If deletion fails
        """
        try:
            file = self.drive.CreateFile({"id": file_id})
            file.Trash()
            print(f"[poetry-reader] ✓ Deleted file: {file_id}")
            return True
        except Exception as e:
            raise DriveManagerError(f"Failed to delete file {file_id}: {str(e)}") from e

    def download_markdowns_from_folder(
        self, folder_id: str, local_dir: str, filenames: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Download markdown files from a Google Drive folder.

        Args:
            folder_id: Google Drive folder ID containing markdown files
            local_dir: Local directory where files will be saved
            filenames: Optional list of specific filenames to download (if None, downloads all .md files)

        Returns:
            Dict mapping filename to local path

        Raises:
            DriveManagerError: If download fails
        """
        # Ensure local directory exists
        Path(local_dir).mkdir(parents=True, exist_ok=True)

        # List all markdown files in the folder
        md_files = self.list_files_in_folder(folder_id, file_extension=".md")

        if not md_files:
            print(f"[poetry-reader] No markdown files found in folder {folder_id}")
            return {}

        downloaded = {}

        for file_info in md_files:
            filename = file_info.title

            # Skip if specific filenames requested and this isn't one of them
            if filenames and filename not in filenames:
                continue

            local_path = str(Path(local_dir) / filename)

            try:
                self.download_file(file_info.id, local_path)
                downloaded[filename] = local_path
            except Exception as e:
                print(f"[poetry-reader] ✗ Failed to download {filename}: {e}")

        print(f"[poetry-reader] ✓ Downloaded {len(downloaded)} markdown files")
        return downloaded
