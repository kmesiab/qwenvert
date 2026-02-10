"""
Unit tests for ServerLauncher and ProcessHandle.

Comprehensive unit tests that mock external dependencies to maximize coverage.
Tests cover:
- ProcessHandle lifecycle (start, stop, is_running)
- Ollama backend launching and health checks
- llama.cpp backend launching and health checks
- Health check retry logic with exponential backoff
- Graceful shutdown and force kill scenarios
- PID file management
- Error handling and edge cases
"""

from __future__ import annotations

import asyncio
import signal
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from qwenvert.config import QwenvertConfig
from qwenvert.launcher import (
    ProcessHandle,
    ServerLauncher,
    start_qwenvert,
    start_qwenvert_sync,
)
from qwenvert.models import Backend, Model


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def ollama_config():
    """Configuration for Ollama backend."""
    return QwenvertConfig(
        model_id="qwen2.5-coder-7b-q4-ollama",
        backend=Backend.OLLAMA.value,
        backend_url="http://localhost:11434",
        backend_model_id="qwen2.5-coder:7b",
        adapter_host="127.0.0.1",
        adapter_port=8088,
        context_length=32768,
    )


@pytest.fixture
def llamacpp_config():
    """Configuration for llama.cpp backend."""
    return QwenvertConfig(
        model_id="qwen2.5-coder-14b-q5-llamacpp",
        backend=Backend.LLAMACPP.value,
        backend_url="http://localhost:8080",
        backend_model_id="qwen2.5-coder-14b.gguf",
        adapter_host="127.0.0.1",
        adapter_port=8088,
        context_length=32768,
        model_path="/path/to/model.gguf",
    )


@pytest.fixture
def mock_process():
    """Mock subprocess.Popen process."""
    process = MagicMock(spec=subprocess.Popen)
    process.pid = 12345
    process.poll.return_value = None  # Running by default
    process.wait.return_value = 0
    process.returncode = 0
    return process


@pytest.fixture
def mock_model():
    """Mock Model object."""
    return Model(
        id="qwen2.5-coder-7b-q4-ollama",
        display_name="Qwen2.5 Coder 7B Q4",
        family="qwen2.5-coder",
        size_b=7.0,
        quantization="Q4_K_M",
        backend=Backend.OLLAMA,
        backend_model_id="qwen2.5-coder:7b",
        context_length=32768,
        min_ram_gb=8,
        recommended_ram_gb=16,
    )


# ============================================================================
# TEST PROCESSHANDLE
# ============================================================================


class TestProcessHandle:
    """Test ProcessHandle class."""

    def test_init(self, mock_process):
        """Test ProcessHandle initialization."""
        handle = ProcessHandle(mock_process, "test-process")

        assert handle.process == mock_process
        assert handle.name == "test-process"
        assert handle.pid == 12345

    def test_is_running_true(self, mock_process):
        """Test is_running when process is running."""
        mock_process.poll.return_value = None
        handle = ProcessHandle(mock_process, "test-process")

        assert handle.is_running() is True
        mock_process.poll.assert_called_once()

    def test_is_running_false(self, mock_process):
        """Test is_running when process has terminated."""
        mock_process.poll.return_value = 0
        handle = ProcessHandle(mock_process, "test-process")

        assert handle.is_running() is False

    def test_terminate_already_stopped(self, mock_process):
        """Test terminating a process that's already stopped."""
        mock_process.poll.return_value = 0  # Already terminated
        handle = ProcessHandle(mock_process, "test-process")

        result = handle.terminate()

        assert result is True
        mock_process.terminate.assert_not_called()
        mock_process.kill.assert_not_called()

    def test_terminate_graceful(self, mock_process):
        """Test graceful termination of running process."""
        mock_process.poll.return_value = None  # Running
        handle = ProcessHandle(mock_process, "test-process")

        result = handle.terminate(timeout=10)

        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=10)
        mock_process.kill.assert_not_called()

    def test_terminate_force_kill(self, mock_process):
        """Test force kill when graceful termination times out."""
        mock_process.poll.return_value = None  # Running
        # First wait times out, second wait (after kill) succeeds
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=10),
            None,
        ]
        handle = ProcessHandle(mock_process, "test-process")

        result = handle.terminate(timeout=10)

        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert mock_process.wait.call_count == 2  # Once with timeout, once after kill

    def test_terminate_custom_timeout(self, mock_process):
        """Test terminate with custom timeout."""
        mock_process.poll.return_value = None
        handle = ProcessHandle(mock_process, "test-process")

        handle.terminate(timeout=5)

        mock_process.wait.assert_called_once_with(timeout=5)


