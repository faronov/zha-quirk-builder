# ZHA Quirk Builder

Standalone desktop editor for generating and validating ZHA QuirkBuilder v2 files.
It does not depend on Zigbee Hub and does not connect to a coordinator.

## Development

Python 3.12 or newer is required because the current ZHA and zha-quirks releases
require Python 3.12.

```shell
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/zha-quirk-builder
```

On Windows, use `.venv\Scripts\pip` and `.venv\Scripts\zha-quirk-builder`.

The compatibility result always includes the exact installed Python, zigpy, ZHA,
and zha-quirks versions. Dependencies track the current compatible minor release
line and resolve to the newest version available from the configured package
index. A successful syntax check alone is not presented as upstream compatibility.

## Desktop packages

GitHub Actions builds:

- `ZHA-Quirk-Builder-windows-x64.zip` containing a standalone `.exe`;
- `ZHA-Quirk-Builder-macos-x64.zip` containing a standalone `.app`.

No separate Python installation is required for packaged applications. Push a
tag such as `v0.1.0` to create a GitHub release containing both archives.
