"""
BLE EMG Data Receiver
Real-time display with 2-second sliding window and packet loss statistics
"""

import asyncio
import time
from collections import deque
from threading import Thread, Lock
from bleak import BleakClient, BleakScanner
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

# ============== Configuration ==============
SAMPLE_RATE = 500  # Hz
WINDOW_SEC = 2  # seconds
WINDOW_SIZE = SAMPLE_RATE * WINDOW_SEC  # 1000 points for 2 sec window
SAMPLES_PER_PACKET = 7  # Each packet contains 7 samples

# Both devices named "EMG2ch_B", differentiated by packet header
# Device 1: header starts with "ABE"
# Device 2: header starts with "ABB"
DEVICE_NAME = "EMG2ch_B"
UUID_NOTIFY = "6b400003-b5a3-f393-e0a9-e50e24dcca9e"

DEVICES = {
    'ABE': {
        'label': 'Device 1 (ABE)',
        'header': 'ABE',
    },
    'ABB': {
        'label': 'Device 2 (ABB)',
        'header': 'ABB',
    }
}

# ============== Data Storage ==============
# Real-time sliding window data
realtime_data = {
    key: {
        't2': deque(maxlen=WINDOW_SIZE),
        't4': deque(maxlen=WINDOW_SIZE)
    } for key in DEVICES
}

# All collected data (for final plot)
all_data = {key: {'t2': [], 't4': []} for key in DEVICES}

# Packet statistics
packet_stats = {
    key: {
        'received': 0,
        'expected_seq': None,
        'lost': 0,
        'start_time': None
    } for key in DEVICES
}

data_lock = Lock()
running = True


# ============== Data Parsing ==============
def parse_emg_packet(hex_text: str) -> tuple:
    """Parse EMG data packet, return (t2_list, t4_list, seq_num)"""
    t2_list, t4_list = [], []
    bit_num = 24

    # Extract sequence number from header (4th character, position 3)
    seq_num = int(hex_text[3], 16) if len(hex_text) > 3 else None

    for i in range(1, 8):
        start = 4 + bit_num * (i - 1)
        end = 4 + bit_num * i
        if end > len(hex_text):
            break

        group = hex_text[start:end]
        t2_list.append(float(int(group[6:12], 16)))
        t4_list.append(float(int(group[18:24], 16)))

    return t2_list, t4_list, seq_num


def get_device_by_header(hex_str: str) -> str | None:
    """Identify device by packet header"""
    header = hex_str[:3]
    for key, cfg in DEVICES.items():
        if cfg['header'] == header:
            return key
    return None


def handle_notification(data: bytes):
    """Handle BLE notification and store data"""
    global running
    hex_str = data.hex().upper()

    device_key = get_device_by_header(hex_str)
    if device_key is None:
        return

    try:
        t2, t4, seq_num = parse_emg_packet(hex_str)

        with data_lock:
            stats = packet_stats[device_key]

            # Initialize start time
            if stats['start_time'] is None:
                stats['start_time'] = time.time()

            # Track packet loss using sequence number
            if seq_num is not None:
                if stats['expected_seq'] is not None:
                    expected = stats['expected_seq']
                    if seq_num != expected:
                        # Calculate lost packets (handle wrap-around 0-F)
                        if seq_num > expected:
                            lost = seq_num - expected
                        else:
                            lost = (16 - expected) + seq_num
                        stats['lost'] += lost
                stats['expected_seq'] = (seq_num + 1) % 16

            stats['received'] += 1

            # Store data
            realtime_data[device_key]['t2'].extend(t2)
            realtime_data[device_key]['t4'].extend(t4)
            all_data[device_key]['t2'].extend(t2)
            all_data[device_key]['t4'].extend(t4)

    except Exception as e:
        print(f"Parse error: {e}")


