# CR-01 Express Delivery: impact prediction (written before implementation)

Recorded before any CR-01 code was changed. The review after implementation
is in the report (Task 5, Part C).

## 1. Behavior or requirements that will change

- `express` becomes a third valid fulfillment value for `quote()` and
  `place_order()`, the `--fulfillment` option of `quote`/`place`, and the
  menu's fulfillment prompt. Until now it is rejected with `ValueError`
  (the CLI parser rejects it with exit status 2).
- New delivery-charge rule: express is a flat 1,200 cents and is never
  waived. The free-delivery threshold (10,000 cents after discount) keeps
  applying to standard `delivery` only.
- Unchanged: the student discount (still on merchandise only, same
  threshold and rounding), pickup, standard delivery, validation, stock,
  order numbering, history and cancellation. Defaults stay `regular` and
  `pickup`.

## 2. Files, classes and methods expected to change

| File | Expected change |
|---|---|
| `supplydesk/service.py` | Add `EXPRESS_DELIVERY` and `EXPRESS_DELIVERY_FEE_CENTS`; add express to `FULFILLMENT_OPTIONS`; one new branch in `_delivery_cents()`. `quote`, `place_order`, `cancel_order` and the storage format should need no change because they already go through `_price_request()`. |
| `supplydesk/cli.py` | No logic change: `--fulfillment` choices already come from `FULFILLMENT_OPTIONS`. Add help text so the fee difference is discoverable. |
| `supplydesk/menu.py` | Probably no code change: the fulfillment prompt is built from `FULFILLMENT_OPTIONS` and will list express automatically. |
| `supplydesk/storage.py` | No change (schema version 1 already stores `fulfillment` and `delivery_cents`). |
| `README.md`, `FUNCTIONAL_SPEC.md` | Document express, its fee and an example. |

## 3. Tests needed

Existing tests that must be updated (they encode the old rule):

- `test_validation.test_fulfillment_must_be_exactly_pickup_or_delivery`
  lists `express` as invalid.
- `test_menu.test_blank_answers_default_to_regular_and_pickup` checks the
  exact fulfillment prompt text.

New tests (`tests/test_express.py`):

- The three CR-01 examples: $22, $84, and $120 vs $132.
- Fee is never waived, including at and above the 10,000-cent threshold.
- Student discount unchanged with express, including the 5,000-cent
  boundary; discount not applied to the fee.
- Quote and placed order agree; express orders keep fulfillment, items,
  fee, discount and total after `get_order`, reopening the save file, and
  cancellation; stock and order numbering behave as before.
- Other fulfillment values (`Express`, `EXPRESS`, `courier`, empty) stay
  invalid.
- CLI: the CR-01 example command returns `total_cents` 8400; `--help`
  lists express; defaults unchanged.
- Menu: express accepted at the prompt; prompt lists express; blank still
  means pickup.

The golden transcripts should stay unchanged, since prompts are not part of
the recorded output and the recorded sessions do not use express.
