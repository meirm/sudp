#!/usr/bin/env python3
"""SUDP package setup."""

from setuptools import setup, find_packages

setup(
    name="sudp",
    version="0.4.0",
    description="Simple UDP Protocol",
    author="Meir Michanie",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pytest==7.4.3",
        "pytest-cov==4.1.0",
        "black==23.11.0",
        "isort==5.12.0",
        "flake8==6.1.0",
        "mypy==1.7.0",
        "pyyaml==6.0.1",
        "websockets==12.0",
        "python-dotenv==1.0.0"
    ],
    entry_points={
        "console_scripts": [
            "sudpd=sudp.server.daemon:main",
            "sudpc=sudp.client.daemon:main"
        ]
    }
) 