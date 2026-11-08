"""Invalid and exceptional requests (FUNCTIONAL_SPEC.md, "Requests and validation")."""

import unittest

from tests.support import ServiceTestCase, item


class InvalidRequestTests(ServiceTestCase):
    def assert_both_operations_reject(self, message, *args):
        with self.assertRaisesRegex(ValueError, message):
            self.service.quote(*args)
        with self.assertRaisesRegex(ValueError, message):
            self.service.place_order(*args)

    def test_customer_type_must_be_exactly_regular_or_student(self):
        for customer in ("Student", "REGULAR", "", None, "staff"):
            with self.subTest(customer=customer):
                self.assert_both_operations_reject(
                    "Customer type", customer, [item("notebook", 1)])

    def test_fulfillment_must_be_exactly_a_supported_option(self):
        # CR-01 made "express" valid; it was listed here as invalid before.
        for fulfillment in ("Delivery", "", None, "Express", "ship"):
            with self.subTest(fulfillment=fulfillment):
                self.assert_both_operations_reject(
                    "Fulfillment", "regular", [item("notebook", 1)], fulfillment)

    def test_items_must_be_a_nonempty_list(self):
        for items in (None, (), "notebook", item("notebook", 1), (item("notebook", 1),)):
            with self.subTest(items=items):
                self.assert_both_operations_reject("at least one item", "regular", items)

    def test_each_item_must_be_a_dictionary(self):
        self.assert_both_operations_reject("Each item", "regular", ["notebook:1"])

    def test_unknown_or_missing_product_id_is_rejected(self):
        self.assert_both_operations_reject("Unknown product", "regular", [item("laptop", 1)])
        self.assert_both_operations_reject("Unknown product", "regular", [{"quantity": 1}])
        self.assert_both_operations_reject("Unknown product", "regular", [item("Notebook", 1)])

    def test_quantity_must_be_a_real_integer_when_calling_the_service(self):
        for quantity in (True, False, 2.0, 1.5, "2", None):
            with self.subTest(quantity=quantity):
                self.assert_both_operations_reject(
                    "Quantity must be an integer", "regular", [item("notebook", quantity)])
        self.assert_both_operations_reject(
            "Quantity must be an integer", "regular", [{"product_id": "notebook"}])

    def test_one_bad_line_rejects_the_whole_request(self):
        self.assert_both_operations_reject(
            "Unknown product", "regular", [item("notebook", 1), item("laptop", 1)])
        self.assertFalse(self.path.exists())

    def test_quote_rejects_duplicate_lines_over_combined_stock(self):
        # Hoodie stock is 5; two lines of 3 ask for 6 in total.
        with self.assertRaisesRegex(ValueError, "Not enough stock for hoodie"):
            self.service.quote("regular", [item("hoodie", 3), item("hoodie", 3)])

    def test_place_rejects_duplicate_lines_over_combined_stock(self):
        with self.assertRaisesRegex(ValueError, "Not enough stock for hoodie"):
            self.service.place_order("regular", [item("hoodie", 3), item("hoodie", 3)])
        self.assertEqual(self.stock_of("hoodie"), 5)
        self.assertEqual(self.service.list_orders(), [])

    def test_duplicate_lines_within_stock_are_kept_as_separate_lines(self):
        order = self.service.place_order("regular", [item("hoodie", 2), item("hoodie", 3)])
        self.assertEqual([line["quantity"] for line in order["items"]], [2, 3])
        self.assertEqual(order["subtotal_cents"], 20000)
        self.assertEqual(self.stock_of("hoodie"), 0)

    def test_rejected_placement_leaves_saved_data_unchanged(self):
        self.service.place_order("regular", [item("mug", 1)])
        saved_before = self.saved_text()
        bad_requests = [
            ("staff", [item("mug", 1)], "pickup"),
            ("regular", [item("mug", 1)], "drone"),
            ("regular", [item("mug", 0)], "pickup"),
            ("regular", [item("mug", 1), item("laptop", 1)], "pickup"),
            ("regular", [item("bag", 5)], "pickup"),
        ]
        for request in bad_requests:
            with self.subTest(request=request):
                with self.assertRaises(ValueError):
                    self.service.place_order(*request)
                self.assertEqual(self.saved_text(), saved_before)
        next_order = self.service.place_order("regular", [item("mug", 1)])
        self.assertEqual(next_order["order_id"], "ORD-0002")


class UnknownOrderTests(ServiceTestCase):
    def test_get_unknown_order_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown order: ORD-0099"):
            self.service.get_order("ORD-0099")

    def test_cancel_unknown_order_raises_and_changes_nothing(self):
        self.service.place_order("regular", [item("mug", 1)])
        saved_before = self.saved_text()
        with self.assertRaisesRegex(ValueError, "Unknown order: ORD-0099"):
            self.service.cancel_order("ORD-0099")
        self.assertEqual(self.saved_text(), saved_before)


class SaveFileErrorTests(ServiceTestCase):
    def test_malformed_save_file_raises_instead_of_resetting(self):
        self.path.write_text("{ this is not json", encoding="utf-8")
        for operation in (
            lambda: self.service.catalog(),
            lambda: self.service.quote("regular", [item("mug", 1)]),
            lambda: self.service.place_order("regular", [item("mug", 1)]),
            lambda: self.service.list_orders(),
        ):
            with self.assertRaises(ValueError):
                operation()
        self.assertEqual(self.saved_text(), "{ this is not json")


if __name__ == "__main__":
    unittest.main()
