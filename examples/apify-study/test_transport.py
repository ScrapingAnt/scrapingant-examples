"""Offline authenticated transport tests; no provider or credential access."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import evidence_transport as transport


class AgeTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = Path(os.environ.get('STUDY_TEST_AGE_BIN', '/tmp/apify-age-bin/age/age'))
        cls.keygen = cls.binary.with_name('age-keygen')
        if not cls.binary.is_file() or not cls.keygen.is_file():
            raise RuntimeError('Pinned age binaries are required for transport tests')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.identity = self.root / 'identity.agekey'
        subprocess.run([str(self.keygen), '-o', str(self.identity)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.recipient = subprocess.run([str(self.keygen), '-y', str(self.identity)], check=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode().strip()
        self.payload = json.dumps({'schema_version': 1, 'synthetic_transport_test': True,
                                   'records': [{'case_id': 'synthetic-only', 'name': 'PRIVATE_CANARY'}]}).encode()
        self.cipher = self.root / 'capture.age'
        self.private = self.root / 'private.json'

    def encrypt(self):
        return transport.encrypt_capture(self.payload, self.cipher, self.binary, self.recipient)

    def verify(self, receipt, **kwargs):
        return transport.decrypt_and_verify(self.cipher.read_bytes(), self.private, self.binary,
            self.identity, receipt['plaintext_sha256'], receipt['ciphertext_sha256'], **kwargs)

    def test_standard_age_roundtrip_requires_durable_readback(self):
        receipt = self.encrypt()
        self.assertNotIn(b'PRIVATE_CANARY', self.cipher.read_bytes())
        self.assertFalse(self.private.exists())
        self.assertEqual(receipt['plaintext_sha256'], hashlib.sha256(self.payload).hexdigest())
        self.assertTrue(receipt['remote_file_readback_verified'])
        approval = self.verify(receipt, validate_payload=lambda value: value['synthetic_transport_test'] is True)
        self.assertEqual(self.private.read_bytes(), self.payload)
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o600)
        self.assertEqual(set(approval), {'plaintext_sha256', 'ciphertext_sha256', 'scope_approved'})
        self.assertTrue(approval['scope_approved'])

    def test_tampering_and_wrong_identity_never_create_plaintext(self):
        receipt = self.encrypt()
        cipher = self.cipher.read_bytes()
        tampered = cipher[:-1] + bytes([cipher[-1] ^ 1])
        for blob, key in [(tampered, self.identity), (cipher, self.root / 'other.agekey')]:
            if not key.exists():
                subprocess.run([str(self.keygen), '-o', str(key)], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self.subTest(key=key.name), self.assertRaises(transport.TransportError):
                transport.decrypt_and_verify(blob, self.private, self.binary, key,
                    receipt['plaintext_sha256'], hashlib.sha256(blob).hexdigest(), validate_payload=lambda _: True)
            self.assertFalse(self.private.exists())

    def test_mismatched_hashes_fail_before_age_or_write(self):
        receipt = self.encrypt()
        for plain, cipher in [('0'*64, receipt['ciphertext_sha256']),
                              (receipt['plaintext_sha256'], '0'*64)]:
            with self.subTest(plain=plain), self.assertRaises(transport.TransportError):
                transport.decrypt_and_verify(self.cipher.read_bytes(), self.private, self.binary,
                    self.identity, plain, cipher, validate_payload=lambda _: True)
            self.assertFalse(self.private.exists())

    def test_validation_and_durable_write_failure_cannot_approve(self):
        receipt = self.encrypt()
        for validator in [None, lambda _: False, lambda _: 1]:
            with self.subTest(validator=validator), self.assertRaises(transport.TransportError):
                self.verify(receipt, validate_payload=validator)
            self.assertFalse(self.private.exists())
        with patch.object(transport.os, 'fsync', side_effect=OSError('PRIVATE_FAILURE')):
            with self.assertRaises(transport.TransportError) as caught:
                self.verify(receipt, validate_payload=lambda _: True)
        self.assertNotIn('PRIVATE_FAILURE', str(caught.exception))

    def test_identity_must_be_private_regular_file(self):
        receipt = self.encrypt()
        self.identity.chmod(0o644)
        with self.assertRaises(transport.TransportError):
            self.verify(receipt, validate_payload=lambda _: True)
        self.identity.chmod(0o600)
        link = self.root / 'link.agekey'
        link.symlink_to(self.identity)
        with self.assertRaises(transport.TransportError):
            transport.decrypt_and_verify(self.cipher.read_bytes(), self.private, self.binary, link,
                receipt['plaintext_sha256'], receipt['ciphertext_sha256'], validate_payload=lambda _: True)

    def test_invalid_and_oversized_payloads_never_invoke_crypto(self):
        for payload in [b'', b'not-json', b'[]', b'{"scope":true,"scope":false}',
                        b'{"cost":NaN}',b'{"cost":Infinity}',b'{"cost":-Infinity}',
                        b'{"nested":{"cost":1e999}}',b'{"nested":{"cost":-1e999}}',
                        b'{}'*(transport.MAX_PLAINTEXT_BYTES//2+1)]:
            with self.subTest(size=len(payload)), patch.object(transport.subprocess, 'run') as invoked:
                with self.assertRaises(transport.TransportError):
                    transport.encrypt_capture(payload, self.cipher, self.binary, self.recipient)
                invoked.assert_not_called()
        self.assertFalse(self.cipher.exists())

    def test_crypto_process_has_no_inherited_provider_secret(self):
        with patch.dict(os.environ, {'APIFY_TOKEN': 'SYNTHETIC_PROVIDER_SECRET'}):
            real_run = subprocess.run
            calls = []
            def checked(*args, **kwargs):
                calls.append(kwargs)
                self.assertNotIn('APIFY_TOKEN', kwargs['env'])
                return real_run(*args, **kwargs)
            with patch.object(transport.subprocess, 'run', side_effect=checked):
                receipt = self.encrypt()
                self.verify(receipt, validate_payload=lambda _: True)
        self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
