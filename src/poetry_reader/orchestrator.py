"""
Orchestrator for automated video processing from Google Drive.

Coordinates the entire flow: downloading Excel, processing markdowns,
generating videos, uploading to Drive, and updating the tracker.
"""

import glob
import os
import random
import tempfile
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .drive.manager import DriveManager
from .drive.tracker import ExcelTracker
from .generate_videos import main as generate_video


@dataclass
class ProcessingResult:
    """Result of processing a single markdown."""

    titulo: str
    autor: str
    status: str  # 'success', 'failed', 'skipped'
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass
class ProcessingReport:
    """Final report of all processing."""

    total: int
    successful: int
    failed: int
    skipped: int
    results: List[ProcessingResult]
    total_duration_seconds: float


class OrchestratorError(Exception):
    """Raised when orchestration fails."""

    pass


class VideoOrchestrator:
    """
    Orchestrates the automated video processing workflow.

    Flow:
    1. Download Excel tracker from Drive
    2. Load and parse tracker
    3. Get pending markdowns
    4. For each pending:
       - Create temporary .md file
       - Generate video
       - Upload to Drive
       - Update tracker
    5. Upload updated tracker
    6. Generate report
    """

    def __init__(
        self,
        drive_manager: DriveManager,
        tracker: ExcelTracker,
        config: Dict[str, Any],
    ):
        """
        Initialize VideoOrchestrator.

        Args:
            drive_manager: DriveManager instance for Drive operations
            tracker: ExcelTracker instance for state management
            config: Configuration dictionary with video generation params
        """
        self.drive_manager = drive_manager
        self.tracker = tracker
        self.config = config

        # Extract config values
        self.video_config = config.get("video", {})
        self.local_config = config.get("local", {})
        self.drive_config = config.get("drive", {})

        # Local directories
        self.output_dir = Path(self.local_config.get("output_dir", "./output"))
        self.cache_dir = Path(self.local_config.get("cache_dir", "./drive_cache"))
        self.temp_md_dir = self.cache_dir / "temp_markdowns"

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.temp_md_dir.mkdir(parents=True, exist_ok=True)

    def process_all(
        self, limit: Optional[int] = None, dry_run: bool = False
    ) -> ProcessingReport:
        """
        Process all pending markdowns.

        Args:
            limit: Maximum number of videos to process (None = all)
            dry_run: If True, simulate without actually processing

        Returns:
            ProcessingReport with statistics and results
        """
        start_time = datetime.now()
        print("\n" + "=" * 60)
        print("STARTING AUTOMATED VIDEO PROCESSING")
        print("=" * 60 + "\n")

        # List all markdown files from Drive folder
        markdowns_folder_id = self.drive_config.get("markdowns_folder_id")
        if not markdowns_folder_id:
            raise OrchestratorError(
                "markdowns_folder_id not configured in drive config"
            )

        print("[poetry-reader] Scanning Drive folder for markdown files...")
        drive_files = self.drive_manager.list_files_in_folder(
            markdowns_folder_id, file_extension=".md"
        )

        if not drive_files:
            print("[poetry-reader] No markdown files found in Drive folder.")
            return ProcessingReport(
                total=0,
                successful=0,
                failed=0,
                skipped=0,
                results=[],
                total_duration_seconds=0.0,
            )

        drive_filenames = {f.title for f in drive_files}
        print(f"[poetry-reader] Found {len(drive_filenames)} markdown files in Drive")

        # Get already processed files from tracker
        processed_filenames = self.tracker.get_processed_filenames()
        print(f"[poetry-reader] {len(processed_filenames)} files already processed")

        # Determine which files need processing
        files_to_process = drive_filenames - processed_filenames

        if not files_to_process:
            print("[poetry-reader] All files are already processed!")
            return ProcessingReport(
                total=0,
                successful=0,
                failed=0,
                skipped=0,
                results=[],
                total_duration_seconds=0.0,
            )

        # Apply limit if specified
        files_list = list(files_to_process)
        if limit is not None and limit < len(files_list):
            files_list = files_list[:limit]
            print(f"[poetry-reader] Processing limited to {limit} files")

        print(f"[poetry-reader] Files to process: {len(files_list)}\n")

        # Download markdown files from Drive
        downloaded_files = self.drive_manager.download_markdowns_from_folder(
            markdowns_folder_id, str(self.temp_md_dir), files_list
        )

        # Build pending list with file content
        pending = []
        for filename in files_list:
            if filename not in downloaded_files:
                print(f"[poetry-reader] ⚠ Failed to download: {filename}")
                continue

            local_path = downloaded_files[filename]

            # Add to tracker if not exists, or get existing index
            index = self.tracker.get_index_by_filename(filename)
            if index is None:
                index = self.tracker.add_new_file(filename)

            try:
                markdown_data = self._parse_markdown_file(index, local_path)
                pending.append(markdown_data)
            except Exception as e:
                print(f"[poetry-reader] ⚠ Failed to parse {filename}: {e}")
                self.tracker.mark_failed(index, f"Failed to parse markdown: {e}")

        if not pending:
            print("[poetry-reader] No valid markdowns to process.")
            return ProcessingReport(
                total=0,
                successful=0,
                failed=0,
                skipped=0,
                results=[],
                total_duration_seconds=0.0,
            )

        print(f"[poetry-reader] Markdowns to process: {len(pending)}\n")

        # Process each markdown
        results = []
        successful = 0
        failed = 0
        skipped = 0

        for i, markdown_data in enumerate(pending, 1):
            print(f"\n[{i}/{len(pending)}] Processing: '{markdown_data['titulo']}'")
            print(f"  Author: {markdown_data['autor']}")

            if dry_run:
                print("  [DRY RUN] Skipping actual processing")
                results.append(
                    ProcessingResult(
                        titulo=markdown_data["titulo"],
                        autor=markdown_data["autor"],
                        status="skipped",
                    )
                )
                skipped += 1
                continue

            # Process the markdown
            result = self.process_single_markdown(markdown_data)
            results.append(result)

            if result.status == "success":
                successful += 1
            elif result.status == "failed":
                failed += 1
            else:
                skipped += 1

            # Save tracker after each processing (incremental saves)
            try:
                self.tracker.save()
            except Exception as e:
                print(f"  [WARNING] Failed to save tracker: {e}")

        # Final save and upload
        if not dry_run:
            print("\n" + "-" * 60)
            print("Finalizing...")
            try:
                self.tracker.save()
                print("[poetry-reader] ✓ Tracker saved locally")

                # Upload updated tracker to Drive
                excel_file_id = self.drive_config.get("excel_tracker_id")
                if excel_file_id:
                    self.drive_manager.update_file(
                        excel_file_id, self.tracker.excel_path
                    )
                    print("[poetry-reader] ✓ Tracker uploaded to Drive")
            except Exception as e:
                print(f"[ERROR] Failed to finalize tracker: {e}")

        # Generate report
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        report = ProcessingReport(
            total=len(pending),
            successful=successful,
            failed=failed,
            skipped=skipped,
            results=results,
            total_duration_seconds=duration,
        )

        self._print_report(report)
        return report

    def process_single_markdown(
        self, markdown_data: Dict[str, Any]
    ) -> ProcessingResult:
        """
        Process a single markdown into video.

        Args:
            markdown_data: Dict with keys: index, autor, titulo, texto, filepath

        Returns:
            ProcessingResult with outcome
        """
        start_time = datetime.now()
        index = markdown_data["index"]
        titulo = markdown_data["titulo"]
        autor = markdown_data["autor"]
        md_file = Path(markdown_data["filepath"])

        try:
            print(f"  → Processing markdown: {md_file.name}")

            # Generate video
            print(f"  → Generating video...")
            self._generate_video(md_file)

            # Find generated video file
            video_file = self._find_generated_video(titulo)
            if not video_file or not video_file.exists():
                raise OrchestratorError(f"Video file not found after generation")

            print(f"  → Video generated: {video_file.name}")

            # Upload video to Drive
            videos_folder_id = self.drive_config.get("videos_output_folder_id")
            if not videos_folder_id:
                raise OrchestratorError(
                    "videos_output_folder_id not configured in drive config"
                )

            print(f"  → Uploading to Drive...")

            # Check if file already exists and delete it to avoid multiple versions
            existing_file = self.drive_manager.find_file_by_name(
                videos_folder_id, video_file.name
            )
            if existing_file:
                print(f"  → Replacing existing file: {video_file.name}")
                self.drive_manager.delete_file(existing_file.id)

            video_id = self.drive_manager.upload_file(
                str(video_file), videos_folder_id, video_file.name
            )

            # Get shareable link for reporting (not saved to Excel)
            try:
                video_url = self.drive_manager.get_shareable_link(video_id)
            except Exception:
                video_url = f"https://drive.google.com/file/d/{video_id}"

            # Mark as processed in tracker
            self.tracker.mark_processed(index, video_id)

            # Cleanup - no need to delete downloaded files, they stay in temp_md_dir

            duration = (datetime.now() - start_time).total_seconds()
            print(f"  ✓ Success! (Duration: {duration:.1f}s)")

            return ProcessingResult(
                titulo=titulo,
                autor=autor,
                status="success",
                video_id=video_id,
                video_url=video_url,
                duration_seconds=duration,
            )

        except Exception as e:
            error_msg = str(e)
            print(f"  ✗ Failed: {error_msg}")

            # Mark as failed in tracker
            try:
                self.tracker.mark_failed(index, error_msg)
            except Exception as tracker_error:
                print(f"  [WARNING] Failed to mark as failed: {tracker_error}")

            duration = (datetime.now() - start_time).total_seconds()

            return ProcessingResult(
                titulo=titulo,
                autor=autor,
                status="failed",
                error=error_msg,
                duration_seconds=duration,
            )

    def _get_random_background_image(self) -> Optional[str]:
        """Get a random background image from the images folder.

        Returns:
            Path to a random image file, or None if no images found
        """
        # Look for image files in the images/ folder at project root
        project_root = Path(__file__).parent.parent.parent
        images_dir = project_root / "images"

        if not images_dir.exists():
            return None

        # Find all image files with supported extensions
        image_patterns = ["*.jpg", "*.jpeg", "*.png"]
        image_files = []

        for pattern in image_patterns:
            image_files.extend(glob.glob(str(images_dir / pattern)))

        if not image_files:
            return None

        # Select a random image
        selected_image = random.choice(image_files)
        print(f"  Selected background image: {selected_image}")

        return selected_image

    def _generate_video(self, markdown_file: Path) -> None:
        """
        Generate video from markdown file using generate_videos.main().

        Args:
            markdown_file: Path to markdown file

        Raises:
            OrchestratorError: If video generation fails
        """
        try:
            # Extract video generation parameters from config
            resolution = (
                self.video_config.get("resolution", {}).get("width", 1080),
                self.video_config.get("resolution", {}).get("height", 1920),
            )

            # Get random background image from images folder
            image_path = self._get_random_background_image()
            if not image_path:
                # Fallback to config image if no images in folder
                image_path = self.video_config.get("image_path")

            # Create a temporary input directory with just this file
            temp_input_dir = self.temp_md_dir / "input_temp"
            temp_input_dir.mkdir(exist_ok=True)

            # Copy the markdown to temp input dir
            import shutil

            temp_md_copy = temp_input_dir / markdown_file.name
            shutil.copy(markdown_file, temp_md_copy)

            # Call generate_videos.main()
            generate_video(
                input_dir=str(temp_input_dir),
                out_dir=str(self.output_dir),
                image_path=image_path,
                gradient_palette=self.video_config.get("gradient_palette"),
                add_particles=self.video_config.get("add_particles", True),
                font_size=self.video_config.get("font_size", 80),
                fade_duration=self.video_config.get("fade_duration", 0.5),
                force_lang=self.video_config.get("force_lang"),
                fps=self.video_config.get("fps", 30),
                num_particles=self.video_config.get("num_particles", 80),
                tts_backend=self.video_config.get("tts_backend", "kokoro"),
                tts_model=self.video_config.get("tts_model"),
                tts_voice=self.video_config.get("tts_voice"),
                resolution=resolution,
                tiktok_mode=self.video_config.get("tiktok_mode", True),
                zoom_background=self.video_config.get("zoom_background", True),
            )

            # Cleanup temp input dir
            shutil.rmtree(temp_input_dir)

        except Exception as e:
            raise OrchestratorError(f"Video generation failed: {str(e)}") from e

    def _find_generated_video(self, titulo: str) -> Optional[Path]:
        """
        Find the generated video file in output directory.

        Args:
            titulo: Title of the video (used to match filename)

        Returns:
            Path to video file or None if not found
        """
        # Look for .mp4 files in output directory
        mp4_files = list(self.output_dir.glob("*.mp4"))

        if not mp4_files:
            return None

        # If there's only one file, return it
        if len(mp4_files) == 1:
            return mp4_files[0]

        # Try to find by title match
        safe_titulo = "".join(
            c for c in titulo if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()

        for video_file in mp4_files:
            if safe_titulo.lower() in video_file.stem.lower():
                return video_file

        # Return the most recent file
        return max(mp4_files, key=lambda p: p.stat().st_mtime)

    def _parse_markdown_file(self, index: int, file_path: str) -> Dict[str, Any]:
        """
        Parse a markdown file and extract metadata and content.

        Expected format:
        Titulo: {titulo}
        Autor: {autor}

        {texto}

        Args:
            index: DataFrame index
            file_path: Path to markdown file

        Returns:
            Dict with keys: index, autor, titulo, texto, filepath
        """
        content = Path(file_path).read_text(encoding="utf-8")

        lines = content.split("\n")
        titulo = ""
        autor = ""
        texto_start = 0

        # Parse header lines
        for i, line in enumerate(lines):
            if line.startswith("Titulo:"):
                titulo = line.replace("Titulo:", "").strip()
            elif line.startswith("Autor:"):
                autor = line.replace("Autor:", "").strip()
            elif line.strip() == "" and titulo and autor:
                # Empty line after both headers marks start of text
                texto_start = i + 1
                break

        # Extract text content
        texto = "\n".join(lines[texto_start:]).strip()

        if not titulo:
            # Use filename as fallback
            titulo = Path(file_path).stem

        if not autor:
            autor = "Desconocido"

        return {
            "index": index,
            "autor": autor,
            "titulo": titulo,
            "texto": texto,
            "filepath": file_path,
        }

    def _cleanup_temp_files(self, files: List[Path]) -> None:
        """
        Remove temporary files.

        Args:
            files: List of file paths to remove
        """
        for filepath in files:
            try:
                if filepath.exists():
                    filepath.unlink()
            except Exception as e:
                print(f"  [WARNING] Failed to cleanup {filepath}: {e}")

    def _print_report(self, report: ProcessingReport) -> None:
        """
        Print processing report to console.

        Args:
            report: ProcessingReport to print
        """
        print("\n" + "=" * 60)
        print("PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Total:      {report.total}")
        print(f"Successful: {report.successful}")
        print(f"Failed:     {report.failed}")
        print(f"Skipped:    {report.skipped}")
        print(f"Duration:   {report.total_duration_seconds:.1f}s")
        print("=" * 60)

        if report.successful > 0:
            print("\n✓ Successful:")
            for r in report.results:
                if r.status == "success":
                    print(f"  - {r.titulo} (by {r.autor})")
                    if r.video_url:
                        print(f"    {r.video_url}")

        if report.failed > 0:
            print("\n✗ Failed:")
            for r in report.results:
                if r.status == "failed":
                    print(f"  - {r.titulo} (by {r.autor})")
                    print(f"    Error: {r.error}")

        videos_folder_id = self.drive_config.get("videos_output_folder_id")
        if videos_folder_id:
            print(
                f"\nVideos uploaded to: https://drive.google.com/drive/folders/{videos_folder_id}"
            )

        excel_tracker_id = self.drive_config.get("excel_tracker_id")
        if excel_tracker_id:
            print(
                f"Excel tracker: https://docs.google.com/spreadsheets/d/{excel_tracker_id}"
            )

        print()
