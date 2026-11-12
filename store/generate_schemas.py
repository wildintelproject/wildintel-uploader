"""Writes the JSON Schemas of what the app keeps (store/files/*.schema.json), from the models the app itself validates with.

    .venv/bin/python store/generate_schemas.py

The schemas are as the JSON files are *kept* — not as the API takes them: a visit says `when` (an instant) and not `date` and `time`, and what it points to by id (`location_ref`…).
JSON Schema cannot say everything (a value unique among the items, a reference to another file, what a status allows): that goes in each schema as `x-…` keywords —
`x-file`, `x-unique`, `x-references`, `x-rules` — which a validator ignores and a person reads. Nothing here is used by the app: it is a description to have at hand.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from wildintel_uploader.core.config import Camera, SdCard, Settings, Trapper, TrapperRole
from wildintel_uploader.core.schemas.requests import DeploymentFields, LocationRecord, ResearchProjectRecord, VisitRecord

OUT = Path(__file__).parent / "files"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
UUID = {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"}
INSTANT = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", "description": "ISO 8601, UTC, with a Z — written by the app, never typed."}
DAY = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
AUDIT = {
    "id": {**UUID, "description": "Its internal id: a UUID the app generates when it is kept. It never changes, and what points to the record points to it."},
    "created_at": {**INSTANT, "description": "When it was kept here."},
    "updated_at": {**INSTANT, "description": "When it was last changed."},
    "deleted_at": {**INSTANT, "description": "When it was removed, if it was. Nothing is deleted: a removed record stays, with all it said, and is no longer listed."},
}


def clean(node):
    """A schema of pydantic with what is noise left out: the titles of the fields and the `default`s."""
    if isinstance(node, dict):
        return {k: clean(v) for k, v in node.items() if k not in ("title", "default")}
    if isinstance(node, list):
        return [clean(v) for v in node]
    return node


def model(cls) -> dict:
    return clean(cls.model_json_schema(mode="validation"))


def with_audit(schema: dict) -> dict:
    schema = copy.deepcopy(schema)
    for name, spec in AUDIT.items():
        schema["properties"].setdefault(name, spec)
    return schema


def document(name: str, title: str, description: str, body: dict, *, as_list: bool = True, file: str, **extra) -> None:
    """Writes store/files/<name>.schema.json — the file is a list of `body`, or one `body`."""
    defs = body.pop("$defs", None)
    root: dict = {"$schema": DRAFT, "$id": f"{name}.schema.json", "title": title, "description": description, "x-file": file, **extra}
    if as_list:
        root.update({"type": "array", "items": body})
    else:
        root.update(body)
    if defs:
        root["$defs"] = defs
    (OUT / f"{name}.schema.json").write_text(json.dumps(root, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PROJECT = "<collections folder>/<research project id>/"

    # ── the research project ─────────────────────────────────────────────────────────────────────────────────────────────
    project = with_audit(model(ResearchProjectRecord))
    document("research_project", "Research project", "The research project itself: what its folder is called, what it studies and how it was designed. One file for each project.",
             project, as_list=False, file=PROJECT + "research_project.json", **{
                 "x-unique": [["acronym"]], "x-rules": ["The acronym names the project's folder, so it can only have letters, digits, '_', '-' and '.', and starts with a letter or a digit.",
                                                        "A project is not deleted: its status is archived."]})

    # ── what belongs to a research project ───────────────────────────────────────────────────────────────────────────────
    locations = with_audit(model(LocationRecord))
    document("locations", "Locations", "The places of a research project where the cameras are put up. A location is also a site of Camtrap DP.", locations,
             file=PROJECT + "locations.json", **{
                 "x-unique": [["location_id"]], "x-rules": [
                     "location_id is unique in the research project, whatever its case.",
                     "A location that is deleted keeps its id: the visits that point to it still do.",
                     "timezone is an IANA name (Europe/Madrid); ignore_dst says whether its cameras ignore summer time — the day and the time of its visits are told on that wall clock.",
                     "An archived location is not expected in the revisions that start after status_date (with no date, after it was made)."]})

    cameras = with_audit(model(Camera))
    cameras["properties"].pop("research_project", None)     # not kept: the file is the project's
    document("cameras", "Cameras", "The cameras of a research project. What a visit does to a camera (put it up, take it away, find it stolen) is what changes its status.", cameras,
             file=PROJECT + "cameras.json", **{
                 "x-unique": [["label"], ["camera_id"]], "x-rules": [
                     "label is unique in the research project, whatever its case; so is camera_id when it has one.",
                     "An archived camera says why (archive_reason): lost, stolen, broken or other. It never goes back to planned, ready or active.",
                     "status: ready (available, not in the field), active (it is up at a location); the visits change it, not a person.",
                     "A camera can be up at one location at a time."]})

    cards = with_audit(model(SdCard))
    cards["properties"].pop("research_project", None)
    document("sd_cards", "SD cards", "The SD cards of a research project.", cards, file=PROJECT + "sd_cards.json", **{
        "x-unique": [["label"]], "x-rules": [
            "label is unique in the research project, whatever its case.",
            "Only a ready card can be left in a camera; a card is active while it is in one and is ready again when a visit collects it.",
            "An archived card says why (archive_reason). It never goes back to planned, ready or active.",
            "A card collected in a revision cannot be left again in the same revision."]})

    roles = with_audit(model(TrapperRole))
    roles["properties"].pop("research_project", None)
    roles["properties"]["trapper_ref"] = {**UUID, "description": "The id of the trapper — when it is in the list of trappers; the name is then not kept."}
    roles["properties"]["trapper"] = {"type": "string", "minLength": 1, "description": "The name of the trapper, when it is not in the list of trappers."}
    roles["required"] = ["role"]
    roles["anyOf"] = [{"required": ["trapper_ref"]}, {"required": ["trapper"]}]
    document("roles", "Roles", "What a trapper is in a research project (a contributor of Camtrap DP).", roles, file=PROJECT + "roles.json", **{
        "x-unique": [["trapper_ref", "role"]], "x-references": {"trapper_ref": "trappers.id"}})

    # ── the visits ───────────────────────────────────────────────────────────────────────────────────────────────────────
    visit = with_audit(model(VisitRecord))
    props = visit["properties"]
    for told in ("date", "time", "location_id", "camera_id", "sd", "setup_by"):
        props.pop(told, None)
    props["when"] = {**INSTANT, "description": "The instant of the visit — what is kept. The day and the time of the wall clock of its location are worked out from it and its location's timezone."}
    props["location_ref"] = {**UUID, "description": "The location, by id. When the research project has none that is called so, location_id is kept as it was said."}
    props["location_id"] = {"type": "string", "minLength": 1, "maxLength": 100, "description": "The location as it was said — only when the research project has no such location (no location_ref)."}
    props["camera_ref"] = {**UUID, "description": "The camera, by id."}
    props["camera_id"] = {"type": ["string", "null"], "description": "The camera as it was said — only when the research project has no such camera."}
    props["sd_ref"] = {**UUID, "description": "The SD card left in the camera, by id."}
    props["sd"] = {"type": ["string", "null"], "description": "The SD card as it was said — only when the research project has no such card."}
    props["setup_by_ref"] = {**UUID, "description": "Who set the camera up, by id of the trapper."}
    props["setup_by"] = {"type": ["string", "null"], "description": "Who set it up as it was said — only when it is not a trapper."}
    props["trapper_refs"] = {"type": "array", "items": UUID, "uniqueItems": True, "description": "Who went, by id of the trappers."}
    props["trappers"] = {**props["trappers"], "description": "The names of who went that are not trappers of the list, comma separated."}
    visit["required"] = ["session"]
    visit["anyOf"] = [{"required": ["location_ref"]}, {"required": ["location_id"]}]
    document("visits", "Visits", "The visits to the cameras of a research project: the history of the field work, from which its deployments are worked out. A visit has one or more "
             "actions and is made at one location in one revision (R0001, R0002…): a revision is one visit to each location that is not archived.", visit,
             file=PROJECT + "visits.json", **{
                 "x-unique": [["location_ref", "session"], ["location_id", "session"]],
                 "x-references": {"location_ref": "locations.id", "camera_ref": "cameras.id", "sd_ref": "sd_cards.id", "setup_by_ref": "trappers.id", "trapper_refs[]": "trappers.id",
                                  "deployment_id": "<collections folder>/<research project id>/<R000N>/<deployment id>/deployment.json"},
                 "x-rules": [
                     "A location has one visit in a revision, and a visit is after the last one to its location and after every visit of the revisions before its own.",
                     "A revision starts when the one before it is finished: every location that is not archived has its visit in it — made, or marked as not visited (camera_status Not revised, no actions). "
                     "An unknown visit (unknown_visits.json) counts as one.",
                     "The first visit to a location can only be an Installation, unless the revisions before are unknown.",
                     "A camera is up at one location at a time; a card is in one camera at a time. A Revision or a Desinstallation collects the card that was in the camera.",
                     "state is worked out from the visits (see visit_deployments.refresh_states): deployed, collected, stolen, not_visited or no_camera.",
                     "deployment_id is the deployment the visit started — the images of the card it left, once they are imported; it is kept by the app.",
                     "latitude and longitude are where the trapper was when the visit was noted: they are not those of the location."]})

    unknown = {"type": "object", "additionalProperties": False, "required": ["session"], "properties": {
        "location_ref": {**UUID, "description": "The location, by id."}, "location_id": {"type": "string", "minLength": 1, "description": "The location as it was said, when it is not one of the project's."},
        "session": {"type": "string", "pattern": r"^R\d+$"}}, "anyOf": [{"required": ["location_ref"]}, {"required": ["location_id"]}]}
    document("unknown_visits", "Unknown visits", "The visits that nothing is known of — no day, no camera, no card — to a location in a revision before its first known visit. "
             "They count as visits to finish a revision, but nothing can be checked against them. A real visit that comes later takes the place of its unknown one.", unknown,
             file=PROJECT + "unknown_visits.json", **{"x-unique": [["location_ref", "session"]], "x-references": {"location_ref": "locations.id"},
                                                       "x-rules": ["Only for a revision before the first known visit of the location."]})

    failures = {"type": "object", "additionalProperties": False, "required": ["deployment_id", "destination"], "properties": {
        "deployment_id": {"type": "string", "minLength": 1}, "destination": {"type": "string", "minLength": 1, "description": "Where the upload was to go (trapper…)."},
        "note": {"type": ["string", "null"], "description": "Why it failed."}, "at": {"type": "string", "description": "When it was tried, ISO 8601 with its offset."}}}
    document("upload_failures", "Upload failures", "The uploads of the deployments that were tried and failed. An upload that was done is not here, and a success takes the failure away.",
             failures, file=PROJECT + "upload_failures.json", **{"x-unique": [["deployment_id", "destination"]]})

    # ── the people ───────────────────────────────────────────────────────────────────────────────────────────────────────
    trappers = with_audit(model(Trapper))
    document("trappers", "Trappers", "The people who go to the field. They belong to no research project: what each is in a project is its role.", trappers,
             file="<collections folder>/trappers.json", **{"x-unique": [["username"], ["name"]], "x-rules": [
                 "username is unique whatever its case, and has no spaces.", "An inactive trapper is no longer suggested; an archived one is out of use. One taken from Trapper (trapper_pk) can only be seen here."]})

    # ── what is written beside the images ────────────────────────────────────────────────────────────────────────────────
    document("collection", "Collection", "A collection — a revision: R0001, R0002… — of a research project. Its folder holds its deployments.",
             {"type": "object", "additionalProperties": False, "required": ["name"], "properties": {"name": {"type": "string", "pattern": r"^R\d+$"}}},
             as_list=False, file=PROJECT + "<R000N>/collection.json")
    deployment = model(DeploymentFields)
    document("deployment", "Deployment", "A deployment, as Camtrap DP names its fields: where a camera was, from when to when, and how. Kept beside its images. Its images, "
             "their metadata (images.json) and how they were prepared (preprocessing.json) are files, not records.", deployment, as_list=False,
             file=PROJECT + "<R000N>/<deployment id>/deployment.json", **{
                 "x-unique": [["deployment_id"]], "x-references": {"location_id": "locations.location_id"},
                 "x-rules": ["deployment_id is <R000N>-<location id>: the revision, a dash and the location.", "camera_height and camera_depth are mutually exclusive.",
                             "start_date and end_date are ISO 8601 with the offset of the location's timezone; the end is after the start."]})

    # ── the settings ─────────────────────────────────────────────────────────────────────────────────────────────────────
    settings = clean(Settings.model_json_schema(mode="validation"))
    document("settings", "Settings", "The settings of the app: kept in settings.toml of the user's configuration folder, not in the collections folder. It has the connection to Trapper "
             "and the like, so what is kept of them is a secret.", settings, as_list=False, file="<user configuration folder>/settings.toml")
    print(f"{len(list(OUT.glob('*.schema.json')))} schemas in {OUT}")


if __name__ == "__main__":
    main()
