from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="qwenvert",
    version="0.1.0",
    author="Kyle Mesiab",
    author_email="kmesiab@gmail.com",
    description="One-click local LLM inference for Claude Code on Mac M1",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kmesiab/qwenvert",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: MacOS :: MacOS X",
    ],
    python_requires=">=3.9,<3.13",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "httpx>=0.25.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "click>=8.1.0",
        "rich>=13.7.0",
        "huggingface-hub>=0.19.0",
        "psutil>=5.9.0",
        "py-cpuinfo>=9.0.0",
        "prometheus-client>=0.19.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0.1",
        "aiofiles>=23.2.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.11.0",
            "ruff>=0.1.6",
            "mypy>=1.7.0",
        ],
        "mlx": [
            "mlx>=0.0.8",
            "mlx-lm>=0.0.6",
        ],
    },
    entry_points={
        "console_scripts": [
            "qwenvert=qwenvert.cli.main:cli",
        ],
    },
)
