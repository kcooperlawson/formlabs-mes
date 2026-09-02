"""
test_gateway_discover.py - Standalone mDNS discovery test, isolated from
run_gateway.py's full startup logic.

Run this on the LAPTOP (or whichever PC is trying to find the database)
while test_gateway_announce.py is running on the desktop. Prints exactly
what it finds, or a clear diagnosis of what to check if it finds nothing.
"""
import socket
import time

print("Listening for a formlabsmes database announcement for 10 seconds...")
print(f"(this machine's hostname: {socket.gethostname()})")
print()

try:
    from service_discovery import discover
except ImportError as e:
    print(f"Can't even import service_discovery.py / zeroconf: {e}")
    print("Run: .\\venv\\Scripts\\python.exe -m pip install zeroconf")
    raise SystemExit(1)

start = time.time()
found = discover(timeout_s=10)
elapsed = time.time() - start

print(f"Search took {elapsed:.1f}s")
print()

if found:
    print(f"FOUND {len(found)} database(s):")
    for f in found:
        print(f"  - {f['plant']}: {f['host']}:{f['port']}/{f['dbname']}")
    print()
    print("Network discovery works. If run_gateway.py still isn't connecting,")
    print("the remaining issue is Postgres itself refusing the connection -")
    print("see README_DEVICE_GATEWAY.md's Auto-discovery section (listen_addresses,")
    print("pg_hba.conf, and the Windows Firewall port 5432 rule on the desktop).")
else:
    print("FOUND NOTHING. In order of likelihood, check:")
    print("  1. Is test_gateway_announce.py (or the main app, Home.py) actually")
    print("     running on the desktop RIGHT NOW? The announcement stops the")
    print("     moment that process stops.")
    print("  2. Are both PCs on the SAME network? Same Wi-Fi/router, not one on")
    print("     a guest network or a different VLAN, and neither on a VPN.")
    print("  3. Windows network profile: on BOTH PCs, Settings > Network & Internet")
    print("     > (your connection) > Network profile type should be 'Private',")
    print("     not 'Public'. Windows blocks a lot of discovery traffic on Public.")
    print("  4. Windows Firewall on the DESKTOP: mDNS uses UDP port 5353. Check")
    print("     Windows Defender Firewall with Advanced Security > Inbound Rules")
    print("     for a rule covering UDP 5353 (often grouped under 'Network")
    print("     Discovery' or 'Function Discovery'), enabled for your active")
    print("     profile. If none exists, add one: New Rule > Port > UDP > 5353 >")
    print("     Allow the connection > apply to Private (and Domain if used).")
    print("  5. A managed switch or router doing 'client isolation' / 'AP")
    print("     isolation' on Wi-Fi blocks device-to-device traffic entirely -")
    print("     common on guest networks and some mesh Wi-Fi systems. Check the")
    print("     router's Wi-Fi settings for that option if 1-4 all check out.")
