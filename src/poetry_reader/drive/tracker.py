"""
Excel tracker module for managing video processing state.

Handles loading, updating, and saving the Excel file that tracks
which markdowns have been processed into videos.
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any


class TrackerError(Exception):
    """Raised when tracker operations fail."""

    pass


class ExcelTracker:
    """
    Manager for Excel tracking file.

    The Excel file tracks which markdowns have been processed into videos.
    Markdown files are stored in Google Drive and downloaded when needed.

    Expected columns:
    - Archivo: Name of the markdown file (e.g., "poema1.md")
    - Hecho: Boolean or "Sí"/"No" - whether processed
    """

    REQUIRED_COLUMNS = ["Archivo", "Hecho"]
    OPTIONAL_COLUMNS = ["video_drive_id", "fecha_procesado", "error"]

    def __init__(self, excel_path: str):
        """
        Initialize ExcelTracker.

        Args:
            excel_path: Path to Excel file (.xlsx)
        """
        self.excel_path = excel_path
        self.df: Optional[pd.DataFrame] = None
        self._original_df: Optional[pd.DataFrame] = None

    def load(self) -> pd.DataFrame:
        """
        Load Excel file into DataFrame.

        Returns:
            pd.DataFrame: Loaded data

        Raises:
            TrackerError: If file not found or invalid format
        """
        if not Path(self.excel_path).exists():
            raise TrackerError(f"Excel file not found: {self.excel_path}")

        try:
            self.df = pd.read_excel(self.excel_path)
            self._original_df = self.df.copy()

            # Validate structure
            if not self.validate_structure():
                missing = set(self.REQUIRED_COLUMNS) - set(self.df.columns)
                raise TrackerError(
                    f"Excel missing required columns: {missing}\n"
                    f"Required: {self.REQUIRED_COLUMNS}\n"
                    f"Found: {list(self.df.columns)}"
                )

            # Add optional columns if they don't exist
            for col in self.OPTIONAL_COLUMNS:
                if col not in self.df.columns:
                    # Use object dtype for string columns to avoid float conversion issues
                    if col == "video_drive_id":
                        self.df[col] = pd.Series(dtype="object")
                    else:
                        self.df[col] = None

            # Ensure video_drive_id is always object dtype (not float64)
            # This prevents errors when assigning string IDs
            if "video_drive_id" in self.df.columns:
                self.df["video_drive_id"] = self.df["video_drive_id"].astype("object")

            # Normalize 'Hecho' column to boolean
            self._normalize_hecho_column()

            print(
                f"[poetry-reader] ✓ Excel loaded: {len(self.df)} rows, "
                f"{self._count_pending()} pending"
            )

            return self.df

        except Exception as e:
            raise TrackerError(f"Failed to load Excel: {str(e)}") from e

    def validate_structure(self) -> bool:
        """
        Validate that Excel has required columns.

        Returns:
            bool: True if structure is valid
        """
        if self.df is None:
            return False
        return all(col in self.df.columns for col in self.REQUIRED_COLUMNS)

    def _normalize_hecho_column(self) -> None:
        """
        Normalize 'Hecho' column to boolean values.

        Handles various input formats:
        - True/False
        - "Sí"/"No"
        - "Yes"/"No"
        - 1/0
        - Empty/NaN (treated as False)
        """
        if self.df is None:
            return

        def to_bool(value):
            if pd.isna(value):
                return False
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                value_lower = value.strip().lower()
                return value_lower in ("sí", "si", "yes", "true", "1", "hecho")
            return False

        self.df["Hecho"] = self.df["Hecho"].apply(to_bool)

    def get_pending_files(self) -> List[Dict[str, Any]]:
        """
        Get list of markdown files that haven't been processed yet.

        Returns:
            List of dicts with keys: index, filename

        Example:
            [
                {'index': 0, 'filename': 'poema1.md'},
                {'index': 5, 'filename': 'poema2.md'}
            ]
        """
        if self.df is None:
            raise TrackerError("Excel not loaded. Call load() first.")

        pending_df = self.df[self.df["Hecho"] == False].copy()

        result = []
        for idx, row in pending_df.iterrows():
            result.append(
                {
                    "index": idx,
                    "filename": row["Archivo"],
                }
            )

        return result

    def get_processed_filenames(self) -> set:
        """
        Get set of filenames that have been processed (Hecho = True).

        Returns:
            Set of filenames marked as done
        """
        if self.df is None:
            raise TrackerError("Excel not loaded. Call load() first.")

        processed_df = self.df[self.df["Hecho"] == True]
        return set(processed_df["Archivo"].tolist())

    def add_new_file(self, filename: str) -> int:
        """
        Add a new file to the tracker.

        Args:
            filename: Name of the markdown file

        Returns:
            Index of the newly added row
        """
        if self.df is None:
            raise TrackerError("Excel not loaded. Call load() first.")

        # Create new row DataFrame to preserve dtypes
        new_row_df = pd.DataFrame(
            [
                {
                    "Archivo": filename,
                    "Hecho": False,
                    "video_drive_id": None,
                    "fecha_procesado": None,
                    "error": None,
                }
            ]
        )

        # Concatenate preserving dtypes
        self.df = pd.concat([self.df, new_row_df], ignore_index=True)

        # Ensure video_drive_id remains object dtype
        self.df["video_drive_id"] = self.df["video_drive_id"].astype("object")

        new_idx = len(self.df) - 1
        print(f"[poetry-reader] ✓ Added new file to tracker: {filename}")
        return new_idx

    def mark_processed(
        self, index: int, video_id: str, video_url: Optional[str] = None
    ) -> None:
        """
        Mark a markdown as successfully processed.

        Args:
            index: DataFrame index of the row
            video_id: Google Drive file ID of generated video
            video_url: Optional shareable link to video
        """
        if self.df is None:
            raise TrackerError("Excel not loaded. Call load() first.")

        if index not in self.df.index:
            raise TrackerError(f"Invalid index: {index}")

        self.df.at[index, "Hecho"] = True
        self.df.at[index, "video_drive_id"] = video_id
        self.df.at[index, "fecha_procesado"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.df.at[index, "error"] = None  # Clear any previous errors

        print(f"[poetry-reader] ✓ Marked as processed: {self.df.at[index, 'Archivo']}")

    def mark_failed(self, index: int, error_message: str) -> None:
        """
        Mark a markdown as failed to process.

        Args:
            index: DataFrame index of the row
            error_message: Error description
        """
        if self.df is None:
            raise TrackerError("Excel not loaded. Call load() first.")

        if index not in self.df.index:
            raise TrackerError(f"Invalid index: {index}")

        self.df.at[index, "Hecho"] = False
        self.df.at[index, "error"] = error_message
        self.df.at[index, "fecha_procesado"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        print(
            f"[poetry-reader] ✗ Marked as failed: {self.df.at[index, 'Archivo']} - {error_message}"
        )

    def save(self, output_path: Optional[str] = None) -> None:
        """
        Save DataFrame back to Excel.

        Args:
            output_path: Optional different path to save to (default: original path)

        Raises:
            TrackerError: If save fails
        """
        if self.df is None:
            raise TrackerError("No data to save. Load Excel first.")

        save_path = output_path or self.excel_path

        try:
            # Ensure parent directory exists
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)

            # Save to Excel
            self.df.to_excel(save_path, index=False, engine="openpyxl")
            print(f"[poetry-reader] ✓ Excel saved: {save_path}")

        except Exception as e:
            raise TrackerError(f"Failed to save Excel: {str(e)}") from e

    def _count_pending(self) -> int:
        """Count number of pending markdowns."""
        if self.df is None:
            return 0
        return len(self.df[self.df["Hecho"] == False])

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about the tracker.

        Returns:
            Dict with keys: total, processed, pending, failed
        """
        if self.df is None:
            return {"total": 0, "processed": 0, "pending": 0, "failed": 0}

        total = len(self.df)
        processed = len(self.df[self.df["Hecho"] == True])
        pending = len(self.df[self.df["Hecho"] == False])
        failed = len(self.df[~self.df["error"].isna()])

        return {
            "total": total,
            "processed": processed,
            "pending": pending,
            "failed": failed,
        }

    def reset_row(self, index: int) -> None:
        """
        Reset a row to unprocessed state (clear video_id, error, etc.).

        Args:
            index: DataFrame index of the row
        """
        if self.df is None:
            raise TrackerError("Excel not loaded. Call load() first.")

        if index not in self.df.index:
            raise TrackerError(f"Invalid index: {index}")

        self.df.at[index, "Hecho"] = False
        self.df.at[index, "video_drive_id"] = None
        self.df.at[index, "video_url"] = None
        self.df.at[index, "fecha_procesado"] = None
        self.df.at[index, "error"] = None

        print(f"[poetry-reader] ✓ Reset row: {self.df.at[index, 'Archivo']}")

    def get_row_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Find a row by filename.

        Args:
            filename: Filename to search for

        Returns:
            Dict with row data or None if not found
        """
        if self.df is None:
            return None

        matches = self.df[self.df["Archivo"] == filename]
        if len(matches) == 0:
            return None

        row = matches.iloc[0]
        return row.to_dict()

    def get_index_by_filename(self, filename: str) -> Optional[Any]:
        """
        Find the index of a row by filename.

        Args:
            filename: Filename to search for

        Returns:
            Index of the row or None if not found
        """
        if self.df is None:
            return None

        matches = self.df[self.df["Archivo"] == filename]
        if len(matches) == 0:
            return None

        return matches.index[0]
