# timefix — checking and fixing the dates and times of the images

The times of the images of a folder, in the camera's order, against the period the visits give (from the visit that left the camera to the one
that collected its card): the runs where the time never goes backwards, how each fits the period, and the offset suggested for one that doesn't.
A run can be shifted by an offset, or images whose time can't be trusted taken out — every fix written down beside them.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `TimeFixService` |  | `timeline`, `shift`, `remove` |

## How it is used

```python
timeline = timefix.timeline(folder, VisitOfTheImages("DONA", "DONA_01", "2026-03-01", "10:00:00"))
timefix.shift(folder, visit, first="IMG_0010.JPG", last="IMG_0099.JPG", offset_seconds=3600, reason="The clock was an hour behind.")
```

The web app has `/api/timefix/…`.

## What it refuses

`TimeFixError` — the message says why (the visit isn't there, no later visit collected its card…).

## How it is made

- `domain/` — the rules (the period, the runs, the suggestions: `rules.py`) and the ports.
- `application/use_cases.py` — the contract over the ports.
- `infrastructure/` — the images and their dates (`images.py`), the fixes written down (`corrections.py`), the visits through their contract
  (`outside.py`), `api_schemas.py`.
