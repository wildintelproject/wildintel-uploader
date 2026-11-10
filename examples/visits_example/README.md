# Example visits (CSV files)

Visits to the camera traps for trying **Register visits → From a CSV file**, in folders by what they are and by the group of entities they are made for.
Import the entities of the group first (Settings → Entities, with its research project picked) and load each file on a research project that has no visits yet.

| Folder | Source step | Made for the entities in | What is in it |
|---|---|---|---|
| [`custom_csv/small`](custom_csv/small) | Custom CSV | [`entities_example/small`](../entities_example/small) (project `WICP`, 4 locations) | The cases of the rules of a visit — all correct, a revision that starts before the one before is finished, unknown sites, rows that cannot be read, a theft and a site given up, columns to match by hand. |
| [`custom_csv/wicp_02`](custom_csv/wicp_02) | Custom CSV | [`entities_example/wicp_02`](../entities_example/wicp_02) (project `WICP_02`, 4 locations) | The same cases and more: three revisions, the rules of the SD cards, a visit that could not be made, and eleven revisions in one file (`R0010` to `R0020`). |
| [`custom_csv/aicc`](custom_csv/aicc) | Custom CSV | [`entities_example/aicc`](../entities_example/aicc) (project `AICC`, 60 locations) | A census of 60 sites in four revisions, made from an Epicollect download. |
| [`wildintel_csv`](wildintel_csv) | WildINTEL Epicollect CSV | [`entities_example/small`](../entities_example/small) | The download of the Epicollect5 project of the new form. |
| [`wildintel_csv/wicp_02`](wildintel_csv/wicp_02) | WildINTEL Epicollect CSV | [`entities_example/wicp_02`](../entities_example/wicp_02) | Four revisions, one file each: the installation, a revision with no problems, a theft with the camera replaced and a theft with none. |
| [`legacy_wildintel_csv`](legacy_wildintel_csv) | WildINTEL Epicollect Legacy CSV | [`entities_example/small`](../entities_example/small), and [`entities_example/big`](../entities_example/big) for `visit_epicollect_valid.csv` | The download of the Epicollect5 project of the old field flow. |

Each folder has its own README that says, for each file, which option to pick and what to expect.
