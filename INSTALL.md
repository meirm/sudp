We need to create entry point scripts that will be installed to `/usr/local/bin`. Let me create these scripts and a setup script to install them:

```plain text:scripts/sudpc
#!/usr/bin/env python3
"""SUDP client daemon entry point."""

from sudp.client.daemon import main

if __name__ == "__main__":
    main()
```

```plain text:scripts/sudpd
#!/usr/bin/env python3
"""SUDP server daemon entry point."""

from sudp.server.daemon import main

if __name__ == "__main__":
    main()
```

```python:setup.py
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
```
Now you can install everything with:

```bash
# Install package and scripts
sudo pip install -e .

# Create sudp user and group
sudo useradd -r -s /bin/false sudp

# Create required directories
sudo mkdir -p /etc/sudp /var/run/sudp
sudo chown -R sudp:sudp /etc/sudp /var/run/sudp

# Set script permissions
sudo chmod 755 /usr/local/bin/sudpc /usr/local/bin/sudpd

# Reload systemd
sudo systemctl daemon-reload
```

After installation, you can:

1. Start the daemons:
```bash
# Using systemd
sudo systemctl start sudpd
sudo systemctl start sudpc

# Or manually
sudo sudpd start
sudo sudpc start
```

2. Check status:
```bash
# Using systemd
sudo systemctl status sudpd
sudo systemctl status sudpc

# Or manually
sudpd status
sudpc status
```

3. Stop the daemons:
```bash
# Using systemd
sudo systemctl stop sudpd
sudo systemctl stop sudpc

# Or manually
sudo sudpd stop
sudo sudpc stop
```

4. Enable autostart:
```bash
sudo systemctl enable sudpd
sudo systemctl enable sudpc
```

The setup script:
1. Installs the Python package from `src/`
2. Installs the daemon scripts to `/usr/local/bin`
3. Installs config files to `/etc/sudp`
4. Installs systemd service files
5. Sets up proper permissions and ownership

Would you like me to proceed with implementing the next component from the roadmap?