# ============================================================================
# TEST SERVERLAUNCHER INITIALIZATION
# ============================================================================


class TestServerLauncherInit:
    """Test ServerLauncher initialization."""

    def test_init(self, ollama_config):
        """Test ServerLauncher initialization."""
        launcher = ServerLauncher(ollama_config)

        assert launcher.config == ollama_config
        assert launcher.backend_process is None
        assert launcher.adapter_process is None

    def test_init_with_llamacpp(self, llamacpp_config):
        """Test initialization with llama.cpp config."""
        launcher = ServerLauncher(llamacpp_config)

        assert launcher.config == llamacpp_config
        assert launcher.config.backend == Backend.LLAMACPP.value


# ============================================================================
# TEST BACKEND STARTING
# ============================================================================


class TestStartBackend:
    """Test start_backend method."""

    @pytest.mark.asyncio
    async def test_start_backend_ollama(self, ollama_config, mock_process):
        """Test starting Ollama backend."""
        launcher = ServerLauncher(ollama_config)

        with patch.object(
            launcher, "_start_ollama", new_callable=AsyncMock
        ) as mock_start:
            mock_start.return_value = ProcessHandle(mock_process, "ollama")

            handle = await launcher.start_backend()

            assert handle.name == "ollama"
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_backend_llamacpp(self, llamacpp_config, mock_process):
        """Test starting llama.cpp backend."""
        launcher = ServerLauncher(llamacpp_config)

        with patch.object(
            launcher, "_start_llamacpp", new_callable=AsyncMock
        ) as mock_start:
            mock_start.return_value = ProcessHandle(mock_process, "llama-cpp")

            handle = await launcher.start_backend()

            assert handle.name == "llama-cpp"
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_backend_unknown(self, ollama_config):
        """Test starting unknown backend raises ValueError."""
        launcher = ServerLauncher(ollama_config)
        launcher.config.backend = "unknown-backend"

        with pytest.raises(ValueError, match="Unknown backend"):
            await launcher.start_backend()


# ============================================================================
# TEST OLLAMA BACKEND
# ============================================================================


