# Example CSV files

For trying the CSV options of the app. They are in two folders, and each folder has a README that says what is in it:

- [`visits_example`](visits_example) — **visits** (Register visits → From a CSV file), by the option they are for (Custom CSV, From WildINTEL Epicollect, From WildINTEL Epicollect Legacy) and by the group of entities they are made to fit.
- [`entities_example`](entities_example) — **entities** (Settings → Entities, one tab each), in groups: `small` (the research project `WICP`, four locations), `wicp_02` (`WICP_02`), `aicc` (`AICC`, 60 locations) and `big` (`WICP`, the sites of the Doñana form).

Each group of entities has the same five files:

- `research_projects.csv` — Research projects → Import CSV (kept at once in the collections folder). They can also be taken from Trapper.
- `locations.csv` — Locations → pick a research project first → Import CSV: the ones it has are updated, the others added. They can also be taken from Trapper, when the research project was.
- `trappers.csv` — Trappers → Import CSV (the trappers are not tied to a research project).
- `sd_cards.csv` and `cameras.csv` — SD cards / Cameras → pick a research project first → Import CSV: they are added to that project. Then press Save.

`big` has the 72 sites of the Doñana form download, as `WICP_` + four digits (`_B` for a second camera): their coordinates are those of the entries (the median of each site) and the names are invented. Its `sd_cards.csv` has the 193 cards that appear in that download (`aicensuscameras`); their brand, capacity and day in production are invented.

Import the entities of a group first, then load the visits that are made for it.
