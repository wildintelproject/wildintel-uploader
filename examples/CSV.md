# Example CSV files (in this folder)

For trying the CSV options of the app.

**Visits** (Register visits → From a CSV file). The sites have to be locations of the research project picked: `visits_epicollect.csv` and `visits_mapped.csv` use `TATR_0001` and `TATR_0002` (project TATR); `visits_donana.csv` uses `DONA_0005`, `DONA_0005_B`, `DONA_0007` and
`DONA_0009` (project DONA — the sites written as numbers get that prefix and four digits).

- `visits_epicollect.csv` — "From Wildintel Epicollect": the Epicollect download of a field trip, as the field records read it. The time is
  `created_at` (UTC), put in the timezone of the location. The last row, with no collection number, is ignored.
- `visits_donana.csv` — the same with the Spanish headers and codes of the Doñana form (R, I, D, ROBADA).
- `visits_mapped.csv` — "From a CSV file": a CSV with columns of its own. The page shows its columns and you say which field each gives;
  `Lugar`, `Dia`, `Tarea`, `Quien`, `Fotos` and `Tarjeta` are not matched by themselves — pick them. Dates are written day first.

**Entities** (Settings → Entities, one tab each):
- `research_projects.csv` — Research projects → Import CSV (kept at once in the collections folder). They can also be taken from Trapper.
- `locations.csv` — Locations → pick a research project first → Import CSV: the ones it has are updated, the others added. It has the 72 sites of the
  Doñana form download, as `WICP_` + four digits (`_B` for a second camera): their coordinates are those of the entries (the median of each
  site), the names are invented. They can also be taken
  from Trapper, when the research project was.
- `trappers.csv` — Trappers → Import CSV (the trappers are not tied to a research project).
- `sd_cards.csv` and `cameras.csv` — SD cards / Cameras → pick a research project first → Import CSV: they are added to that project.
  Then press Save. `sd_cards.csv` has the 193 cards that appear in the Doñana form download (`aicensuscameras`); their brand, capacity and
  day in production are invented.
