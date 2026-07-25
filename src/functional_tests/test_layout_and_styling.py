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

    def test_dashboard_and_list_are_responsive(self):
        self.sign_up()
        self.browser.set_window_size(1024, 768)

        inputbox = self.get_item_input_box()
        self.assertGreater(inputbox.size["width"], 250)
        self.assert_page_has_no_horizontal_overflow()

        self.add_list_item("Testing the responsive list")
        self.assertGreater(self.get_item_input_box().size["width"], 250)
        self.assert_page_has_no_horizontal_overflow()

        self.browser.set_window_size(390, 844)
        self.assert_page_has_no_horizontal_overflow()