# ============== BLE Connection ==============
async def scan_devices():
    """Scan for EMG devices and match by address"""
    print("Scanning for EMG devices (10 seconds)...")
    devices = await BleakScanner.discover(timeout=10.0)

    print(f"\nFound {len(devices)} devices:")
    for d in devices:
        print(f"  - {d.name or '(no name)'} : {d.address}")

    found = {}
    for d in devices:
        # Match by address (both devices have same name)
        for key, cfg in DEVICES.items():
            if d.address == cfg['address']:
                found[key] = d
                print(f"\n>>> Found {cfg['label']}: {d.address}")

    return found


async def connect_and_receive(device, device_key: str):
    """Connect to device and receive data"""
    cfg = DEVICES[device_key]
    print(f"\n[{cfg['label']}] Connecting...")

    try:
        client = BleakClient(device.address)
        await client.connect()
        print(f"[{cfg['label']}] Connected!")

        def on_notify(_, data):
            handle_notification(bytes(data))

        await client.start_notify(cfg['uuid_notify'], on_notify)
        return client
    except Exception as e:
        print(f"[{cfg['label']}] Connection failed: {e}")
        return None


async def ble_main():
    """Main BLE task"""
    global running

    found_devices = await scan_devices()
    if not found_devices:
        print("\nNo EMG devices found!")
        running = False
        return

    clients = {}
    for key, device in found_devices.items():
        client = await connect_and_receive(device, key)
        if client:
            clients[key] = client

    if not clients:
        print("\nFailed to connect to any device!")
        running = False
        return

    names = [DEVICES[k]['label'] for k in clients]
    print(f"\n{'='*50}")
    print(f"Connected: {', '.join(names)}")
    print("Close chart window to stop")
    print(f"{'='*50}\n")

    while running:
        await asyncio.sleep(0.1)

    # Disconnect
    for key, client in clients.items():
        if client.is_connected:
            await client.stop_notify(DEVICES[key]['uuid_notify'])
            await client.disconnect()
            print(f"[{DEVICES[key]['label']}] Disconnected")


