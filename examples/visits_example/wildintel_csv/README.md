# WildINTEL Epicollect examples (the new form)

For **Register visits → From a CSV file**. Made to fit the entities in [`../../entities_example/small`](../../entities_example/small) (research project **WICP**): import those first (Settings → Entities, with the research project picked). Load it on a research project with no visits yet.

## `wildintel_epicollect.csv` — WildINTEL Epicollect CSV (the new form)
The download of the project `new-cameratrap-control-test`, with the 26 questions of the form `Cameratrap visit` and the headers as Epicollect5 writes them — the number of the question, an underscore and its text, **cut at 20 characters** (`5_Status_of_the_came`, `6_Card_and_batteries`, `7_N_pictures_collect`, `10_Action_after_thef`), and the coordinates in `lat_`, `long_`, `accuracy_`, `UTM_…` columns. Pick **WildINTEL Epicollect**; no mapping is asked.

- The sites are written as the locations are (`WICP_0001`), the cameras by their serial number, and who went in one cell (`Ana Pérez, Luis Gómez`).
- The time is when the entry was created (`created_at`, UTC), not the `Time` of the form, which is local.
- `R0001` installs the four cameras (status *New site*, no action: the form does not ask one). `R0002` has an inspection with *Card changed*, an inspection with *Card full* (the photos are not counted), a *Camera removal* with *no batteries* and a *Stolen* camera followed by *Site removal*.
- Expected: **8 visits, no problems, no warnings.**
- The headers of the form were read from the project; no entry has been downloaded from it yet, so the cut of `7_N_pictures_collect` is the one to check first with a real download.

## [`wicp_02`](wicp_02)
Four downloads, one for each revision of the research project **WICP_02**: the installation, a revision with no problems, a theft with the camera replaced and a theft with no replacement. See [its README](wicp_02/README.md).
