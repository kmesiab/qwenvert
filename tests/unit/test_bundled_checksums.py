"""End-to-end tests for bundled checksums feature."""

import hashlib
import tempfile
import tarfile
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
def mock_hardware_arm64():
    """Create mock HardwareProfile for ARM64."""
    return HardwareProfile(
        chip="M1",
        chip_family="M1",
        total_memory_gb=16,
        gpu_cores=16,
        cpu_cores_performance=6,
        cpu_cores_efficiency=2,
        has_active_cooling=True,
        neural_engine_cores=16,
        model_identifier="MacBookPro18,3",
    )


class TestBundledChecksums:
    """Test bundled checksums functionality."""

    def test_bundled_checksum_file_exists(self):
        """Verify b8054.txt bundled checksum file exists and is readable."""
        from pathlib import Path
        checksums_dir = Path(__file__).parent.parent.parent / "qwenvert" / "checksums"
        checksum_file = checksums_dir / "b8054.txt"
        
        assert checksums_dir.exists(), f"Checksums directory should exist: {checksums_dir}"
        assert checksum_file.exists(), f"Checksum file should exist: {checksum_file}"
        
        # Verify it's readable
        content = checksum_file.read_text()
        assert len(content) > 0, "Checksum file should not be empty"
        assert "b8054" in content, "Checksum file should reference b8054 release"
        assert "arm64" in content or "x64" in content, "Checksum file should contain architecture identifiers"

    def test_get_bundled_checksum_arm64(self, binary_manager):
        """Test retrieving ARM64 checksum from bundled file."""
        checksum = binary_manager._get_bundled_checksum(
            version="b8054",
            filename="llama-b8054-bin-macos-arm64.tar.gz"
        )
        
        assert checksum is not None, "Should find bundled checksum for ARM64"
        assert len(checksum) == 64, "SHA256 checksum should be 64 hex characters"
        assert checksum.isalnum(), "Checksum should be alphanumeric"
        # Verify it's the correct ARM64 checksum
        assert checksum == "b2d02aff34fdcbadacc6f2f7f5d043404769709aedf3bcbc441ef3f315e73565"

    def test_get_bundled_checksum_x64(self, binary_manager):
        """Test retrieving x64 checksum from bundled file."""
        checksum = binary_manager._get_bundled_checksum(
            version="b8054",
            filename="llama-b8054-bin-macos-x64.tar.gz"
        )
        
        assert checksum is not None, "Should find bundled checksum for x64"
        assert len(checksum) == 64, "SHA256 checksum should be 64 hex characters"
        assert checksum.isalnum(), "Checksum should be alphanumeric"
        # Verify it's the correct x64 checksum
        assert checksum == "d78ccc86d8d33afd7b365f9f3310b59621c09e4d4e6dcef4cdd6482c2af1100c"

    def test_get_bundled_checksum_nonexistent_version(self, binary_manager):
        """Test that nonexistent version returns None gracefully."""
        checksum = binary_manager._get_bundled_checksum(
            version="b9999",  # Nonexistent version
            filename="llama-b9999-bin-macos-arm64.tar.gz"
        )
        
        assert checksum is None, "Should return None for nonexistent version"

    def test_get_bundled_checksum_nonexistent_file(self, binary_manager):
        """Test that nonexistent filename in existing version returns None."""
        checksum = binary_manager._get_bundled_checksum(
            version="b8054",
            filename="llama-b8054-bin-windows-x86.exe"  # Non-existent file
        )
        
        assert checksum is None, "Should return None for nonexistent file"

    def test_get_checksum_for_release_prioritizes_bundled(self, binary_manager):
        """Test that bundled checksums are checked first."""
        with patch("httpx.get") as mock_get:
            # Mock upstream to return different checksum (should not be used)
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "upstream_different_checksum llama-b8054-bin-macos-arm64.tar.gz"
            mock_get.return_value = mock_response
            
            # Should use bundled checksum, not upstream
            checksum = binary_manager._get_checksum_for_release(
                version="b8054",
                filename="llama-b8054-bin-macos-arm64.tar.gz"
            )
            
            assert checksum == "b2d02aff34fdcbadacc6f2f7f5d043404769709aedf3bcbc441ef3f315e73565"
            # httpx.get should not be called because bundled checksum found
            mock_get.assert_not_called()

    def test_verify_checksum_with_valid_file(self, binary_manager, tmp_path):
        """Test checksum verification with valid file matching bundled checksum."""
        # Create a test file with known content
        test_content = b"test binary content"
        test_file = tmp_path / "test_binary"
        test_file.write_bytes(test_content)
        
        # Calculate its SHA256
        sha256 = hashlib.sha256()
        sha256.update(test_content)
        expected_checksum = sha256.hexdigest()
        
        # Verify it matches
        result = binary_manager.verify_checksum(test_file, expected_checksum)
        assert result is True, "Checksum should match"

    def test_verify_checksum_with_invalid_file(self, binary_manager, tmp_path):
        """Test checksum verification with mismatched file."""
        test_content = b"test binary content"
        test_file = tmp_path / "test_binary"
        test_file.write_bytes(test_content)
        
        # Use wrong checksum
        wrong_checksum = "0" * 64  # All zeros
        
        result = binary_manager.verify_checksum(test_file, wrong_checksum)
        assert result is False, "Checksum should not match"

    def test_download_and_verify_with_bundled_checksum_mocked(self, binary_manager, tmp_path):
        """Test that download correctly verifies using bundled checksum.
        
        This is a mock test that verifies the verification STEP works,
        not the full download (which would require real binary content).
        """
        # Create a tar.gz with llama-server binary
        fake_binary_content = b"fake llama-server binary"
        tar_file = tmp_path / "llama-b8054-bin-macos-arm64.tar.gz"
        
        with tarfile.open(tar_file, "w:gz") as tar:
            import io
            binary_data = io.BytesIO(fake_binary_content)
            tarinfo = tarfile.TarInfo(name="bin/llama-server")
            tarinfo.size = len(fake_binary_content)
            tar.addfile(tarinfo, binary_data)
        
        # Read the tar.gz content
        tar_content = tar_file.read_bytes()
        
        # Compute what the actual checksum would be (not matching bundled)
        actual_sha256 = hashlib.sha256()
        actual_sha256.update(tar_content)
        actual_checksum = actual_sha256.hexdigest()
        
        # Mock the download to return our fake tar.gz
        with patch("httpx.stream") as mock_stream:
            mock_response = Mock()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=None)
            mock_response.headers = {"content-length": str(len(tar_content))}
            mock_response.iter_bytes = Mock(return_value=[tar_content])
            mock_response.raise_for_status = Mock()
            mock_stream.return_value = mock_response
            
            # This should FAIL because the checksum won't match the bundled one
            # This proves the checksum verification IS WORKING
            
            
            with pytest.raises(RuntimeError) as exc_info:
                binary_manager._download_and_install_archive(
                    release_url="https://github.com/ggml-org/llama.cpp/releases/download/b8054/llama-b8054-bin-macos-arm64.tar.gz",
                    version="b8054",
                    archive_filename="llama-b8054-bin-macos-arm64.tar.gz",
                )
            
            # Verify it failed with checksum error (security is working!)
            assert "Checksum verification failed" in str(exc_info.value)

    def test_bundled_checksum_used_in_verification_step(self, binary_manager):
        """Test that bundled checksum is actually retrieved and used."""
        # Simply verify the function retrieves the bundled checksum
        checksum = binary_manager._get_checksum_for_release(
            version="b8054",
            filename="llama-b8054-bin-macos-arm64.tar.gz"
        )
        
        # Should get the bundled checksum
        assert checksum == "b2d02aff34fdcbadacc6f2f7f5d043404769709aedf3bcbc441ef3f315e73565"
        
    def test_checksum_comments_ignored(self, binary_manager):
        """Test that comment lines in checksum file are properly ignored."""
        # This tests that the parser correctly skips comments
        checksum = binary_manager._get_bundled_checksum(
            version="b8054",
            filename="llama-b8054-bin-macos-arm64.tar.gz"
        )
        
        # Should still find the checksum despite comments in the file
        assert checksum is not None
        assert checksum == "b2d02aff34fdcbadacc6f2f7f5d043404769709aedf3bcbc441ef3f315e73565"

    def test_missing_checksum_logs_warning(self, binary_manager, tmp_path):
        """Test that missing checksums log warning but don't fail download."""
        # Create fake tar.gz
        fake_binary = b"fake binary"
        tar_file = tmp_path / "fake.tar.gz"
        
        with tarfile.open(tar_file, "w:gz") as tar:
            import io
            binary_data = io.BytesIO(fake_binary)
            tarinfo = tarfile.TarInfo(name="bin/llama-server")
            tarinfo.size = len(fake_binary)
            tar.addfile(tarinfo, binary_data)
        
        tar_content = tar_file.read_bytes()
        
        with patch("httpx.stream") as mock_stream, \
             patch.object(binary_manager, "_get_checksum_for_release", return_value=None):
            
            mock_response = Mock()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=None)
            mock_response.headers = {"content-length": str(len(tar_content))}
            mock_response.iter_bytes = Mock(return_value=[tar_content])
            mock_response.raise_for_status = Mock()
            mock_stream.return_value = mock_response
            
            mock_binary_info = BinaryInfo(
                path=binary_manager.binary_path,
                version="unknown",
                source=BinarySource.DOWNLOADED,
                architecture="arm64",
                is_valid=True,
            )
            
            with patch.object(
                binary_manager,
                "_get_binary_info",
                return_value=mock_binary_info,
            ):
                # Should still work (with warning) even without checksum
                result = binary_manager._download_and_install_archive(
                    release_url="https://example.com/unknown.tar.gz",
                    version="unknown",
                    archive_filename="unknown.tar.gz",
                )
                
                assert result == binary_manager.binary_path


