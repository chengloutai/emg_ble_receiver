"""
Simple BLE Scanner - Test if both EMG2ch devices can be found
"""

import asyncio
from bleak import BleakScanner


async def scan():
    print("Scanning for BLE devices (15 seconds)...")
    print("Make sure both EMG2ch_A and EMG2ch_B are powered on!\n")

    devices = await BleakScanner.discover(timeout=15.0)

    print(f"Found {len(devices)} devices:\n")
    print("-" * 60)

    emg_devices = []
    for d in sorted(devices, key=lambda x: x.name or ""):
        name = d.name or "(no name)"
        print(f"  {name:20} | {d.address}")

        if "EMG2ch" in (d.name or ""):
            emg_devices.append(d)

    print("-" * 60)
    print(f"\nEMG Devices Found: {len(emg_devices)}")

    if emg_devices:
        for d in emg_devices:
            print(f"  ✓ {d.name} - {d.address}")
    else:
        print("  ✗ No EMG2ch devices found!")
        print("\nTroubleshooting:")
        print("  1. Check if devices are powered on")
        print("  2. Check if devices are in advertising mode")
        print("  3. Make sure devices are not connected to other apps")
        print("  4. Try moving devices closer to your computer")


if __name__ == "__main__":
    asyncio.run(scan())
