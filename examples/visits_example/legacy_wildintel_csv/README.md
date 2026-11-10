# WildINTEL Epicollect Legacy examples

For **Register visits → From a CSV file**. Made to fit the entities in [`../../entities_example/small`](../../entities_example/small) (research project **WICP**): import those first (Settings → Entities, with the research project picked). Load it on a research project with no visits yet.

## `wildintel_epicollect_legacy.csv` — WildINTEL Epicollect Legacy CSV
The download of the Epicollect5 project of the old field flow, with its columns (`2_Collection`, `4_Location`, `6_Action`, …), with the sites as numbers (`1` is `WICP_0001`). Pick **WildINTEL Epicollect Legacy CSV**; no mapping is asked.

- The time is when the entry was created (`created_at`, UTC), put in the timezone of the location.
- It has a `Revision` with *Card full* (the photos are not counted), a `Revision + Desinstallation` with *no batteries*, and a last entry with no collection number (an old version of the form): it is **ignored**, and counted as such.
- Expected: **7 visits, 1 ignored**, and a note that `WICP_0004` was visited in `R0001` and not in `R0002`.

## `visit_epicollect_valid.csv` — the legacy form, for the `big` entities

Pick **WildINTEL Epicollect Legacy CSV**; no mapping is asked. It is made to fit the entities in [`../../entities_example/big`](../../entities_example/big) (research project **WICP**, with the locations as `WICP_` + four digits, the cameras, the SD cards and the trappers of that folder): import those first instead of the `small` ones.

- 18 visits in three field trips to six active sites (`WICP_0008` … `WICP_0020`), with active cameras and SD cards, and the trappers of `trappers.csv`.
- The cameras and the cards are where the visits before say they are, so every row is read with nothing left out.
- Expected: **18 visits, no problems, no warnings.**