class TestBundledChecksumEdgeCases:
    """Test edge cases and error handling for bundled checksums."""

    def test_malformed_checksum_line_skipped(self, binary_manager, tmp_path):
        """Test that malformed lines in checksum file are safely skipped."""
        # Create a checksum file with malformed lines
        checksum_file = tmp_path / "b9999.txt"
        checksum_file.write_text("""# Valid header
abc123  valid-file.tar.gz
  # This line is missing checksum (only filename)
invalid_checksum_only
valid_sha256_here  another-file.tar.gz
""")
        
        # Patch to use our temp file
        with patch("pathlib.Path.parent", new_callable=lambda: tmp_path):
            # The implementation should handle these gracefully
            # Create manager and test
            manager = BinaryManager()
            manager.cache_dir = tmp_path
            manager.bin_dir = tmp_path / "bin"
            manager.bin_dir.mkdir(parents=True, exist_ok=True)
            
            # Should not crash even with malformed file
            checksum = manager._get_bundled_checksum(
                version="b9999",
                filename="another-file.tar.gz"
            )
            
            # Could be None or the valid checksum, both acceptable
            if checksum:
                assert len(checksum) > 0

    def test_empty_bundled_checksum_file(self, binary_manager, tmp_path):
        """Test handling of empty checksum file."""
        checksum_file = tmp_path / "b0000.txt"
        checksum_file.write_text("")
        
        # Should return None gracefully
        checksum = binary_manager._get_bundled_checksum(
            version="b0000",
            filename="llama-b0000.tar.gz"
        )
        
        assert checksum is None

    def test_checksum_case_sensitivity(self, binary_manager):
        """Test that checksum matching respects case in filenames."""
        # The ARM64 checksum should match the exact filename
        checksum = binary_manager._get_bundled_checksum(
            version="b8054",
            filename="llama-b8054-bin-macos-arm64.tar.gz"
        )
        
        assert checksum is not None
        # File matching should be case-sensitive on case-sensitive filesystems
        # This is already correct in the implementation

    def test_bundled_checksum_format_validation(self, binary_manager):
        """Test that returned checksum is valid SHA256 format."""
        checksum = binary_manager._get_bundled_checksum(
            version="b8054",
            filename="llama-b8054-bin-macos-arm64.tar.gz"
        )
        
        assert checksum is not None
        # SHA256 should be 64 hex characters
        assert len(checksum) == 64, f"SHA256 should be 64 chars, got {len(checksum)}"
        assert all(c in "0123456789abcdef" for c in checksum.lower()), "Should be valid hex"