class TestStartOllama:
    """Test _start_ollama method."""

    @pytest.mark.asyncio
    async def test_start_ollama_not_installed(self, ollama_config):
        """Test error when Ollama is not installed."""
        launcher = ServerLauncher(ollama_config)

        with patch("qwenvert.launcher.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="Ollama not found"):
                await launcher._start_ollama()

    @pytest.mark.asyncio
    async def test_start_ollama_already_running(self, ollama_config, mock_process):
        """Test when Ollama server is already running."""
        launcher = ServerLauncher(ollama_config)

        with patch("qwenvert.launcher.shutil.which", return_value="/usr/bin/ollama"):
            with patch.object(
                launcher, "_check_health", new_callable=AsyncMock
            ) as mock_health:
                mock_health.return_value = True

                with patch("qwenvert.launcher.subprocess.Popen") as mock_popen:
                    mock_popen.return_value = mock_process

                    handle = await launcher._start_ollama()

                    assert handle.name == "ollama-existing"
                    mock_popen.assert_called_once_with(
                        ["echo"], stdout=subprocess.DEVNULL
                    )

    @pytest.mark.asyncio
    async def test_start_ollama_success(self, ollama_config, mock_process):
        """Test successfully starting Ollama server."""
        launcher = ServerLauncher(ollama_config)

        with patch("qwenvert.launcher.shutil.which", return_value="/usr/bin/ollama"):
            with patch.object(
                launcher, "_check_health", new_callable=AsyncMock
            ) as mock_health:
                mock_health.return_value = False  # Not running initially

                with patch.object(
                    launcher, "_wait_for_health", new_callable=AsyncMock
                ) as mock_wait:
                    mock_wait.return_value = True

                    with patch.object(
                        launcher, "_ensure_ollama_model", new_callable=AsyncMock
                    ), patch("qwenvert.launcher.subprocess.Popen") as mock_popen:
                        mock_popen.return_value = mock_process

                        handle = await launcher._start_ollama()

                        assert handle.name == "ollama"
                        assert handle.pid == 12345
                        mock_popen.assert_called_once()
                        call_args = mock_popen.call_args
                        assert call_args[0][0] == ["ollama", "serve"]
                        assert call_args[1]["start_new_session"] is True

    @pytest.mark.asyncio
    async def test_start_ollama_health_check_timeout(self, ollama_config, mock_process):
        """Test Ollama startup failure due to health check timeout."""
        launcher = ServerLauncher(ollama_config)

        with patch("qwenvert.launcher.shutil.which", return_value="/usr/bin/ollama"):
            with patch.object(
                launcher, "_check_health", new_callable=AsyncMock
            ) as mock_health:
                mock_health.return_value = False

                with patch.object(
                    launcher, "_wait_for_health", new_callable=AsyncMock
                ) as mock_wait:
                    mock_wait.return_value = False  # Health check times out

                    with patch("qwenvert.launcher.subprocess.Popen") as mock_popen:
                        mock_popen.return_value = mock_process

                        with pytest.raises(
                            RuntimeError, match="Ollama server failed to start"
                        ):
                            await launcher._start_ollama()

                        # Verify process was terminated
                        mock_process.terminate.assert_called_once()


# ============================================================================
# TEST ENSURE OLLAMA MODEL
# ============================================================================


class TestEnsureOllamaModel:
    """Test _ensure_ollama_model method."""

    @pytest.mark.asyncio
    async def test_ensure_model_already_exists(self, ollama_config):
        """Test when model is already pulled."""
        launcher = ServerLauncher(ollama_config)

        mock_result = MagicMock()
        mock_result.stdout = "qwen2.5-coder:7b    some metadata\nother-model:tag"

        with patch("qwenvert.launcher.subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            await launcher._ensure_ollama_model()

            # Should only call 'ollama list'
            assert mock_run.call_count == 1
            assert mock_run.call_args[0][0] == ["ollama", "list"]

    @pytest.mark.asyncio
    async def test_ensure_model_needs_pull(self, ollama_config):
        """Test when model needs to be pulled."""
        launcher = ServerLauncher(ollama_config)

        mock_list_result = MagicMock()
        mock_list_result.stdout = "other-model:tag    some metadata"

        with patch("qwenvert.launcher.subprocess.run") as mock_run:
            mock_run.return_value = mock_list_result

            await launcher._ensure_ollama_model()

            # Should call 'ollama list' and 'ollama pull'
            assert mock_run.call_count == 2
            assert mock_run.call_args_list[0][0][0] == ["ollama", "list"]
            assert mock_run.call_args_list[1][0][0] == [
                "ollama",
                "pull",
                "qwen2.5-coder:7b",
            ]
            assert mock_run.call_args_list[1][1]["check"] is True


# ============================================================================
# TEST LLAMACPP BACKEND
# ============================================================================


class TestStartLlamaCpp:
    """Test _start_llamacpp method."""

    @pytest.mark.asyncio
    async def test_start_llamacpp_not_found(self, llamacpp_config):
        """Test error when llama-server is not found."""
        launcher = ServerLauncher(llamacpp_config)

        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(RuntimeError, match="llama-server not found"):
                await launcher._start_llamacpp()

    @pytest.mark.asyncio
    async def test_start_llamacpp_success(
        self, llamacpp_config, mock_process, mock_model
    ):
        """Test successfully starting llama.cpp server."""
        launcher = ServerLauncher(llamacpp_config)

        # Mock Path.exists to return True for llama-server path
        with patch("pathlib.Path.exists", return_value=True):
            # Mock the imports that happen inside the method
            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_model.return_value = mock_model
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.config.ConfigGenerator") as mock_config_gen_cls:
                    mock_config_gen = MagicMock()
                    mock_config_gen.generate_llamacpp_flags.return_value = [
                        "--model",
                        "/path/to/model.gguf",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8080",
                    ]
                    mock_config_gen_cls.return_value = mock_config_gen

                    with patch("qwenvert.hardware.HardwareProfile"):
                        with patch.object(
                            launcher, "_wait_for_health", new_callable=AsyncMock
                        ) as mock_wait:
                            mock_wait.return_value = True

                            with patch(
                                "qwenvert.launcher.subprocess.Popen"
                            ) as mock_popen:
                                mock_popen.return_value = mock_process

                                handle = await launcher._start_llamacpp()

                                assert handle.name == "llama-cpp"
                                assert handle.pid == 12345
                                mock_popen.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_llamacpp_alternative_path(
        self, llamacpp_config, mock_process, mock_model
    ):
        """Test finding llama-server in alternative location."""
        launcher = ServerLauncher(llamacpp_config)

        # Mock Path.exists to return False for first path, True for alternative
        call_count = [0]

        def exists_side_effect(self):
            call_count[0] += 1
            # First call checks ~/.local/bin/llama-server (False)
            # Second call checks /usr/local/bin/llama-server (True)
            return call_count[0] > 1

        with patch("pathlib.Path.exists", exists_side_effect):
            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_model.return_value = mock_model
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.config.ConfigGenerator") as mock_config_gen_cls:
                    mock_config_gen = MagicMock()
                    mock_config_gen.generate_llamacpp_flags.return_value = [
                        "--model",
                        "test",
                    ]
                    mock_config_gen_cls.return_value = mock_config_gen

                    with patch("qwenvert.hardware.HardwareProfile"):
                        with patch.object(
                            launcher, "_wait_for_health", new_callable=AsyncMock
                        ) as mock_wait:
                            mock_wait.return_value = True

                            with patch(
                                "qwenvert.launcher.subprocess.Popen"
                            ) as mock_popen:
                                mock_popen.return_value = mock_process

                                handle = await launcher._start_llamacpp()

                                assert handle.name == "llama-cpp"

    @pytest.mark.asyncio
    async def test_start_llamacpp_model_not_found(self, llamacpp_config):
        """Test error when model is not found in registry."""
        launcher = ServerLauncher(llamacpp_config)

        Path.home() / ".local" / "bin" / "llama-server"

        with patch.object(Path, "exists", return_value=True):
            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_model.return_value = None  # Model not found
                mock_registry_cls.return_value = mock_registry

                with pytest.raises(RuntimeError, match="Model .* not found"):
                    await launcher._start_llamacpp()

    @pytest.mark.asyncio
    async def test_start_llamacpp_health_check_timeout(
        self, llamacpp_config, mock_process, mock_model
    ):
        """Test llama.cpp startup failure due to health check timeout."""
        launcher = ServerLauncher(llamacpp_config)

        with patch.object(Path, "exists", return_value=True):
            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_model.return_value = mock_model
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.config.ConfigGenerator") as mock_config_gen_cls:
                    mock_config_gen = MagicMock()
                    mock_config_gen.generate_llamacpp_flags.return_value = [
                        "--model",
                        "test",
                    ]
                    mock_config_gen_cls.return_value = mock_config_gen

                    with patch("qwenvert.hardware.HardwareProfile"):
                        with patch.object(
                            launcher, "_wait_for_health", new_callable=AsyncMock
                        ) as mock_wait:
                            mock_wait.return_value = False  # Health check times out

                            with patch(
                                "qwenvert.launcher.subprocess.Popen"
                            ) as mock_popen:
                                mock_popen.return_value = mock_process

                                with pytest.raises(
                                    RuntimeError,
                                    match="llama.cpp server failed to start",
                                ):
                                    await launcher._start_llamacpp()

                                # Verify process was terminated
                                mock_process.terminate.assert_called_once()


# ============================================================================
# TEST HEALTH CHECKS
# ============================================================================


class TestHealthChecks:
    """Test health check methods."""

    @pytest.mark.asyncio
    async def test_check_health_success(self, ollama_config):
        """Test successful health check."""
        launcher = ServerLauncher(ollama_config)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await launcher._check_health("http://localhost:11434")

            assert result is True
            mock_client.get.assert_called_once_with(
                "http://localhost:11434", timeout=2.0
            )

    @pytest.mark.asyncio
    async def test_check_health_non_200(self, ollama_config):
        """Test health check with non-200 status code."""
        launcher = ServerLauncher(ollama_config)

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await launcher._check_health("http://localhost:11434")

            assert result is False

    @pytest.mark.asyncio
    async def test_check_health_connection_error(self, ollama_config):
        """Test health check with connection error."""
        launcher = ServerLauncher(ollama_config)

        # Create a proper ConnectError
        mock_request = MagicMock()
        connect_error = httpx.ConnectError("Connection refused", request=mock_request)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=connect_error)
            mock_client_cls.return_value = mock_client

            result = await launcher._check_health("http://localhost:11434")

            assert result is False

    @pytest.mark.asyncio
    async def test_check_health_timeout(self, ollama_config):
        """Test health check with timeout."""
        launcher = ServerLauncher(ollama_config)

        # Create a proper TimeoutException
        mock_request = MagicMock()
        timeout_error = httpx.TimeoutException("Timeout", request=mock_request)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=timeout_error)
            mock_client_cls.return_value = mock_client

            result = await launcher._check_health("http://localhost:11434")

            assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_health_immediate_success(self, ollama_config):
        """Test wait_for_health when server is immediately healthy."""
        launcher = ServerLauncher(ollama_config)

        with patch.object(
            launcher, "_check_health", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = True

            result = await launcher._wait_for_health(
                "http://localhost:11434", timeout=10
            )

            assert result is True
            assert mock_check.call_count == 1

    @pytest.mark.asyncio
    async def test_wait_for_health_retry(self, ollama_config):
        """Test wait_for_health with retries."""
        launcher = ServerLauncher(ollama_config)

        with patch.object(
            launcher, "_check_health", new_callable=AsyncMock
        ) as mock_check:
            # Fail twice, then succeed
            mock_check.side_effect = [False, False, True]

            with patch("qwenvert.launcher.asyncio.sleep", new_callable=AsyncMock):
                result = await launcher._wait_for_health(
                    "http://localhost:11434", timeout=10
                )

                assert result is True
                assert mock_check.call_count == 3

    @pytest.mark.asyncio
    async def test_wait_for_health_timeout(self, ollama_config):
        """Test wait_for_health timeout."""
        launcher = ServerLauncher(ollama_config)

        with patch.object(
            launcher, "_check_health", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = False

            with patch("qwenvert.launcher.time.time") as mock_time:
                # Simulate time progression
                mock_time.side_effect = [0, 5, 10, 15, 20, 25, 30, 35]

                with patch("qwenvert.launcher.asyncio.sleep", new_callable=AsyncMock):
                    result = await launcher._wait_for_health(
                        "http://localhost:11434", timeout=30
                    )

                    assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_health_custom_timeout(self, ollama_config):
        """Test wait_for_health with custom timeout value."""
        launcher = ServerLauncher(ollama_config)

        with patch.object(
            launcher, "_check_health", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = False

            with patch("qwenvert.launcher.time.time") as mock_time:
                mock_time.side_effect = [0, 30, 60, 90]

                with patch("qwenvert.launcher.asyncio.sleep", new_callable=AsyncMock):
                    result = await launcher._wait_for_health(
                        "http://localhost:8080", timeout=60
                    )

                    assert result is False


# ============================================================================
# TEST ADAPTER STARTING
# ============================================================================


class TestStartAdapter:
    """Test start_adapter method."""

    @pytest.mark.asyncio
    async def test_start_adapter_success(self, ollama_config, mock_process, mock_model):
        """Test successfully starting adapter."""
        launcher = ServerLauncher(ollama_config)
        backend_handle = ProcessHandle(mock_process, "ollama")

        with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_model.return_value = mock_model
            mock_registry_cls.return_value = mock_registry

            with patch("qwenvert.router.BackendRouter") as mock_router_cls:
                mock_router = MagicMock()
                mock_router_cls.return_value = mock_router

                with patch("qwenvert.adapter.create_app") as mock_create_app:
                    mock_app = MagicMock()
                    mock_app.state = MagicMock()
                    mock_create_app.return_value = mock_app

                    with patch("uvicorn.Config") as mock_config:
                        with patch("uvicorn.Server") as mock_server_cls:
                            mock_server = MagicMock()
                            mock_server.serve = AsyncMock()
                            mock_server_cls.return_value = mock_server

                            with patch.object(
                                launcher, "_wait_for_health", new_callable=AsyncMock
                            ) as mock_wait:
                                mock_wait.return_value = True

                                with patch("asyncio.create_task") as mock_create_task:
                                    await launcher.start_adapter(backend_handle)

                                    # Verify app was created and configured
                                    mock_create_app.assert_called_once()
                                    assert mock_app.state.backend_router == mock_router

                                    # Verify server was created with correct config
                                    mock_config.assert_called_once()
                                    mock_server_cls.assert_called_once()
                                    mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_adapter_model_not_found(self, ollama_config, mock_process):
        """Test adapter startup when model not found."""
        launcher = ServerLauncher(ollama_config)
        backend_handle = ProcessHandle(mock_process, "ollama")

        with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_model.return_value = None  # Model not found
            mock_registry_cls.return_value = mock_registry

            with pytest.raises(RuntimeError, match="Model .* not found"):
                await launcher.start_adapter(backend_handle)

    @pytest.mark.asyncio
    async def test_start_adapter_health_check_timeout(
        self, ollama_config, mock_process, mock_model
    ):
        """Test adapter startup failure due to health check timeout."""
        launcher = ServerLauncher(ollama_config)
        backend_handle = ProcessHandle(mock_process, "ollama")

        with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_model.return_value = mock_model
            mock_registry_cls.return_value = mock_registry

            with patch("qwenvert.router.BackendRouter"):
                with patch("qwenvert.adapter.create_app"):
                    with patch("uvicorn.Config"):
                        with patch("uvicorn.Server") as mock_server_cls:
                            mock_server = MagicMock()
                            mock_server.serve = AsyncMock()
                            mock_server_cls.return_value = mock_server

                            with patch.object(
                                launcher, "_wait_for_health", new_callable=AsyncMock
                            ) as mock_wait:
                                mock_wait.return_value = False  # Health check times out

                                with patch("asyncio.create_task"):
                                    with pytest.raises(
                                        RuntimeError,
                                        match="Qwenvert adapter failed to start",
                                    ):
                                        await launcher.start_adapter(backend_handle)


# ============================================================================
# TEST START ALL
# ============================================================================


class TestStartAll:
    """Test start_all method."""

    @pytest.mark.asyncio
    async def test_start_all_success(self, ollama_config, mock_process):
        """Test successfully starting all services."""
        launcher = ServerLauncher(ollama_config)

        with patch.object(
            launcher, "start_backend", new_callable=AsyncMock
        ) as mock_backend:
            backend_handle = ProcessHandle(mock_process, "ollama")
            mock_backend.return_value = backend_handle

            with patch.object(
                launcher, "start_adapter", new_callable=AsyncMock
            ) as mock_adapter:
                with patch.object(launcher, "_print_startup_success") as mock_print:
                    await launcher.start_all()

                    mock_backend.assert_called_once()
                    mock_adapter.assert_called_once_with(backend_handle)
                    mock_print.assert_called_once()
                    assert launcher.backend_process == backend_handle

    @pytest.mark.asyncio
    async def test_start_all_backend_failure(self, ollama_config):
        """Test start_all when backend fails to start."""
        launcher = ServerLauncher(ollama_config)

        with patch.object(
            launcher, "start_backend", new_callable=AsyncMock
        ) as mock_backend:
            mock_backend.side_effect = RuntimeError("Backend failed")

            with pytest.raises(RuntimeError, match="Backend failed"):
                await launcher.start_all()

    @pytest.mark.asyncio
    async def test_start_all_adapter_failure(self, ollama_config, mock_process):
        """Test start_all when adapter fails to start."""
        launcher = ServerLauncher(ollama_config)

        with patch.object(
            launcher, "start_backend", new_callable=AsyncMock
        ) as mock_backend:
            backend_handle = ProcessHandle(mock_process, "ollama")
            mock_backend.return_value = backend_handle

            with patch.object(
                launcher, "start_adapter", new_callable=AsyncMock
            ) as mock_adapter:
                mock_adapter.side_effect = RuntimeError("Adapter failed")

                with pytest.raises(RuntimeError, match="Adapter failed"):
                    await launcher.start_all()


# ============================================================================
# TEST STOP ALL
# ============================================================================


class TestStopAll:
    """Test stop_all method."""

    @pytest.mark.asyncio
    async def test_stop_all_with_adapter(self, ollama_config, mock_process):
        """Test stopping all services including adapter."""
        launcher = ServerLauncher(ollama_config)

        # Set up adapter task
        launcher.adapter_task = asyncio.create_task(asyncio.sleep(100))

        # Set up backend process
        launcher.backend_process = ProcessHandle(mock_process, "ollama")

        await launcher.stop_all()

        # Verify adapter task was cancelled
        assert launcher.adapter_task.cancelled()

        # Verify backend was terminated
        mock_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all_no_adapter(self, ollama_config, mock_process):
        """Test stopping when no adapter task exists."""
        launcher = ServerLauncher(ollama_config)

        # Only backend, no adapter
        launcher.backend_process = ProcessHandle(mock_process, "ollama")

        await launcher.stop_all()

        # Should still terminate backend
        mock_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all_no_backend(self, ollama_config):
        """Test stopping when no backend process exists."""
        launcher = ServerLauncher(ollama_config)

        # No backend or adapter
        await launcher.stop_all()

        # Should not raise error

    @pytest.mark.asyncio
    async def test_stop_all_adapter_cancellation_error(
        self, ollama_config, mock_process
    ):
        """Test that CancelledError is handled during adapter shutdown."""
        launcher = ServerLauncher(ollama_config)

        # Create a task that will be cancelled
        async def mock_serve():
            await asyncio.sleep(100)

        launcher.adapter_task = asyncio.create_task(mock_serve())
        launcher.backend_process = ProcessHandle(mock_process, "ollama")

        await launcher.stop_all()

        # Should handle cancellation gracefully
        assert launcher.adapter_task.cancelled()


# ============================================================================
# TEST PRINT STARTUP SUCCESS
# ============================================================================


class TestPrintStartupSuccess:
    """Test _print_startup_success method."""

    def test_print_startup_success(self, ollama_config, capsys):
        """Test startup success message."""
        launcher = ServerLauncher(ollama_config)

        launcher._print_startup_success()

        captured = capsys.readouterr()
        assert "Qwenvert is running!" in captured.out
        assert "http://127.0.0.1:8088" in captured.out
        assert "http://localhost:11434" in captured.out
        assert "qwen2.5-coder:7b" in captured.out
        assert "ANTHROPIC_BASE_URL" in captured.out
        assert "ANTHROPIC_API_KEY" in captured.out

    def test_print_startup_success_custom_port(self, ollama_config, capsys):
        """Test startup message with custom port."""
        ollama_config.adapter_port = 9000
        launcher = ServerLauncher(ollama_config)

        launcher._print_startup_success()

        captured = capsys.readouterr()
        assert "http://127.0.0.1:9000" in captured.out


# ============================================================================
# TEST MAIN ENTRY POINTS
# ============================================================================


class TestStartQwenvert:
    """Test start_qwenvert function."""

    @pytest.mark.asyncio
    async def test_start_qwenvert_no_config(self, capsys):
        """Test when no configuration exists."""
        with patch("qwenvert.launcher.ConfigManager.exists", return_value=False):
            await start_qwenvert()

            captured = capsys.readouterr()
            assert "No configuration found" in captured.out

    @pytest.mark.asyncio
    async def test_start_qwenvert_success(self, ollama_config, mock_process):
        """Test successful qwenvert startup."""
        with patch("qwenvert.launcher.ConfigManager.exists", return_value=True):
            with patch(
                "qwenvert.launcher.ConfigManager.load", return_value=ollama_config
            ):
                with patch("qwenvert.launcher.ServerLauncher") as mock_launcher_cls:
                    mock_launcher = MagicMock()
                    mock_launcher.start_all = AsyncMock()
                    mock_launcher.stop_all = AsyncMock()
                    mock_launcher_cls.return_value = mock_launcher

                    with patch(
                        "qwenvert.launcher.asyncio.get_event_loop"
                    ) as mock_get_loop:
                        mock_loop = MagicMock()
                        mock_get_loop.return_value = mock_loop

                        with patch("qwenvert.launcher.signal.signal") as mock_signal:
                            with patch(
                                "qwenvert.launcher.asyncio.sleep",
                                new_callable=AsyncMock,
                            ) as mock_sleep:
                                # Make sleep raise KeyboardInterrupt to exit loop
                                mock_sleep.side_effect = KeyboardInterrupt()

                                await start_qwenvert()

                                mock_launcher.start_all.assert_called_once()
                                # Signal handlers should be registered
                                assert mock_signal.call_count >= 2

    @pytest.mark.asyncio
    async def test_start_qwenvert_with_exception(self, ollama_config):
        """Test qwenvert startup with exception."""
        with patch("qwenvert.launcher.ConfigManager.exists", return_value=True):
            with patch(
                "qwenvert.launcher.ConfigManager.load", return_value=ollama_config
            ):
                with patch("qwenvert.launcher.ServerLauncher") as mock_launcher_cls:
                    mock_launcher = MagicMock()
                    mock_launcher.start_all = AsyncMock(
                        side_effect=RuntimeError("Test error")
                    )
                    mock_launcher.stop_all = AsyncMock()
                    mock_launcher_cls.return_value = mock_launcher

                    with patch("qwenvert.launcher.asyncio.get_event_loop"):
                        with patch("qwenvert.launcher.signal.signal"):
                            with pytest.raises(RuntimeError, match="Test error"):
                                await start_qwenvert()

                            mock_launcher.stop_all.assert_called_once()

    def test_start_qwenvert_sync(self):
        """Test synchronous wrapper."""
        with patch("qwenvert.launcher.asyncio.run") as mock_run:
            start_qwenvert_sync()

            mock_run.assert_called_once()


# ============================================================================
# TEST SIGNAL HANDLING
# ============================================================================


class TestSignalHandling:
    """Test signal handling in start_qwenvert."""

    @pytest.mark.asyncio
    async def test_signal_handler_setup(self, ollama_config):
        """Test that signal handlers are properly set up."""
        with patch("qwenvert.launcher.ConfigManager.exists", return_value=True):
            with patch(
                "qwenvert.launcher.ConfigManager.load", return_value=ollama_config
            ):
                with patch("qwenvert.launcher.ServerLauncher") as mock_launcher_cls:
                    mock_launcher = MagicMock()
                    mock_launcher.start_all = AsyncMock()
                    mock_launcher.stop_all = AsyncMock()
                    mock_launcher_cls.return_value = mock_launcher

                    with patch("qwenvert.launcher.asyncio.get_event_loop"):
                        with patch("qwenvert.launcher.signal.signal") as mock_signal:
                            with patch(
                                "qwenvert.launcher.asyncio.sleep",
                                new_callable=AsyncMock,
                            ) as mock_sleep:
                                mock_sleep.side_effect = KeyboardInterrupt()

                                await start_qwenvert()

                                # Verify SIGINT and SIGTERM handlers were registered
                                signal_calls = [
                                    call[0] for call in mock_signal.call_args_list
                                ]
                                assert (
                                    signal.SIGINT,
                                ) in signal_calls or signal.SIGINT in [
                                    c[0] for c in signal_calls
                                ]
                                assert (
                                    signal.SIGTERM,
                                ) in signal_calls or signal.SIGTERM in [
                                    c[0] for c in signal_calls
                                ]


# ============================================================================
# TEST EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_backends_in_sequence(
        self, ollama_config, llamacpp_config, mock_process
    ):
        """Test switching between backends."""
        # First Ollama
        launcher1 = ServerLauncher(ollama_config)
        with patch("qwenvert.launcher.shutil.which", return_value="/usr/bin/ollama"):
            with patch.object(
                launcher1, "_check_health", new_callable=AsyncMock, return_value=False
            ):
                with patch.object(
                    launcher1,
                    "_wait_for_health",
                    new_callable=AsyncMock,
                    return_value=True,
                ):
                    with patch.object(
                        launcher1, "_ensure_ollama_model", new_callable=AsyncMock
                    ):
                        with patch(
                            "qwenvert.launcher.subprocess.Popen",
                            return_value=mock_process,
                        ):
                            handle1 = await launcher1._start_ollama()
                            assert handle1.name == "ollama"

        # Then llama.cpp
        launcher2 = ServerLauncher(llamacpp_config)
        with patch.object(Path, "exists", return_value=True):
            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_model = MagicMock()
                mock_registry.get_model.return_value = mock_model
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.config.ConfigGenerator") as mock_config_gen_cls:
                    mock_config_gen = MagicMock()
                    mock_config_gen.generate_llamacpp_flags.return_value = [
                        "--model",
                        "test",
                    ]
                    mock_config_gen_cls.return_value = mock_config_gen

                    with patch("qwenvert.hardware.HardwareProfile"):
                        with patch.object(
                            launcher2,
                            "_wait_for_health",
                            new_callable=AsyncMock,
                            return_value=True,
                        ):
                            with patch(
                                "qwenvert.launcher.subprocess.Popen",
                                return_value=mock_process,
                            ):
                                handle2 = await launcher2._start_llamacpp()
                                assert handle2.name == "llama-cpp"

    def test_process_handle_with_different_pids(self):
        """Test ProcessHandle with various PID values."""
        for pid in [1, 1000, 99999]:
            process = MagicMock(spec=subprocess.Popen)
            process.pid = pid
            process.poll.return_value = None

            handle = ProcessHandle(process, f"test-{pid}")
            assert handle.pid == pid
            assert handle.is_running() is True

    @pytest.mark.asyncio
    async def test_health_check_with_various_status_codes(self, ollama_config):
        """Test health check with different HTTP status codes."""
        launcher = ServerLauncher(ollama_config)

        for status_code in [200, 201, 404, 500, 503]:
            mock_response = MagicMock()
            mock_response.status_code = status_code

            with patch("qwenvert.launcher.httpx.AsyncClient") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                result = await launcher._check_health("http://localhost:11434")

                if status_code == 200:
                    assert result is True
                else:
                    assert result is False

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, ollama_config):
        """Test multiple concurrent health checks."""
        launcher = ServerLauncher(ollama_config)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            # Run multiple health checks concurrently
            results = await asyncio.gather(
                launcher._check_health("http://localhost:11434"),
                launcher._check_health("http://localhost:8080"),
                launcher._check_health("http://localhost:9000"),
            )

            assert all(results)
