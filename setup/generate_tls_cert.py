"""
generate_tls_cert.py - makes this PC a self-signed HTTPS certificate.

Streamlit can terminate TLS itself (server.sslCertFile / server.sslKeyFile in
.streamlit/config.toml or on the command line) with no reverse proxy and
nothing else to install. This script makes the one thing that approach still
needs: a certificate and a private key, valid for however operators actually
reach this PC - its hostname, "localhost", 127.0.0.1, and its LAN IP.

Written for Finding 1 in the security posture doc: everything, including the
PIN at sign-in and every session cookie, currently goes over plain HTTP. A
phone on the same plant network can read all of it. This closes that gap
without asking for a network team or a second process.

    python setup\\generate_tls_cert.py          write certs\\mes.crt / mes.key
                                                 if missing, expired soon, or
                                                 no longer covers this PC's
                                                 address
    python setup\\generate_tls_cert.py --force  regenerate unconditionally
    python setup\\generate_tls_cert.py --check  report status only, write
                                                 nothing (exit 1 if action
                                                 is needed)

It is a SELF-SIGNED certificate. Browsers and phones will show a "not
trusted" warning the first time they connect - that is expected, not a
bug. Tap through it, or install certs\\mes.crt as a trusted certificate on
each device once. If you have a certificate from an internal CA instead,
skip this script and point .streamlit\\config.toml (or the launcher flags
in run_mes.bat / START_HERE.bat) at that file pair instead - anything at
certs\\mes.crt / certs\\mes.key is picked up automatically either way.

Exit 0 = certs\\mes.crt / mes.key are in place and good. Exit 1 = stopped
before writing anything usable.
"""
import datetime
import ipaddress
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CERTS_DIR = ROOT / "certs"
CERT_FILE = CERTS_DIR / "mes.crt"
KEY_FILE = CERTS_DIR / "mes.key"

VALID_DAYS = 3650          # ten years - this is a floor PC, not a web server
RENEW_WITHIN_DAYS = 60      # nag this far ahead of expiry


def lan_ip():
    """Same trick _preflight.py uses: the address a phone on the floor would
    actually type, not whatever gethostbyname() returns on a PC with a VPN
    or a Hyper-V adapter also installed."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packet sent; this only picks a route
        return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return ""
    finally:
        s.close()


def _san_names(hostname, ip):
    """The DNS names and IPs the certificate needs to cover."""
    from cryptography import x509

    dns = {hostname, "localhost"}
    ips = {ipaddress.ip_address("127.0.0.1")}
    if ip:
        try:
            ips.add(ipaddress.ip_address(ip))
        except ValueError:
            pass
    names = [x509.DNSName(d) for d in sorted(dns)]
    names += [x509.IPAddress(i) for i in sorted(ips, key=str)]
    return names, dns, {str(i) for i in ips}


def _existing_cert_ok(hostname, ip):
    """True if certs\\mes.crt / mes.key exist, are not close to expiring, and
    already cover this PC's current hostname and IP. False otherwise, with a
    reason printed."""
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        print("  No certificate yet.")
        return False

    try:
        from cryptography import x509
    except ImportError:
        print("  [X] The 'cryptography' package isn't installed.")
        print("      Run START_HERE.bat option 1 (or 2) first - it installs")
        print("      requirements.txt, which now includes it.")
        sys.exit(1)

    try:
        cert = x509.load_pem_x509_certificate(CERT_FILE.read_bytes())
    except Exception as exc:
        print(f"  Existing certificate can't be read ({exc}) - regenerating.")
        return False

    try:
        expires = cert.not_valid_after_utc.replace(tzinfo=None)
    except AttributeError:  # older cryptography versions
        expires = cert.not_valid_after
    days_left = (expires - datetime.datetime.utcnow()).days

    if days_left < RENEW_WITHIN_DAYS:
        print(f"  Existing certificate expires {expires.date().isoformat()}"
              f" ({days_left} day(s) left) - renewing.")
        return False

    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        covered_dns = set(san.get_values_for_type(x509.DNSName))
        covered_ip = {str(i) for i in san.get_values_for_type(x509.IPAddress)}
    except x509.ExtensionNotFound:
        covered_dns, covered_ip = set(), set()

    _, want_dns, want_ip = _san_names(hostname, ip)
    if not want_dns.issubset(covered_dns) or not want_ip.issubset(covered_ip):
        print(f"  Existing certificate doesn't cover this PC's current "
              f"address ({hostname} / {ip or '?'}) - regenerating.")
        return False

    print(f"  Certificate is good until {expires.date().isoformat()} and "
          f"covers {hostname} and {ip or '(no LAN IP found)'}.")
    return True


def generate(hostname, ip):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    CERTS_DIR.mkdir(exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Formlabs MES"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    san_names, _, _ = _san_names(hostname, ip)
    now = datetime.datetime.utcnow()

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=VALID_DAYS))
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=True,
                content_commitment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    KEY_FILE.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    print(f"  Wrote {CERT_FILE.relative_to(ROOT)} and {KEY_FILE.relative_to(ROOT)}")
    print(f"  Valid for {hostname}, localhost, 127.0.0.1"
          + (f" and {ip}" if ip else "") + f", for {VALID_DAYS // 365} years.")


def main():
    force = "--force" in sys.argv
    check_only = "--check" in sys.argv

    hostname = socket.gethostname()
    ip = lan_ip()

    print()
    print("  ===================================================")
    print("   HTTPS CERTIFICATE")
    print("  ===================================================")

    if not force and _existing_cert_ok(hostname, ip):
        print()
        print("  Nothing to do. run_mes.bat and START_HERE.bat pick this up")
        print("  automatically the next time the MES starts.")
        return 0

    if check_only:
        print()
        print("  A new or renewed certificate is needed. Run this again")
        print("  without --check to write it.")
        return 1

    try:
        import cryptography  # noqa: F401
    except ImportError:
        print()
        print("  [X] The 'cryptography' package isn't installed.")
        print("      Run START_HERE.bat option 1 (or 2) first - it installs")
        print("      requirements.txt, which now includes it.")
        return 1

    print()
    generate(hostname, ip)
    print()
    print("  This is a SELF-SIGNED certificate: browsers and phones will")
    print("  show a 'not trusted' warning the first time they connect to")
    print("  this PC. That's expected - tap/click through it, or install")
    print(f"  {CERT_FILE.relative_to(ROOT)} as a trusted certificate on a")
    print("  device once to stop the warning there.")
    print()
    print("  Restart the MES (START_HERE.bat, option 3) and it will serve")
    print("  https:// instead of http://.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
