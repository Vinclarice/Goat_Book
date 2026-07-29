from selenium.webdriver.common.by import By

from .base import FunctionalTest


class LayoutAndStylingTest(FunctionalTest):
    def assert_page_has_no_horizontal_overflow(self):
        dimensions = self.browser.execute_script(
            """
            return {
              viewport: window.innerWidth,
              document: document.documentElement.scrollWidth
            };
            """
        )
        self.assertLessEqual(dimensions["document"], dimensions["viewport"])

    def test_agenda_and_list_are_responsive(self):
        self.sign_up()
        self.browser.set_window_size(1024, 768)

        # The agenda's quick-add box is the widest control on the page.
        inputbox = self.get_item_input_box()
        self.assertGreater(inputbox.size["width"], 250)
        self.assert_page_has_no_horizontal_overflow()

        self.start_new_list("Testing the responsive list")
        self.assertGreater(self.get_item_input_box().size["width"], 250)
        self.assert_page_has_no_horizontal_overflow()

        self.browser.set_window_size(390, 844)
        self.assert_page_has_no_horizontal_overflow()

    def test_agenda_with_tasks_has_no_horizontal_overflow_on_mobile(self):
        self.sign_up()
        self.start_new_list("A task with a reasonably long description")
        self.browser.find_element(By.LINK_TEXT, "Today").click()

        for width, height in ((1024, 768), (390, 844)):
            self.browser.set_window_size(width, height)
            self.assert_page_has_no_horizontal_overflow()
