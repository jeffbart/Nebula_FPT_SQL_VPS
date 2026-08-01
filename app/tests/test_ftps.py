import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import ssl
import tempfile
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from ftp.server import Server


class FakePathIO:
    def __init__(self, *_, state=None, **__):
        self._state = state or []

    @property
    def state(self):
        return self._state


class FakeUserManager:
    async def notify_logout(self, _):
        return None


def create_certificate(directory: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]
    )
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    certificate_path = directory / "certificate.pem"
    key_path = directory / "key.pem"
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return certificate_path, key_path


class ExplicitFTPSTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_tls_upgrades_control_channel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            certificate_path, key_path = create_certificate(Path(temporary))
            server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server_context.minimum_version = ssl.TLSVersion.TLSv1_2
            server_context.load_cert_chain(certificate_path, key_path)

            server = Server(
                FakeUserManager(),
                FakePathIO,
                tls_context=server_context,
                tls_required=True,
            )
            await server.start("127.0.0.1", 0)
            port = server.server.sockets[0].getsockname()[1]

            client_context = ssl.create_default_context()
            client_context.check_hostname = False
            client_context.verify_mode = ssl.CERT_NONE
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            try:
                self.assertTrue((await reader.readline()).startswith(b"220 "))
                writer.write(b"AUTH TLS\r\n")
                await writer.drain()
                self.assertTrue((await reader.readline()).startswith(b"234 "))

                await writer.start_tls(
                    client_context,
                    server_hostname="localhost",
                )
                writer.write(b"NOOP\r\n")
                await writer.drain()
                self.assertTrue((await reader.readline()).startswith(b"200 "))

                writer.write(b"PBSZ 0\r\nPROT P\r\nEPSV\r\n")
                await writer.drain()
                self.assertTrue((await reader.readline()).startswith(b"200 "))
                self.assertTrue((await reader.readline()).startswith(b"200 "))
                epsv_response = (await reader.readline()).decode("ascii")
                self.assertTrue(epsv_response.startswith("229 "))
                passive_port = int(epsv_response.split("|")[3])

                data_reader, data_writer = await asyncio.open_connection(
                    "127.0.0.1",
                    passive_port,
                    ssl=client_context,
                    server_hostname="localhost",
                )
                data_writer.close()
                await data_writer.wait_closed()
            finally:
                writer.close()
                await writer.wait_closed()
                await server.close()


if __name__ == "__main__":
    unittest.main()
