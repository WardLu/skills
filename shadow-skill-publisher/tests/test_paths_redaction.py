import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from shadow_skill_publisher.paths import attempt_root, resolve_publisher_home, source_id
from shadow_skill_publisher.redaction import redact_text


class PathTests(unittest.TestCase):
    def test_explicit_home_precedes_environment(self):
        actual = resolve_publisher_home(Path("/tmp/explicit"), {"SHADOW_SKILL_PUBLISHER_HOME": "/tmp/env"})
        self.assertEqual(actual, Path("/tmp/explicit").resolve())

    def test_environment_precedes_default_without_reading_home(self):
        actual = resolve_publisher_home(None, {"SHADOW_SKILL_PUBLISHER_HOME": "/tmp/publisher"})
        self.assertEqual(actual, Path("/tmp/publisher").resolve())

    def test_attempt_root_is_nested_and_does_not_create(self):
        home = Path("/tmp/publisher-test-does-not-exist")
        actual = attempt_root(home, "run-01")
        self.assertEqual(actual, home.resolve() / "runs" / "run-01")
        self.assertFalse(actual.exists())
        with self.assertRaises(ValueError):
            attempt_root(home, "../escape")

    def test_source_id_is_stable_and_does_not_include_path(self):
        value = source_id(Path("/tmp/private-source"))
        self.assertEqual(value, source_id(Path("/tmp/./private-source")))
        self.assertNotIn("private-source", value)
        self.assertEqual(len(value), 16)


class RedactionTests(unittest.TestCase):
    def test_redaction_removes_credentials_and_private_home(self):
        token = "gh" + "p_" + "12345678901234567890"
        private_home = "/" + "Users" + "/example-user"
        raw = f"token={token} path={private_home}/private/file.md"
        clean = redact_text(raw)
        self.assertNotIn("gh" + "p_", clean)
        self.assertNotIn(private_home, clean)

    def test_redacts_supported_secret_shapes(self):
        private_key = "-----BEGIN " + "PRIVATE KEY-----\\nsecret\\n-----END " + "PRIVATE KEY-----"
        database_url = "postgres://" + "example-user:example-pass@db.example/app"
        windows_home = "C:\\" + "Users\\Example\\secret.txt"
        unix_home = "/" + "home" + "/example/a.txt"
        raw = (
            "Authorization: Bearer abc123\n"
            f"db={database_url}\n"
            "Cookie: sid=secret-value; theme=dark\n"
            "qr_payload=otpauth://totp/private\n"
            f"key={private_key}\n"
            f"win={windows_home} home={unix_home}"
        )
        clean = redact_text(raw)
        for secret in ("abc123", "example-pass", "secret-value", "otpauth", "BEGIN " + "PRIVATE KEY", windows_home, unix_home):
            self.assertNotIn(secret, clean)

    def test_redacts_caller_supplied_values_deterministically(self):
        self.assertEqual(redact_text("a=one b=one", ["one"]), "a=[REDACTED_PRIVATE] b=[REDACTED_PRIVATE]")


if __name__ == "__main__":
    unittest.main()
