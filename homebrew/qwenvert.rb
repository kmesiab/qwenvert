# Homebrew Formula for qwenvert
# This is a template - actual formula should be generated after publishing to PyPI
#
# To create your tap:
#   gh repo create homebrew-qwenvert --public
#   git clone https://github.com/kmesiab/homebrew-qwenvert.git
#   mkdir Formula
#   cp this-file.rb homebrew-qwenvert/Formula/qwenvert.rb
#
# To install:
#   brew tap kmesiab/qwenvert
#   brew install qwenvert

class Qwenvert < Formula
  include Language::Python::Virtualenv

  desc "Local LLM adapter for Claude Code on Apple Silicon"
  homepage "https://github.com/kmesiab/qwenvert"
  url "https://files.pythonhosted.org/packages/source/q/qwenvert/qwenvert-0.1.0.tar.gz"
  sha256 "REPLACE_WITH_ACTUAL_SHA256"  # Get from: shasum -a 256 dist/qwenvert-0.1.0.tar.gz
  license "Apache-2.0"
  head "https://github.com/kmesiab/qwenvert.git", branch: "main"

  depends_on "python@3.11"

  # Core dependencies
  resource "click" do
    url "https://files.pythonhosted.org/packages/source/c/click/click-8.1.7.tar.gz"
    sha256 "ca9853ad459e787e2192211578cc907e7594e294c7ccc834310722b41b9ca6de"
  end

  resource "httpx" do
    url "https://files.pythonhosted.org/packages/source/h/httpx/httpx-0.27.0.tar.gz"
    sha256 "a0cb88a46f32dc874e04ee956e4c2764aba2aa228f650b06788ba6bda2962ab5"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.7.0.tar.gz"
    sha256 "5cb5123b5cf9ee70584244246816e9114227e0b98ad9176eede6ad54bf5403fa"
  end

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/source/p/pyyaml/pyyaml-6.0.1.tar.gz"
    sha256 "bfdf460b1736c775f2ba9f6a92bca30bc2095067b8a9d77876d1fad6cc3b4a43"
  end

  resource "fastapi" do
    url "https://files.pythonhosted.org/packages/source/f/fastapi/fastapi-0.115.0.tar.gz"
    sha256 "f93b4ca3529a8ebc6fc3fcf710e5efa8de3df9b41570958abf1d97d843138004"
  end

  resource "uvicorn" do
    url "https://files.pythonhosted.org/packages/source/u/uvicorn/uvicorn-0.32.0.tar.gz"
    sha256 "f78b36b143c16f54ccdb8190d0a26b5f1901fe5a3c777e1ab29f26391af8551e"
  end

  resource "pydantic" do
    url "https://files.pythonhosted.org/packages/source/p/pydantic/pydantic-2.9.0.tar.gz"
    sha256 "c7a8a9fdf7d100afa49647eae340e2d23efa382466a8d177efcd1381e9be5598"
  end

  resource "psutil" do
    url "https://files.pythonhosted.org/packages/source/p/psutil/psutil-5.9.0.tar.gz"
    sha256 "869842dbd66bb80c3217158e629d6fceaecc3a3166d3d1faee515b05dd26ca25"
  end

  resource "huggingface-hub" do
    url "https://files.pythonhosted.org/packages/source/h/huggingface-hub/huggingface-hub-0.19.0.tar.gz"
    sha256 "f0e7bb0b36fbbf4f8c49f75dbf6211f2f8c2c6f75b0d7b6e98bb8a30bca66a0d"
  end

  # Add OpenTelemetry dependencies...
  # (Use `brew create` to auto-generate all resources with correct URLs/SHA256s)

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      qwenvert requires either Ollama or llama.cpp to be installed:

      For Ollama (recommended):
        brew install ollama
        ollama serve
        ollama pull qwen2.5-coder:1.5b-instruct-q4_K_M

      For llama.cpp:
        brew install llama.cpp

      Then initialize qwenvert:
        qwenvert init --backend ollama
        qwenvert start

      Configure Claude Code to use qwenvert:
        export ANTHROPIC_BASE_URL=http://127.0.0.1:8088
        export ANTHROPIC_API_KEY=local-qwen

      Documentation: https://github.com/kmesiab/qwenvert
    EOS
  end

  test do
    # Test CLI is installed
    assert_match "qwenvert", shell_output("#{bin}/qwenvert --version")

    # Test help command
    assert_match "Usage:", shell_output("#{bin}/qwenvert --help")

    # Test hardware detection (will work on any Mac)
    system bin/"qwenvert", "hardware"
  end
end

# To auto-generate the full formula with all dependencies:
#
# 1. Publish to PyPI first
# 2. Install homebrew-pypi-poet:
#      pip install homebrew-pypi-poet
# 3. Generate resources:
#      poet qwenvert > qwenvert.rb
# 4. Manually add the header (lines 1-22) to the generated file
# 5. Test locally:
#      brew install --build-from-source ./qwenvert.rb
#      brew test qwenvert
#      brew audit --strict qwenvert
