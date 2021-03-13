#!/usr/bin/env python3

from pathlib import Path

from datetime import datetime
from dateutil.relativedelta import relativedelta

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from cryptography.x509.oid import NameOID

from init import shell


def generate_selfsigned():
    """Generate a self-signed certificate with associated keys.

    The certificate will have a fake CNAME and subjAltName since
    the expectation is that this certificate will only be used by
    clients that know its fingerprint and will not use a validation
    via a CA certificate and hostname. This approach is similar to
    Certificate Pinning, however, here a certificate is not embedded
    into the application but is generated on initialization at one
    node and its fingerprint is copied in a token to another node
    via a secure channel.
    https://owasp.org/www-community/controls/Certificate_and_Public_Key_Pinning
    """
    cert_path, key_path = (
        Path(shell.config_get('config.cluster.tls-cert-path')),
        Path(shell.config_get('config.cluster.tls-key-path')),
    )
    # Do not generate a new certificate and key if there is already an existing
    # pair. TODO: improve this check and allow renewal.
    if cert_path.exists() and key_path.exists():
        return

    dummy_cn = 'microstack.run'
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    common_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, dummy_cn)
    ])
    san = x509.SubjectAlternativeName([x509.DNSName(dummy_cn)])
    basic_contraints = x509.BasicConstraints(ca=True, path_length=0)
    now = datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(common_name)
        .issuer_name(common_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + relativedelta(years=10))
        .add_extension(basic_contraints, False)
        .add_extension(san, False)
        .sign(key, hashes.SHA256(), default_backend())
    )

    cert_fprint = cert.fingerprint(hashes.SHA256()).hex()
    shell.config_set(**{'config.cluster.fingerprint': cert_fprint})

    serialized_cert = cert.public_bytes(encoding=serialization.Encoding.PEM)
    serialized_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_path.write_bytes(serialized_cert)
    key_path.write_bytes(serialized_key)
