# WildINTEL Uploader

Import camera-trap deployments into [Trapper](https://gitlab.com/trapper-project/trapper) from a
local folder of images — as a web app or from the command line.

## What it does today

**Import deployment** — the only option so far:

1. Pick a local folder of images (copy them off the camera's memory card first; don't point this
   at the card itself).
2. Pick the research project, classification project and location the deployment belongs to.
3. Fill in the deployment's details — the same fields Trapper's own deployment form asks for
   (dates, camera setup, habitat, bait, comments...). Start/end dates and the camera model are
   guessed from the images' EXIF data and can be edited.
4. The images are organized into a local folder (nothing in the source folder is touched), and the
   deployment is registered in Trapper.

It does not upload the images themselves to Trapper yet — that's a separate option this app
doesn't have.

## Getting started

See the [User Manual](user-manual.md) for how to run an import, or the
[Developer Manual](developer-manual.md) to set the project up locally.
