"""
Google Drive integration package for Poetry Reader.

This package handles authentication, file management, and Excel tracking
for automated video processing from Google Drive.
"""

from .auth import authenticate
from .manager import DriveManager
from .tracker import ExcelTracker

__all__ = ["authenticate", "DriveManager", "ExcelTracker"]
