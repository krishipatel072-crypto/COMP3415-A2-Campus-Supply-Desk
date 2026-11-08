"""Shared fixtures for the Campus Supply Desk tests."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from supplydesk.service import OrderService


def item(product_id, quantity):
    return {"product_id": product_id, "quantity": quantity}


class ServiceTestCase(unittest.TestCase):
    """Each test gets its own temporary save file and service."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def write_state(self, catalog, orders=(), next_order_number=1):
        """Create a valid schema-1 save file with a custom catalog."""
        state = {
            "schema_version": 1,
            "next_order_number": next_order_number,
            "catalog": catalog,
            "orders": list(orders),
        }
        self.path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def saved_text(self):
        return self.path.read_text(encoding="utf-8")

    def stock_of(self, product_id):
        for product in self.service.catalog():
            if product["product_id"] == product_id:
                return product["stock"]
        raise AssertionError("No product " + product_id)


class ScriptedInput:
    """Replaces input(): returns scripted answers, then signals end of input."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt=""):
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer


def run_menu_session(service, answers):
    """Run the interactive menu with scripted answers.

    Returns (exit_code, printed_output, prompts_shown).
    """
    from supplydesk.menu import run_menu

    scripted = ScriptedInput(answers)
    output = io.StringIO()
    with mock.patch("builtins.input", scripted), contextlib.redirect_stdout(output):
        code = run_menu(service)
    return code, output.getvalue(), scripted.prompts


def run_cli(path, *args):
    """Run an individual command against a save file.

    Returns (exit_code, stdout, stderr). Argument-parsing errors raise SystemExit.
    """
    from supplydesk.cli import main

    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(["--data", str(path), *args])
    return code, stdout.getvalue(), stderr.getvalue()
