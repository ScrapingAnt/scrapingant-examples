"""Generate certs/localhost.pem (self-signed, SAN localhost, 10 years) and certs/expired.pem (validity in 2024)."""
import datetime as dt, os
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

def make(name, not_before, not_after, cn="localhost", issuer=None, ca=True, san=True):
    """Self-signed unless issuer=(cert, key) is given; then a leaf signed by that CA."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    b = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer[0].subject if issuer else subject)
         .public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(not_before).not_valid_after(not_after)
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if san:
        b = b.add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
    cert = b.sign(issuer[1] if issuer else key, hashes.SHA256())
    open(f"certs/{name}.pem", "wb").write(cert.public_bytes(serialization.Encoding.PEM))
    open(f"certs/{name}-key.pem", "wb").write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    return cert, key

os.makedirs("certs", exist_ok=True)
now = dt.datetime.now(dt.timezone.utc)
if not os.path.exists("certs/localhost.pem"):
    make("localhost", now - dt.timedelta(days=1), now + dt.timedelta(days=3650))
if not os.path.exists("certs/expired.pem"):
    make("expired", dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc), dt.datetime(2024, 2, 1, tzinfo=dt.timezone.utc))
if not os.path.exists("certs/internal.pem"):
    ca = make("ca", now - dt.timedelta(days=1), now + dt.timedelta(days=3650), cn="Example Internal CA", san=False)
    make("internal", now - dt.timedelta(days=1), now + dt.timedelta(days=825), issuer=ca, ca=False)
print("certs ready")
