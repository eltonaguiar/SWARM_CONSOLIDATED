#!/usr/bin/env python3
"""
setup.py — SWARM_CONSOLIDATED deployment package.

Install with:
    pip install .           # minimal
    pip install .[dev]      # dev tools (lint, test)
    pip install .[all]      # everything including playwright
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="swarm_consolidated",
    version="1.0.0",
    description="AI Agent Swarm — multi-engine orchestration for coding, research, PR review, and debate",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="eltonaguiar",
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": [
            "ruff>=0.5.0",
            "mypy>=1.8.0",
        ],
        "playwright": [
            "playwright>=1.40.0",
        ],
        "all": [
            "ruff>=0.5.0",
            "mypy>=1.8.0",
            "playwright>=1.40.0",
        ],
    },
    packages=find_packages(),
    py_modules=[
        "swarm_task",
        "swarm_unified",
        "swarm_model_eval",
        "swarm_e2e_fix",
        "swarm_fix_worktree",
        "swarm_acceptance_driver",
    ],
    entry_points={
        "console_scripts": [
            "swarm-task=swarm_task:main",
            "swarm-unified=swarm_unified:main",
            "swarm-eval=swarm_model_eval:main",
            "swarm-fix=swarm_e2e_fix:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
