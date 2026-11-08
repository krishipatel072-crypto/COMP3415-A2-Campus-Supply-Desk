"""Pricing rules: normal cases and boundaries (FUNCTIONAL_SPEC.md, "Prices")."""

import unittest

from tests.support import ServiceTestCase, item


class PricingNormalTests(ServiceTestCase):
    def test_quote_lists_every_line_with_name_price_and_line_total(self):
        quote = self.service.quote("regular", [item("notebook", 2), item("mug", 1)])
        self.assertEqual(quote["customer_type"], "regular")
        self.assertEqual(quote["fulfillment"], "pickup")
        self.assertEqual(quote["items"], [
            {"product_id": "notebook", "name": "Notebook", "unit_price_cents": 500,
             "quantity": 2, "line_total_cents": 1000},
            {"product_id": "mug", "name": "Campus mug", "unit_price_cents": 1500,
             "quantity": 1, "line_total_cents": 1500},
        ])
        self.assertEqual(quote["subtotal_cents"], 2500)
        self.assertEqual(quote["total_cents"], 2500)

    def test_spec_example_regular_delivery_three_hoodies_ships_free(self):
        quote = self.service.quote("regular", [item("hoodie", 3)], "delivery")
        self.assertEqual(quote["subtotal_cents"], 12000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 12000)

    def test_student_above_threshold_gets_ten_percent_off(self):
        quote = self.service.quote("student", [item("hoodie", 1), item("mug", 1)])
        self.assertEqual(quote["subtotal_cents"], 5500)
        self.assertEqual(quote["discount_cents"], 550)
        self.assertEqual(quote["total_cents"], 4950)

    def test_regular_customer_never_gets_a_discount(self):
        quote = self.service.quote("regular", [item("hoodie", 2)])
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["total_cents"], 8000)

    def test_pickup_is_free(self):
        quote = self.service.quote("regular", [item("pen-pack", 1)], "pickup")
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 750)


class PricingBoundaryTests(ServiceTestCase):
    def test_student_discount_applies_at_exactly_fifty_dollars(self):
        # Spec: discount when the subtotal is "at least 5,000 cents".
        quote = self.service.quote("student", [item("bag", 2)])
        self.assertEqual(quote["subtotal_cents"], 5000)
        self.assertEqual(quote["discount_cents"], 500)
        self.assertEqual(quote["total_cents"], 4500)

    def test_student_just_below_fifty_dollars_gets_no_discount(self):
        quote = self.service.quote("student", [item("hoodie", 1), item("pen-pack", 1)])
        self.assertEqual(quote["subtotal_cents"], 4750)
        self.assertEqual(quote["discount_cents"], 0)

    def test_standard_delivery_is_free_at_exactly_one_hundred_dollars(self):
        quote = self.service.quote("regular", [item("hoodie", 2), item("notebook", 4)], "delivery")
        self.assertEqual(quote["subtotal_cents"], 10000)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 10000)

    def test_standard_delivery_is_charged_just_below_one_hundred_dollars(self):
        quote = self.service.quote("regular", [item("hoodie", 2), item("mug", 1)], "delivery")
        self.assertEqual(quote["subtotal_cents"], 9500)
        self.assertEqual(quote["delivery_cents"], 600)
        self.assertEqual(quote["total_cents"], 10100)

    def test_free_delivery_threshold_uses_amount_after_discount(self):
        # Subtotal 10,500 is over $100, but 10,500 - 1,050 = 9,450 is not.
        quote = self.service.quote("student", [item("hoodie", 2), item("bag", 1)], "delivery")
        self.assertEqual(quote["discount_cents"], 1050)
        self.assertEqual(quote["delivery_cents"], 600)
        self.assertEqual(quote["total_cents"], 10050)

    def test_discount_rounds_half_a_cent_upward(self):
        # The bundled prices always give whole-cent discounts, so a custom
        # catalog is needed to reach the rounding rule at all.
        cases = [(5004, 500), (5005, 501), (5006, 501), (5025, 503)]
        for price, expected_discount in cases:
            with self.subTest(price=price):
                self.write_state([{"product_id": "kit", "name": "Kit",
                                   "unit_price_cents": price, "stock": 5}])
                quote = self.service.quote("student", [item("kit", 1)])
                self.assertEqual(quote["discount_cents"], expected_discount)
                self.assertEqual(quote["total_cents"], price - expected_discount)

    def test_quantity_limits_one_and_ninety_nine_are_accepted(self):
        self.write_state([{"product_id": "notebook", "name": "Notebook",
                           "unit_price_cents": 500, "stock": 150}])
        self.assertEqual(self.service.quote("regular", [item("notebook", 1)])["total_cents"], 500)
        self.assertEqual(self.service.quote("regular", [item("notebook", 99)])["total_cents"], 49500)

    def test_quantity_zero_and_one_hundred_are_rejected(self):
        self.write_state([{"product_id": "notebook", "name": "Notebook",
                           "unit_price_cents": 500, "stock": 150}])
        for quantity in (0, -1, 100):
            with self.subTest(quantity=quantity):
                with self.assertRaisesRegex(ValueError, "Quantity must be an integer from 1 to 99"):
                    self.service.quote("regular", [item("notebook", quantity)])

    def test_ordering_all_remaining_stock_is_allowed(self):
        order = self.service.place_order("regular", [item("hoodie", 5)])
        self.assertEqual(order["subtotal_cents"], 20000)
        self.assertEqual(self.stock_of("hoodie"), 0)

    def test_one_more_than_available_stock_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Not enough stock for hoodie"):
            self.service.quote("regular", [item("hoodie", 6)])

    def test_empty_item_list_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one item"):
            self.service.quote("regular", [])
        with self.assertRaisesRegex(ValueError, "at least one item"):
            self.service.place_order("regular", [])
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
