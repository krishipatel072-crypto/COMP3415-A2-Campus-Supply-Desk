"""Interactive menu behavior (FUNCTIONAL_SPEC.md, "Interactive interface")."""

import unittest

from supplydesk.menu import money
from tests.support import ServiceTestCase, item, run_menu_session


class MenuTests(ServiceTestCase):
    def run_menu(self, *answers):
        return run_menu_session(self.service, answers)

    def test_quote_shows_dollars_and_creates_no_order(self):
        code, out, _ = self.run_menu("2", "regular", "notebook", "2", "", "", "0")
        self.assertEqual(code, 0)
        self.assertIn("Notebook x 2: $10.00", out)
        self.assertIn("Total: $10.00", out)
        self.assertIn("Quote only: no stock reserved and no order created.", out)
        self.assertFalse(self.path.exists())

    def test_blank_answers_default_to_regular_and_pickup(self):
        _, out, prompts = self.run_menu("2", "", "notebook", "1", "", "", "0")
        self.assertIn("Customer: regular | Fulfillment: pickup", out)
        self.assertIn("Customer type [regular/student] (Enter = regular): ", prompts)
        self.assertIn("Fulfillment [pickup/delivery/express] (Enter = pickup): ", prompts)  # CR-01

    def test_non_numeric_quantity_asks_to_reenter_the_item(self):
        _, out, _ = self.run_menu("2", "", "notebook", "two", "notebook", "2", "", "", "0")
        self.assertIn("Please enter a whole number. Re-enter this item.", out)
        self.assertIn("Total: $10.00", out)

    def test_declining_placement_leaves_saved_data_unchanged(self):
        _, out, _ = self.run_menu("3", "", "mug", "1", "", "", "n", "0")
        self.assertIn("Order not placed.", out)
        self.assertFalse(self.path.exists())

    def test_confirming_placement_saves_the_order(self):
        _, out, _ = self.run_menu("3", "student", "hoodie", "2", "", "delivery", "y", "0")
        self.assertIn("ORD-0001 - placed", out)
        self.assertIn("Total: $78.00", out)
        self.assertEqual(self.stock_of("hoodie"), 3)

    def test_cancellation_requires_confirmation(self):
        self.service.place_order("regular", [item("mug", 1)])
        _, out, _ = self.run_menu("6", "ORD-0001", "n", "0")
        self.assertIn("Cancellation abandoned.", out)
        self.assertEqual(self.service.get_order("ORD-0001")["status"], "placed")

        _, out, _ = self.run_menu("6", "ORD-0001", "y", "0")
        self.assertIn("ORD-0001 - cancelled", out)
        self.assertEqual(self.stock_of("mug"), 8)

    def test_history_and_lookup(self):
        _, out, _ = self.run_menu("4", "0")
        self.assertIn("No orders yet.", out)
        self.service.place_order("regular", [item("bag", 1)])
        _, out, _ = self.run_menu("4", "5", "ORD-0001", "0")
        self.assertEqual(out.count("ORD-0001 - placed"), 2)

    def test_invalid_request_is_reported_and_menu_stays_available(self):
        _, out, _ = self.run_menu("2", "", "laptop", "1", "", "", "1", "0")
        self.assertIn("Error: Unknown product.", out)
        self.assertIn("Returning to the menu.", out)
        self.assertIn("Canvas bag", out.split("Returning to the menu.")[1])
        self.assertTrue(out.rstrip().endswith("Goodbye."))

    def test_unknown_option_is_explained(self):
        _, out, _ = self.run_menu("9", "0")
        self.assertIn("Choose a number from 0 to 6.", out)

    def test_end_of_input_and_ctrl_c_exit_cleanly(self):
        code, out, _ = self.run_menu()
        self.assertEqual(code, 0)
        self.assertIn("Goodbye.", out)
        code, out, _ = self.run_menu("2", "", KeyboardInterrupt())
        self.assertEqual(code, 0)
        self.assertIn("Goodbye.", out)

    def test_money_formats_cents_as_dollars(self):
        self.assertEqual(money(0), "$0.00")
        self.assertEqual(money(5), "$0.05")
        self.assertEqual(money(1000), "$10.00")
        self.assertEqual(money(123456), "$1234.56")


if __name__ == "__main__":
    unittest.main()