def run_ble_thread():
    """Run BLE in separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(ble_main())
    except Exception as e:
        print(f"BLE error: {e}")
    finally:
        loop.close()


# ============== Real-time Plotting ==============
def calc_packet_loss_rate(key: str) -> float:
    """Calculate packet loss rate for a device"""
    stats = packet_stats[key]
    total = stats['received'] + stats['lost']
    if total == 0:
        return 0.0
    return (stats['lost'] / total) * 100


def realtime_plot():
    """Real-time plotting with 2-second sliding window"""
    global running

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('EMG Real-time Data (2 sec window)', fontsize=14)

    # Time axis for 2-second window
    time_axis = [i / SAMPLE_RATE for i in range(WINDOW_SIZE)]

    plot_config = [
        ('ABE', 't2', axes[0, 0], 'b-', 'Device 1 (ABE) - T2'),
        ('ABE', 't4', axes[1, 0], 'r-', 'Device 1 (ABE) - T4'),
        ('ABB', 't2', axes[0, 1], 'g-', 'Device 2 (ABB) - T2'),
        ('ABB', 't4', axes[1, 1], 'm-', 'Device 2 (ABB) - T4'),
    ]

    lines = {}
    stats_texts = {}

    for key, channel, ax, color, title in plot_config:
        ax.set_title(title)
        ax.set_xlabel('Time (sec)')
        ax.set_ylabel('Value')
        ax.set_xlim(0, WINDOW_SEC)
        ax.set_ylim(0, 1000000)
        ax.grid(True, alpha=0.3)
        line, = ax.plot([], [], color, linewidth=1)
        lines[(key, channel)] = line

        # Add stats text only for T2 channel (top row)
        if channel == 't2':
            stats_texts[key] = ax.text(0.02, 0.98, '', transform=ax.transAxes,
                                        verticalalignment='top', fontsize=9,
                                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.show(block=False)
    plt.pause(0.1)

    print("\nReal-time display started...")

    try:
        while plt.fignum_exists(fig.number) and running:
            with data_lock:
                for key, channel, ax, color, title in plot_config:
                    data = list(realtime_data[key][channel])
                    if data:
                        # Pad with zeros if less than window size
                        if len(data) < WINDOW_SIZE:
                            padded = [0] * (WINDOW_SIZE - len(data)) + data
                        else:
                            padded = data[-WINDOW_SIZE:]

                        lines[(key, channel)].set_data(time_axis, padded)

                        # Auto-scale Y axis
                        max_val = max(padded) if max(padded) > 0 else 1
                        ax.set_ylim(0, max_val * 1.1)

                # Update stats text (only on first subplot of each device)
                for key in DEVICES:
                    if key in stats_texts:
                        loss_rate = calc_packet_loss_rate(key)
                        stats = packet_stats[key]
                        elapsed = time.time() - stats['start_time'] if stats['start_time'] else 0
                        stats_texts[key].set_text(
                            f"Packets: {stats['received']}\n"
                            f"Lost: {stats['lost']}\n"
                            f"Loss rate: {loss_rate:.2f}%\n"
                            f"Time: {elapsed:.1f}s"
                        )

            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.05)

    except Exception as e:
        print(f"Plot error: {e}")

    running = False
    plt.close('all')


# ============== Final Summary Plot ==============
def plot_summary():
    """Plot all collected data and show statistics"""
    print("\n" + "="*50)
    print("Collection Summary")
    print("="*50)

    for key in DEVICES:
        label = DEVICES[key]['label']
        stats = packet_stats[key]
        loss_rate = calc_packet_loss_rate(key)
        elapsed = time.time() - stats['start_time'] if stats['start_time'] else 0

        print(f"\n{label}:")
        print(f"  Total samples: T2={len(all_data[key]['t2'])}, T4={len(all_data[key]['t4'])}")
        print(f"  Packets received: {stats['received']}")
        print(f"  Packets lost: {stats['lost']}")
        print(f"  Packet loss rate: {loss_rate:.2f}%")
        print(f"  Collection time: {elapsed:.1f} seconds")

    has_data = any(all_data[k]['t2'] or all_data[k]['t4'] for k in DEVICES)
    if not has_data:
        print("\nNo data collected")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('EMG Complete Data Collection', fontsize=14)

    plot_config = [
        ('ABE', 't2', axes[0, 0], 'b-', 'Device 1 (ABE) - T2'),
        ('ABE', 't4', axes[1, 0], 'r-', 'Device 1 (ABE) - T4'),
        ('ABB', 't2', axes[0, 1], 'g-', 'Device 2 (ABB) - T2'),
        ('ABB', 't4', axes[1, 1], 'm-', 'Device 2 (ABB) - T4'),
    ]

    for key, channel, ax, color, title in plot_config:
        data = all_data[key][channel]
        stats = packet_stats[key]
        loss_rate = calc_packet_loss_rate(key)

        ax.set_title(f"{title} (Loss: {loss_rate:.2f}%)")
        ax.set_xlabel('Sample')
        ax.set_ylabel('Value')
        ax.grid(True, alpha=0.3)

        if data:
            ax.plot(range(len(data)), data, color, linewidth=0.5)
            ax.set_xlim(0, len(data))
            ax.set_ylim(0, max(data) * 1.1 if max(data) > 0 else 1)

    plt.tight_layout()
    plt.show()


# ============== Main ==============
def main():
    global running

    print("="*50)
    print("EMG Real-time Receiver")
    print(f"Window: {WINDOW_SEC} sec | Sample rate: {SAMPLE_RATE} Hz")
    print(f"Devices: {DEVICES['ABE']['label']} & {DEVICES['ABB']['label']}")
    print("="*50)

    # Start BLE thread
    ble_thread = Thread(target=run_ble_thread, daemon=True)
    ble_thread.start()

    # Wait for connection
    time.sleep(2)

    if running:
        # Run real-time plot (blocks until window closed)
        realtime_plot()

    # Show summary
    plot_summary()
    print("\nDone")


if __name__ == "__main__":
    main()
