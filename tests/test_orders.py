"""Order placement, history and cancellation behavior that refactoring must preserve."""

import json
import unittest

from supplydesk.service import OrderService
from tests.support import ServiceTestCase, item

QUOTE_FIELDS = ["customer_type", "fulfillment", "items", "subtotal_cents",
                "discount_cents", "delivery_cents", "total_cents"]
ORDER_FIELDS = ["order_id", "status"] + QUOTE_FIELDS


class QuoteTests(ServiceTestCase):
    def test_quote_creates_no_save_file_order_or_stock_change(self):
        before = self.service.catalog()
        quote = self.service.quote("student", [item("hoodie", 2)], "delivery")
        self.assertNotIn("order_id", quote)
        self.assertNotIn("status", quote)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.service.catalog(), before)
        self.assertEqual(self.service.list_orders(), [])

    def test_viewing_the_catalog_creates_no_save_file(self):
        products = self.service.catalog()
        self.assertEqual([p["product_id"] for p in products],
                         ["notebook", "pen-pack", "hoodie", "mug", "bag"])
        self.assertFalse(self.path.exists())

    def test_quote_and_placed_order_agree(self):
        request = ("student", [item("hoodie", 2), item("mug", 1)], "delivery")
        quote = self.service.quote(*request)
        order = self.service.place_order(*request)
        self.assertEqual({key: order[key] for key in QUOTE_FIELDS}, quote)

    def test_result_fields_keep_their_documented_order(self):
        # Individual commands print these dictionaries as JSON, so the field
        # order is part of the visible output.
        quote = self.service.quote("regular", [item("mug", 1)])
        order = self.service.place_order("regular", [item("mug", 1)])
        self.assertEqual(list(quote), QUOTE_FIELDS)
        self.assertEqual(list(order), ORDER_FIELDS)
        self.assertEqual(list(order["items"][0]),
                         ["product_id", "name", "unit_price_cents", "quantity", "line_total_cents"])

    def test_quote_does_not_reserve_stock_and_placement_rechecks_it(self):
        self.service.quote("regular", [item("hoodie", 5)])
        self.service.place_order("regular", [item("hoodie", 3)])
        with self.assertRaisesRegex(ValueError, "Not enough stock for hoodie"):
            self.service.quote("regular", [item("hoodie", 3)])
        with self.assertRaisesRegex(ValueError, "Not enough stock for hoodie"):
            self.service.place_order("regular", [item("hoodie", 3)])


class PlacementTests(ServiceTestCase):
    def test_placement_deducts_only_ordered_units(self):
        self.service.place_order("regular", [item("notebook", 3), item("mug", 2)])
        stock = {p["product_id"]: p["stock"] for p in self.service.catalog()}
        self.assertEqual(stock, {"notebook": 17, "pen-pack": 10, "hoodie": 5, "mug": 6, "bag": 4})

    def test_order_ids_increase_and_are_never_reused(self):
        first = self.service.place_order("regular", [item("mug", 1)])
        second = self.service.place_order("regular", [item("mug", 1)])
        self.service.cancel_order(second["order_id"])
        third = self.service.place_order("regular", [item("mug", 1)])
        self.assertEqual([first["order_id"], second["order_id"], third["order_id"]],
                         ["ORD-0001", "ORD-0002", "ORD-0003"])

    def test_saved_file_uses_schema_version_one(self):
        self.service.place_order("regular", [item("mug", 1)])
        state = json.loads(self.saved_text())
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["next_order_number"], 2)

    def test_history_lists_all_orders_in_placement_order(self):
        for product in ("notebook", "mug", "bag"):
            self.service.place_order("regular", [item(product, 1)])
        self.service.cancel_order("ORD-0002")
        history = self.service.list_orders()
        self.assertEqual([o["order_id"] for o in history], ["ORD-0001", "ORD-0002", "ORD-0003"])
        self.assertEqual([o["status"] for o in history], ["placed", "cancelled", "placed"])

    def test_reopening_the_save_file_preserves_history_and_stock(self):
        self.service.place_order("student", [item("hoodie", 2)], "delivery")
        self.service.place_order("regular", [item("bag", 1)])
        reopened = OrderService(self.path)
        self.assertEqual(reopened.list_orders(), self.service.list_orders())
        self.assertEqual(reopened.catalog(), self.service.catalog())
        self.assertEqual(reopened.place_order("regular", [item("mug", 1)])["order_id"], "ORD-0003")

    def test_historical_prices_are_not_recalculated(self):
        self.service.place_order("regular", [item("notebook", 2)])
        state = json.loads(self.saved_text())
        state["catalog"][0]["unit_price_cents"] = 900
        self.path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(self.service.get_order("ORD-0001")["total_cents"], 1000)
        self.assertEqual(self.service.quote("regular", [item("notebook", 2)])["total_cents"], 1800)


class CancellationTests(ServiceTestCase):
    def test_cancel_restores_stock_and_keeps_the_original_record(self):
        placed = self.service.place_order("student", [item("hoodie", 2)], "delivery")
        cancelled = self.service.cancel_order(placed["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual({k: cancelled[k] for k in QUOTE_FIELDS},
                         {k: placed[k] for k in QUOTE_FIELDS})
        self.assertEqual(self.service.get_order("ORD-0001")["status"], "cancelled")
        self.assertEqual(self.stock_of("hoodie"), 5)

    def test_cancelling_an_already_cancelled_order_changes_nothing(self):
        self.service.place_order("regular", [item("pen-pack", 2)])
        self.service.cancel_order("ORD-0001")
        self.assertEqual(self.stock_of("pen-pack"), 10)
        again = self.service.cancel_order("ORD-0001")
        self.assertEqual(again["status"], "cancelled")
        self.assertEqual(self.stock_of("pen-pack"), 10)


if __name__ == "__main__":
    unittest.main()
