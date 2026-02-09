"""
Integration tests for qwenvert.

These tests validate end-to-end functionality:
- Full /v1/messages API flow
- Backend integration (Ollama, llama.cpp)
- Real inference requests
- Streaming and non-streaming modes

Note: Some tests require running backends and are marked with @pytest.mark.integration
Run with: pytest -m integration
"""
