"""
Integration tests for server lifecycle and process management.

Tests the ServerLauncher, health checks, and graceful shutdown.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from qwenvert.launcher import ServerLauncher, ProcessHandle
from qwenvert.models import Backend


class TestServerLauncher:
    """Test server launching and lifecycle management."""

    @pytest.mark.asyncio
    async def test_ollama_backend_launch(self, sample_model_7b_q4, temp_config_dir):
        """Test launching Ollama backend."""
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=sample_model_7b_q4.backend.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # Mock process
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.returncode = None
            mock_subprocess.return_value = mock_process

            launcher = ServerLauncher(config=config)

            # Mock health check to succeed immediately
            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                handle = await launcher.start_backend()

                assert handle is not None
                assert handle.pid == 12345
                assert handle.process == mock_process

    @pytest.mark.asyncio
    async def test_llamacpp_backend_launch(self, sample_model_14b_q5, temp_config_dir):
        """Test launching llama.cpp backend."""
        from qwenvert.config import QwenvertConfig

        # Update model to llama.cpp
        from qwenvert.models import Model

        llamacpp_model = Model(
            id=sample_model_14b_q5.id,
            display_name=sample_model_14b_q5.display_name,
            family=sample_model_14b_q5.family,
            size_b=sample_model_14b_q5.size_b,
            quantization=sample_model_14b_q5.quantization,
            backend=Backend.LLAMACPP,
            backend_model_id=sample_model_14b_q5.backend_model_id,
            context_length=sample_model_14b_q5.context_length,
            min_ram_gb=sample_model_14b_q5.min_ram_gb,
            recommended_ram_gb=sample_model_14b_q5.recommended_ram_gb,
        )

        config = QwenvertConfig(
            model_id=llamacpp_model.id,
            backend=llamacpp_model.backend.value,
            backend_url="http://localhost:8080",
            backend_model_id=llamacpp_model.backend_model_id,
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = MagicMock()
            mock_process.pid = 12346
            mock_process.returncode = None
            mock_subprocess.return_value = mock_process

            launcher = ServerLauncher(config=config)

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                handle = await launcher.start_backend()

                assert handle is not None
                assert handle.pid == 12346

                # Verify llama.cpp command line
                call_args = mock_subprocess.call_args
                cmd = call_args[0] if call_args else []
                assert any("llama" in str(arg).lower() for arg in cmd)

    @pytest.mark.asyncio
    async def test_backend_health_check_retry(self, sample_model_7b_q4):
        """Test that launcher retries health checks on startup."""
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=sample_model_7b_q4.backend.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = MagicMock()
            mock_process.pid = 12347
            mock_process.returncode = None
            mock_subprocess.return_value = mock_process

            launcher = ServerLauncher(config=config)

            # Mock health check failing twice, then succeeding
            call_count = 0

            async def mock_health_check(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise httpx.ConnectError("Connection refused")
                mock_response = MagicMock()
                mock_response.status_code = 200
                return mock_response

            with patch("httpx.AsyncClient.get", side_effect=mock_health_check):
                handle = await launcher.start_backend()

                assert handle is not None
                assert call_count >= 3  # Retried at least twice

    @pytest.mark.asyncio
    async def test_backend_health_check_timeout(self, sample_model_7b_q4):
        """Test that launcher times out if backend never becomes healthy."""
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=sample_model_7b_q4.backend.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = MagicMock()
            mock_process.pid = 12348
            mock_process.returncode = None
            mock_subprocess.return_value = mock_process

            launcher = ServerLauncher(config=config)

            # Mock health check always failing
            with patch(
                "httpx.AsyncClient.get",
                side_effect=httpx.ConnectError("Connection refused"),
            ):
                with pytest.raises((TimeoutError, RuntimeError, Exception)):
                    # Should timeout after max retries
                    await launcher.start_backend()

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, sample_model_7b_q4):
        """Test graceful shutdown of backend process."""
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=sample_model_7b_q4.backend.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = MagicMock()
            mock_process.pid = 12349
            mock_process.returncode = None
            mock_process.terminate = MagicMock()
            mock_process.wait = AsyncMock()
            mock_subprocess.return_value = mock_process

            launcher = ServerLauncher(config=config)

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                handle = await launcher.start_backend()

                # Stop the backend
                await launcher.stop_backend(handle)

                # Verify terminate was called
                mock_process.terminate.assert_called_once()
                mock_process.wait.assert_called_once()


class TestAdapterLauncher:
    """Test adapter server launching."""

    @pytest.mark.asyncio
    async def test_adapter_start(self, sample_model_7b_q4):
        """Test starting the adapter server."""
        from qwenvert.config import QwenvertConfig

        # Mock backend handle
        mock_process = MagicMock()
        mock_process.pid = 12350
        backend_handle = ProcessHandle(
            process=mock_process,
            name="ollama",
        )

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=sample_model_7b_q4.backend.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        launcher = ServerLauncher(config=config)

        with patch("uvicorn.Server.serve") as mock_serve:
            mock_serve.return_value = None

            # Start adapter (this would normally block)
            # We'll just verify it's set up correctly
            uvicorn_config = launcher._create_adapter_config(backend_handle)

            assert uvicorn_config.host == "127.0.0.1"
            assert uvicorn_config.port == 8088


class TestHealthChecks:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_backend_health_check_success(self, sample_model_7b_q4):
        """Test successful backend health check."""
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=sample_model_7b_q4.backend.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
        )

        launcher = ServerLauncher(config=config)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_get.return_value = mock_response

            is_healthy = await launcher._check_health("http://localhost:11434")
            assert is_healthy is True

    @pytest.mark.asyncio
    async def test_backend_health_check_failure(self, sample_model_7b_q4):
        """Test failed backend health check."""
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=sample_model_7b_q4.backend.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
        )

        launcher = ServerLauncher(config=config)

        with patch(
            "httpx.AsyncClient.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            is_healthy = await launcher._check_health("http://localhost:11434")
            assert is_healthy is False

    @pytest.mark.asyncio
    async def test_backend_health_check_http_error(self, sample_model_7b_q4):
        """Test backend health check with HTTP error."""
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=sample_model_7b_q4.backend.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
        )

        launcher = ServerLauncher(config=config)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500 Server Error", request=MagicMock(), response=mock_response
            )
            mock_get.return_value = mock_response

            is_healthy = await launcher._check_health("http://localhost:11434")
            assert is_healthy is False


class TestProcessManagement:
    """Test process management utilities."""

    @pytest.mark.asyncio
    async def test_process_is_running(self):
        """Test checking if process is running."""

        mock_process = MagicMock()
        mock_process.pid = 12351
        mock_process.returncode = None  # Still running
        mock_process.poll.return_value = None

        handle = ProcessHandle(
            process=mock_process,
            name="test_process",
        )

        assert handle.is_running() is True

    @pytest.mark.asyncio
    async def test_process_has_exited(self):
        """Test detecting process exit."""

        mock_process = MagicMock()
        mock_process.pid = 12352
        mock_process.returncode = 0  # Exited
        mock_process.poll.return_value = 0

        handle = ProcessHandle(
            process=mock_process,
            name="test_process",
        )

        assert handle.is_running() is False

    @pytest.mark.asyncio
    async def test_force_kill_on_timeout(self, sample_model_7b_q4):
        """Test force killing process if graceful shutdown times out."""
        from qwenvert.config import QwenvertConfig

        mock_process = MagicMock()
        mock_process.pid = 12353
        mock_process.returncode = None
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()

        # Mock wait to timeout
        async def mock_wait_timeout():
            await asyncio.sleep(0.1)
            raise asyncio.TimeoutError()

        mock_process.wait = mock_wait_timeout

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=sample_model_7b_q4.backend.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        launcher = ServerLauncher(config=config)

        handle = ProcessHandle(
            process=mock_process,
            name="ollama",
        )

        with pytest.raises(asyncio.TimeoutError):
            await launcher.stop_backend(handle, timeout=0.2)

        # Should have called kill after timeout
        mock_process.kill.assert_called()


class TestRealServerIntegration:
    """Real integration tests (require actual servers)."""

    @pytest.mark.integration
    @pytest.mark.skipif(True, reason="Requires actual Ollama installation")
    @pytest.mark.asyncio
    async def test_full_lifecycle_ollama(self, sample_model_7b_q4, temp_config_dir):
        """Test full server lifecycle with real Ollama.

        Prerequisites:
        - Ollama installed
        - qwen2.5-coder:7b model downloaded
        """
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=sample_model_7b_q4.backend.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        launcher = ServerLauncher(config=config)

        # Start backend
        backend_handle = await launcher.start_backend()
        assert backend_handle.is_running()

        # Verify health
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/tags")
            assert response.status_code == 200

        # Stop backend
        await launcher.stop_backend(backend_handle)
        assert not backend_handle.is_running()

    @pytest.mark.integration
    @pytest.mark.skipif(True, reason="Requires llama.cpp installation")
    @pytest.mark.asyncio
    async def test_full_lifecycle_llamacpp(self, sample_model_14b_q5, temp_config_dir):
        """Test full server lifecycle with real llama.cpp.

        Prerequisites:
        - llama.cpp built
        - Model file downloaded
        """
        from qwenvert.config import QwenvertConfig
        from qwenvert.models import Model

        llamacpp_model = Model(
            id=sample_model_14b_q5.id,
            display_name=sample_model_14b_q5.display_name,
            family=sample_model_14b_q5.family,
            size_b=sample_model_14b_q5.size_b,
            quantization=sample_model_14b_q5.quantization,
            backend=Backend.LLAMACPP,
            backend_model_id="/path/to/model.gguf",
            context_length=sample_model_14b_q5.context_length,
            min_ram_gb=sample_model_14b_q5.min_ram_gb,
            recommended_ram_gb=sample_model_14b_q5.recommended_ram_gb,
        )

        config = QwenvertConfig(
            model_id=llamacpp_model.id,
            backend=llamacpp_model.backend.value,
            backend_url="http://localhost:8080",
            backend_model_id=llamacpp_model.backend_model_id,
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        launcher = ServerLauncher(config=config)

        # Start backend
        backend_handle = await launcher.start_backend()
        assert backend_handle.is_running()

        # Verify health
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8080/health")
            assert response.status_code == 200

        # Stop backend
        await launcher.stop_backend(backend_handle)
        assert not backend_handle.is_running()
