# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Upcoming release

### Added
- **QR codes** for the cameras, the SD cards and the locations: each one's page, in *Settings › Entities*, shows its QR code — it says `wildintel:<camera|sdcard|location>:<research project>:<id>` — with a button to download it as an SVG, to print on a label.
- **Manage uploads** (it was *Upload deployment to Trapper*): a menu entry, in the style of *Manage deployments*, with **Upload deployment to Trapper** and **Uploads dashboard** — the created deployments of the default research project, by revision: for each, a label for every platform it was uploaded to with the day, or *Not uploaded*; then where they were uploaded (*All* and each uploader — Trapper for now, ready for others) and a ring with the uploads done over the most there can be (the deployments of the revision times the uploaders picked).
- **Default research project fixed** when registering visits (by hand or from a file) and in Import deployments, as in Import deployment: it is the one of the settings, with a link to change it, and is not picked on the page.
- **Import deployments** (entry of *Manage deployments*; *Import collection* is gone from the menu): pick one or several closed visits — with one it is Import deployment (a folder with the images); with several, a folder with a subfolder of images for each visit, and the subfolder of each is said. The visits have to be of one revision.
- **Import deployment**: the research project is the default one of the settings (with a link to change it), followed by a square for each revision and the closed visits without a deployment; the first step is called *When was it collected?* and the dates one *Dates of the deployment*. The collection's `FileTimestampLog` (dates) and `FieldworkLog` (details) are one more source — *Log files* — when they have the deployment's row (`GET /api/deployment-import/log-entry`).
- **Release**: a macOS `.dmg` for Intel Macs (`macos-x86_64`), beside the Apple Silicon one (`macos-arm64`).
- **Register visits** (new task): the visits to the camera traps — who went, when, to which site and what was done — by hand, from the Epicollect
  download or from any CSV, kept in the research project's `visits.json`. The Camera section comes before the SD card, and what the visit before
  said fills in the Camera, Site and Grouping sections. Entities (research projects, locations, trappers, SD cards and cameras) have their own
  tab in Settings, with CSV import; `examples/` has example CSVs of all of them.
- **The deployments the visits say and the logs of their collections** (`/api/visits/deployments`, `/api/visits/field-logs`, as the field records of the first piece of the field workflow): each site's visits give
  a deployment for every pair of consecutive ones where the first left a camera and the second collected its card — *closed* — or for a camera still out — *open*. A deployment belongs to the collection the session of
  the visit that collected it names, minus one, which is also the revision Import deployment and Import session give a visit's deployment. The logs are written, with no button for it, when a visit is registered: each
  collection's `<R000N>_FileTimestampLog.csv` and `<R000N>_FieldworkLog.csv`, with the details both visits give merged: `Setup: … | Retrieval: …` for a text, the tags and groups of both, the setup's number or yes/no with the
  retrieval's value noted in `deploymentComments`.
- **Locations from the file itself**: the sites of a file that are not locations come with the coordinates of their first visit, and **Add the N sites with coordinates as locations** keeps them all at once (the ones that look like a misprint are left for the user).
- **Manage visits** is the task of the menu (it was *Register visits*): it offers **Register visits** and **Visit dashboard** — the visits kept to a research project (newest first, with a filter and the deployment each closed) and, in a second tab, the
  deployments they say (closed, and the ones whose camera is still out).
