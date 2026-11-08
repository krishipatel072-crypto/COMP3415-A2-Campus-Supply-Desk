"""Golden-master checks: complete menu and command sessions must not change.

The expected transcripts in tests/golden/ were recorded from the original
starter implementation. They avoid the known defects, so any difference means
visible behavior changed. To re-record after an intended change, run:

    python -m tests.test_characterization --record
"""

from pathlib import Path
import sys
import tempfile
import unittest

from supplydesk.service import OrderService
from tests.support import run_cli, run_menu_session

GOLDEN = Path(__file__).with_name("golden")

MENU_ANSWERS = [
    "1",
    "2", "student", "hoodie", "2", "mug", "1", "", "delivery",
    "3", "", "notebook", "x", "notebook", "3", "", "", "y",
    "3", "regular", "bag", "1", "", "", "n",
    "4",
    "5", "ORD-0001",
    "6", "ORD-0001", "y",
    "6", "ORD-0001", "n",
    "2", "", "laptop", "1", "", "",
    "2", "regular", "bag", "9", "", "",
    "7",
    "1",
    "0",
]

COMMANDS = [
    ["catalog"],
    ["quote", "--customer", "student", "--fulfillment", "delivery", "--item", "hoodie:2"],
    ["place", "--fulfillment", "delivery", "--item", "hoodie:3"],
    ["place", "--item", "notebook:2", "--item", "pen-pack:1"],
    ["quote", "--item", "bag:9"],
    ["cancel", "ORD-0001"],
    ["orders"],
    ["show", "ORD-0002"],
    ["show", "ORD-0404"],
    ["catalog"],
]


def menu_transcript():
    with tempfile.TemporaryDirectory() as directory:
        service = OrderService(Path(directory) / "state.json")
        code, output, _ = run_menu_session(service, MENU_ANSWERS)
    return output + "exit=" + str(code) + "\n"


def command_transcript():
    parts = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "state.json"
        for command in COMMANDS:
            code, out, err = run_cli(path, *command)
            parts.append("$ " + " ".join(command) + "\nexit=" + str(code) + "\n" + out + err)
    return "".join(parts)


class GoldenMasterTests(unittest.TestCase):
    maxDiff = None

    def test_full_menu_session_output_is_unchanged(self):
        expected = (GOLDEN / "menu_session.txt").read_text(encoding="utf-8")
        self.assertEqual(menu_transcript(), expected)

    def test_command_session_output_is_unchanged(self):
        expected = (GOLDEN / "command_session.txt").read_text(encoding="utf-8")
        self.assertEqual(command_transcript(), expected)


if __name__ == "__main__":
    if "--record" in sys.argv:
        GOLDEN.mkdir(exist_ok=True)
        (GOLDEN / "menu_session.txt").write_text(menu_transcript(), encoding="utf-8")
        (GOLDEN / "command_session.txt").write_text(command_transcript(), encoding="utf-8")
        print("Recorded golden transcripts in", GOLDEN)
    else:
        unittest.main()
