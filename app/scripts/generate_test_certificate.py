"""Gera certificado autoassinado somente para o laboratório FTPS."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True, help="DNS ou IP usado pelo WinSCP")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, arguments.host)]
    )
    try:
        alternative_name = x509.IPAddress(ipaddress.ip_address(arguments.host))
    except ValueError:
        alternative_name = x509.DNSName(arguments.host)

    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([alternative_name]),
            critical=False,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    certificate_path = arguments.output / "nebulaftp.crt"
    key_path = arguments.output / "nebulaftp.key"
    certificate_path.write_bytes(
        certificate.public_bytes(serialization.Encoding.PEM)
    )
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    print(certificate_path)
    print(key_path)


if __name__ == "__main__":
    main()
