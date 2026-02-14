"""Unit tests for enhanced BinaryManager functionality (Phase 1 & 2)."""

import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from qwenvert.binary_manager import BinaryInfo, BinaryManager, BinarySource
from qwenvert.hardware import HardwareProfile


@pytest.fixture
def binary_manager(tmp_path):
    """Create BinaryManager with temporary cache directory."""
    manager = BinaryManager()
    manager.cache_dir = tmp_path
    manager.bin_dir = tmp_path / "bin"
    manager.binary_path = manager.bin_dir / "llama-server"
    manager.bin_dir.mkdir(parents=True, exist_ok=True)
    return manager


@pytest.fixture
def mock_hardware():
    """Create mock HardwareProfile."""
    return HardwareProfile(
        chip="M1 Pro",
        chip_family="M1",
        total_memory_gb=16,
        gpu_cores=16,
        cpu_cores_performance=6,
        cpu_cores_efficiency=2,
        has_active_cooling=True,
        neural_engine_cores=16,
        model_identifier="MacBookPro18,3",
    )


class TestVersionCache:
    """Test version caching functionality."""

    def test_save_and_load_version_cache(self, binary_manager):
        """Test saving and loading version cache."""
        # Save cache
        binary_manager._save_version_cache(
            version="b3600",
            url="https://github.com/ggerganov/llama.cpp/releases/download/b3600/llama-b3600-bin-macos-arm64.zip",
            checksum="abc123",
        )

        # Load cache
        cache_data = binary_manager._load_version_cache()

        assert cache_data is not None
        assert cache_data["version"] == "b3600"
        assert "github.com" in cache_data["download_url"]
        assert cache_data["checksum"] == "abc123"
        assert cache_data["architecture"] is not None

    def test_cache_expiration(self, binary_manager):
        """Test cache expiration after 24 hours."""
        # Save cache with old timestamp
        cache_file = binary_manager.cache_dir / "version_cache.json"
        old_timestamp = time.time() - (25 * 3600)  # 25 hours ago

        cache_data = {
            "version": "b3600",
            "download_url": "https://example.com/download",
            "checksum": "abc123",
            "timestamp": old_timestamp,
            "architecture": "arm64",
        }

        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Load cache - should be None due to expiration
        loaded = binary_manager._load_version_cache()
        assert loaded is None

    def test_cache_architecture_mismatch(self, binary_manager):
        """Test cache rejection on architecture mismatch."""
        import platform

        cache_file = binary_manager.cache_dir / "version_cache.json"

        # Save cache with different architecture
        current_arch = platform.machine()
        wrong_arch = "x86_64" if current_arch == "arm64" else "arm64"

        cache_data = {
            "version": "b3600",
            "download_url": "https://example.com/download",
            "checksum": "abc123",
            "timestamp": time.time(),
            "architecture": wrong_arch,
        }

        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Load cache - should be None due to architecture mismatch
        loaded = binary_manager._load_version_cache()
        assert loaded is None


class TestOfflineFallback:
    """Test offline operation with version cache."""

    def test_get_latest_release_with_cache_fallback(self, binary_manager):
        """Test fallback to cache when GitHub API unavailable."""
        import httpx

        # Save cache
        binary_manager._save_version_cache(
            version="b3600",
            url="https://example.com/download",
            checksum=None,
        )

        # Mock GitHub API to fail
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Network error")

            # Should use cache fallback
            version = binary_manager.get_latest_release_version(use_cache=True)
            assert version == "b3600"

    def test_get_latest_release_without_cache(self, binary_manager):
        """Test fallback to hardcoded version without cache."""
        import httpx

        # Mock GitHub API to fail
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Network error")

            # Should use hardcoded fallback
            version = binary_manager.get_latest_release_version(use_cache=False)
            assert version == "b3600"


class TestHomebrewInstallation:
    """Test Homebrew installation functionality."""

    def test_install_via_homebrew_success(self, binary_manager):
        """Test successful Homebrew installation."""
        with patch("shutil.which") as mock_which:
            with patch("subprocess.run") as mock_run:
                mock_which.return_value = "/opt/homebrew/bin/brew"
                mock_run.return_value = Mock(returncode=0)

                # Mock detect_binary to return success after install
                mock_binary_info = BinaryInfo(
                    path=Path("/opt/homebrew/bin/llama-server"),
                    version="b3600",
                    source=BinarySource.HOMEBREW,
                    architecture="arm64",
                    is_valid=True,
                )

                with patch.object(
                    binary_manager, "detect_binary", return_value=mock_binary_info
                ):
                    result = binary_manager.install_via_homebrew()

                    assert result is not None
                    assert result == mock_binary_info.path
                    mock_run.assert_called_once()

    def test_install_via_homebrew_no_brew(self, binary_manager):
        """Test Homebrew installation when brew not found."""
        with patch("shutil.which", return_value=None):
            result = binary_manager.install_via_homebrew()
            assert result is None

    def test_install_via_homebrew_timeout(self, binary_manager):
        """Test Homebrew installation timeout."""
        import subprocess

        with patch("shutil.which", return_value="/opt/homebrew/bin/brew"):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("brew", 300)
                result = binary_manager.install_via_homebrew()
                assert result is None


