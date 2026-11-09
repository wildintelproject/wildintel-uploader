# Example visits (CSV files)

Visits to the camera traps for trying **Register visits → From a CSV file**. All of them are made to fit the entities in
[`../entities_example/small`](../entities_example/small), so import those first (Settings → Entities, with the research project **WICP** picked):

| Entity | What the visits use |
|---|---|
| Research project | `WICP` |
| Locations | `WICP_0001` … `WICP_0004` (UTC, no summer time; `WICP_0004` is *planned*) |
| Cameras | `BR5071050724`, `RE5699252753`, `RE1161042648`, `SP1776213899` (labels `CAM-001` … `CAM-004`) |
| SD cards | `1` … `8` |
| Trappers | `Ana Pérez`, `Luis Gómez` |

A *revision* is one visit to **every** location that is not archived, so each file with two revisions visits the four locations in `R0001`.
Dates are in September and October 2026. Load a file on a research project that has no visits yet (or the import will say they are already kept).

Each file says in the Source step which option to pick. Where it says **auto**, the columns are matched by their names and nothing has to be mapped.

## Files

### `custom_csv_valid.csv` — Custom CSV, all correct
The one to start with. Its headers are the names of the fields of a visit, so **Custom CSV** matches every column by itself (auto). The data is right:

- `R0001`: an Installation at each of the four locations, with its camera and its card.
- `R0002`: a Revision at three of them (collecting the card of `R0001` and leaving another) and a Revision + Desinstallation at `WICP_0002` (the camera is revised and taken away: a camera is never taken away without looking at it first).
- Expected: **8 visits, no problems, no warnings, no new sites.**

### `revision2_before_revision1_finished.csv` — a revision cannot start before the one before is finished
`R0001` only visits `WICP_0001` and `WICP_0002`; then `R0002` already has visits. Auto.

- Expected: the two visits of `R0001` are kept; the two of `R0002` are **refused**, each with *"R0002 cannot start: R0001 is not finished, 2 location(s) still to be visited in it: WICP_0003, WICP_0004."*
- In the form (By hand) the same thing shows when `R0002` is started: it offers to mark the missing locations as not visited.

### `wildintel_epicollect.csv` — From WildINTEL Epicollect (the new form)
The download of the project `new-cameratrap-control-test`, with the 26 questions of the form `Cameratrap visit` and the headers as Epicollect5 writes them — the number of the question, an underscore and its text, **cut at 20 characters** (`5_Status_of_the_came`, `6_Card_and_batteries`, `7_N_pictures_collect`, `10_Action_after_thef`), and the coordinates in `lat_`, `long_`, `accuracy_`, `UTM_…` columns. Pick **WildINTEL Epicollect**; no mapping is asked.

- The sites are written as the locations are (`WICP_0001`), the cameras by their serial number, and who went in one cell (`Ana Pérez, Luis Gómez`).
- The time is when the entry was created (`created_at`, UTC), not the `Time` of the form, which is local.
- `R0001` installs the four cameras (status *New site*, no action: the form does not ask one). `R0002` has an inspection with *Card changed*, an inspection with *Card full* (the photos are not counted), a *Camera removal* with *no batteries* and a *Stolen* camera followed by *Site removal*.
- Expected: **8 visits, no problems, no warnings.**
- The headers of the form were read from the project; no entry has been downloaded from it yet, so the cut of `7_N_pictures_collect` is the one to check first with a real download.

### `wildintel_epicollect_legacy.csv` — From WildINTEL Epicollect Legacy
The download of the Epicollect5 project of the old field flow, with its columns (`2_Collection`, `4_Location`, `6_Action`, …), with the sites as numbers (`1` is `WICP_0001`). Pick **WildINTEL Epicollect Legacy**; no mapping is asked.

- The time is when the entry was created (`created_at`, UTC), put in the timezone of the location.
- It has a `Revision` with *Card full* (the photos are not counted), a `Revision + Desinstallation` with *no batteries*, and a last entry with no collection number (an old version of the form): it is **ignored**, and counted as such.
- Expected: **7 visits, 1 ignored**, and a note that `WICP_0004` was visited in `R0001` and not in `R0002`.

### `columns_to_map.csv` — columns of its own, to be mapped by hand
Semicolon-separated, with Spanish headers, dates day first (`14/09/2026`) and a column that is not used. Pick **Custom CSV**.

- Matched by themselves: `Hora` (time), `Camara` (camera id) and `Observaciones` (notes).
- To be picked: `Lugar` → site, `Dia` → date, `Tarea` → actions, `Quien` → who went, `Fotos` → photos, `Tarjeta` → SD card.
- `Columna que no se usa` is left out.
- Expected: **6 visits, no problems**, and a note that the cameras of `WICP_0003` and `WICP_0004` are still out in `R0002`.

### `unknown_sites.csv` — sites that are not locations
Auto. A site that is not a location is not thrown away as a mistake: its visits are **held**, and the page tells a new site from a misprint.

- `WICP_0005` is new: it has coordinates (820 m from `WICP_0004`), so the page offers to add it as a location. Its camera and card (`BR9999999999`, `9`) are not in the entities.
- `WICP_0O01` is written with the letter O: it is one character apart from `WICP_0001`, so it looks like a misprint (fix the file).
- Expected: **4 visits kept, 2 new sites.**

### `rules_of_a_visit.csv` — a visit follows the rules of a visit, from a file as from the form
Auto. The visits of a file are refused for what the form refuses, each with its row; what the form only questions is kept with a warning.

- `R0001` installs the four cameras. In `R0002`: `WICP_0001` has a Revision with 0 photos (**kept**, with a warning: no deployment is produced for it); `WICP_0002` revises a camera that is not the one at the site (**refused**); `WICP_0003` leaves card `4`, which is still in the camera of `WICP_0004` (**refused**).
- Expected: **6 visits, 2 problems, 1 warning.**

### `row_errors.csv` — rows that cannot be read
Auto. The four Installations are right; the four Revisions of `R0002` each have a different mistake, so each is reported with its row of the file and **none is kept**:

| Row | Mistake |
|---|---|
| 6 | the action `Visit` does not exist |
| 7 | `31/02/2026` is not a date |
| 8 | the card code `Full` is not one of OK, CarFull, SinPilas, CarFullSinPilas |
| 9 | the number of photos is `many` |

- Expected: **4 visits, 4 problems.**

### `theft_and_archive.csv` — a theft, and a site given up
Auto. As `custom_csv_valid.csv`, but in `R0002` the camera of `WICP_0003` was stolen and the site is given up (`Stolen + Archive`); the other three locations are revised as usual.

- Expected: **8 visits, no problems, no warnings.**

## Things to try with them

- Load the same file twice: the second time every visit is **already kept** and skipped.
- Load `revision2_before_revision1_finished.csv`, then `custom_csv_valid.csv`: the visits of `R0001` are skipped, the rest are kept.
- Open the **visit book** after `custom_csv_valid.csv` to see the revisions, their dates and the status of every visit.
