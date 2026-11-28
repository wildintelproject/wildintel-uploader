"""What the answers of the web API are made of (#248): each module says what a route of it answers with a schema of its api_schemas, made from this —
the keys an answer has and the kind of each, which the OpenAPI of the app shows. A key an answer leaves out stays out (the routes answer with
response_model_exclude_unset), and one it holds that its schema does not say yet is passed on as it is, never dropped (extra="allow")."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Answer(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
