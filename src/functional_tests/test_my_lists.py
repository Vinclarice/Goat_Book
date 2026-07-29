from selenium.webdriver.common.by import By

from .base import FunctionalTest


class MyListsTest(FunctionalTest):
    def open_list_from_sidebar(self, title):
        """Clicks the "open" arrow next to a list in the agenda sidebar.

        The list name itself filters the agenda rather than navigating,
        so opening the list is a separate control.
        """
        for row in self.browser.find_elements(By.CSS_SELECTOR, ".list-row-nav"):
            if title in row.text:
                row.find_element(By.CSS_SELECTOR, ".list-open").click()
                return
        raise AssertionError(f'No sidebar entry contains "{title}"')

    def sidebar_list_titles(self):
        return [
            row.text
            for row in self.browser.find_elements(By.CSS_SELECTOR, ".list-row-nav")
        ]

    def test_logged_in_users_lists_are_saved_and_reachable_from_the_agenda(self):
        # Edith is a logged-in user
        self.sign_up()

        # She goes to the home page and starts a list
        self.browser.get(self.live_server_url)
        self.start_new_list("Reticulate splines")
        self.add_list_item("Immanentize eschaton")
        first_list_url = self.browser.current_url

        # She notices a "Today" link back to her agenda.
        self.browser.find_element(By.LINK_TEXT, "Today").click()

        # She sees her username in the page heading
        self.wait_for(
            lambda: self.assertIn(
                "Hello, edith",
                self.browser.find_element(By.CSS_SELECTOR, "h1").text,
            )
        )

        # Her list is in the sidebar, named after its first item, and its
        # tasks are on the agenda itself.
        self.wait_for(
            lambda: self.assertTrue(
                any(
                    "Reticulate splines" in title
                    for title in self.sidebar_list_titles()
                )
            )
        )
        self.assertIn(
            "Immanentize eschaton",
            self.browser.find_element(By.TAG_NAME, "body").text,
        )

        # Opening it from the sidebar takes her back to the list itself.
        self.open_list_from_sidebar("Reticulate splines")
        self.wait_for(
            lambda: self.assertEqual(self.browser.current_url, first_list_url)
        )

        # She decides to start another list, just to see
        self.browser.get(self.live_server_url)
        self.start_new_list("Click cows")
        second_list_url = self.browser.current_url

        # It shows up on the agenda alongside the first one
        self.browser.find_element(By.LINK_TEXT, "Today").click()
        self.wait_for(
            lambda: self.assertTrue(
                any("Click cows" in title for title in self.sidebar_list_titles())
            )
        )
        self.open_list_from_sidebar("Click cows")
        self.wait_for(
            lambda: self.assertEqual(self.browser.current_url, second_list_url)
        )

        # She logs out.  The "Today" option disappears
        self.browser.find_element(By.CSS_SELECTOR, "#id_logout").click()
        self.wait_for(
            lambda: self.assertEqual(
                self.browser.find_elements(By.LINK_TEXT, "Today"),
                [],
            )
        )
