# Logical demo configuration

The installed default is [`../src/raftel_arm01/defaults.json`](../src/raftel_arm01/defaults.json).
Copy it to a local JSON file and pass `raftel-sort --config /path/to/experiment.json`.
All coordinates are metres in `arm_base`, x right, y forward, z up. No joint geometry,
servo settings, calibrated workspace, or physical safety approval is implied.
The packaged file is the single source of defaults and is included in wheels.
