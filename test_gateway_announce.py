"""
test_gateway_announce.py - Standalone, foreground mDNS announcer for
testing network discovery in isolation from the full Streamlit app.

Run this on the DESKTOP (the PC hosting the database) while testing
whether another PC on the network can find it. Leave it running in its
own terminal window, then run test_gateway_discover.py on the other PC.

This does exactly what service_announcer.py does inside Home.py, just as
a standalone script that's easy to point people at for debugging - if
THIS doesn't get found by test_gateway_discover.py on another PC, the
problem is network/firewall, not anything in the Streamlit app.
"""
import time
from dotenv import load_dotenv
load_dotenv()

import service_announcer

print("Starting mDNS announcement... (Ctrl+C to stop)")
service_announcer.start_announcing()

if service_announcer._zeroconf is None:
    print("FAILED to start announcing - check the warning printed above "
          "(usually: DB_URL missing, or the zeroconf package isn't installed "
          "in this Python environment).")
else:
    print("Announcing successfully. Leave this running and try "
          "test_gateway_discover.py from another PC now.")
    try:
        while True:
            time.sleep(5)
            print(".", end="", flush=True)
    except KeyboardInterrupt:
        print("\nStopping.")
