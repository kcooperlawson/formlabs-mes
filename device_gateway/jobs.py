"""
device_gateway/jobs.py - Find Devices and Test Connection, run on the gateway PC.

The admin page is usually open on a PC with no cable to any machine. When it
asks this gateway to look (see device_crud.create_gateway_job), service.py
claims the job and hands it to run_job() here, so the COM ports listed and the
subnet scanned are the ones on the PC the hardware is actually plugged into.

Every job is bounded. A Test Connection against an OPC-UA or MQTT host that
drops packets has no adapter-level timeout of its own, so it runs on a worker
thread that the job stops waiting for - the same guard the API's own
/test-connection endpoint uses.
"""
import concurrent.futures

from .discovery import guess_local_subnet, list_serial_ports, scan_network

TEST_CONNECTION_TIMEOUT_S = 10.0


def _test_connection(params: dict) -> dict:
    import device_crud

    protocol = params.get("protocol", "")
    tag_map = device_crud.probe_tag_map(protocol, params.get("probe_tags") or [])
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(device_crud.test_device_connection, protocol, params.get("connection") or {}, tag_map)
        try:
            result = future.result(timeout=TEST_CONNECTION_TIMEOUT_S)
        except concurrent.futures.TimeoutError:
            return {"ok": False, "raw": {}, "error": f"Timed out after {TEST_CONNECTION_TIMEOUT_S:.0f}s waiting for a response."}
    finally:
        # Don't block on a hung adapter call; the thread is abandoned.
        pool.shutdown(wait=False)
    if "error" in result:
        return {"ok": False, "raw": {}, "error": result["error"]}
    return {"ok": True, "raw": result.get("raw", {}), "error": None}


def run_job(kind: str, params: dict):
    """The result for one job. Raises for anything that should be shown to
    the person as an error (a malformed subnet, an unknown kind)."""
    if kind == "serial_ports":
        return list_serial_ports()
    if kind == "subnet":
        return {"subnet": guess_local_subnet()}
    if kind == "scan":
        return scan_network(str(params.get("subnet") or ""))
    if kind == "test_connection":
        return _test_connection(params)
    raise ValueError(f"Unknown gateway job {kind!r}")
