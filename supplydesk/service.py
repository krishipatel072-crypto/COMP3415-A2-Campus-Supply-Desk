"""Operations used by the command-line order desk."""

from supplydesk.storage import JsonStore


class OrderService:
    def __init__(self, state_path=".supplydesk/state.json"):
        self.store = JsonStore(state_path)

    def catalog(self):
        return self.store.load()["catalog"]

    def quote(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        return _price_request(state["catalog"], customer_type, items, fulfillment)

    def place_order(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        priced = _price_request(state["catalog"], customer_type, items, fulfillment)
        order = {
            "order_id": "ORD-" + str(state["next_order_number"]).zfill(4),
            "status": "placed",
            **priced,
        }
        _adjust_stock(state["catalog"], order["items"], -1)
        state["next_order_number"] += 1
        state["orders"].append(order)
        self.store.save(state)
        return order

    def list_orders(self):
        return self.store.load()["orders"]

    def get_order(self, order_id):
        return _find_order(self.store.load()["orders"], order_id)

    def cancel_order(self, order_id):
        state = self.store.load()
        order = _find_order(state["orders"], order_id)
        _adjust_stock(state["catalog"], order["items"], +1)
        order["status"] = "cancelled"
        self.store.save(state)
        return order


def _price_request(catalog, customer_type, items, fulfillment):
    """Validate a request against the catalog and price it.

    quote() and place_order() both use this, so they cannot drift apart.
    Raises ValueError for an invalid request; changes nothing.
    """
    _check_request_shape(customer_type, items, fulfillment)
    lines = [_build_line(catalog, item) for item in items]
    subtotal = sum(line["line_total_cents"] for line in lines)
    discount = _discount_cents(customer_type, subtotal)
    delivery = _delivery_cents(fulfillment, subtotal - discount)
    return {
        "customer_type": customer_type,
        "fulfillment": fulfillment,
        "items": lines,
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "delivery_cents": delivery,
        "total_cents": subtotal - discount + delivery,
    }


def _check_request_shape(customer_type, items, fulfillment):
    if customer_type not in ("regular", "student"):
        raise ValueError("Customer type must be regular or student.")
    if fulfillment not in ("pickup", "delivery"):
        raise ValueError("Fulfillment must be pickup or delivery.")
    if not isinstance(items, list) or not items:
        raise ValueError("An order must contain at least one item.")


def _build_line(catalog, item):
    """Validate one requested item and return its priced order line."""
    if not isinstance(item, dict):
        raise ValueError("Each item must contain a product_id and quantity.")
    product = _find_product(catalog, item.get("product_id"))
    if product is None:
        raise ValueError("Unknown product.")
    quantity = item.get("quantity")
    if type(quantity) is not int or quantity < 1 or quantity > 99:
        raise ValueError("Quantity must be an integer from 1 to 99.")
    if quantity > product["stock"]:
        raise ValueError("Not enough stock for " + product["product_id"] + ".")
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "unit_price_cents": product["unit_price_cents"],
        "quantity": quantity,
        "line_total_cents": product["unit_price_cents"] * quantity,
    }


def _discount_cents(customer_type, subtotal):
    if customer_type == "student" and subtotal > 5000:
        return (subtotal * 10 + 50) // 100
    return 0


def _delivery_cents(fulfillment, merchandise_after_discount):
    if fulfillment == "delivery" and merchandise_after_discount < 10000:
        return 600
    return 0


def _find_product(catalog, product_id):
    for product in catalog:
        if product["product_id"] == product_id:
            return product
    return None


def _find_order(orders, order_id):
    for order in orders:
        if order["order_id"] == order_id:
            return order
    raise ValueError("Unknown order: " + order_id)


def _adjust_stock(catalog, lines, direction):
    """Add (direction=+1) or remove (direction=-1) each line's units."""
    for line in lines:
        product = _find_product(catalog, line["product_id"])
        if product is not None:
            product["stock"] += direction * line["quantity"]
