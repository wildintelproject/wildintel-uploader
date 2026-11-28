"""The modules of the app, each a hexagon of its own (#248): `domain` (its models and rules, pure Python, and the ports its use cases are given their
adapters through), `application` (its use cases) and `infrastructure` (the adapters: files, ExifTool, TRAPPER…). The entry points that drive them — the web API and
the command line — are in `entrypoints`, and what several modules use is in `shared`."""
