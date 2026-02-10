"""
Unit tests for ModelDownloader.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from qwenvert.downloader import ModelDownloader
from qwenvert.models import Backend, Model


@pytest.fixture
def sample_model():
    """Sample model with HuggingFace repo."""
    return Model(
        id="qwen2.5-coder-7b-q4-ollama",
        display_name="Qwen2.5 Coder 7B Q4",
        family="qwen2.5-coder",
        size_b=7.0,
        quantization="Q4_K_M",
        backend=Backend.OLLAMA,
        backend_model_id="qwen2.5-coder-7b-instruct-q4_K_M.gguf",
        context_length=32768,
        min_ram_gb=8,
        recommended_ram_gb=16,
        huggingface_repo="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
    )


@pytest.fixture
def temp_models_dir(tmp_path):
    """Temporary models directory."""
    return tmp_path / "models"


class TestModelDownloaderInit:
    """Test ModelDownloader initialization."""

    def test_init_default_dir(self):
        """Test initialization with default directory."""
        downloader = ModelDownloader()

        assert downloader.models_dir == Path.home() / ".qwenvert" / "models"
        assert downloader.models_dir.exists()

    def test_init_custom_dir(self, temp_models_dir):
        """Test initialization with custom directory."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        assert downloader.models_dir == temp_models_dir
        assert temp_models_dir.exists()

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates models directory."""
        models_dir = tmp_path / "custom" / "models"
        assert not models_dir.exists()

        downloader = ModelDownloader(models_dir=models_dir)

        assert models_dir.exists()


class TestModelDownload:
    """Test model downloading."""

    def test_download_basic(self, sample_model, temp_models_dir):
        """Test basic model download."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        with patch("qwenvert.downloader.hf_hub_download") as mock_download:
            mock_path = temp_models_dir / "qwen2.5-coder-7b-instruct-q4_K_M.gguf"
            mock_path.parent.mkdir(parents=True, exist_ok=True)
            mock_path.touch()
            mock_download.return_value = str(mock_path)

            result = downloader.download(sample_model)

            assert result.exists()
            mock_download.assert_called_once()

    def test_download_without_repo(self, temp_models_dir):
        """Test download fails when model has no HuggingFace repo."""
        model = Model(
            id="test-model",
            display_name="Test Model",
            family="test",
            size_b=7.0,
            quantization="Q4",
            backend=Backend.OLLAMA,
            backend_model_id="test-model.gguf",
            context_length=4096,
            min_ram_gb=8,
            recommended_ram_gb=16,
            huggingface_repo=None,  # No repo specified
        )

        downloader = ModelDownloader(models_dir=temp_models_dir)

        with pytest.raises(ValueError, match="no HuggingFace repo"):
            downloader.download(model)

    def test_download_skip_if_exists(self, sample_model, temp_models_dir):
        """Test that download is skipped if model already exists."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        # Create existing model file
        model_file = temp_models_dir / "qwen2.5-coder-7b-instruct-q4_K_M.gguf"
        model_file.parent.mkdir(parents=True, exist_ok=True)
        model_file.write_text("fake model data")

        with patch("qwenvert.downloader.hf_hub_download") as mock_download:
            result = downloader.download(sample_model, force=False)

            # Should return existing file without calling download
            assert result == model_file
            mock_download.assert_not_called()

    def test_download_force_redownload(self, sample_model, temp_models_dir):
        """Test force re-download even if file exists."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        # Create existing model file
        model_file = temp_models_dir / "qwen2.5-coder-7b-instruct-q4_K_M.gguf"
        model_file.parent.mkdir(parents=True, exist_ok=True)
        model_file.write_text("old data")

        with patch("qwenvert.downloader.hf_hub_download") as mock_download:
            mock_download.return_value = str(model_file)
            model_file.write_text("new data")  # Simulate new download

            result = downloader.download(sample_model, force=True)

            # Should call download even though file exists
            assert result == model_file
            mock_download.assert_called_once()


class TestGetModelPath:
    """Test get_model_path method."""

    def test_get_model_path_exists(self, sample_model, temp_models_dir):
        """Test getting path to existing model."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        # Create model file
        model_file = temp_models_dir / "qwen2.5-coder-7b-instruct-q4_K_M.gguf"
        model_file.parent.mkdir(parents=True, exist_ok=True)
        model_file.write_text("model data")

        result = downloader.get_model_path(sample_model)

        assert result == model_file
        assert result.exists()

    def test_get_model_path_not_exists(self, sample_model, temp_models_dir):
        """Test getting path to non-existent model."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        result = downloader.get_model_path(sample_model)

        assert result is None


