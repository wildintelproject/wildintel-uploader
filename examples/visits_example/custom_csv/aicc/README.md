# Custom CSV example for AICC

## `aicc_census.csv` — a census of 60 sites, for the entities of AICC

Made from the Epicollect download `form-1__aicensuscameras.csv` (240 entries of 60 sites) to fit the entities in [`../../entities_example/aicc`](../../../entities_example/aicc) — research project **AICC**, its 60 locations (`GA3`, `PD7`…, Europe/Berlin), cameras `1`…`75`, SD cards and the trappers `Pedro` and `Néstor`. Import them first, with the research project **AICC** picked. Source: **From a CSV file → Custom CSV**, **auto** (the headers are the names of the fields of a visit). Load it on a project with no visits yet.

The form numbers its two "collections" per deployment, but a revision is one visit to **every** site and is after the one before it, so the 240 entries are four revisions, in time order:

| Revision | When | What | Visits |
|---|---|---|---|
| `R0001` | Oct 2025 | `Installation` at the 60 sites | 60 |
| `R0002` | Nov 2025 – Mar 2026 | `Desinstallation` (55) or `Stolen` (5) — the cameras are taken away or found stolen | 60 |
| `R0003` | May – Jun 2026 | `Installation` again at the 60 sites | 60 |
| `R0004` | Jun – Aug 2026 | `Revision` (59), and one `Desinstallation` | 60 |

- The day and the time are the ones of the form; the time is the clock of the location (Europe/Berlin).
- A camera or a card that the form writes and the entities do not have (cameras `7`, `17`, `49`…`52`, `56`, `57`, `63`, or a card written as "68 now. Before 26") is replaced by one the entities do have and that is free at that moment, so no rule of the cameras or the cards is broken. A `Revision` leaves a card only where the form says one was put in (`… now N`).
- **The GPS is not the one of the form**: each note has the coordinates of its location with a few metres of difference (under 30 m), so none is farther than the tolerance of the location.
- Expected: **240 visits, no problems and one warning**: *R0004 GB5: Revision with 0 photos; no deployment will be produced for it* (as the form has it).
