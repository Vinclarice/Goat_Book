from selenium.webdriver.common.by import By

from .base import FunctionalTest


TEST_USERNAME = "edith"
TEST_EMAIL = "edith@example.com"
TEST_PASSWORD = "correct horse battery staple 47!"


class LoginTest(FunctionalTest):
    def test_signup_login_and_logout_with_a_password(self):
        self.browser.get(self.live_server_url)
        self.browser.find_element(By.LINK_TEXT, "Create account").click()

        self.browser.find_element(By.NAME, "username").send_keys(TEST_USERNAME)
        self.browser.find_element(By.NAME, "email").send_keys(TEST_EMAIL)
        self.browser.find_element(By.NAME, "password1").send_keys(TEST_PASSWORD)
        self.browser.find_element(By.NAME, "password2").send_keys(TEST_PASSWORD)
        self.browser.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

        self.wait_to_be_logged_in(TEST_USERNAME)

        self.browser.find_element(By.ID, "id_logout").click()
        self.wait_to_be_logged_out(TEST_USERNAME)

        self.browser.find_element(By.LINK_TEXT, "Log in").click()
        self.browser.find_element(By.NAME, "username").send_keys(TEST_USERNAME)
        self.browser.find_element(By.NAME, "password").send_keys(TEST_PASSWORD)
        self.browser.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

        self.wait_to_be_logged_in(TEST_USERNAME)
