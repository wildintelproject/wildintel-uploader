# WildINTEL Epicollect examples for WICP_02 (the new form)

One download of the Epicollect5 form `Cameratrap visit` for each revision, with the columns as Epicollect5 writes them — `created_by` and `title` too, which the app ignores — the number of the question, an underscore and its text, **cut at 20 characters**
(`5_Status_of_the_came`, `8_N_pictures_collect`, `10_Action_after_the_`, `11_Action_after_thef`) — and the answers as the form gives them. Made for the entities in
[`../../../entities_example/wicp_02`](../../../entities_example/wicp_02) — import them first, with the research project **WICP_02** picked — and loaded **in order** on a research project with no visits yet, with
**Register visits → From a CSV file → WildINTEL Epicollect CSV** (no mapping is asked). Each revision is one visit to every site; the time of a visit is when the entry was created (`created_at`, UTC).

What the form asks, as these files answer it:

- **The site and the card are chosen from a list** (`4_locationID`: `WICP_02_001`…; `23_SD_to_insert`: `SD 1`…`SD 8` — the app reads the number of the card).
- **Status of the camera**: *OK*, *Altered*, *Knocked down*, *Damaged*, *Stolen*, or **No camera at the site** (a new site, or one whose camera was taken away: a camera is put up).
- **The batteries and the card are two questions** (`6_Batteries_Status`: *OK*, *No batteries*; `7_Card_Status`: *OK*, *Full Card*). With the card full the photos are not counted: `8_N_pictures_collect` is empty.
- **After the review** (`10_Action_after_the_`): *Keep the camera* — the card is changed —, *Camera replacement*, *Camera removal* or *Site removal*. After a theft (`11_Action_after_thef`): *Camera replacement*, *Camera removal* — not replaced, the site stays open — or *Site removal*.

| File | What happens | Expected |
|---|---|---|
| `revision_1_installation.csv` | `R0001` (2026-09-14): the four cameras are put up (*No camera at the site*: the form asks the set-up of the camera, not an action), cards 1–4. | **4 visits, no warnings.** |
| `revision_2_all_revised.csv` | `R0002` (2026-10-19): the four are revised and kept (*Keep the camera*), cards 1–4 collected and 5–8 left. `001` is as it should be; `002` is *Altered* (put back in place); `003` has the **card full** (photos not counted, the date and time of the camera were bad); `004` has **no batteries**. | **4 visits, no warnings.** |
| `revision_3_theft_replaced.csv` | `R0003` (2026-11-23): at `WICP_02_002` the camera is found **stolen** and replaced (*Stolen*, *Camera replacement*: a *Stolen + Installation* with the new camera `SP2468013579`, card 2). The others are revised: `003` *Knocked down*, `004` *Damaged*; cards 5, 7 and 8 collected, 1, 3 and 4 left. | **4 visits, 1 warning**: card 6 went with the stolen camera, so it has no deployment. |
| `revision_4_theft_not_replaced.csv` | `R0004` (2026-12-28): at `WICP_02_003` the camera is found **stolen and not replaced** (*Stolen*, *Camera removal*: the site stays open, with no camera). The other three are revised (the new camera of `WICP_02_002` included). | **4 visits, no warnings.** |
| `revision_5_replacement_removal_and_site_given_up.csv` | `R0005` (2027-02-01), what is done after a review: `001` *Camera replacement* (a *Revision + Desinstallation + Installation*, with the new camera `GA3344556677`); `002` *Camera removal* (the camera is taken away, the site stays open); `003` *No camera at the site* — the camera taken from `001` is put up there —; `004` *Site removal* (a *Revision + Desinstallation + Archive*: the site is given up). | **4 visits, no warnings.** Load it after `R0004`. |
| `revision_5_refused.csv` | `R0005` that breaks the rules of the sites, to see what the app says: `002` says *No camera at the site* where one is still put up, and `003` is revised although its camera was stolen in `R0004`. `001` and `004` are right. | **2 visits kept, 2 problems** (*already has a camera*, *has no camera*). Load it after `R0004`, **instead of** the other `R0005`. |

The new cameras (`CAM-005`, `CAM-006`) are in the cameras of the entities of the group.
