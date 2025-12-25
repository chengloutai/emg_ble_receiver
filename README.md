# EMG BLE Receiver

BLE EMG data receiver for dual EMG2ch_B devices with real-time visualization and packet loss tracking.

## Features

- Real-time 2-second sliding window display
- Dual device support (identified by packet header: ABE / ABB)
- Packet loss rate tracking
- 500 Hz sampling rate
- 4-channel display (2 devices x 2 channels: T2, T4)

## Files

| File | Description |
|------|-------------|
| `ble_emg_receiver.py` | Main receiver with real-time plotting |
| `ble_scan_test.py` | Simple BLE scanner to find EMG devices |
| `ble_compare_devices.py` | Tool to compare and identify devices |

## Requirements

```bash
pip install bleak matplotlib
```

## Usage

### 1. Scan for devices
```bash
python ble_scan_test.py
```

### 2. Compare devices (find header differences)
```bash
python ble_compare_devices.py
```

### 3. Run real-time receiver
```bash
python ble_emg_receiver.py
```

Close the chart window to stop recording and view the complete data summary.

## Device Configuration

Both devices are named `EMG2ch_B` but differentiated by packet header:
- **Device 1**: Header starts with `ABE`
- **Device 2**: Header starts with `ABB`

## Data Format

Each packet contains 7 samples with 24 hex characters per group:
- T2: characters 6-12
- T4: characters 18-24
