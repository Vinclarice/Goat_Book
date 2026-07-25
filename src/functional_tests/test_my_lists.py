from selenium.webdriver.common.by import By

from .base import FunctionalTest


class MyListsTest(FunctionalTest):
    def find_list_link(self, title):
        links = self.browser.find_elements(By.CSS_SELECTOR, "a.list-row")
        for link in links:
            if title in link.text:
                return link
        raise AssertionError(f'No list link contains "{title}"')

    def test_logged_in_users_lists_are_saved_as_my_lists(self):
        # Edith is a logged-in user
        self.sign_up()

        # She goes to the home page and starts a list
        self.browser.get(self.live_server_url)
        self.add_list_item("Reticulate splines")
        self.add_list_item("Immanentize eschaton")
        first_list_url = self.browser.current_url

        # She notices a "My lists" link, for the first time.
        self.browser.find_element(By.LINK_TEXT, "My lists").click()

        # She sees her username in the page heading
        self.wait_for(
            lambda: self.assertIn(
                "Welcome, edith",
                self.browser.find_element(By.CSS_SELECTOR, "h1").text,
            )
        )

        # And she sees that her list is in there,
        # named according to its first list item
        self.wait_for(
            lambda: self.find_list_link("Reticulate splines")
        )
        self.find_list_link("Reticulate splines").click()
        self.wait_for(
            lambda: self.assertEqual(self.browser.current_url, first_list_url)
        )

        # She decides to start another list, just to see
        self.browser.get(self.live_server_url)
        self.add_list_item("Click cows")
        second_list_url = self.browser.current_url

        # Under "my lists", her new list appears
        self.browser.find_element(By.LINK_TEXT, "My lists").click()
        self.wait_for(lambda: self.find_list_link("Click cows"))
        self.find_list_link("Click cows").click()
        self.wait_for(
            lambda: self.assertEqual(self.browser.current_url, second_list_url)
        )

        # She logs out.  The "My lists" option disappears
        self.browser.find_element(By.CSS_SELECTOR, "#id_logout").click()
        self.wait_for(
            lambda: self.assertEqual(
                self.browser.find_elements(By.LINK_TEXT, "My lists"),
                [],
            )
        )
