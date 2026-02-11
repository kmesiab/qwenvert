"""
Model downloader for qwenvert.

Downloads Qwen GGUF models from HuggingFace Hub with progress tracking,
integrity verification, and resume support.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from huggingface_hub import hf_hub_download


if TYPE_CHECKING:
    from .models import Model


logger = logging.getLogger(__name__)


class ModelDownloader:
    """
    Download and manage Qwen models from HuggingFace.

    Features:
    - Progress bar with download speed
    - Resume interrupted downloads
    - Checksum verification
    - Organized storage in ~/.qwenvert/models/
    """

    def __init__(self, models_dir: Path | None = None) -> None:
        """
        Initialize model downloader.

        Args:
            models_dir: Directory to store models (default: ~/.qwenvert/models/)
        """
        if models_dir is None:
            models_dir = Path.home() / ".qwenvert" / "models"

        self.models_dir = models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Model storage directory: {self.models_dir}")

    def download(
        self,
        model: Model,
        force: bool = False,
    ) -> Path:
        """
        Download a model from HuggingFace.

        Args:
            model: Model configuration with HuggingFace repo info
            force: Force re-download even if file exists

        Returns:
            Path to downloaded model file

        Raises:
            ValueError: If model doesn't have HuggingFace repo info
            RuntimeError: If download fails
        """
        if not model.huggingface_repo:
            raise ValueError(f"Model {model.id} has no HuggingFace repo specified")

        # Extract filename from backend_model_id
        # e.g., "qwen2.5-coder-7b-instruct-q4_K_M.gguf"
        filename = self._get_model_filename(model)

        # Check if already downloaded
        local_path = self.models_dir / filename
        if local_path.exists() and not force:
            logger.info(f"Model already exists: {local_path}")
            return local_path

        logger.info(f"Downloading {model.display_name} from {model.huggingface_repo}")
        logger.info(f"Filename: {filename}")

        try:
            # Download with progress bar
            downloaded_path = hf_hub_download(
                repo_id=model.huggingface_repo,
                filename=filename,
                cache_dir=str(self.models_dir / ".cache"),
                local_dir=str(self.models_dir),
            )

            # Move to expected location if needed (cross-filesystem safe)
            downloaded_path_obj = Path(downloaded_path)
            if downloaded_path_obj != local_path:
                shutil.move(str(downloaded_path_obj), str(local_path))

            logger.info(f"✅ Download complete: {local_path}")
            logger.info(f"   Size: {local_path.stat().st_size / (1024**3):.2f} GB")

            return local_path

        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to download {model.display_name}: {e}") from e

    def _get_model_filename(self, model: Model) -> str:
        """
        Extract GGUF filename from model configuration.

        Args:
            model: Model configuration

        Returns:
            GGUF filename

        Raises:
            ValueError: If filename can't be determined
        """
        # Check if model has explicit gguf_filename attribute
        if hasattr(model, "gguf_filename") and model.gguf_filename:
            return model.gguf_filename

        backend_id = model.backend_model_id

        # If backend_model_id is already a .gguf filename
        if backend_id.endswith(".gguf"):
            return Path(backend_id).name

        # Construct from model metadata with more careful formatting
        # Format: {family}-{size}b-instruct-{quantization}.gguf
        # Keep original formatting to match HuggingFace filenames
        family = model.family.lower()

        # Format size as integer if whole number, else keep decimal
        size = int(model.size_b) if model.size_b == int(model.size_b) else model.size_b

        # Lowercase quantization to match HuggingFace filenames (e.g., q4_k_m)
        quant = model.quantization.lower()

        filename = f"{family}-{size}b-instruct-{quant}.gguf"
        logger.debug(f"Constructed filename: {filename}")

        return filename

    def verify_checksum(
        self,
        model_path: Path,
        expected_checksum: str | None = None,
    ) -> bool:
        """
        Verify model file integrity with SHA256 checksum.

        Args:
            model_path: Path to model file
            expected_checksum: Expected SHA256 hash (optional)

        Returns:
            True if checksum matches or not provided, False otherwise
        """
        if not expected_checksum:
            logger.warning("No checksum provided, skipping verification")
            return True

        logger.info("Verifying checksum...")

        sha256 = hashlib.sha256()
        with open(model_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        actual_checksum = sha256.hexdigest()

        if actual_checksum == expected_checksum:
            logger.info("✅ Checksum verified")
            return True
        logger.error("❌ Checksum mismatch!")
        logger.error(f"   Expected: {expected_checksum}")
        logger.error(f"   Actual:   {actual_checksum}")
        return False

    def list_downloaded_models(self) -> list[Path]:
        """
        List all downloaded model files.

        Returns:
            List of paths to .gguf files
        """
        if not self.models_dir.exists():
            return []

        return sorted(self.models_dir.glob("*.gguf"))

    def get_model_path(self, model: Model) -> Path | None:
        """
        Get path to downloaded model if it exists.

        Args:
            model: Model configuration

        Returns:
            Path to model file, or None if not downloaded
        """
        filename = self._get_model_filename(model)
        model_path = self.models_dir / filename

        return model_path if model_path.exists() else None

    def delete_model(self, model: Model) -> bool:
        """
        Delete a downloaded model.

        Args:
            model: Model configuration

        Returns:
            True if deleted, False if not found
        """
        model_path = self.get_model_path(model)

        if model_path and model_path.exists():
            logger.info(f"Deleting {model_path}")
            model_path.unlink()
            return True

        return False

    def get_disk_usage(self) -> dict[str, float]:
        """
        Get disk usage statistics for models directory.

        Returns:
            Dictionary with total_gb and available_gb
        """
        if not self.models_dir.exists():
            return {"total_gb": 0.0, "available_gb": 0.0}

        # Calculate total size of downloaded models
        total_bytes = sum(p.stat().st_size for p in self.models_dir.glob("*.gguf"))

        # Get available disk space
        stat = shutil.disk_usage(self.models_dir)

        return {
            "total_gb": total_bytes / (1024**3),
            "available_gb": stat.free / (1024**3),
        }
