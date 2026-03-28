"""Quick validator for DCom code checksum"""

# Device 1 packets (what we send)
packets_hex = ['4D4F', '494E', '941E', '008E', '28FE', '032E', '000E', '000E', '200E', '81EE']
packets = [bytes.fromhex(p) for p in packets_hex]

print("Device 1 (our packets):")
checksum = 0
for i, pkt in enumerate(packets):
    for b in pkt:
        checksum += (b >> 4) & 0xF
        checksum += b & 0xF
    print(f'After packet {i+1}: checksum={checksum}, mod 16={checksum % 16}')

print(f'\nFinal checksum mod 16: {checksum % 16} (should be 0)')
print(f'✓ VALID' if checksum % 16 == 0 else '✗ INVALID')


