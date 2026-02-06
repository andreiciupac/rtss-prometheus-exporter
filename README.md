# RTSS Prometheus Exporter

**Export gaming FPS and frame time metrics from RTSS to Prometheus/Grafana.**

This exporter reads real-time performance data directly from [RivaTuner Statistics Server (RTSS)](https://www.guru3d.com/files-details/rtss-rivatuner-statistics-server-download.html) shared memory and exposes it as Prometheus metrics. Monitor your gaming PC's performance remotely, create beautiful Grafana dashboards, and track FPS across all your games.

## Features

- **Zero-overhead monitoring** - Reads directly from RTSS shared memory (no hooks, no injection)
- **Per-process metrics** - Labeled by game executable name for easy filtering
- **Automatic cleanup** - Stale metrics removed when games close (no flat-line graphs)
- **Session-aware** - Correctly handles Windows Session 0 isolation
- **Lightweight** - Pure Python, minimal dependencies

## Metrics Exposed

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `rtss_fps` | Gauge | `process` | Current frames per second |
| `rtss_frame_time_milliseconds` | Gauge | `process` | Current frame time in milliseconds |

**Example output:**
```prometheus
rtss_fps{process="cyberpunk2077.exe"} 87.3
rtss_fps{process="baldursgate3.exe"} 143.8
rtss_frame_time_milliseconds{process="cyberpunk2077.exe"} 11.45
rtss_frame_time_milliseconds{process="baldursgate3.exe"} 6.95
```

## Requirements

- **Windows 10/11** (the gaming PC where RTSS runs)
- **Python 3.10+** ([download](https://www.python.org/downloads/))
- **RTSS 7.3.0+** ([download](https://www.guru3d.com/files-details/rtss-rivatuner-statistics-server-download.html))

The exporter must run on the same Windows machine as RTSS due to session-local shared memory. Your Prometheus/Grafana server can be on any other machine (e.g., Ubuntu server on your network).

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/andreiciupac/rtss-prometheus-exporter.git
   cd rtss-prometheus-exporter
   ```

2. **Install dependencies:**
   ```bash
  py -m pip install -r requirements.txt
   ```

3. **Test it works:**
   ```bash
   py -m rtss_exporter
   ```

   Visit `http://localhost:9101/metrics` - you should see Prometheus metrics.

## Configuration

### CLI Options

```bash
py -m rtss_exporter [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | 9101 | HTTP port for metrics endpoint |
| `--interval` | 2.0 | Poll interval in seconds |
| `--log-level` | INFO | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |

### Windows Firewall

**Required for remote Prometheus scraping.** Open an elevated PowerShell:

```powershell
New-NetFirewallRule `
    -DisplayName "RTSS Prometheus Exporter" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 9101 `
    -Action Allow `
    -Profile Private
```

**Security tip:** Restrict to your Prometheus server IP only:
```powershell
# Add this parameter to the command above:
-RemoteAddress 192.168.1.100
```

## Running as a Service

To have the exporter start automatically when you log in to Windows, you need to set it up as a background service. **Important:** Standard Windows services won't work due to Session 0 isolation (explained below).

### Recommended: Task Scheduler

The simplest and most reliable method. Task Scheduler handles credentials properly and doesn't require third-party tools.

1. **Open Task Scheduler** (`Win+R` → `taskschd.msc`)

2. **Create Task** (not "Create Basic Task")
   - **General tab:**
     - Name: `RTSS Prometheus Exporter`
     - Select "Run only when user is logged on"
     - Check "Run with highest privileges"

3. **Triggers tab:**
     - New → "At log on" → Your specific user → OK

4. **Actions tab:**
     - New → "Start a program"
     - Program/script: `C:\Path\To\Python\python.exe` (find with `python -c "import sys; print(sys.executable)"`)
     - Add arguments: `-m rtss_exporter --port 9101`
     - Start in: `C:\Path\To\rtss-prometheus-exporter`

5. **Conditions tab:**
     - **Uncheck** "Start only if on AC power"

6. **Settings tab:**
     - Check "Allow task to be run on demand"
     - Check "Run task as soon as possible after a scheduled start is missed"
     - If already running: "Do not start a new instance"

7. **Save** (will prompt for password)

8. **Test:** Right-click the task → "Run", then visit `http://localhost:9101/metrics`

### Alternative: NSSM

[NSSM (Non-Sucking Service Manager)](https://nssm.cc/) can wrap the Python script as a Windows service. **Note:** NSSM requires your actual Windows account password, not a PIN.

1. Download NSSM from https://nssm.cc/download

2. Install (elevated Command Prompt):

```cmd
nssm install RTSSExporter "C:\Path\To\python.exe" "-m rtss_exporter --port 9101"
nssm set RTSSExporter AppDirectory "C:\Path\To\rtss-prometheus-exporter"
nssm set RTSSExporter ObjectName ".\YourUsername" "YourPassword"
nssm set RTSSExporter Start SERVICE_AUTO_START
nssm start RTSSExporter
```

**Tip:** Use `nssm edit RTSSExporter` to configure via GUI.

### Why Not a Standard Windows Service?

Windows services run in **Session 0** (isolated, non-interactive). RTSS runs in your user session (Session 1+). The shared memory `RTSSSharedMemoryV2` is created in the **session-local** kernel namespace:

```
\Sessions\1\BaseNamedObjects\RTSSSharedMemoryV2  ← RTSS creates here (your session)
\Sessions\0\BaseNamedObjects\RTSSSharedMemoryV2  ← Services look here (DOES NOT EXIST)
```

The exporter **must** run in the same session as RTSS. Both Task Scheduler and NSSM (when configured with your user account) achieve this.

## Prometheus Configuration

Add to `/etc/prometheus/prometheus.yml` on your Prometheus server:

```yaml
scrape_configs:
  - job_name: 'rtss'
    scrape_interval: 2s       # Match exporter's poll interval for smooth graphs
    scrape_timeout: 5s
    static_configs:
      - targets: ['192.168.1.XXX:9101']  # Replace with your gaming PC's IP
        labels:
          instance: 'gaming-pc'
```

Then reload: `sudo systemctl reload prometheus`

**Scrape interval notes:**
- **2-3 seconds recommended** - Matches the exporter's default 2s poll interval
- Prometheus will attempt scraping even when the target is down (minimal overhead)
- Lower intervals = smoother FPS graphs in Grafana
- Storage impact is negligible (~60 MB/year at 2s intervals)

## Grafana Dashboard

Suggested panel layout for a gaming performance dashboard:

### Panel 1: FPS Over Time (Time Series)
```promql
rtss_fps{instance="gaming-pc"}
```
- Legend: `{{process}}`
- Y-axis: FPS (min: 0)
- Thresholds: Yellow at 60, Red at 30

### Panel 2: Frame Time Over Time (Time Series)
```promql
rtss_frame_time_milliseconds{instance="gaming-pc"}
```
- Legend: `{{process}}`
- Y-axis: milliseconds (min: 0)
- Thresholds: Yellow at 16.67ms (60fps), Red at 33.33ms (30fps)

### Panel 3: Current FPS (Stat)
```promql
rtss_fps{instance="gaming-pc"}
```
- Color mode: Background
- Green > 60, Yellow > 30, Red below

### Panel 4: Active Processes (Table)
- Query A: `rtss_fps{instance="gaming-pc"}`
- Query B: `rtss_frame_time_milliseconds{instance="gaming-pc"}`
- Transform: Merge on `process` label
- Columns: Process, FPS, Frame Time (ms)

## Troubleshooting

### No metrics shown (empty gauges)

1. **Check RTSS is running** - Look for the RTSS icon in your system tray
2. **Run with DEBUG logging:**
   ```bash
   python -m rtss_exporter --log-level DEBUG
   ```
3. **Common issues:**
   - `OpenFileMappingW failed (error 2)` → RTSS not running
   - `Invalid RTSS header` → RTSS version mismatch (needs v2.0+)
   - No games showing → Make sure RTSS OSD is enabled for the game

### Service not starting (Task Scheduler/NSSM)

1. **Check Python path** - Get the correct path:
   ```bash
   python -c "import sys; print(sys.executable)"
   ```
2. **Check working directory** - Must be the repo root
3. **NSSM logon failure** - Use your actual Microsoft account password, not PIN
4. **View service logs:**
   ```bash
   # Task Scheduler: Check Task History tab
   # NSSM: Check logs\stdout.log and logs\stderr.log
   ```

### Firewall blocks remote access

1. **Verify the rule exists:**
   ```powershell
   Get-NetFirewallRule -DisplayName "RTSS Prometheus Exporter"
   ```
2. **Test from Prometheus server:**
   ```bash
   curl http://<gaming-pc-ip>:9101/metrics
   ```
3. **Temporarily disable firewall to isolate issue:**
   ```powershell
   Set-NetFirewallProfile -Profile Private -Enabled False  # TESTING ONLY!
   ```

## Architecture

```
RTSS (user session)
  → Named Shared Memory "RTSSSharedMemoryV2"
    → Python ctypes (OpenFileMappingW → MapViewOfFile)
      → struct.unpack (parse RTSS v2 header + app entries)
        → prometheus_client Gauges (with process labels)
          → HTTP server (0.0.0.0:9101/metrics)
            → Remote Prometheus (scrapes every 2s)
              → Grafana dashboards
```

**Technical details:**
- Uses `OpenFileMappingW` (read-only) to access existing shared memory
- Parses RTSS v2 header (36 bytes) and app entry structs (284 bytes per entry)
- Extracts executable name from null-terminated `char[MAX_PATH]` fields
- Handles 32-bit `GetTickCount` wraparound for FPS calculation
- Calls `Gauge.remove()` on stale process labels to prevent flat-line graphs

## Development

### Project Structure

```
rtss-prometheus-exporter/
├── rtss_exporter/
│   ├── __init__.py          # Package version
│   ├── __main__.py          # CLI entry point
│   ├── config.py            # Constants (port, poll interval, RTSS signature)
│   ├── shared_memory.py     # Win32 ctypes wrapper for shared memory access
│   ├── structs.py           # RTSS struct definitions and binary parsing
│   ├── collector.py         # Prometheus Gauge management and stale cleanup
│   └── exporter.py          # Main poll loop
├── tests/
│   ├── test_structs.py      # Struct parsing unit tests (26 tests)
│   └── test_collector.py    # Metric collector unit tests
├── requirements.txt
├── pyproject.toml
└── README.md
```

### Running Tests

```bash
py -m pip install -r requirements.txt
py -m unittest discover tests -v
```

All tests use Python's built-in `unittest` module (no pytest required).

### Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

**Ideas for contributions:**
- Grafana dashboard JSON export
- Additional metrics (min/max FPS, percentiles)
- Support for other RTSS versions
- Windows installer/MSI package
- Documentation improvements

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **RivaTuner Statistics Server** ([Unwinder](https://www.guru3d.com/files-details/rtss-rivatuner-statistics-server-download.html)) - The backbone of PC gaming performance monitoring
- **prometheus_client** - Python library for Prometheus metrics

## Related Projects

- [MSI Afterburner](https://www.msi.com/Landing/afterburner) - GPU overclocking and monitoring (uses RTSS)
- [HWiNFO](https://www.hwinfo.com/) - Hardware monitoring with RTSS integration
- [windows_exporter](https://github.com/prometheus-community/windows_exporter) - General Windows system metrics for Prometheus

---

**Questions or issues?** Open an issue on GitHub!
