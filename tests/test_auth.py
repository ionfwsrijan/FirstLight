import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firstlight.auth import allowed, issue, roles, verify


def _token(secret: str):
    return issue("somebody", "parent", secret, 3600, now=time.time())


class TestRoles(unittest.TestCase):
    def test_role_sets(self):
        self.assertTrue(allowed("parent", "school:read"))
        self.assertFalse(allowed("parent", "run:morning"))
        self.assertTrue(allowed("officer", "run:morning"))
        self.assertTrue(allowed("officer", "ledger:read"))
        self.assertTrue(allowed("principal", "alert:send"))
        self.assertFalse(allowed("parent", "alert:send"))
        self.assertFalse(allowed("nobody", "anything"))

    def test_roles_exposed(self):
        self.assertEqual(set(roles()), {"parent", "principal", "officer"})


class TestTokens(unittest.TestCase):
    def test_roundtrip(self):
        t = _token("secret")
        claims = verify(t, "secret")
        self.assertIsNotNone(claims)
        self.assertEqual(claims["sub"], "somebody")
        self.assertEqual(claims["role"], "parent")

    def test_wrong_secret(self):
        t = _token("secret")
        self.assertIsNone(verify(t, "other"))

    def test_expired(self):
        body = {"sub": "x", "role": "parent", "iat": 0, "exp": 10}
        import json

        from firstlight.auth.tokens import _b64

        payload = _b64(json.dumps(body, sort_keys=True).encode())
        from firstlight.auth.tokens import _sign

        t = f"{payload}.{_sign(payload, 'secret')}"
        self.assertIsNone(verify(t, "secret", now=9999))

    def test_tampered(self):
        t = _token("secret")
        mangled = t[:-3] + ("abc" if t[-3:] != "abc" else "xyz")
        self.assertIsNone(verify(mangled, "secret"))

    def test_garbage(self):
        self.assertIsNone(verify("", "secret"))
        self.assertIsNone(verify("not-a-token", "secret"))


if __name__ == "__main__":
    unittest.main()