class TestGetOrInstallBinary:
    """Test multi-strategy binary installation."""

    def test_get_or_install_existing_binary(self, binary_manager, mock_hardware):
        """Test get_or_install with existing binary."""
        mock_binary = BinaryInfo(
            path=Path("/usr/local/bin/llama-server"),
            version="b3600",
            source=BinarySource.SYSTEM,
            architecture="arm64",
            is_valid=True,
        )

        with patch.object(binary_manager, "detect_binary", return_value=mock_binary):
            result = binary_manager.get_or_install_binary(
                hardware=mock_hardware, auto_install=True
            )

            assert result == mock_binary

    def test_get_or_install_download_strategy(self, binary_manager, mock_hardware):
        """Test get_or_install with download strategy."""
        # Mock detection to return None
        with patch.object(binary_manager, "detect_binary", return_value=None):
            with patch.object(
                binary_manager,
                "download_binary",
                return_value=Path("/cache/llama-server"),
            ) as mock_download:
                mock_binary = BinaryInfo(
                    path=Path("/cache/llama-server"),
                    version="b3600",
                    source=BinarySource.DOWNLOADED,
                    architecture="arm64",
                    is_valid=True,
                )

                with patch.object(
                    binary_manager, "_get_binary_info", return_value=mock_binary
                ):
                    with patch.object(binary_manager, "_save_version_cache"):
                        result = binary_manager.get_or_install_binary(
                            hardware=mock_hardware, auto_install=True
                        )

                        assert result is not None
                        mock_download.assert_called_once()

    def test_get_or_install_no_auto_install(self, binary_manager, mock_hardware):
        """Test get_or_install with auto_install=False."""
        with patch.object(binary_manager, "detect_binary", return_value=None):
            with pytest.raises(RuntimeError, match="auto-install disabled"):
                binary_manager.get_or_install_binary(
                    hardware=mock_hardware, auto_install=False
                )


class TestVersionManagement:
    """Test version management methods."""

    def test_list_available_versions(self, binary_manager):
        """Test listing available versions from GitHub."""
        mock_releases = [
            {
                "tag_name": "b3601",
                "published_at": "2024-02-13T10:00:00Z",
                "html_url": "https://github.com/ggerganov/llama.cpp/releases/tag/b3601",
                "prerelease": False,
            },
            {
                "tag_name": "b3600",
                "published_at": "2024-02-12T10:00:00Z",
                "html_url": "https://github.com/ggerganov/llama.cpp/releases/tag/b3600",
                "prerelease": False,
            },
        ]

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_releases
            mock_get.return_value = mock_response

            versions = binary_manager.list_available_versions(limit=10)

            assert len(versions) == 2
            assert versions[0]["version"] == "b3601"
            assert versions[1]["version"] == "b3600"

    def test_get_installed_version(self, binary_manager):
        """Test getting installed version."""
        mock_binary = BinaryInfo(
            path=Path("/usr/local/bin/llama-server"),
            version="b3600",
            source=BinarySource.SYSTEM,
            architecture="arm64",
            is_valid=True,
        )

        with patch.object(binary_manager, "detect_binary", return_value=mock_binary):
            version = binary_manager.get_installed_version()
            assert version == "b3600"

    def test_get_installed_version_not_found(self, binary_manager):
        """Test getting version when binary not installed."""
        with patch.object(binary_manager, "detect_binary", return_value=None):
            version = binary_manager.get_installed_version()
            assert version is None

    def test_backup_binary(self, binary_manager):
        """Test binary backup creation."""
        # Create a fake binary
        binary_manager.binary_path.write_text("fake binary")

        backup_path = binary_manager.backup_binary()

        assert backup_path is not None
        assert backup_path.exists()
        assert ".backup." in str(backup_path)

    def test_backup_binary_not_found(self, binary_manager):
        """Test backup when binary doesn't exist."""
        backup_path = binary_manager.backup_binary()
        assert backup_path is None

    def test_rollback_binary(self, binary_manager):
        """Test binary rollback from backup."""
        # Create original binary and backup
        binary_manager.binary_path.write_text("original")
        _ = binary_manager.backup_binary()

        # Modify original
        binary_manager.binary_path.write_text("modified")

        # Mock validation
        mock_binary = BinaryInfo(
            path=binary_manager.binary_path,
            version="b3600",
            source=BinarySource.DOWNLOADED,
            architecture="arm64",
            is_valid=True,
        )

        with patch.object(binary_manager, "_get_binary_info", return_value=mock_binary):
            result = binary_manager.rollback_binary()

            assert result is True
            # Content should be restored
            assert binary_manager.binary_path.read_text() == "original"

    def test_rollback_binary_no_backup(self, binary_manager):
        """Test rollback when no backup exists."""
        result = binary_manager.rollback_binary()
        assert result is False


