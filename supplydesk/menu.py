"""Interactive terminal adapter; business rules remain in OrderService."""

from supplydesk.service import (
    CUSTOMER_TYPES, DEFAULT_CUSTOMER_TYPE, DEFAULT_FULFILLMENT, FULFILLMENT_OPTIONS,
)

CENTS_PER_DOLLAR = 100
CUSTOMER_PROMPT = (f"Customer type [{'/'.join(CUSTOMER_TYPES)}] "
                   f"(Enter = {DEFAULT_CUSTOMER_TYPE}): ")
FULFILLMENT_PROMPT = (f"Fulfillment [{'/'.join(FULFILLMENT_OPTIONS)}] "
                      f"(Enter = {DEFAULT_FULFILLMENT}): ")


def money(cents):
    dollars, remainder = divmod(cents, CENTS_PER_DOLLAR)
    return f"${dollars}.{remainder:02d}"


def show_catalog(products):
    print("\nProduct ID       Name                     Price     Stock")
    for product in products:
        print(f"{product['product_id']:<16} {product['name']:<24} "
              f"{money(product['unit_price_cents']):>8} {product['stock']:>8}")


def show_order(order):
    print("\n" + order.get("order_id", "Quote") + " - " + order.get("status", "not placed"))
    print(f"Customer: {order['customer_type']} | Fulfillment: {order['fulfillment']}")
    for line in order['items']:
        print(f"  {line['name']} x {line['quantity']}: {money(line['line_total_cents'])}")
    for label, key in (("Subtotal", "subtotal_cents"), ("Discount", "discount_cents"),
                       ("Delivery", "delivery_cents"), ("Total", "total_cents")):
        print(f"{label}: {money(order[key])}")


def read_request(service):
    show_catalog(service.catalog())
    print("Enter product IDs from the table. Blank product ID finishes the item list.")
    customer = input(CUSTOMER_PROMPT).strip() or DEFAULT_CUSTOMER_TYPE
    items = []
    while True:
        product_id = input("Product ID (Enter = finish): ").strip()
        if not product_id:
            break
        raw = input("Quantity: ").strip()
        try:
            quantity = int(raw)
        except ValueError:
            print("Please enter a whole number. Re-enter this item.")
            continue
        items.append({"product_id": product_id, "quantity": quantity})
    fulfillment = input(FULFILLMENT_PROMPT).strip() or DEFAULT_FULFILLMENT
    return customer, items, fulfillment


def confirmed(prompt):
    """Only an explicit y (any case) counts as yes."""
    return input(prompt).strip().lower() == "y"


def view_catalog(service):
    show_catalog(service.catalog())


def get_quote(service):
    request = read_request(service)
    show_order(service.quote(*request))
    print("Quote only: no stock reserved and no order created.")


def place_order(service):
    request = read_request(service)
    show_order(service.quote(*request))
    if confirmed("Place this order? [y/N]: "):
        show_order(service.place_order(*request))
    else:
        print("Order not placed.")


def view_history(service):
    orders = service.list_orders()
    if not orders:
        print("No orders yet.")
    for order in orders:
        show_order(order)


def find_order(service):
    show_order(service.get_order(input("Order ID: ").strip()))


def cancel_order(service):
    order_id = input("Order ID to cancel: ").strip()
    if confirmed("Cancel this order? [y/N]: "):
        show_order(service.cancel_order(order_id))
    else:
        print("Cancellation abandoned.")


EXIT_OPTION = "0"
MENU_OPTIONS = (
    ("1", "View products and stock", view_catalog),
    ("2", "Get a quote", get_quote),
    ("3", "Place an order", place_order),
    ("4", "View order history", view_history),
    ("5", "Find an order", find_order),
    ("6", "Cancel an order", cancel_order),
)
MENU_HANDLERS = {key: handler for key, _, handler in MENU_OPTIONS}
MENU_TEXT = ("\n" + "\n".join(f"{key}. {label}" for key, label, _ in MENU_OPTIONS)
             + f"\n{EXIT_OPTION}. Exit")
UNKNOWN_OPTION_MESSAGE = f"Choose a number from {EXIT_OPTION} to {MENU_OPTIONS[-1][0]}."
# Errors a menu action may raise for bad input or an unreadable save file.
RECOVERABLE_ERRORS = (ValueError, OSError, KeyError, TypeError)


def run_menu(service):
    print("Campus Supply Desk | All prices are CAD. Orders are saved automatically.")
    while True:
        try:
            print(MENU_TEXT)
            choice = input("Choose an option: ").strip()
            if choice == EXIT_OPTION:
                print("Goodbye.")
                return 0
            handler = MENU_HANDLERS.get(choice)
            if handler is None:
                print(UNKNOWN_OPTION_MESSAGE)
            else:
                handler(service)
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return 0
        except RECOVERABLE_ERRORS as error:
            print(f"Error: {error}")
            print("Returning to the menu. Check your input or state file before retrying.")
