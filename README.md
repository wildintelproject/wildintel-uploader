# WildINTEL Uploader

Import camera-trap deployments into [Trapper](https://gitlab.com/trapper-project/trapper) from a
local folder of images — as a web app or from the command line.

Sibling project of [wildintel-zooniverse](https://github.com/wildintelproject/wildintel-zooniverse),
same architecture: a FastAPI backend with a React frontend, packaged into one executable per
platform.

**Today's only feature — import deployment:** pick a local folder of images (copied off the
camera's memory card first, not the card itself), the research project / classification project /
location it belongs to, and its details (dates, camera setup, habitat...) — the same fields
Trapper's own deployment form asks for, most guessed or optional. The images are organized locally
and the deployment is registered in Trapper. Uploading the images themselves isn't part of this
yet.

See the [documentation](https://wildintelproject.github.io/wildintel-uploader/) for the full user
and developer manuals.

## Quick start

```
./setup.sh
uv run wucli dev
```

Or, once packaged, download the executable for your platform from the
[releases page](https://github.com/wildintelproject/wildintel-uploader/releases) — no
installation needed.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
