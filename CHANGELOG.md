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
  - The camera model and id are read with ExifTool (Pillow without it); the collection's
    `<COLLECTION>_FileTimestampLog.csv` is kept up to date.
  - After a good import, a button opens the folder in the file explorer.
- **Import session**: a folder with one subfolder per deployment. The revision, the checks and the
  preprocessing are common; the location, the dates and the rest of the details are asked for each
  deployment, with a filterable list for big sessions, "next incomplete", and filling the details from the
  previous revision of the same deployment (one or all).
- **Upload deployment to Trapper**: pick a collection kept locally and upload its deployments — creating the
  location and the deployment in Trapper if they are missing, packing the images in zip + yaml parts and
  sending them. A *dry run* says what would be done changing nothing, and *only generate the files* writes the
  zips, the yamls and the collection's deployments csv to leave them for later.
- Validating and preprocessing the images use several CPUs at once (Settings › General › Workers; by default the
  CPUs the machine has, up to 4).
- **Settings**: General (images folder, log, update check), Trapper (account and test), Validation and
  Postvalidation (each check an entry with a quick switch, and a gear only where it has settings),
  Preprocessing (steps, width, authorship, license, dates) and Config — several settings files to switch
  between.
- Tables of checks have "all" boxes to run, or require, every check at once.
- A command line (`wildintel-uploader`) sharing the settings with the web app.
