# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Upcoming release

### Added
- **Import deployment**: organize a folder of camera-trap images into the local collections folder
  (`<Documents>/wildintel-uploader/collections/<research project>/<R000N>/<deployment id>`), in a wizard:
  folder → validate → origin → details → postvalidation → preprocessing → import.
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
- **Sync local collections**: pick a research project and one of its classification projects in Trapper, and the collections
  folder gets what it lacks — the research project (`research_project.json`) and its `locations.json`, the collections
  starting with R (each with its `collection.json` and `<collection>_FileTimestampLog.csv`) and each deployment's
  `deployment.json`, a deployment going to the collection its id starts with. What is already there is kept as it is, nothing is
  changed in Trapper and no image is downloaded, so no `preprocessing.json` is made. Each deployment also gets an `images.json` made
  from what Trapper holds for its images (names, Trapper's pk, when they were taken, observation types, species and tags — not the
  size, the pixels nor the hashes), marked `"source": "trapper"`. **Upload session to Trapper** is listed as
  coming soon.
- Every deployment kept locally gets an **`images.json`** beside its `deployment.json`: the number of images, the first and the
  last, and for each one its name (and the original, when renamed), when it was taken — the camera's wall clock, the instant
  and its epoch seconds — the camera, the size and the pixels, and the hashes, for statistics without opening the images again.
  A deployment copied without preprocessing has the names, the EXIF wall-clock time, the size and the pixels.
- Validating and preprocessing the images use several CPUs at once (Settings › General › Workers; by default the
  CPUs the machine has, up to 4).
- **Settings**: General (images folder, log, update check), Trapper (account and test), Validation and
  Postvalidation (each check an entry with a quick switch, and a gear only where it has settings),
  Preprocessing (steps, width, authorship, license, dates) and Config — several settings files to switch
  between.
- Tables of checks have "all" boxes to run, or require, every check at once.
- A command line (`wildintel-uploader`) sharing the settings with the web app.
- **Documentation**: a web and a command-line user manual, a developer manual, features and about pages, with screenshots
  generated by `uv run wucli docs screenshots` (Playwright over the built frontend and a fake backend).
- `tools/make_example_deployment.py` makes a deployment of any number of sample images (3000 by default), each with the
  camera's make, model and serial number and its capture date in the EXIF.

### Changed
- Settings › Preprocessing › License is a list — CC0, CC BY and CC BY-NC — and shows the URL that is written into each image.
  A license set by hand in `settings.toml` is kept and shown as *Other*.

### Fixed
- The frontend type-checks again (`npm run build`): the resume screen knows every task, the Trapper credentials may be left
  blank, and the tests' fixtures follow `SessionSummary`.