- **The visit book** is of the default research project (Settings › General), named at the top with a link to the settings; it is paged (ten rows), can be sorted by any column, has a square for each revision (all of them, or one, with how many of its visits are done) and five status squares (all, not done, open, closed, no deployment yet) that count and filter the rows with a bar of how many visits are done, and has a row — *Not done* — for each location (not retired) that has no visit in a session the visits have. It (`/api/visits/book`) lists a visit as *Session · Where · When · Status (open or closed) · Actions · Images stored · On Trapper* (a tick when the deployment was uploaded from here or synced from Trapper) (a tick, with a link to the deployment's details, once it is created and its images imported, or **Store images** on a closed visit that has none), then its actions, camera, card, photos and who went; **View** (the eye button of the entities) shows everything the visit says; **Store images** opens Import deployment with that visit chosen.
- **Import deployments** (it was *Import session*, then *Import collection*; it is an entry of *Manage deployments*) is redesigned around the visits: the research project, a **revision** (a square for each one with its closed visits without a deployment) and the visits ticked; **one visit** works as Import deployment — the folder is the deployment's, with its images in it, scanned like Import deployment does — and **several** as a collection, a folder with one subfolder each. Import deployment is left as it was.
- **Manage deployments** is the task of the menu (it was *Import deployment*): it offers **Import deployment** and **Deployments dashboard** — the deployments of the default research project as a book (it was a tab of the visit book, which is of the visits only), where the tick of the images stored of a visit links to the deployment. The status is a book as the Visits one: a square for each revision, the status squares of the one picked (the deployments, closed with their images stored, camera still out, not on Trapper yet) and a table — deployment, where, status, period, card and photos, on Trapper —; `/api/visits/deployments` says for each whether its images are stored (`images_stored`) and whether it is on Trapper.
- **The cameras and the SD cards are kept in the folder of their research project** (`<research project>/cameras.json` and `sd_cards.json`, beside `locations.json` and `visits.json`), so they travel with its collections; only the trappers stay in
  `settings.toml`. `GET /api/settings` gives the ones of every research project and `PUT /api/settings` saves each project's list in its folder — a camera or a card needs its research project (`422` otherwise). Those kept in `settings.toml`
  until now are moved when the settings are read (one that was free for any goes to each research project; one of a project that is not in the collections folder stays in the settings).
- **Settings › Visit sources › WildINTEL Epicollect** (and *Keep the seconds in the logs*, now in **General**; it was *Field records*) (`FIELDLOG`): the time of a visit (when its entry was created, or the date and the hour typed), whether the logs keep the seconds (off: cut to the minute) and the column of the field app's file
  that gives each field of a visit, for forms whose questions are named otherwise. Reading a file also warns of a typed date that differs from the day of the entry and of a jump in the session numbers, says as notes the sites of
  the trip before not visited on this one, the visits where nothing was collected and those with no photo count, leaves a report (`visits_import_<day>_<time>.txt`) beside the visits, and treats a row with the session, site, camera and
  actions of a visit already kept as that visit. **Show the deployments** (Register visits) lists the deployments the visits say, closed and still out.
- **The form of a deployment of a visit starts from the same mix as the logs**: `/api/visits/closed` gives each closed visit its `details` — what the two visits say of the deployment, mixed as the FieldworkLog mixes them
  (`Setup: … | Retrieval: …`, the tags and groups of both, the setup's number, both visits' notes in the comments) — and *What the field sheet says* (Import deployment and Import session) fills the form with it.
- **Registering a visit makes the folders and the logs**: the folder of each collection the visit changes (with its `collection.json`) gets its `<R000N>_FileTimestampLog.csv` and `<R000N>_FieldworkLog.csv` at once — by hand or from a file —,
  as importing the deployment or the collection did before (`field_logs` in the answer of `/api/visits/save` and `/api/visits/import-csv`).
- **A history of visits for a CSV import** (`history_xlsx` in `/api/visits/import-csv`, `visits_xlsx.py`, new dependency `openpyxl`): the fieldwork datasheet, an `.xlsx`, completes the visits kept before the file's are applied on top of both.
- **A location's timezone (and its summer-time setting) cannot be changed once it is created**: the instants kept for it were worked out with them. The server refuses a different one (`409`), and the form of a location shows them disabled.
- **The time of a visit is kept as an instant**: `when`, ISO 8601 in UTC with a Z (`2024-09-04T11:10:00Z`), in the research project's `visits.json`. The day (`date`) and the
  time (`time`) the forms and the tables show are the wall clock of the visit's location, in the timezone the location says; the API gives both. A `visits.json` kept with a day and
  a time only is moved to instants when it is read (in the timezone its locations say) and written back. A new location is UTC, following summer time, unless it says otherwise.
- **The rules of a visit live in the backend** (`visit_rules`), for the form and for a CSV: by hand a visit is refused (`422`) when its site is not a location of the research project, it is already kept,
  it lacks what its actions ask (the camera, the card left, the photos collected) or its camera or card are not where it says — a Revision, a Desinstallation or a Stolen camera is of the camera that is at the site, unless the visit also installs another. The form of a Revision, a Desinstallation or a Stolen camera comes with that camera chosen and offers no other unless the visit also installs one. A CSV is treated as the field records are: the visits are kept and
  questioned — `warnings` for what is odd (a camera or a card at two sites or in the wrong place, two Revisions in a session, a visit not after the one before, a Revision with 0 photos, an Installation
  with the card of the visit before not collected) and `new_sites` for a site that is not a location, with the distance to the nearest one and the ids one character apart, so a new site is told
  from a misnamed one; the page offers to add it as a location.
- **Import deployment** is a wizard of five stages — origin → images → dates and details → check details → prepare and save —, and can be *of a visit*:
  the **Closed visit** (one with a collected card and no deployment yet) gives the location, the revision, the camera, the site and the period. The SD card is asked in
  the images stage. The chips above each stage fill in as it goes (research project, visit with its range, photos and card, then id, location and dates).
  - Two postvalidation checks against the visit, as strict as the others and turned on or off in Settings › Postvalidation (`sd_card`, `photo_count`): the card is
    the one the visit left, and the photos are those the visit counted. They pass, with a note, when the visit says nothing.
  - *Dates*: a new source, **Visits of the field work**, picked first. **Epicollect5 is no longer a source of the dates** (it still fills the camera, the site and the notes).
  - *More details*: **where do they come from** — what the field sheet says, what the previous deployment says (each with how many fields it found), or by hand. The first two are shown
    as they say and cannot be edited until *Fill in by hand* is picked, which keeps their values. The visits are never changed by what is edited.
  - Importing links the visit to the deployment it gave (`POST /api/visits/link`).
- **Import session of visits**: tick the visits of one session in the origin (the session is the revision), choose the folder of subfolders, link each folder to its visit
  (by the name, editable) with its SD card, and go on as in a single deployment — with the list of folders headed by *N of M have a visit*, a progress bar, All / Missing / Ready
  and a filter. The locations are the visits', so *Where were they taken?* is left out. Without closed visits it works as before.
- **Check and fix dates and times** (Utils): compares the images of a folder with the period of the visit and shifts a run of images or removes the ones that cannot be trusted; every fix is written down.
- The app uses DM Sans for the text and DM Mono for identifiers, paths, raw dates and codes (Google Fonts).
- **Import deployment**: organize a folder of camera-trap images into the local collections folder
  (`<Documents>/wildintel-uploader/collections/<research project>/<R000N>/<deployment id>`), in a wizard of four
  stages: images → origin and dates → check details → prepare and save.
  - *Validate*: corrupted images, shooting order vs. filename sequence, folder structure, same camera,
    required EXIF fields and duplicate images — each one optional, and each one can be required to continue.
  - *Origin*: the research project and location, picked from the collections folder, added by hand or
    taken from Trapper.
  - *Details*: the deployment's id from its revision (`R0003-DONA_01`), the period with its timezone and
    Camtrap DP's own fields, validated in the browser and in the backend.
    It says when that deployment already exists in the collections folder, and, when an earlier revision of it
    was kept, offers to fill the form in from it (everything but the start and end dates).
  - *Postvalidation*: the naming and the dates against wildintel-tools' rules, and statistical checks
    (number of images, of sequences and their length) against the previous revisions of the location.
  - *Preprocessing*: renaming, resizing to a width and XMP metadata (as wildintel-tools did), listed before
    the import; `preprocessing.json` records what was done to each image, with its hashes (`source_hash`
    of the original, `hash` of the image kept, `final_hash` of the file with its metadata).
  - The camera model and id are read with ExifTool (Pillow without it) — the executables ship with their
    own copy; the collection's
    `<COLLECTION>_FileTimestampLog.csv` is kept up to date.
  - After a good import, a button opens the folder in the file explorer.
- **Import session**: a folder with one subfolder per deployment. The revision, the checks and the
  preprocessing are common; the location, the dates and the rest of the details are asked for each
  deployment, with a filterable list for big sessions, "next incomplete", and filling the details from the
  previous revision of the same deployment (one or all).
  - If the session folder has a `<COLLECTION>_FileTimestampLog.csv` (the file wildintel-tools asks for beside
    a collection's deployments), the start and end of each deployment it has a row for are taken from it
    instead of from the images' EXIF, and the *Details* step says so. See `examples/session_example_timestamp_log`.
- The timezone and the summer-time ("ignore DST") setting belong to the **location**, never to a deployment: the details
  no longer ask for them, nor does any request carry them. They are said, in bold, in a sentence before the details
  (the location, its GPS coordinates, its timezone and whether it ignores summer time), and the images are read and
  the deployment registered in the ones the location has kept. New locations ask for both; a location without a
  timezone is reported instead of guessing one (`/api/deployment-import/locations/update` still changes them).
- The *revision* of a deployment (and of a session) starts as the next one expected — one after the highest kept for the
  location (`/api/deployment-import/next-revision`) — and says so; it can be changed.
- Once a deployment or a session is imported, an **Upload to Trapper** button goes to the upload page with the research
  project and the collection already chosen. Pressing the title in the navbar goes back to the welcome screen.
- **Upload deployment to Trapper**: pick a collection kept locally and upload its deployments — creating the
  location and the deployment in Trapper if they are missing, packing the images in zip + yaml parts and
  sending them. A *dry run* says what would be done changing nothing, and *only generate the files* writes the
  zips, the yamls and the collection's deployments csv to leave them for later.
  A *Test connection* button checks, changing nothing, that the account reaches the research project, its locations
  (and which of the deployments' own would be created) and the uploader's login, each one reported on its own.
  The collection's yaml names the research project's *classification project* (picked under the deployments, or the only
  one it has; typed by pk when generating without an account) — not the research project's own pk.
  The package names the deployment in lower case, as Trapper keeps it, and declares the timezone and summer-time
  setting of the location it goes to (Trapper refuses a package that disagrees with it).
- **Epicollect5 entries**: when the entry of the Epicollect5 form (one row per deployment) of a location and revision exists — the newest one is used — *When was it collected?* offers to fill in the camera, the site and the notes from it, through the mapping of Settings › Epicollect5 (its *When* group keeps the day and the time apart and maps the revision; *Test connection* tries the project and client type). When Epicollect5 is on but has no entry, a warning says so and opens its settings.
- **Epicollect5 settings**: a switch turns the use of Epicollect5 on or off (off by default), and another sends what an entry answers in inputs with no mapping to the comments of the deployment. *When was it collected?* says when Epicollect5 has an entry for the location and revision.
- **Upload to Trapper**: an option deletes the package files — the zips, the yamls and the deployment's row of the deployments csv — once they are up; without it they are kept (and the csv written) in the packages folder, and the result says where. The deployment's row of a collection's *FileTimestampLog* is written in lower case, as Trapper keeps its ids.
- **Folders**: *Settings › General* sets a folder of their own for the collections, the reports and the packages (`DATA.collections_dir`, `DATA.reports_dir`, `DATA.packages_dir`); blank, each stays in its folder inside the data folder, in Documents. The sessions in progress live in the system's state folder (`~/.local/state/wildintel-uploader/sessions` on Linux) and the log file in its log folder (`~/.local/state/wildintel-uploader/log`); neither can be changed, and what was in Documents or beside `settings.toml` is moved there at start.
- **About the app** (*Settings › General*): the name and the version, the update check and links to report a problem (a GitHub issue that already says the version), the documentation, the source code and the release notes.
- **Session scan and the timestamp log**: the scan says whether it found the `<collection>_FileTimestampLog.csv` (and that its dates are imported), warns when it did not, and — after the table of folders, by name — when entries of it have no folder, and the table of folders has a column saying which are in the log. Messages in boxes (warnings, results, notices) all have the icon of their kind; *Skip*, *Warn* and *Must pass* are blue, yellow and red; every step has its Back beside its Continue.
- **Where the dates come from**: each deployment's start and end are taken from one source, chosen in a picker shared by *Import deployment* (Epicollect5 → the images' EXIF → by hand) and *Import session* (Epicollect5 → the timestamp log → EXIF → by hand). The dates can only be edited with *Manual entry*, and a source the user picked is never replaced by another.
- **Icons**: the ticks and warnings in front of sentences, in the round badges of the steps and in the figures of the dashboards are the same line icons as the boxed messages, not text glyphs (✔, ⚠).
- **Select all / Deselect all** in the lists of Trapper's research projects and locations. Locations that already exist are reused, not created again.
- **Boxed messages** share one component with the icon of their kind (success, info, warning, error); the checks' *Skip*, *Warn* and *Must pass* are blue, yellow and red; every *Continue* has a *Back* beside it, and *Start over* sits with the other buttons.
- **Results of the postvalidation of a session** are laid out like those of the folders: figures, a message, *By deployment* / *By check*, and for each deployment the checks it failed with *View the images* and *Download report*.
- **Upload results**: what was uploaded and what failed are in one list — a failure with its reason —, with counts of the deployments uploaded and failed and of the locations and deployments created in Trapper, the date of the run and its report — kept with the others in *Settings › Reports* (kind *Upload*, `POST /api/upload/report`) — to download.
- **Locations of someone else**: Trapper only takes a deployment whose location the account owns or manages. The dry run warns when the location may not be usable (it goes by the owner and by whether Trapper offers the account to delete it — the managers are not listed), and when Trapper refuses the deployment the error says who owns the location.
- `examples/session_example_faulty`: a session with a fault in every folder (corrupted, unordered, subfolders, mixed cameras, missing EXIF, duplicates) and a timestamp log that does not fit.
- **Utils** (menu): *Repair local deployments* and *Sync local collections* are kept under one button, apart from the import and upload tasks.
- **Sync local collections**: pick a research project and one of its classification projects in Trapper, and the collections
  folder gets what it lacks — the research project (`research_project.json`) and its `locations.json`, the collections
  starting with R (each with its `collection.json` and `<collection>_FileTimestampLog.csv`) and each deployment's
  `deployment.json`, a deployment going to the collection its id starts with. What is already there is kept as it is, nothing is
  changed in Trapper and no image is downloaded unless asked for (*Also download the images from Trapper*: through the classification project's media, four at a time, the ones already there kept), so no `preprocessing.json` is made. Each deployment also gets an `images.json` made
  from what Trapper holds for its images (names, Trapper's pk, when they were taken, observation types, species and tags — not the
  size, the pixels nor the hashes), marked `"source": "trapper"`.
- Every deployment kept locally gets an **`images.json`** beside its `deployment.json`: the number of images, the first and the
  last, and for each one its name (and the original, when renamed), when it was taken — the camera's wall clock, the instant
  and its epoch seconds — the camera, the size and the pixels, and the hashes, for statistics without opening the images again.
  A deployment copied without preprocessing has the names, the EXIF wall-clock time, the size and the pixels.
- Validating and preprocessing the images use several CPUs at once (Settings › General › Workers; by default the
  CPUs the machine has, up to 4).
- **Settings**: General (data folder, log, update check), Trapper (account and test), Validation and
  Postvalidation (each check an entry with a quick switch, and a gear only where it has settings),
  Preprocessing (steps, width, authorship, license, dates) and Config — several settings files to switch
  between.
- Tables of checks have "all" boxes to run, or require, every check at once.
- A command line (`wildintel-uploader`) sharing the settings with the web app.
- **Documentation**: a web and a command-line user manual, a developer manual, features and about pages, with screenshots
  generated by `uv run wucli docs screenshots` (Playwright over the built frontend and a fake backend).
- `tools/make_example_deployment.py` makes a deployment of any number of sample images (3000 by default), each with the
  camera's make, model and serial number and its capture date in the EXIF.
  With `--faulty` it comes with problems for every validation: corrupted and empty images, duplicates, shots out of order, missing
  EXIF, a second camera and a subfolder.

- **Reports**: every validation, postvalidation and preprocessing writes a report of what was checked and done, image by image
  (`<data folder>/reports/*.json`). Each step shows it — the checks with how many images passed and failed, and the images that
  failed with the check and why — and it downloads as a CSV (a row per image and check) or a JSON. A **Reports** task lists the
  reports to look at again or delete.

### Changed
- **Scan** only counts the files and the images of the folder; it no longer opens them. Their dates and camera are read when the
  deployment details open (`/api/deployment-import/guess-details`), so scanning thousands of images is instant.
- The validation step is a dashboard: when it was last run, the valid images, the images with issues and the tests that failed, a table of tests with
  a badge and the number of failed images each, and — opened from one — the images that failed it as thumbnails, with search, filter by error, sort, a
  grid or a list, pages and a view of everything the report says of an image. A report's images are served as thumbnails
  (`/api/reports/{id}/image`).
- **Preprocessing is a step of its own** (`/api/deployment-import/preprocess`), run like the validations, with the same dashboard: the steps to do, a status for each, the images processed and skipped, and the skipped ones as thumbnails. The deployment is left pending — it can be preprocessed again — until the **Import** step consolidates it (`/api/deployment-import/consolidate`): its `deployment.json` is written and it is sealed.
- **Repair local deployments** (new task): a deployment is valid if its `seal.json` still matches it; for the others the metadata files (`deployment.json`, `preprocessing.json`, `images.json`, `seal.json`) are written again from the folder's own contents, the collection's `FileTimestampLog.csv` prevailing over the images' dates, and the images are validated, postvalidated and checked against what preprocessing leaves (`/api/repair/*`, a `repair` report).
- The reports moved from the menu to **Settings › Reports**.
- The deployment's details keep the period always in view and show the rest one section at a time — Camera, Site, Grouping and notes — from a row of buttons (with a red dot on the one that has a wrong field), instead of the *show all fields* checkbox.
- The steps of an upload link to the location, the deployment and the collection in Trapper (`url` in the step events), to check them there.
- The largest zip of an upload (`TRAPPER.max_zip_mb`, 500 MB by default) is set in Settings › Trapper, no longer on the upload page; the upload endpoint no longer takes it.
- Upload: choosing the research project and the collection says whether the configured Trapper account has access to them (`/api/upload/check-selection`); **Test connection** comes after the classification project.
- The postvalidation step has the same dashboard (Run checks); the images out of range or from another camera open as thumbnails.
- The tables of checks have a first column that shows the check running and then how it ended (✔ passed, ⚠ failed, ✘ failed and
  required), and the plain list of results below them is gone: the report is what is shown.
- Settings › Preprocessing › License is a list — CC0, CC BY and CC BY-NC — and shows the URL that is written into each image.
  A license set by hand in `settings.toml` is kept and shown as *Other*.

### Fixed
- A location with the timezone `UTC` (or any other) is accepted on Windows: the app ships the `tzdata` timezone database, which Windows lacks for
  Python's `zoneinfo`, and the executables bundle it.
- Creating a deployment in Trapper no longer fails with *Type error in the cell … deploymentStart*: the CSV's dates are the wall clock of
  the location's timezone, with no `Z` or offset, as Trapper's import form reads them.
- Adding a research project or a location *from Trapper* no longer asks for the credentials: it connects by itself with the
  account saved in the settings, and says so when there isn't one.
- The `*_exiftool_tmp` files ExifTool leaves when it is interrupted writing the metadata are removed.
- The upload's login to Trapper copes with an answer without `results` (the session at the top, or as a cookie) and, when there is
  no session at all, says what Trapper answered instead of failing with a bare `'results'`.
- The frontend type-checks again (`npm run build`): the resume screen knows every task, the Trapper credentials may be left
  blank, and the tests' fixtures follow `SessionSummary`.
