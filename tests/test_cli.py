"""Individual commands: JSON output, defaults and exit statuses."""

import json
import unittest

from tests.support import ServiceTestCase, run_cli


class CommandTests(ServiceTestCase):
    def test_quote_command_prints_json_in_cents_and_saves_nothing(self):
        code, out, err = run_cli(self.path, "quote", "--customer", "regular", "--item", "notebook:2")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(json.loads(out)["total_cents"], 1000)
        self.assertFalse(self.path.exists())

    def test_omitted_options_default_to_regular_and_pickup(self):
        code, out, _ = run_cli(self.path, "quote", "--item", "notebook:1")
        result = json.loads(out)
        self.assertEqual((result["customer_type"], result["fulfillment"]), ("regular", "pickup"))

    def test_repeated_item_options_build_one_request(self):
        code, out, _ = run_cli(self.path, "quote", "--customer", "student",
                               "--item", "hoodie:1", "--item", "mug:1")
        result = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["discount_cents"], 550)

    def test_spec_example_student_delivery_two_hoodies(self):
        _, out, _ = run_cli(self.path, "quote", "--customer", "student",
                            "--fulfillment", "delivery", "--item", "hoodie:2")
        self.assertEqual(json.loads(out)["total_cents"], 7800)

    def test_place_show_orders_and_cancel_round_trip(self):
        code, out, _ = run_cli(self.path, "place", "--item", "mug:1")
        self.assertEqual(code, 0)
        placed = json.loads(out)
        self.assertEqual(placed["order_id"], "ORD-0001")

        code, out, _ = run_cli(self.path, "show", "ORD-0001")
        self.assertEqual((code, json.loads(out)), (0, placed))

        code, out, _ = run_cli(self.path, "orders")
        self.assertEqual((code, json.loads(out)), (0, [placed]))

        code, out, _ = run_cli(self.path, "cancel", "ORD-0001")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "cancelled")

    def test_catalog_command_shows_current_stock(self):
        run_cli(self.path, "place", "--item", "bag:3")
        code, out, _ = run_cli(self.path, "catalog")
        stock = {p["product_id"]: p["stock"] for p in json.loads(out)}
        self.assertEqual(code, 0)
        self.assertEqual(stock["bag"], 1)

    def test_rejected_request_exits_with_status_2_and_an_error(self):
        code, out, err = run_cli(self.path, "place", "--item", "laptop:1")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(err.strip(), "Error: Unknown product.")
        self.assertFalse(self.path.exists())

    def test_unknown_order_exits_with_status_2(self):
        code, _, err = run_cli(self.path, "show", "ORD-0042")
        self.assertEqual(code, 2)
        self.assertIn("Unknown order: ORD-0042", err)

    def test_badly_formed_options_are_rejected_by_the_parser(self):
        bad_arguments = [
            ("quote", "--item", "notebook"),
            ("quote", "--item", "notebook:two"),
            ("quote", "--item", ":2"),
            ("quote", "--customer", "staff", "--item", "notebook:1"),
            ("quote", "--fulfillment", "courier", "--item", "notebook:1"),
            ("quote",),
        ]
        for arguments in bad_arguments:
            with self.subTest(arguments=arguments):
                with self.assertRaises(SystemExit) as raised:
                    run_cli(self.path, *arguments)
                self.assertEqual(raised.exception.code, 2)

    def test_no_command_opens_the_menu(self):
        from unittest import mock
        with mock.patch("builtins.input", side_effect=["0"]):
            code, out, _ = run_cli(self.path)
        self.assertEqual(code, 0)
        self.assertIn("Goodbye.", out)


if __name__ == "__main__":
    unittest.main()