class TestSecurityValidation:
    """Test security validation in binary extraction."""

    def test_security_check_exists_in_download_helper(self, binary_manager):
        """Verify that Zip Slip security check is present in _download_and_install_zip().

        NOTE: This is a brittle source-inspection test that guards against accidental
        removal of security logic. The functional tests (test_zip_slip_functional_*)
        are the primary validation of actual behavior. This test may break on harmless
        refactors (variable renames, comment changes) but serves as a guardrail.
        """
        import inspect

        # Read the source code of the common download helper
        source = inspect.getsource(binary_manager._download_and_install_zip)

        # Verify security check is in place
        assert (
            "is_relative_to" in source
        ), "Zip Slip check using is_relative_to() must be present"
        assert "SecurityError" in source, "SecurityError exception must be raised"
        assert "resolve()" in source, "Path resolution must be present"
        assert (
            "Zip Slip attack detected" in source
        ), "Clear error message must be present"

    def test_security_check_before_extraction(self, binary_manager):
        """Verify that Zip Slip validation happens BEFORE extraction (not after).

        NOTE: This is a brittle source-inspection test that validates order of operations
        to prevent TOCTOU vulnerabilities. The functional tests verify actual behavior.
        This test may break on refactors but serves as a TOCTOU guardrail.
        """
        import inspect

        # Read the source code of the helper
        source = inspect.getsource(binary_manager._download_and_install_zip)

        # Find the positions of key operations
        security_check_pos = source.find("is_relative_to")
        extract_pos = source.find("zip_ref.extract")

        assert security_check_pos != -1, "Security check must be present"
        assert extract_pos != -1, "Extraction must be present"

        # CRITICAL: Security check must come BEFORE extraction
        assert (
            security_check_pos < extract_pos
        ), "Zip Slip validation must happen BEFORE extraction to prevent TOCTOU vulnerability"

    def test_download_methods_use_secure_helper(self, binary_manager):
        """Verify that both download methods use the secure helper."""
        import inspect

        # Check download_binary uses the helper
        download_binary_source = inspect.getsource(binary_manager.download_binary)
        assert (
            "_download_and_install_zip" in download_binary_source
        ), "download_binary must use secure helper"

        # Check download_specific_version uses the helper
        download_specific_source = inspect.getsource(
            binary_manager.download_specific_version
        )
        assert (
            "_download_and_install_zip" in download_specific_source
        ), "download_specific_version must use secure helper"

    def test_security_error_exception_exists(self):
        """Verify SecurityError exception class exists."""
        from qwenvert.binary_manager import SecurityError

        # Verify it's an Exception subclass
        assert issubclass(SecurityError, Exception)

        # Verify we can instantiate and raise it
        with pytest.raises(SecurityError) as exc_info:
            raise SecurityError("Test security violation")

        assert "security violation" in str(exc_info.value).lower()

    def test_zip_safe_path_validation_logic(self, binary_manager):
        """Test the path validation logic with safe paths."""
        # Simulate a safe extraction path
        safe_path = binary_manager.bin_dir / "llama-server"
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text("test")

        # Apply the security check logic
        extract_path_resolved = safe_path.resolve()
        bin_dir_resolved = binary_manager.bin_dir.resolve()

        # Safe path should be relative to target directory
        is_safe = extract_path_resolved.is_relative_to(bin_dir_resolved)
        assert is_safe, "Safe path within target directory should pass validation"

    def test_zip_slip_detection_logic(self, binary_manager, tmp_path):
        """Test that the is_relative_to() check would detect malicious paths."""
        from qwenvert.binary_manager import SecurityError

        # Simulate a path that escaped the target directory
        malicious_path = tmp_path / "outside" / "evil-binary"
        malicious_path.parent.mkdir(parents=True, exist_ok=True)
        malicious_path.write_text("malicious")

        # Apply the security check
        extract_path_resolved = malicious_path.resolve()
        bin_dir_resolved = binary_manager.bin_dir.resolve()

        # Malicious path should NOT be relative to target directory
        is_safe = extract_path_resolved.is_relative_to(bin_dir_resolved)
        assert not is_safe, "Path outside target directory should fail validation"

        # This is what our code does when path is unsafe
        if not is_safe:
            # Would raise SecurityError
            with pytest.raises(SecurityError):
                raise SecurityError(
                    f"Zip Slip detected: {extract_path_resolved} is outside {bin_dir_resolved}"
                )

    def test_zip_slip_functional_malicious_archive(self, binary_manager, tmp_path):
        """Functional test: Create real malicious zip and verify production code blocks it."""
        import zipfile

        # Create a malicious zip file with path traversal
        malicious_zip = tmp_path / "malicious.zip"
        with zipfile.ZipFile(malicious_zip, "w") as zf:
            # Try to escape to parent directory
            malicious_member_name = "../../evil-llama-server"
            zf.writestr(malicious_member_name, b"malicious payload")

        # Mock download to return our malicious zip
        with patch("httpx.stream") as mock_stream:
            zip_content = malicious_zip.read_bytes()
            mock_response = Mock()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=None)
            mock_response.headers = {"content-length": str(len(zip_content))}
            mock_response.iter_bytes = Mock(return_value=[zip_content])
            mock_stream.return_value = mock_response

            # Should raise RuntimeError (which wraps SecurityError)
            with pytest.raises(RuntimeError) as exc_info:
                binary_manager._download_and_install_zip(
                    release_url=f"file://{malicious_zip}",
                    version="malicious",
                    zip_filename="malicious.zip",
                )

            # Verify the error message indicates security violation
            error_msg = str(exc_info.value).lower()
            assert (
                "zip slip" in error_msg or "security" in error_msg
            ), f"Expected security error, got: {exc_info.value}"

        # Verify no files were extracted outside bin_dir
        parent_dir = binary_manager.bin_dir.parent
        evil_files = list(parent_dir.glob("**/evil-llama-server"))
        assert len(evil_files) == 0, "Malicious file should not be extracted"

    def test_zip_slip_functional_safe_archive(self, binary_manager, tmp_path):
        """Functional test: Create safe zip and verify production code accepts it."""
        import zipfile

        # Create a safe zip file with proper path
        safe_zip = tmp_path / "safe.zip"
        with zipfile.ZipFile(safe_zip, "w") as zf:
            # Legitimate member name (no path traversal)
            zf.writestr("bin/llama-server", b"safe binary content")

        # Mock download to return our safe zip
        with patch("httpx.stream") as mock_stream:
            zip_content = safe_zip.read_bytes()
            mock_response = Mock()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=None)
            mock_response.headers = {"content-length": str(len(zip_content))}
            mock_response.iter_bytes = Mock(return_value=[zip_content])
            mock_stream.return_value = mock_response

            # Mock binary validation to avoid exec format errors with fake binary
            mock_binary_info = BinaryInfo(
                path=binary_manager.binary_path,
                version="safe",
                source=BinarySource.DOWNLOADED,
                architecture="arm64",
                is_valid=True,
            )

            with patch.object(
                binary_manager, "_get_binary_info", return_value=mock_binary_info
            ):
                # Should succeed without raising
                try:
                    binary_manager._download_and_install_zip(
                        release_url=f"file://{safe_zip}",
                        version="safe",
                        zip_filename="safe.zip",
                    )
                    # Verify binary was created
                    assert (
                        binary_manager.binary_path.exists()
                    ), "Binary should be extracted"
                    assert (
                        binary_manager.binary_path.read_bytes() == b"safe binary content"
                    ), "Binary content should match"
                except Exception as e:
                    pytest.fail(f"Safe archive should not raise exception: {e}")

    def test_zip_slip_functional_absolute_path(self, binary_manager, tmp_path):
        """Functional test: Verify absolute paths in archive are blocked."""
        import zipfile

        # Create a malicious zip with absolute path
        malicious_zip = tmp_path / "absolute.zip"
        with zipfile.ZipFile(malicious_zip, "w") as zf:
            # Absolute path member (intentionally malicious for testing)
            if str(tmp_path).startswith("/"):
                malicious_member = "/tmp/evil-llama-server"  # noqa: S108
            else:
                malicious_member = "C:\\Windows\\System32\\evil-llama-server"
            zf.writestr(malicious_member, b"absolute path payload")

        # Mock download
        with patch("httpx.stream") as mock_stream:
            zip_content = malicious_zip.read_bytes()
            mock_response = Mock()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=None)
            mock_response.headers = {"content-length": str(len(zip_content))}
            mock_response.iter_bytes = Mock(return_value=[zip_content])
            mock_stream.return_value = mock_response

            # Should raise RuntimeError wrapping SecurityError
            with pytest.raises(RuntimeError) as exc_info:
                binary_manager._download_and_install_zip(
                    release_url=f"file://{malicious_zip}",
                    version="absolute",
                    zip_filename="absolute.zip",
                )

            error_msg = str(exc_info.value).lower()
            assert (
                "zip slip" in error_msg or "security" in error_msg
            ), "Should detect absolute path attack"
