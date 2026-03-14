"""
Test which DCom protocols are supported by the connected device.
"""
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from core.combat.dcom.dcom_controller import DComController


def test_protocol_support():
    """Test which protocols the DCom supports."""
    print("=" * 60)
    print("DCom Protocol Support Test")
    print("=" * 60)
    
    controller = DComController()
    
    # Find and connect to device
    print("\nScanning for DCom devices...")
    devices = controller.find_dcom_devices()
    
    if not devices:
        print("No DCom devices found!")
        return
    
    print(f"Found {len(devices)} device(s):")
    for i, (port, desc) in enumerate(devices):
        print(f"  [{i}] {desc} - {port}")
    
    port, desc = devices[0]
    print(f"\nConnecting to {desc} on {port}...")
    
    if not controller.connect(port):
        print("Connection failed!")
        return
    
    print("✓ Connected!\n")
    
    # Test each protocol type
    protocols_to_test = [
        ("V-Pet", "V", "V0"),
        ("Pendulum X", "X", "X0"),
        ("Pendulum Y", "Y", "Y0"),
        ("iC/Accel", "IC", "IC0"),
        ("Color/DMX", "C", "C0"),
    ]
    
    print("Testing protocol support:")
    print("-" * 60)
    
    supported = []
    unsupported = []
    
    for name, code, test_cmd in protocols_to_test:
        print(f"\nTesting {name} ({code})...")
        print(f"  Sending: {test_cmd}")
        
        controller._send_raw(test_cmd + '\r')
        time.sleep(0.2)
        
        # Read response
        response = ""
        start_time = time.time()
        while time.time() - start_time < 0.5:
            if controller.serial_port.in_waiting > 0:
                line = controller.serial_port.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    response = line
                    break
        
        if response:
            print(f"  Response: {response}")
            
            if "N" in response or "Error" in response or "error" in response:
                print(f"  ✗ NOT SUPPORTED")
                unsupported.append((name, code))
            else:
                print(f"  ✓ SUPPORTED")
                supported.append((name, code))
        else:
            print(f"  ⚠ No response (timeout)")
            unsupported.append((name, code))
        
        time.sleep(0.3)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if supported:
        print(f"\n✓ Supported Protocols ({len(supported)}):")
        for name, code in supported:
            print(f"  - {name} ({code})")
    else:
        print("\n✗ No protocols confirmed as supported")
    
    if unsupported:
        print(f"\n✗ Unsupported Protocols ({len(unsupported)}):")
        for name, code in unsupported:
            print(f"  - {name} ({code})")
    
    print("\n" + "=" * 60)
    print("\nNOTE: Your DCom appears to support:", ", ".join([name for name, _ in supported]) if supported else "Unknown")
    print("For DMX/Digimon X battles, you need COLOR protocol (C) support.")
    print("If COLOR is not supported, your DCom may be:")
    print("  - A 2-prong only model (V-Pet/Pendulum only)")
    print("  - Missing COLOR protocol firmware")
    print("  - Requires a firmware update")
    print("=" * 60)
    
    controller.disconnect()


if __name__ == "__main__":
    test_protocol_support()
