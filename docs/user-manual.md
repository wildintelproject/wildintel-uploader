# User Manual

## Import a deployment

Both the web app and the command line walk through the same steps:

1. **Connect to Trapper** — your server URL, username and password (saved after the first
   successful connection, so you won't be asked again).
2. **Source folder** — the local folder with the deployment's images.

    !!! warning "Copy the images locally first"
        Don't point this at the camera's memory card directly — copy the images to a folder on
        your computer first. This app only *reads* the source folder (nothing in it is changed or
        moved), but working from the card itself is slow and risks losing files if the card is
        removed mid-import.

3. **Research project, classification project and location** — picked from your Trapper account.
   The classification project is optional.
4. **Deployment details** — a deployment id, the start/end dates (guessed from the images' EXIF
   data, editable), and the rest of the fields Trapper's own deployment form asks for: camera
   setup (id, model, delay, height, tilt, heading, detection distance), bait, habitat, feature
   type, and comments. Only the deployment id and start date are required — leave the rest blank
   to fill them in later, directly in Trapper.
5. **Import** — the images are copied into this app's own data folder (organized by deployment id,
   never touching the source folder), and the deployment is registered in Trapper.

Uploading the images themselves to Trapper isn't part of this yet — after the import, they're
organized locally, ready for whatever comes next.

## Command line

The same flow, interactively:

```
wildintel-uploader import-deployment
```

Other commands:

```
wildintel-uploader test-connection
wildintel-uploader trapper research-projects
wildintel-uploader trapper classification-projects --rp <pk>
wildintel-uploader trapper locations --rp <pk>
wildintel-uploader config show
wildintel-uploader config set TRAPPER.base_url https://trapper.example.org
```
