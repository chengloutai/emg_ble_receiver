"""
Compare two EMG2ch_B devices - find differences
"""

import asyncio
from bleak import BleakClient, BleakScanner

# Store received data from each device
device_data = {}


async def scan_emg_devices():
    """Find all EMG2ch devices"""
    print("Scanning for EMG2ch devices (10 seconds)...")
    devices = await BleakScanner.discover(timeout=10.0)

    emg_devices = [d for d in devices if d.name and "EMG2ch" in d.name]
    print(f"\nFound {len(emg_devices)} EMG devices:")
    for i, d in enumerate(emg_devices):
        print(f"  [{i}] {d.name} - {d.address}")

    return emg_devices


async def inspect_device(device, index):
    """Connect and inspect a device's services and characteristics"""
    print(f"\n{'='*60}")
    print(f"Device {index}: {device.name} - {device.address}")
    print(f"{'='*60}")

    try:
        async with BleakClient(device.address, timeout=20.0) as client:
            print(f"Connected: {client.is_connected}")

            print("\nServices and Characteristics:")
            for service in client.services:
                print(f"\n  Service: {service.uuid}")
                for char in service.characteristics:
                    props = ", ".join(char.properties)
                    print(f"    Char: {char.uuid}")
                    print(f"          Properties: {props}")

            # Find notify characteristic
            notify_char = None
            for service in client.services:
                for char in service.characteristics:
                    if "notify" in char.properties:
                        notify_char = char.uuid
                        break

            if notify_char:
                print(f"\n--- Receiving sample packets (5 seconds) ---")
                packets = []

                def on_notify(sender, data):
                    hex_str = data.hex().upper()
                    packets.append(hex_str)
                    print(f"  Packet: {hex_str[:40]}... (header: {hex_str[:4]})")

                await client.start_notify(notify_char, on_notify)
                await asyncio.sleep(5)
                await client.stop_notify(notify_char)

                device_data[device.address] = {
                    'name': device.name,
                    'packets': packets,
                    'headers': list(set(p[:4] for p in packets))
                }

                print(f"\nReceived {len(packets)} packets")
                print(f"Unique headers: {device_data[device.address]['headers']}")

    except Exception as e:
        print(f"Error: {e}")


async def main():
    devices = await scan_emg_devices()

    if len(devices) < 2:
        print("\nNeed at least 2 EMG devices for comparison!")
        return

    # Inspect each device
    for i, device in enumerate(devices[:2]):
        await inspect_device(device, i)

    # Compare
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")

    addresses = list(device_data.keys())
    if len(addresses) >= 2:
        d1 = device_data[addresses[0]]
        d2 = device_data[addresses[1]]

        print(f"\nDevice 1: {addresses[0]}")
        print(f"  Headers: {d1['headers']}")

        print(f"\nDevice 2: {addresses[1]}")
        print(f"  Headers: {d2['headers']}")

        # Check header differences
        h1 = d1['headers'][0][:3] if d1['headers'] else None
        h2 = d2['headers'][0][:3] if d2['headers'] else None

        print(f"\n--- Identification Method ---")
        if h1 != h2:
            print(f"✓ Can identify by HEADER: Device1={h1}, Device2={h2}")
        else:
            print(f"✗ Same header: {h1}")
            print(f"  Must identify by ADDRESS:")
            print(f"    Device1: {addresses[0]}")
            print(f"    Device2: {addresses[1]}")


if __name__ == "__main__":
    asyncio.run(main())
