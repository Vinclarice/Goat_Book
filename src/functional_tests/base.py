from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.keys import Keys
import time
import os

from .container_commands import reset_database

MAX_WAIT = 5


def wait(fn):
    def modified_fn(*args, **kwargs):
        start_time = time.time()
        while True:
            try:
                return fn(*args, **kwargs)
            except (AssertionError, WebDriverException) as e:
                if time.time() - start_time > MAX_WAIT:
                    raise e
                time.sleep(0.5)

    return modified_fn


class FunctionalTest(StaticLiveServerTestCase):
    def setUp(self):
        self.browser = webdriver.Firefox()
        self.test_server = os.environ.get("TEST_SERVER")
        if self.test_server:
            self.live_server_url = "http://" + self.test_server
            reset_database(self.test_server)

    def tearDown(self):
        self.browser.quit()

    @wait
    def wait_for_row_in_list_table(self, row_text):
        expected_text = row_text.split(": ", 1)[-1]
        rows = self.browser.find_elements(By.CSS_SELECTOR, "#id_list_table .list-item")
        self.assertTrue(any(expected_text in row.text for row in rows))

    @wait
    def wait_for(self, fn):
        return fn()

    def get_item_input_box(self):
        inputs = self.browser.find_elements(
            By.CSS_SELECTOR,
            "#react-new-task, #id_text",
        )
        return next(input_ for input_ in inputs if input_.is_displayed())

    def add_list_item(self, item_text):
        self.get_item_input_box().send_keys(item_text)
        self.get_item_input_box().send_keys(Keys.ENTER)
        self.wait_for_row_in_list_table(item_text)

    def sign_up(
        self,
        username="edith",
        email="edith@example.com",
        password="correct horse battery staple 47!",
    ):
        self.browser.get(self.live_server_url + "/accounts/signup/")
        self.browser.find_element(By.NAME, "username").send_keys(username)
        self.browser.find_element(By.NAME, "email").send_keys(email)
        self.browser.find_element(By.NAME, "password1").send_keys(password)
        self.browser.find_element(By.NAME, "password2").send_keys(password)
        self.browser.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
        self.wait_to_be_logged_in(username)

    @wait
    def wait_to_be_logged_in(self, username):
        self.browser.find_element(By.CSS_SELECTOR, "#id_logout")
        navbar = self.browser.find_element(By.CSS_SELECTOR, ".navbar")
        self.assertIn(username, navbar.text)

    @wait
    def wait_to_be_logged_out(self, username):
        self.browser.find_element(By.LINK_TEXT, "Log in")
        navbar = self.browser.find_element(By.CSS_SELECTOR, ".navbar")
        self.assertNotIn(username, navbar.text)
