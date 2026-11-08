"""CR-01 Express Delivery acceptance tests (docs/CR-01.md)."""

import contextlib
import io
import json
import unittest

from supplydesk.cli import build_parser
from supplydesk.service import OrderService
from tests.support import ServiceTestCase, item, run_cli, run_menu_session


class ExpressPricingTests(ServiceTestCase):
    def test_cr01_example_regular_two_notebooks(self):
        quote = self.service.quote("regular", [item("notebook", 2)], "express")
        self.assertEqual(quote["fulfillment"], "express")
        self.assertEqual(quote["subtotal_cents"], 1000)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 2200)

    def test_cr01_example_student_two_hoodies(self):
        quote = self.service.quote("student", [item("hoodie", 2)], "express")
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 8400)

    def test_cr01_example_three_hoodies_standard_vs_express(self):
        standard = self.service.quote("regular", [item("hoodie", 3)], "delivery")
        express = self.service.quote("regular", [item("hoodie", 3)], "express")
        self.assertEqual(standard["total_cents"], 12000)
        self.assertEqual(express["total_cents"], 13200)

    def test_express_fee_is_never_waived(self):
        # At and above the 10,000-cent free-standard-delivery threshold.
        at_threshold = self.service.quote("regular", [item("hoodie", 2), item("notebook", 4)], "express")
        self.assertEqual(at_threshold["subtotal_cents"], 10000)
        self.assertEqual(at_threshold["delivery_cents"], 1200)
        large = self.service.quote("student", [item("hoodie", 5), item("bag", 4)], "express")
        self.assertEqual(large["delivery_cents"], 1200)

    def test_student_discount_is_unchanged_and_excludes_the_fee(self):
        at_boundary = self.service.quote("student", [item("bag", 2)], "express")
        self.assertEqual(at_boundary["discount_cents"], 500)
        self.assertEqual(at_boundary["total_cents"], 5000 - 500 + 1200)
        below = self.service.quote("student", [item("hoodie", 1), item("pen-pack", 1)], "express")
        # 4,750 + 1,200 would pass 5,000, but the fee does not count.
        self.assertEqual(below["discount_cents"], 0)
        self.assertEqual(below["total_cents"], 4750 + 1200)

    def test_rounding_rule_unchanged_with_express(self):
        self.write_state([{"product_id": "kit", "name": "Kit", "unit_price_cents": 5005, "stock": 3}])
        quote = self.service.quote("student", [item("kit", 1)], "express")
        self.assertEqual(quote["discount_cents"], 501)
        self.assertEqual(quote["total_cents"], 5005 - 501 + 1200)

    def test_pickup_and_standard_delivery_are_unchanged(self):
        self.assertEqual(self.service.quote("regular", [item("notebook", 2)])["total_cents"], 1000)
        self.assertEqual(
            self.service.quote("student", [item("hoodie", 2)], "delivery")["total_cents"], 7800)
        self.assertEqual(
            self.service.quote("regular", [item("hoodie", 3)], "delivery")["delivery_cents"], 0)

    def test_other_fulfillment_values_remain_invalid(self):
        for fulfillment in ("Express", "EXPRESS", " express", "courier", "", None):
            with self.subTest(fulfillment=fulfillment):
                with self.assertRaisesRegex(ValueError, "Fulfillment"):
                    self.service.quote("regular", [item("mug", 1)], fulfillment)
                with self.assertRaisesRegex(ValueError, "Fulfillment"):
                    self.service.place_order("regular", [item("mug", 1)], fulfillment)
        self.assertFalse(self.path.exists())


class ExpressOrderTests(ServiceTestCase):
    request = ("student", [item("hoodie", 2), item("mug", 1)], "express")

    def test_quote_and_placed_express_order_agree(self):
        quote = self.service.quote(*self.request)
        order = self.service.place_order(*self.request)
        self.assertEqual({k: v for k, v in order.items() if k not in ("order_id", "status")}, quote)
        self.assertEqual(order["delivery_cents"], 1200)

    def test_express_order_survives_retrieval_reopening_and_cancellation(self):
        placed = self.service.place_order(*self.request)
        kept = {k: placed[k] for k in ("fulfillment", "items", "subtotal_cents",
                                       "discount_cents", "delivery_cents", "total_cents")}
        self.assertEqual(self.service.get_order(placed["order_id"]), placed)
        reopened = OrderService(self.path)
        self.assertEqual(reopened.get_order(placed["order_id"]), placed)
        cancelled = reopened.cancel_order(placed["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual({k: cancelled[k] for k in kept}, kept)
        self.assertEqual(OrderService(self.path).get_order(placed["order_id"]), cancelled)

    def test_stock_numbering_and_cancellation_rules_unchanged(self):
        first = self.service.place_order("regular", [item("hoodie", 2)], "express")
        self.assertEqual(self.stock_of("hoodie"), 3)
        with self.assertRaisesRegex(ValueError, "Not enough stock for hoodie"):
            self.service.place_order("regular", [item("hoodie", 2), item("hoodie", 2)], "express")
        self.service.cancel_order(first["order_id"])
        self.service.cancel_order(first["order_id"])
        self.assertEqual(self.stock_of("hoodie"), 5)
        second = self.service.place_order("regular", [item("mug", 1)], "express")
        self.assertEqual(second["order_id"], "ORD-0002")


class ExpressInterfaceTests(ServiceTestCase):
    def test_cr01_example_command(self):
        code, out, _ = run_cli(self.path, "quote", "--customer", "student",
                               "--fulfillment", "express", "--item", "hoodie:2")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["total_cents"], 8400)

    def test_place_command_accepts_express_and_defaults_are_unchanged(self):
        code, out, _ = run_cli(self.path, "place", "--fulfillment", "express", "--item", "mug:1")
        self.assertEqual((code, json.loads(out)["total_cents"]), (0, 2700))
        _, out, _ = run_cli(self.path, "quote", "--item", "mug:1")
        result = json.loads(out)
        self.assertEqual((result["customer_type"], result["fulfillment"]), ("regular", "pickup"))

    def test_command_help_makes_express_discoverable(self):
        for command in ("quote", "place"):
            with self.subTest(command=command):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer), self.assertRaises(SystemExit):
                    build_parser().parse_args([command, "--help"])
                help_text = buffer.getvalue()
                self.assertIn("{pickup,delivery,express}", help_text)
                self.assertIn("$12.00", help_text)

    def test_menu_accepts_express_and_lists_it_in_the_prompt(self):
        code, out, prompts = run_menu_session(
            self.service, ["3", "student", "hoodie", "2", "", "express", "y", "0"])
        self.assertIn("Fulfillment [pickup/delivery/express] (Enter = pickup): ", prompts)
        self.assertIn("Customer: student | Fulfillment: express", out)
        self.assertIn("Delivery: $12.00", out)
        self.assertIn("Total: $84.00", out)
        self.assertEqual(self.service.get_order("ORD-0001")["fulfillment"], "express")

    def test_menu_blank_fulfillment_still_means_pickup(self):
        _, out, _ = run_menu_session(self.service, ["2", "", "notebook", "2", "", "", "0"])
        self.assertIn("Fulfillment: pickup", out)
        self.assertIn("Total: $10.00", out)


if __name__ == "__main__":
    unittest.main()
