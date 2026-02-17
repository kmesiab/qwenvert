"""
Binary management for llama-server.

Handles detection, download, and lifecycle management of llama-server
binaries from official llama.cpp releases.
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx


if TYPE_CHECKING:
    from .hardware import HardwareProfile


logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when a security violation is detected (e.g., Zip Slip attack)."""


class BinarySource(Enum):
    """Source of llama-server binary."""

    SYSTEM = "system"  # Found in system PATH
    HOMEBREW = "homebrew"  # Installed via Homebrew
    DOWNLOADED = "downloaded"  # Downloaded by qwenvert
    COMPILED = "compiled"  # User-compiled from source


@dataclass
class BinaryInfo:
    """Metadata about a llama-server binary."""

    path: Path
    version: str
    source: BinarySource
    architecture: str  # arm64, x86_64
    is_valid: bool

    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"{self.path} (v{self.version}, {self.source.value}, {self.architecture})"
        )


class BinaryManager:
    """Manages llama-server binary lifecycle."""

    # Official llama.cpp GitHub releases (migrated to ggml-org)
    GITHUB_REPO = "ggml-org/llama.cpp"
    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

    # Local storage
    CACHE_DIR = Path.home() / ".cache" / "qwenvert"
    BIN_DIR = CACHE_DIR / "bin"
    BINARY_NAME = "llama-server"

    def __init__(self) -> None:
        """Initialize binary manager."""
        self.cache_dir = self.CACHE_DIR
        self.bin_dir = self.BIN_DIR
        self.binary_path = self.bin_dir / self.BINARY_NAME

        # Ensure directories exist
        self.bin_dir.mkdir(parents=True, exist_ok=True)

    def detect_binary(self) -> BinaryInfo | None:
        """
        Detect existing llama-server installation.

        Checks in priority order:
        1. Local cache (~/.cache/qwenvert/bin/)
        2. System PATH (which llama-server)
        3. Homebrew (/opt/homebrew/bin/llama-server)

        Returns:
            BinaryInfo if found and valid, None otherwise
        """
        # Check local cache first (fastest)
        if self.binary_path.exists():
            info = self._get_binary_info(self.binary_path, BinarySource.DOWNLOADED)
            if info and info.is_valid:
                logger.info(f"Found llama-server in cache: {info}")
                return info

        # Check system PATH
        system_path = shutil.which(self.BINARY_NAME)
        if system_path:
            info = self._get_binary_info(Path(system_path), BinarySource.SYSTEM)
            if info and info.is_valid:
                logger.info(f"Found llama-server in PATH: {info}")
                return info

        # Check Homebrew location
        homebrew_path = Path("/opt/homebrew/bin") / self.BINARY_NAME
        if homebrew_path.exists():
            info = self._get_binary_info(homebrew_path, BinarySource.HOMEBREW)
            if info and info.is_valid:
                logger.info(f"Found llama-server in Homebrew: {info}")
                return info

        logger.info("No valid llama-server binary found")
        return None

    def _get_binary_info(
        self, binary_path: Path, source: BinarySource
    ) -> BinaryInfo | None:
        """
        Get metadata about a binary.

        Args:
            binary_path: Path to binary
            source: Source of binary

        Returns:
            BinaryInfo if valid, None if invalid
        """
        try:
            # Check if executable
            if not binary_path.is_file():
                return None

            # Try to get version
            result = subprocess.run(
                [str(binary_path), "--version"],
                capture_output=True,
                text=True,
                timeout=15,  # Metal library initialization can take 8-10 seconds
                check=False,
            )

            if result.returncode != 0:
                logger.warning(f"Binary {binary_path} failed version check")
                return None

            # Parse version (example: "llama-server version: b1234 (1234)")
            version_output = result.stdout.strip()
            version = self._parse_version(version_output)

            # Get architecture
            arch = self._get_architecture(binary_path)

            return BinaryInfo(
                path=binary_path,
                version=version,
                source=source,
                architecture=arch,
                is_valid=True,
            )

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Failed to get info for {binary_path}: {e}")
            return None

    def _parse_version(self, version_output: str) -> str:
        """
        Parse version from llama-server output.

        Args:
            version_output: Output from --version command

        Returns:
            Version string (e.g., "b1234")
        """
        # Example: "llama-server version: b1234 (1234)"
        # Extract the build number
        parts = version_output.split()
        for i, part in enumerate(parts):
            if part == "version:" and i + 1 < len(parts):
                return parts[i + 1]

        # Fallback: use full output
        return version_output[:50]  # Truncate to reasonable length

    def _get_architecture(self, binary_path: Path) -> str:
        """
        Get binary architecture.

        Args:
            binary_path: Path to binary

        Returns:
            Architecture string (arm64 or x86_64)
        """
        try:
            result = subprocess.run(
                ["file", str(binary_path)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            output = result.stdout.lower()

            if "arm64" in output or "aarch64" in output:
                return "arm64"
            if "x86_64" in output or "x86-64" in output:
                return "x86_64"

            return "unknown"

        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return "unknown"

    def _validate_extract_path(self, member_path: str) -> None:
        """
        Validate that an archive member path does not escape the bin directory.

        Args:
            member_path: Path of the archive member

        Raises:
            SecurityError: If path traversal attack detected
        """
        intended_path = (self.bin_dir / member_path).resolve()
        bin_dir_resolved = self.bin_dir.resolve()

        if not intended_path.is_relative_to(bin_dir_resolved):
            raise SecurityError(
                f"Path traversal attack detected: Archive member '{member_path}' "
                f"would extract to '{intended_path}', "
                f"which is outside the target directory '{bin_dir_resolved}'. "
                "This archive may be malicious."
            )

    def _extract_from_tarball(self, archive_path: Path, release_url: str) -> None:
        """
        Extract llama-server from a .tar.gz archive with path traversal protection.

        Args:
            archive_path: Path to the tar.gz archive
            release_url: URL of the release (for error messages)

        Raises:
            RuntimeError: If no llama-server found in archive
            SecurityError: If path traversal attack detected
        """
        with tarfile.open(archive_path, "r:gz") as tar_ref:
            # Find llama-server executable in the archive
            llama_server_files = [
                member.name
                for member in tar_ref.getmembers()
                if member.name.endswith(("llama-server", "llama-server.exe"))
                and member.isfile()
            ]

            if not llama_server_files:
                raise RuntimeError(f"No llama-server executable found in {release_url}")

            # Extract ALL files (binary + dylibs), stripping top-level directory
            llama_server_path = llama_server_files[0]
            logger.info(f"Extracting {llama_server_path} and dependencies from archive")

            # Extract all members, stripping the version directory (e.g., llama-b8072/)
            for member in tar_ref.getmembers():
                if not (member.isfile() or member.issym() or member.islnk()):
                    continue  # Skip directories, keep files and symlinks

                # Strip first path component (e.g., "llama-b8072/file" -> "file")
                parts = member.name.split('/', 1)
                if len(parts) < 2:
                    continue

                stripped_name = parts[1]

                # SECURITY: Validate stripped path (Zip Slip protection)
                self._validate_extract_path(stripped_name)

                # Extract to bin_dir with stripped name
                member.name = stripped_name
                if hasattr(tarfile, "data_filter"):
                    tar_ref.extract(member, self.bin_dir, filter="data")
                else:
                    tar_ref.extract(member, self.bin_dir)

            logger.info(f"Extracted binary and {len([m for m in tar_ref.getmembers() if m.isfile()])} dependencies")

    def _extract_from_zip(self, archive_path: Path, release_url: str) -> None:
        """
        Extract llama-server from a .zip archive with path traversal protection.

        Args:
            archive_path: Path to the zip archive
            release_url: URL of the release (for error messages)

        Raises:
            RuntimeError: If no llama-server found in archive
            SecurityError: If path traversal attack detected
        """
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            # Find llama-server executable in the archive
            llama_server_files = [
                name
                for name in zip_ref.namelist()
                if name.endswith(("llama-server", "llama-server.exe"))
            ]

            if not llama_server_files:
                raise RuntimeError(f"No llama-server executable found in {release_url}")

            # Extract the executable
            llama_server_path = llama_server_files[0]
            logger.info(f"Extracting {llama_server_path} from zip archive")

            # SECURITY: Validate extraction path BEFORE extracting
            self._validate_extract_path(llama_server_path)

            # Safe to extract - path has been validated
            extract_path = Path(zip_ref.extract(llama_server_path, self.bin_dir))

            # Move to final location
            shutil.move(extract_path, self.binary_path)

    def _download_and_install_archive(
        self,
        release_url: str,
        version: str,
        archive_filename: str,
        progress_callback: Any = None,
    ) -> Path:
        """
        Download, verify, extract, and install llama-server from archive URL.

        Supports both .zip and .tar.gz formats (auto-detected from URL).

        Args:
            release_url: Full URL to archive file (.zip or .tar.gz)
            version: Version string for checksum lookup
            archive_filename: Name of archive file for checksum lookup
            progress_callback: Optional callback for download progress

        Returns:
            Path to installed binary

        Raises:
            RuntimeError: If download, verification, or installation fails
            SecurityError: If path traversal attack detected
        """
        temp_archive = None
        is_tarball = archive_filename.endswith((".tar.gz", ".tgz"))
        suffix = ".tar.gz" if is_tarball else ".zip"

        try:
            # Create temporary file for archive download
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                temp_archive = Path(temp_file.name)

            # Download archive
            self._download_file(release_url, temp_archive, progress_callback)

            # SECURITY: Attempt checksum verification (best-effort with fallback)
            # Try to get checksum from: 1) bundled repo checksums, 2) GitHub release assets
            expected_checksum = self._get_checksum_for_release(
                version, archive_filename
            )

            if expected_checksum:
                logger.info("Verifying download integrity...")
                if not self.verify_checksum(temp_archive, expected_checksum):
                    raise RuntimeError(
                        f"Checksum verification failed for {archive_filename}. "
                        "The downloaded file may be corrupted or tampered with."
                    )
                logger.info("✓ Checksum verification passed")
            else:
                # WARNING: ggml-org/llama.cpp does not publish checksums (as of Feb 2026)
                # We trust HTTPS + GitHub's infrastructure as a fallback
                logger.warning(
                    f"⚠️  Checksum not available for {archive_filename} in release {version}"
                )
                logger.warning(
                    "⚠️  Installing without checksum verification (trusting HTTPS + GitHub)"
                )
                logger.warning(
                    "⚠️  Please report missing checksums: https://github.com/ggml-org/llama.cpp/issues"
                )

            # Extract llama-server executable from archive
            if is_tarball:
                self._extract_from_tarball(temp_archive, release_url)
            else:
                self._extract_from_zip(temp_archive, release_url)

        except SecurityError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Failed to download llama-server from {release_url}: {e}"
            ) from e
        finally:
            # Clean up temporary archive file
            if temp_archive and temp_archive.exists():
                temp_archive.unlink()

        # Make executable
        self.binary_path.chmod(self.binary_path.stat().st_mode | stat.S_IEXEC)

        # Verify it works
        info = self._get_binary_info(self.binary_path, BinarySource.DOWNLOADED)
        if not info or not info.is_valid:
            raise RuntimeError(
                f"Downloaded binary at {self.binary_path} failed validation"
            )

        logger.info(f"Successfully installed llama-server: {info}")
        return self.binary_path

    def download_binary(
        self, hardware: HardwareProfile, progress_callback: Any = None
    ) -> Path:
        """
        Download pre-built llama-server binary from GitHub releases.

        Args:
            hardware: Hardware profile for selecting correct binary
            progress_callback: Optional callback for download progress

        Returns:
            Path to downloaded binary

        Raises:
            RuntimeError: If download fails
        """
        logger.info(f"Downloading llama-server for {hardware.chip}")

        # Get release URL for latest version
        release_url = self._get_release_url(hardware)

        # Extract version and filename from URL for checksum verification
        # URL format: https://github.com/.../releases/download/b8054/llama-b8054-bin-macos-arm64.tar.gz
        url_parts = release_url.split("/")
        version = url_parts[-2]  # e.g., "b8054"
        archive_filename = url_parts[-1]  # e.g., "llama-b8054-bin-macos-arm64.tar.gz"

        # Use common download/install logic
        return self._download_and_install_archive(
            release_url, version, archive_filename, progress_callback
        )

    def _get_checksum_for_release(self, version: str, filename: str) -> str | None:
        """
        Fetch SHA256 checksum for a release file.

        Tries multiple sources in order:
        1. Bundled checksums in qwenvert repo (checksums/ directory)
        2. Checksum files published with GitHub release

        Args:
            version: Release version tag
            filename: Name of the file to get checksum for

        Returns:
            SHA256 checksum string, or None if not found
        """
        try:
            # FIRST: Try bundled checksums from qwenvert repo
            # These are self-hosted verified checksums we maintain
            bundled_checksum = self._get_bundled_checksum(version, filename)
            if bundled_checksum:
                logger.info(
                    f"Found bundled checksum for {filename}: {bundled_checksum[:16]}..."
                )
                return bundled_checksum

            # SECOND: Try upstream checksum files from llama.cpp releases
            # (ggml-org doesn't publish these as of Feb 2026, but we check anyway)
            checksum_files = ["SHA256SUMS", "checksums.txt", f"{filename}.sha256"]

            base_url = (
                f"https://github.com/{self.GITHUB_REPO}/releases/download/{version}"
            )

            for checksum_file in checksum_files:
                try:
                    checksum_url = f"{base_url}/{checksum_file}"
                    response = httpx.get(
                        checksum_url,
                        timeout=10.0,
                        follow_redirects=True,
                    )

                    if response.status_code == 200:
                        # Parse checksum file (format: "checksum filename")
                        content = response.text
                        for line in content.splitlines():
                            parts = line.split()
                            if len(parts) >= 2:
                                checksum, file_in_line = parts[0], parts[1]
                                # Match filename (with or without path prefix)
                                if filename in file_in_line or file_in_line in filename:
                                    logger.info(
                                        f"Found upstream checksum for {filename}: {checksum[:16]}..."
                                    )
                                    return checksum

                except httpx.HTTPError:
                    continue

            logger.debug(
                f"No checksum found for {filename} in release {version} "
                "(neither bundled nor upstream)"
            )
            return None

        except Exception as e:
            logger.warning(f"Failed to fetch checksum: {e}")
            return None

    def _get_bundled_checksum(self, version: str, filename: str) -> str | None:
        """
        Get checksum from bundled checksums directory.

        Qwenvert maintains verified checksums for llama.cpp releases
        in the repo at: qwenvert/checksums/{version}.txt

        Args:
            version: Release version tag (e.g., "b8054")
            filename: Archive filename (e.g., "llama-b8054-bin-macos-arm64.tar.gz")

        Returns:
            SHA256 checksum string, or None if not found
        """
        try:
            # Look for checksums in package data directory
            # Try to find checksums directory relative to this file
            checksums_dir = Path(__file__).parent / "checksums"

            if not checksums_dir.exists():
                return None

            # Check for version-specific checksum file
            checksum_file = checksums_dir / f"{version}.txt"

            if not checksum_file.exists():
                return None

            # Parse checksum file (format: "checksum filename" per line)
            content = checksum_file.read_text()
            for raw_line in content.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split()
                if len(parts) >= 2:
                    checksum, file_in_line = parts[0], parts[1]
                    # Match filename (with or without path prefix)
                    if filename in file_in_line or file_in_line in filename:
                        return checksum

            return None

        except Exception as e:
            logger.debug(f"Failed to read bundled checksum: {e}")
            return None

    def get_latest_release_version(self, use_cache: bool = True) -> str:
        """
        Fetch latest stable release version from GitHub API.

        Falls back to cached version if offline, then to known-good version.

        Args:
            use_cache: If True, use cached version when GitHub API unavailable

        Returns:
            Latest release version tag (e.g., "b3600")
        """
        try:
            response = httpx.get(
                self.GITHUB_API_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10.0,
                follow_redirects=True,
            )
            response.raise_for_status()

            data = response.json()
            version = data.get("tag_name", "")

            if not version:
                raise RuntimeError("No tag_name in GitHub API response")

            logger.info(f"Latest llama.cpp release: {version}")
            return version

        except httpx.HTTPError as e:
            logger.warning(f"GitHub API unavailable: {e}")

            # Try cache fallback if enabled
            if use_cache:
                cache_data = self._load_version_cache()
                if cache_data:
                    logger.info(f"Using cached version: {cache_data['version']}")
                    return cache_data["version"]

            # Final fallback to known-good version
            logger.warning("Falling back to hardcoded version b3600")
            return "b3600"

    def _get_release_url(self, hardware: HardwareProfile) -> str:
        """
        Get download URL for appropriate binary.

        Args:
            hardware: Hardware profile

        Returns:
            Download URL for binary

        Raises:
            RuntimeError: If unable to determine release URL
        """
        base_url = f"https://github.com/{self.GITHUB_REPO}/releases/download"

        # Determine architecture - robust check for Apple Silicon
        machine_lower = platform.machine().lower()

        # Apple Silicon detection: Use chip_family (M1/M2/M3/M4/M5/etc) or arm64 architecture
        # chip_family is extracted via M\d+ regex, so it's future-proof for new M-series chips
        is_apple_silicon = (
            hardware.chip_family.startswith("M")  # M1, M2, M3, M4, M5, etc.
            or "arm" in hardware.chip.lower()
            or "arm64" in machine_lower
            or "aarch64" in machine_lower
        )

        # Note: llama.cpp releases use "arm64" and "x64" (not "x86_64")
        arch = "arm64" if is_apple_silicon else "x64"

        logger.info(
            f"Detected architecture: {arch} (chip={hardware.chip}, machine={platform.machine()})"
        )

        # Get latest release version dynamically
        version = self.get_latest_release_version()

        # Construct URL (format changed from .zip to .tar.gz after repo migration)
        # Example: https://github.com/ggml-org/llama.cpp/releases/download/b8054/llama-b8054-bin-macos-arm64.tar.gz
        url = f"{base_url}/{version}/llama-{version}-bin-macos-{arch}.tar.gz"

        logger.info(f"Release URL: {url}")
        return url

    def _download_file(
        self, url: str, dest: Path, progress_callback: Any = None
    ) -> None:
        """
        Download file from URL.

        Args:
            url: Download URL
            dest: Destination path
            progress_callback: Optional progress callback

        Raises:
            RuntimeError: If download fails
        """
        try:
            with httpx.stream(
                "GET", url, follow_redirects=True, timeout=300
            ) as response:
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(dest, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size:
                            progress_callback(downloaded, total_size)

        except httpx.HTTPError as e:
            raise RuntimeError(f"HTTP error downloading {url}: {e}") from e
        except OSError as e:
            raise RuntimeError(f"File error downloading to {dest}: {e}") from e

    def verify_checksum(self, binary_path: Path, expected_checksum: str) -> bool:
        """
        Verify binary checksum.

        Args:
            binary_path: Path to binary
            expected_checksum: Expected SHA256 checksum

        Returns:
            True if checksum matches
        """
        sha256 = hashlib.sha256()

        with open(binary_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        actual_checksum = sha256.hexdigest()

        if actual_checksum != expected_checksum:
            logger.warning(
                f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
            )
            return False

        logger.info("Checksum verification passed")
        return True

    def get_binary_path(self) -> Path:
        """
        Get path to binary (whether it exists or not).

        Returns:
            Path where binary should be/is located
        """
        return self.binary_path

    def _save_version_cache(
        self, version: str, url: str, checksum: str | None = None
    ) -> None:
        """
        Cache version information for offline operation.

        Args:
            version: Release version tag
            url: Download URL
            checksum: Optional SHA256 checksum
        """
        cache_file = self.cache_dir / "version_cache.json"
        cache_data = {
            "version": version,
            "download_url": url,
            "checksum": checksum,
            "timestamp": time.time(),
            "architecture": platform.machine(),
        }

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)
            logger.info(f"Cached version info for {version}")
        except OSError as e:
            logger.warning(f"Failed to save version cache: {e}")

    def _load_version_cache(self) -> dict | None:
        """
        Load cached version information.

        Returns:
            Cached version data if valid (<24h old, matching arch), None otherwise
        """
        cache_file = self.cache_dir / "version_cache.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cache_data = json.load(f)

            # Check cache age (24 hour TTL)
            age_hours = (time.time() - cache_data["timestamp"]) / 3600
            if age_hours > 24:
                logger.info(f"Version cache expired ({age_hours:.1f}h old)")
                return None

            # Check architecture match
            if cache_data.get("architecture") != platform.machine():
                logger.warning("Architecture mismatch in version cache")
                return None

            logger.info(f"Using cached version info: {cache_data['version']}")
            return cache_data

        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load version cache: {e}")
            return None

    def install_via_homebrew(self) -> Path | None:
        """
        Attempt to install llama.cpp via Homebrew.

        Returns:
            Path to installed binary if successful, None otherwise
        """
        # Check if Homebrew is available
        brew_path = shutil.which("brew")
        if not brew_path:
            logger.warning("Homebrew not found - cannot auto-install")
            return None

        logger.info("Attempting to install llama.cpp via Homebrew...")

        try:
            # Run brew install with timeout
            result = subprocess.run(
                [brew_path, "install", "llama.cpp"],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=False,
            )

            if result.returncode != 0:
                logger.warning(f"Homebrew installation failed: {result.stderr}")
                return None

            logger.info("Successfully installed llama.cpp via Homebrew")

            # Detect the newly installed binary
            binary_info = self.detect_binary()
            if binary_info:
                return binary_info.path

            return None

        except subprocess.TimeoutExpired:
            logger.warning("Homebrew installation timed out after 5 minutes")
            return None
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Failed to install via Homebrew: {e}")
            return None

    def get_or_install_binary(
        self,
        hardware: HardwareProfile | None = None,
        auto_install: bool = True,
    ) -> BinaryInfo:
        """
        Get llama-server binary using multi-strategy approach.

        This method tries multiple strategies in order until one succeeds:
        1. Detect existing (cache/PATH/Homebrew)
        2. Download from GitHub (if online and auto_install=True)
        3. Install via Homebrew (if available and auto_install=True)
        4. Use cached version info for offline download retry

        Args:
            hardware: Hardware profile (auto-detected if None)
            auto_install: If True, automatically install if not found

        Returns:
            BinaryInfo for available binary

        Raises:
            RuntimeError: If all strategies fail
        """
        # Strategy 1: Try to detect existing binary
        binary_info = self.detect_binary()
        if binary_info:
            logger.info(f"Using existing binary: {binary_info}")
            return binary_info

        if not auto_install:
            raise RuntimeError(
                "llama-server not found and auto-install disabled. "
                "Install manually or run without --no-auto-install flag."
            )

        # Import here to avoid circular dependency
        if hardware is None:
            from .hardware import HardwareDetector

            detector = HardwareDetector()
            hardware = detector.detect()

        # Strategy 2: Try to download from GitHub
        logger.info("Binary not found - attempting automatic installation...")
        try:
            binary_path: Path | None = self.download_binary(hardware)
            if binary_path:
                binary_info = self._get_binary_info(
                    binary_path, BinarySource.DOWNLOADED
                )
                if binary_info:
                    # Cache successful download info for offline use
                    version = binary_info.version
                    url = self._get_release_url(hardware)
                    self._save_version_cache(version, url)
                    return binary_info
        except Exception as e:
            logger.warning(f"GitHub download failed: {e}")

        # Strategy 3: Try Homebrew installation
        logger.info("Trying Homebrew installation...")
        binary_path = self.install_via_homebrew()
        if binary_path:
            binary_info = self._get_binary_info(binary_path, BinarySource.HOMEBREW)
            if binary_info:
                return binary_info

        # All strategies failed
        raise RuntimeError(
            "Failed to install llama-server automatically. "
            "Please install manually:\n"
            "  1. Via Homebrew: brew install llama.cpp\n"
            "  2. Download from: https://github.com/ggml-org/llama.cpp/releases\n"
            "  3. Or use Ollama backend: qwenvert init --backend ollama"
        )

    def list_available_versions(self, limit: int = 10) -> list[dict]:
        """
        List available llama.cpp releases from GitHub.

        Args:
            limit: Maximum number of versions to return

        Returns:
            List of dicts with version, date, and download info
        """
        try:
            url = f"https://api.github.com/repos/{self.GITHUB_REPO}/releases"
            response = httpx.get(
                url,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10.0,
                params={"per_page": limit},
                follow_redirects=True,
            )
            response.raise_for_status()

            releases = response.json()
            versions = []

            for release in releases[:limit]:
                versions.append(
                    {
                        "version": release.get("tag_name", "unknown"),
                        "date": release.get("published_at", "unknown"),
                        "url": release.get("html_url", ""),
                        "prerelease": release.get("prerelease", False),
                    }
                )

            return versions

        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch releases from GitHub: {e}")
            return []

    def get_installed_version(self) -> str | None:
        """
        Get version of currently installed binary.

        Returns:
            Version string if installed, None otherwise
        """
        binary_info = self.detect_binary()
        if binary_info:
            return binary_info.version
        return None

    def download_specific_version(
        self, version: str, hardware: HardwareProfile, progress_callback: Any = None
    ) -> Path:
        """
        Download specific version of llama-server.

        Args:
            version: Version tag (e.g., "b3600")
            hardware: Hardware profile
            progress_callback: Optional progress callback

        Returns:
            Path to downloaded binary

        Raises:
            RuntimeError: If download fails
        """
        logger.info(f"Downloading llama-server version {version}")

        # Determine architecture (must match _get_release_url logic for Apple Silicon)
        chip_lower = hardware.chip.lower()
        machine_lower = platform.machine().lower()

        # Note: llama.cpp releases use "arm64" and "x64" (not "x86_64")
        # Check for Apple Silicon (M1/M2/M3/M4/M5 chips)
        is_apple_silicon = (
            hardware.chip_family.startswith("M")
            or "arm" in chip_lower
            or "arm64" in machine_lower
            or "aarch64" in machine_lower
        )
        arch = "arm64" if is_apple_silicon else "x64"

        # Construct URL for specific version (format changed from .zip to .tar.gz)
        base_url = f"https://github.com/{self.GITHUB_REPO}/releases/download"
        archive_filename = f"llama-{version}-bin-macos-{arch}.tar.gz"
        release_url = f"{base_url}/{version}/{archive_filename}"

        logger.info(f"Downloading from: {release_url}")

        # Use common download/install logic
        return self._download_and_install_archive(
            release_url, version, archive_filename, progress_callback
        )

    def backup_binary(self) -> Path | None:
        """
        Create backup of current binary before update.

        Returns:
            Path to backup file, or None if no binary to backup
        """
        if not self.binary_path.exists():
            logger.warning("No binary to backup")
            return None

        # Create backup with timestamp
        backup_path = self.binary_path.with_suffix(f".backup.{int(time.time())}")

        try:
            shutil.copy2(self.binary_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return backup_path
        except OSError as e:
            logger.warning(f"Failed to create backup: {e}")
            return None

    def rollback_binary(self) -> bool:
        """
        Restore binary from most recent backup.

        Returns:
            True if rollback successful, False otherwise
        """
        # Find most recent backup
        backup_files = list(self.bin_dir.glob(f"{self.BINARY_NAME}.backup.*"))

        if not backup_files:
            logger.warning("No backup files found")
            return False

        # Sort by timestamp (newest first)
        backup_files.sort(reverse=True)
        latest_backup = backup_files[0]

        try:
            # Restore from backup
            shutil.copy2(latest_backup, self.binary_path)
            self.binary_path.chmod(self.binary_path.stat().st_mode | stat.S_IEXEC)

            # Verify restored binary
            info = self._get_binary_info(self.binary_path, BinarySource.DOWNLOADED)
            if not info or not info.is_valid:
                logger.warning("Restored binary failed validation")
                return False

            logger.info(f"Successfully rolled back to: {latest_backup}")
            return True

        except OSError as e:
            logger.warning(f"Failed to rollback: {e}")
            return False
