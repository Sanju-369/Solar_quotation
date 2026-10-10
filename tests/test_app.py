import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

class AppTests(unittest.TestCase):
    def test_signup_and_member_login(self):
        with patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:", "ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "test-password-123"}):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15).run()
            app.radio[0].set_value("Sign up").run()
            app.text_input[0].set_value("new")
            self.assertEqual(len(app.text_input), 2)
            app.text_input[1].set_value("short")
            app.button[0].click().run()
            self.assertTrue(app.error)
            app.text_input[1].set_value("pass1234")
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
            app.radio[0].set_value("Sign in").run()
            app.text_input[0].set_value("new")
            app.text_input[1].set_value("pass1234")
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertNotIn("Team members", app.sidebar.radio[0].options)

    def test_create_edit_and_member_flow(self):
        with patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:", "ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "test-password-123"}):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=15).run()
            app.text_input[0].set_value("admin")
            app.text_input[1].set_value("test-password-123")
            app.button[0].click().run()
            self.assertFalse(app.exception)
            app.sidebar.radio[0].set_value("Create quotation").run()
            app.text_input[0].set_value("UI-001")
            app.text_input[1].set_value("Test Customer")
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
            app.sidebar.radio[0].set_value("Live quotations").run()
            self.assertEqual(len(app.dataframe[0].value), 1)
            app.sidebar.radio[0].set_value("Edit quotation").run()
            app.selectbox[1].set_value("Approved")
            app.button[1].click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
            app.sidebar.radio[0].set_value("Team members").run()
            app.text_input[0].set_value("mem")
            app.text_input[1].set_value("member-password-123")
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