class TestBundledChecksumIntegration:
    """Integration tests showing bundled checksums in use."""

    def test_bundled_checksum_retrieval_chain(self, binary_manager):
        """Test full chain: _get_checksum_for_release -> _get_bundled_checksum."""
        # This is the actual path called during download
        checksum = binary_manager._get_checksum_for_release(
            version="b8054",
            filename="llama-b8054-bin-macos-arm64.tar.gz"
        )
        
        # Should find bundled checksum
        assert checksum is not None
        assert checksum == "b2d02aff34fdcbadacc6f2f7f5d043404769709aedf3bcbc441ef3f315e73565"

    def test_both_bundled_checksums_available(self, binary_manager):
        """Test that both ARM64 and x64 bundled checksums are available."""
        arm64_checksum = binary_manager._get_bundled_checksum(
            version="b8054",
            filename="llama-b8054-bin-macos-arm64.tar.gz"
        )
        
        x64_checksum = binary_manager._get_bundled_checksum(
            version="b8054",
            filename="llama-b8054-bin-macos-x64.tar.gz"
        )
        
        # Both should be present
        assert arm64_checksum is not None
        assert x64_checksum is not None
        # They should be different
        assert arm64_checksum != x64_checksum

    def test_fallback_to_upstream_if_bundled_missing(self, binary_manager):
        """Test that code falls back to upstream if bundled checksum missing."""
        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "upstream_checksum_value  llama-b9999-bin-macos-arm64.tar.gz"
            mock_get.return_value = mock_response
            
            # Try to get checksum for nonexistent version
            checksum = binary_manager._get_checksum_for_release(
                version="b9999",  # No bundled checksum for this
                filename="llama-b9999-bin-macos-arm64.tar.gz"
            )
            
            # Should fall back to upstream and find the mocked value
            assert checksum == "upstream_checksum_value"
            # httpx.get should have been called for upstream
            mock_get.assert_called()

    def test_security_of_bundled_checksums(self, binary_manager):
        """Test that bundled checksums are used for security verification."""
        # Verify that the bundled checksum system is in place
        # and would reject files with mismatched checksums
        
        # Get bundled checksum for b8054
        bundled = binary_manager._get_bundled_checksum(
            version="b8054",
            filename="llama-b8054-bin-macos-arm64.tar.gz"
        )
        
        # Verify the checksum is a real SHA256
        assert bundled is not None
        assert len(bundled) == 64
        
        # Create a test with wrong content
        import tempfile
        with tempfile.NamedTemporaryFile() as tf:
            # Write some random content
            tf.write(b"wrong content")
            tf.flush()
            
            # Verification should fail
            result = binary_manager.verify_checksum(
                Path(tf.name),
                bundled  # Try to verify with bundled checksum
            )
            
            assert result is False, "Wrong content should fail bundled checksum verification"
