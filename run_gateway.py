"""
run_gateway.py - Standalone entrypoint for the Device Gateway.

Run this as its own long-lived process, separate from `streamlit run
Home.py`. Streamlit's execution model (rerun the script top-to-bottom on
every interaction) isn't a fit for continuous background polling, and
running the gateway loop inside a Streamlit page would mean it stops the
moment nobody has the app open in a browser tab.

Usage:
    python run_gateway.py

Needs the same .env (DB_URL) your Streamlit app uses — it writes into the
same database Analytics_Hub already reads from, so nothing downstream
needs to change. It also needs whatever network/USB/COM-port access the
machines you register as Devices require, which is the main reason to run
it on a floor PC near those machines rather than wherever Postgres itself
happens to live.

On Windows, wrap it as a background service (nssm, or a Task Scheduler
job set to "run whether user is logged on or not") so it survives reboots
without a terminal window staying open. On Linux, a systemd unit running
`python run_gateway.py` with Restart=on-failure does the same job.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from device_gateway.service import run_forever

if __name__ == "__main__":
    run_forever()
