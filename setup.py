#!/usr/bin/env python3
"""SUDP package setup."""

from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

# Read long description
readme = Path('README.md')
if readme.exists():
    with open(readme) as f:
        long_description = f.read()
else:
    long_description = ""

setup(
    name="sudp",
    version="0.4.0",
    description="Secure UDP over WebSocket",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Meir Michanie",
    author_email="meirm@riunx.com",
    url="https://github.com/meirm/sudp",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    scripts=[
        'scripts/sudpc',
        'scripts/sudpd'
    ],
    install_requires=requirements,
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: No Input/Output Interaction",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Internet :: Proxy Servers",
        "Topic :: System :: Networking",
    ],
    data_files=[
        ('etc/sudp', ['examples/server.yaml', 'examples/client.yaml']),
        ('lib/systemd/system', ['systemd/sudpc.service', 'systemd/sudpd.service']),
    ]
) 