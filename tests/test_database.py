import unittest
from sqlalchemy.exc import IntegrityError
from database import Store, ConflictError

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store = Store("sqlite:///:memory:")
        self.store.initialize("admin", "strong-password-123")
        self.data = dict(number="q-001", customer="Example Customer", phone="9000000000", address="Delhi", capacity=3, amount=150000, status="Draft", notes="Initial")

    def tearDown(self):
        self.store.engine.dispose()

    def test_accounts(self):
        self.assertEqual(self.store.login("ADMIN", "strong-password-123")["role"], "admin")
        self.assertIsNone(self.store.login("admin", "wrong"))
        self.store.add_user("Mem", "member-password-123")
        self.assertEqual(self.store.login("mem", "member-password-123")["role"], "member")

    def test_password_length(self):
        with self.assertRaises(ValueError):
            self.store.add_user("test", "1234567")
        self.store.add_user("test", "12345678")
        self.assertIsNotNone(self.store.login("test", "12345678"))

    def test_username_length(self):
        for username in ("a", "abcdef", "   "):
            with self.assertRaises(ValueError):
                self.store.add_user(username, "member-password-123")
        for username in ("ab", "abcde"):
            self.store.add_user(username, "member-password-123")
            self.assertIsNotNone(self.store.login(username, "member-password-123"))

    def test_conflict_preserves_winner_and_history(self):
        quote_id = self.store.save(self.data, "admin")
        snapshot = self.store.get_quote(quote_id)
        self.store.save(dict(self.data, status="Approved"), "member1", quote_id, snapshot["version"])
        with self.assertRaises(ConflictError):
            self.store.save(dict(self.data, amount=200000), "member2", quote_id, snapshot["version"])
        latest = self.store.get_quote(quote_id)
        self.assertEqual(latest["status"], "Approved")
        self.assertEqual(latest["amount"], 150000)
        self.assertEqual(latest["updated_by"], "member1")
        self.assertEqual(len(self.store.get_history(quote_id)), 2)
        self.store.save(dict(self.data, amount=200000, status="Approved"), "member2", quote_id, latest["version"])
        self.assertEqual(self.store.get_quote(quote_id)["version"], 3)

    def test_duplicate_and_validation(self):
        self.store.save(self.data, "admin")
        with self.assertRaises(IntegrityError):
            self.store.save(dict(self.data, number=" Q-001 "), "admin")
        with self.assertRaises(ValueError):
            self.store.save(dict(self.data, number="Q-002", capacity=0), "admin")
        self.assertEqual(len(self.store.list_quotes()), 1)

    def test_invalid_numbers_and_unchanged_history(self):
        for value in (float("nan"), float("inf"), "invalid", 100000000):
            with self.assertRaises(ValueError):
                self.store.save(dict(self.data, capacity=value), "admin")
        quote_id = self.store.save(self.data, "admin")
        self.store.save(self.data, "admin", quote_id, 1)
        self.assertEqual(self.store.get_history(quote_id)[0]["details"], "Saved without field changes")

if __name__ == "__main__":
    unittest.main()
