"""
Qwenvert - One-click local LLM inference for Claude Code on Mac M1.

A production-grade inference orchestration system optimized for consumer
Mac hardware running Qwen models with Claude Code integration.
"""

__version__ = "0.1.0"
__author__ = "Kyle Mesiab"

from .hardware import HardwareDetector, HardwareProfile

__all__ = [
    "HardwareDetector",
    "HardwareProfile",
]
