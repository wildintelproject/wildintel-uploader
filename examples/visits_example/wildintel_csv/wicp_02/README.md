# WildINTEL Epicollect examples for WICP_02 (the new form)

One download of the Epicollect5 project `new-cameratrap-control-test` for each revision, with the headers as Epicollect5 writes them (`5_Status_of_the_came`, `10_Action_after_thef`, `26_Time`…). Made for
the entities in [`../../../entities_example/wicp_02`](../../../entities_example/wicp_02) — import them first, with the research project **WICP_02** picked — and loaded **in order** on a research project with no visits yet, with
**Register visits → From a CSV file → WildINTEL Epicollect CSV** (no mapping is asked). Each revision is one visit to every site; the time of a visit is when the entry was created (`created_at`, UTC).

| File | What happens | Expected |
|---|---|---|
| `revision_1_installation.csv` | `R0001` (2026-09-14): the four cameras are put up (status *New site*, the form asks no action), cards 1–4. | **4 visits, no warnings.** |
| `revision_2_all_revised.csv` | `R0002` (2026-10-19): the four are inspected (*Camera inspection*, status *OK*, photos counted), cards 1–4 collected and 5–8 left. | **4 visits, no warnings.** |
| `revision_3_theft_replaced.csv` | `R0003` (2026-11-23): at `WICP_02_002` the camera is found **stolen** and replaced (status *Stolen*, action after the theft *Camera replacement*: a *Stolen + Installation* with the new camera `SP2468013579`, card 2). The other three are inspected: cards 5, 7 and 8 collected, 1, 3 and 4 left. | **4 visits, 1 warning**: card 6 went with the stolen camera, so it has no deployment. |
| `revision_4_theft_not_replaced.csv` | `R0004` (2026-12-28): at `WICP_02_003` the camera is found **stolen and not replaced** (*Stolen*, *Camera removal*: the site stays open, with no camera). The other three are inspected (the new camera of `WICP_02_002` included). | **4 visits, no warnings.** |

The new camera of `R0003` (`CAM-005`) is in [`cameras.csv`](../../../entities_example/wicp_02/cameras.csv) of the entities of the group.