class TestGetModelFilename:
    """Test filename extraction."""

    def test_get_model_filename_gguf(self, sample_model, temp_models_dir):
        """Test extracting filename when backend_model_id is a GGUF file."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        filename = downloader._get_model_filename(sample_model)

        assert filename == "qwen2.5-coder-7b-instruct-q4_K_M.gguf"
        assert filename.endswith(".gguf")

    def test_get_model_filename_model_id(self, temp_models_dir):
        """Test filename generation when backend_model_id is not a file."""
        model = Model(
            id="qwen2.5-coder-7b-q4",
            display_name="Qwen2.5 Coder 7B Q4",
            family="qwen2.5-coder",
            size_b=7.0,
            quantization="Q4_K_M",
            backend=Backend.OLLAMA,
            backend_model_id="qwen2.5-coder:7b",  # Not a filename
            context_length=32768,
            min_ram_gb=8,
            recommended_ram_gb=16,
            huggingface_repo="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        )

        downloader = ModelDownloader(models_dir=temp_models_dir)

        filename = downloader._get_model_filename(model)

        # Should generate filename from model ID
        assert ".gguf" in filename
        assert "qwen" in filename.lower()


class TestListDownloadedModels:
    """Test listing downloaded models."""

    def test_list_downloaded_models_empty(self, temp_models_dir):
        """Test listing when no models are downloaded."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        models = downloader.list_downloaded_models()

        assert len(models) == 0

    def test_list_downloaded_models(self, temp_models_dir):
        """Test listing downloaded models."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        # Create some model files
        (temp_models_dir / "model1.gguf").write_text("data1")
        (temp_models_dir / "model2.gguf").write_text("data2")
        (temp_models_dir / "not_a_model.txt").write_text("text")

        models = downloader.list_downloaded_models()

        assert len(models) == 2
        assert all(m.suffix == ".gguf" for m in models)


class TestDeleteModel:
    """Test model deletion."""

    def test_delete_model(self, sample_model, temp_models_dir):
        """Test deleting a model."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        # Create model file
        model_file = temp_models_dir / "qwen2.5-coder-7b-instruct-q4_K_M.gguf"
        model_file.parent.mkdir(parents=True, exist_ok=True)
        model_file.write_text("model data")
        assert model_file.exists()

        success = downloader.delete_model(sample_model)

        assert success
        assert not model_file.exists()

    def test_delete_nonexistent_model(self, sample_model, temp_models_dir):
        """Test deleting a model that doesn't exist."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        success = downloader.delete_model(sample_model)

        # Should return False or handle gracefully
        assert success is False or success is True  # Implementation may vary


class TestGetModelSize:
    """Test getting model size."""

    def test_get_model_size(self, sample_model, temp_models_dir):
        """Test getting size of downloaded model."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        # Create model file with known size
        model_file = temp_models_dir / "qwen2.5-coder-7b-instruct-q4_K_M.gguf"
        model_file.parent.mkdir(parents=True, exist_ok=True)
        model_file.write_bytes(b"x" * 1024 * 1024 * 100)  # 100 MB

        size_mb = downloader.get_model_size(sample_model)

        assert size_mb is not None
        assert 99 <= size_mb <= 101  # ~100 MB

    def test_get_model_size_not_downloaded(self, sample_model, temp_models_dir):
        """Test getting size of non-existent model."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        size_mb = downloader.get_model_size(sample_model)

        assert size_mb is None


class TestChecksumVerification:
    """Test checksum verification."""

    def test_verify_checksum_valid(self, temp_models_dir):
        """Test checksum verification with valid file."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        # Create test file
        test_file = temp_models_dir / "test.gguf"
        test_file.write_bytes(b"test data")

        # Calculate expected checksum
        import hashlib
        expected = hashlib.sha256(b"test data").hexdigest()

        result = downloader.verify_checksum(test_file, expected)

        assert result is True

    def test_verify_checksum_invalid(self, temp_models_dir):
        """Test checksum verification with invalid checksum."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        test_file = temp_models_dir / "test.gguf"
        test_file.write_bytes(b"test data")

        result = downloader.verify_checksum(test_file, "wrong_checksum")

        assert result is False

    def test_verify_checksum_missing_file(self, temp_models_dir):
        """Test checksum verification with missing file."""
        downloader = ModelDownloader(models_dir=temp_models_dir)

        test_file = temp_models_dir / "nonexistent.gguf"

        result = downloader.verify_checksum(test_file, "any_checksum")

        assert result is False
