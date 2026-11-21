# Smart Grid Metering System (`smart-grid-meter-sim`)

Graduation project simulating a smart grid metering system with multi-profile consumption data, transformer load and loss analysis, a Flask ingestion API with SQLite storage, and an interactive subscriber dashboard with event simulation.

## Project Structure
- `config/`: System parameters, meter definitions, and transformer configurations.
- `simulator/`: Multi-day consumption simulator and load/loss calculations.
- `visualization/`: Plotting scripts for daily load profiles and transformer vs. meter comparisons.
- `server/`: Flask API for receiving and validating meter telemetry and storing records in SQLite.
- `streamer/`: Live data streaming client sending readings to the ingestion API.
- `dashboard/`: Web interface for monitoring subscriber telemetry and simulating grid/tamper events.

## Key Features
- Simulates 50 meters (residential, commercial, and industrial) across 3 transformers.
- Validates incoming meter IDs before saving readings and logs system/tamper events.
- Interactive web dashboard for switching meter types and testing events (`Cover Open`, `Magnet Detected`, `Meter Bypass (50%)`, `Power Outage`, `Restore Normal`).
