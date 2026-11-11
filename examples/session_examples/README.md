# Example sessions

A session is the images of a whole field trip (a *revision*): one folder per deployment, each with the images of one camera at one site.
They are for trying **Import session** (see also `examples/Epicollect.md`, which uses `timestamp_log_wicp`).
All the images are small (1280×720) and made up.

| Folder | Deployments | What is in it |
|---|---|---|
| [`valid`](valid) | `DONA_01` (12 images), `DONA_02` (12), `DONA_03` (8) | A good session, with nothing else: the dates of each deployment come from the images' EXIF (Reconyx HyperFire 2, serial `P900123`). |
| [`timestamp_log`](timestamp_log) | the same three | The same session with a `R0003_FileTimestampLog.csv`: the start and the end of `DONA_01` and `DONA_02` are the camera's wall clock written in the log, not the images' EXIF. `DONA_03` is not in the log, so it falls back to its images. The *Details* step says where each date comes from. |
| [`timestamp_log_wicp`](timestamp_log_wicp) | `wicp_0001` (12), `wicp_0002` (12), `wicp_0003` (8) | The same, for the research project **WICP** of `entities_example/small`: the folders are named as its locations (`wicp_0001` …) and the log is `R0003_FileTimestampLog.csv` (revision 3). The log has `wicp_0001`, `wicp_0002` and `wicp_0004`, but there is no `wicp_0004` folder and `wicp_0003` has no row. |
| [`faulty`](faulty) | `dona_0001` … `dona_0006` (72 images) | A session with a fault in every folder and a log that does not fit it, for the validation to find (see below). |

## `faulty`

| Folder | Fault |
|---|---|
| `dona_0001` | `IMG_0009.JPG` is damaged: it cannot be read. |
| `dona_0002` | Images out of order: their capture times do not grow with their names. |
| `dona_0003` | Some images are in a subfolder (`extra/`, which has another, `old/`) and some numbers are missing from the main folder. |
| `dona_0004` | Images of other cameras (`BRN0045821` ×3, `P900999` ×1) among the camera's own. |
| `dona_0005` | Images without capture date and without serial number. |
| `dona_0006` | Images that are the same file repeated (and two with the same capture time). |

`R0005_FileTimestampLog.csv` is the log of revision 5: it has rows for `dona_0001` … `dona_0004` and for `dona_0007`, but not for `dona_0005`
nor `dona_0006`, and `dona_0007` is not in the session. It is for the log checks to say so.

## How to try them

**Import session** → pick the folder. The revision of a session with a log is the number in the log's name (`3` for `timestamp_log` and
`timestamp_log_wicp`, `5` for `faulty`); `valid` has no log, so its dates come from the images.
