from selenium.webdriver.common.by import By

from .base import FunctionalTest


TEST_USERNAME = "edith"
TEST_EMAIL = "edith@example.com"
TEST_PASSWORD = "correct horse battery staple 47!"


class LoginTest(FunctionalTest):
    def test_signup_shows_a_pending_approval_message_instead_of_logging_in(self):
        self.browser.get(self.live_server_url)
        self.browser.find_element(By.LINK_TEXT, "Create account").click()

        self.browser.find_element(By.NAME, "username").send_keys(TEST_USERNAME)
        self.browser.find_element(By.NAME, "email").send_keys(TEST_EMAIL)
        self.browser.find_element(By.NAME, "password1").send_keys(TEST_PASSWORD)
        self.browser.find_element(By.NAME, "password2").send_keys(TEST_PASSWORD)
        self.browser.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

        # She's not logged in -- her account is waiting on admin approval.
        self.wait_for(
            lambda: self.assertIn(
                "pending approval",
                self.browser.find_element(By.TAG_NAME, "body").text,
            )
        )
        self.assertEqual(
            self.browser.find_elements(By.CSS_SELECTOR, "#id_logout"),
            [],
        )

        # An admin approves her account (simulated here; in reality this
        # happens in /admin/).
        self._approve_pending_account(TEST_USERNAME)

        self.browser.find_element(By.LINK_TEXT, "Log in").click()
        self.browser.find_element(By.NAME, "username").send_keys(TEST_USERNAME)
        self.browser.find_element(By.NAME, "password").send_keys(TEST_PASSWORD)
        self.browser.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

        self.wait_to_be_logged_in(TEST_USERNAME)

        self.browser.find_element(By.ID, "id_logout").click()
        self.wait_to_be_logged_out(TEST_USERNAME)

        self.browser.find_element(By.LINK_TEXT, "Log in").click()
        self.browser.find_element(By.NAME, "username").send_keys(TEST_USERNAME)
        self.browser.find_element(By.NAME, "password").send_keys(TEST_PASSWORD)
        self.browser.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

        self.wait_to_be_logged_in(TEST_USERNAME)
