"""Differential check: compare the current OrderService with the original one.

Loads supplydesk/service.py and storage.py from a Git revision (default:
82ed75e, the untouched starter commit, present in every clone), then runs the same random
sequences of valid and invalid operations against both implementations.
After every step it compares the returned value (or the exception type and
message) and the bytes of the save file.

Intended for checking behavior-preserving refactorings. Once intended
behavior changes are made (defect fixes, CR-01) differences are expected.

    python tools/compare_with_baseline.py [--ref 82ed75e] [--runs 2000]
"""

import argparse
import importlib
from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from supplydesk.service import OrderService as CurrentService  # noqa: E402

STARTER_COMMIT = "82ed75e"  # original starter code

PRODUCTS = ["notebook", "pen-pack", "hoodie", "mug", "bag", "laptop", None]
QUANTITIES = [1, 1, 2, 2, 3, 4, 5, 6, 9, 20, 99, 100, 0, -1, True, 2.0, "2", None]
CUSTOMERS = ["regular", "regular", "student", "student", "Student", None]
FULFILLMENTS = ["pickup", "pickup", "delivery", "delivery", "express", ""]


def load_reference(ref, workdir):
    package = Path(workdir) / "reference_supplydesk"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    for name in ("service.py", "storage.py", "catalog.json"):
        source = subprocess.run(
            ["git", "show", f"{ref}:supplydesk/{name}"], cwd=ROOT,
            check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout
        source = source.replace("from supplydesk.", "from reference_supplydesk.")
        (package / name).write_text(source, encoding="utf-8")
    sys.path.insert(0, str(workdir))
    return importlib.import_module("reference_supplydesk.service").OrderService


def random_items(rng):
    roll = rng.random()
    if roll < 0.04:
        return rng.choice([[], (), None, "notebook:1", ["notebook"]])
    lines = []
    for _ in range(rng.randint(1, 3)):
        line = {"product_id": rng.choice(PRODUCTS), "quantity": rng.choice(QUANTITIES)}
        if rng.random() < 0.03:
            del line["quantity"]
        lines.append(line)
    return lines


def valid_request(rng):
    items = [{"product_id": rng.choice(PRODUCTS[:5]), "quantity": rng.randint(1, 4)}
             for _ in range(rng.randint(1, 3))]
    return rng.choice(["regular", "student"]), items, rng.choice(["pickup", "delivery"])


def random_operation(rng):
    kind = rng.choice(["quote", "place", "place", "cancel", "get", "list", "catalog"])
    if kind in ("quote", "place"):
        if rng.random() < 0.6:
            return kind, valid_request(rng)
        return kind, (rng.choice(CUSTOMERS), random_items(rng), rng.choice(FULFILLMENTS))
    if kind in ("cancel", "get"):
        return kind, ("ORD-" + str(rng.randint(1, 6)).zfill(4),)
    return kind, ()


def call(service, kind, args):
    method = {
        "quote": service.quote, "place": service.place_order, "cancel": service.cancel_order,
        "get": service.get_order, "list": service.list_orders, "catalog": service.catalog,
    }[kind]
    try:
        return ("ok", method(*args))
    except Exception as error:  # compare failures as well as results
        return ("error", type(error).__name__, str(error))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", default=STARTER_COMMIT)
    parser.add_argument("--runs", type=int, default=2000)
    parser.add_argument("--steps", type=int, default=15)
    parser.add_argument("--seed", type=int, default=3415)
    options = parser.parse_args()

    rng = random.Random(options.seed)
    operations = mismatches = 0
    with tempfile.TemporaryDirectory() as workdir:
        ReferenceService = load_reference(options.ref, workdir)
        for run in range(options.runs):
            reference_path = Path(workdir) / f"ref-{run}.json"
            current_path = Path(workdir) / f"cur-{run}.json"
            reference, current = ReferenceService(reference_path), CurrentService(current_path)
            for step in range(options.steps):
                kind, args = random_operation(rng)
                expected, actual = call(reference, kind, args), call(current, kind, args)
                same_file = (reference_path.read_bytes() if reference_path.exists() else None) == \
                            (current_path.read_bytes() if current_path.exists() else None)
                operations += 1
                if expected != actual or not same_file:
                    mismatches += 1
                    if mismatches <= 5:
                        print(f"MISMATCH run {run} step {step}: {kind}{args!r}")
                        print("  reference:", expected)
                        print("  current:  ", actual)
    print(f"Reference revision: {options.ref}")
    print(f"Random sequences: {options.runs} x {options.steps} steps (seed {options.seed})")
    print(f"Operations compared: {operations}")
    print(f"Mismatches (result, error or saved file): {mismatches}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
