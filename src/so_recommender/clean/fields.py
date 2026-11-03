"""What is read from the raw API responses, and what each field becomes.

`item_schema` lists the raw fields that are parsed (anything else in the response is ignored).
`fields` says, for each raw field: its clean column, how it is cleaned, whether it is required.
"""

from __future__ import annotations

from functools import partial
from typing import NamedTuple

from .normalize import (
    Field,
    boolean,
    enum,
    html_body,
    html_inline,
    integer,
    plain_text,
    tags,
    unix_seconds,
)

ID = partial(integer, output="bigint", min_value=1)
SCORE = partial(integer, output="int")
COUNT = partial(integer, output="int", min_value=0)
TITLE = partial(plain_text, max_length=300)
LINK = partial(plain_text, max_length=2000)
BODY = partial(html_body, code_column="body_code")
USER_TYPE = partial(
    enum,
    allowed=["registered", "unregistered", "moderator", "team_admin", "does_not_exist"],
    flagged=("does_not_exist",),
)
CLOSED_REASON = partial(
    enum,
    allowed=[
        "Duplicate",
        "exact duplicate",
        "Not suitable for this site",
        "Needs details or clarity",
        "Needs more focus",
        "Opinion-based",
        "not constructive",
        "not a real question",
        "off topic",
        "too localized",
    ],
)


class Source(NamedTuple):
    endpoints: list[str]  # folders in data/raw
    id_field: str
    item_schema: str
    fields: list[Field]


QUESTION = Source(
    endpoints=["questions", "questions_linked", "questions_by_id"],
    id_field="question_id",
    item_schema=(
        "question_id BIGINT, title STRING, body STRING, tags ARRAY<STRING>, score BIGINT, "
        "view_count BIGINT, answer_count BIGINT, comment_count BIGINT, creation_date BIGINT, "
        "closed_date BIGINT, closed_reason STRING, link STRING, "
        "owner STRUCT<user_type: STRING>, "
        "closed_details STRUCT<original_questions: ARRAY<STRUCT<question_id: BIGINT>>>"
    ),
    fields=[
        Field("question_id", "question_id", ID, required=True),
        Field("title", "title", TITLE, required=True),
        Field("body", "body_text", BODY, required=True),
        Field("tags", "tags", tags, required=True),
        Field("score", "score", SCORE, required=True),
        Field("view_count", "view_count", COUNT),
        Field("answer_count", "api_answer_count", COUNT),
        Field("comment_count", "api_comment_count", COUNT),
        Field("creation_date", "creation_date", unix_seconds, required=True),
        Field("closed_date", "closed_date", unix_seconds),
        Field("closed_reason", "closed_reason", CLOSED_REASON),
        Field("link", "link", LINK),
        Field("owner.user_type", "owner_user_type", USER_TYPE),
    ],
)

ANSWER = Source(
    endpoints=["answers"],
    id_field="answer_id",
    item_schema=(
        "answer_id BIGINT, question_id BIGINT, body STRING, score BIGINT, is_accepted BOOLEAN, "
        "comment_count BIGINT, creation_date BIGINT, owner STRUCT<user_type: STRING>"
    ),
    fields=[
        Field("answer_id", "answer_id", ID, required=True),
        Field("question_id", "question_id", ID, required=True),
        Field("body", "body_text", BODY, required=True),
        Field("score", "score", SCORE, required=True),
        Field("is_accepted", "is_accepted", boolean, required=True),
        Field("creation_date", "creation_date", unix_seconds, required=True),
        Field("owner.user_type", "owner_user_type", USER_TYPE),
    ],
)

COMMENT = Source(
    endpoints=["question_comments", "answer_comments"],
    id_field="comment_id",
    item_schema=(
        "comment_id BIGINT, post_id BIGINT, body STRING, score BIGINT, creation_date BIGINT, "
        "owner STRUCT<user_type: STRING>"
    ),
    fields=[
        Field("comment_id", "comment_id", ID, required=True),
        Field("post_id", "post_id", ID, required=True),
        Field("body", "text", html_inline, required=True),
        Field("score", "score", SCORE, required=True),
        Field("creation_date", "creation_date", unix_seconds, required=True),
        Field("owner.user_type", "owner_user_type", USER_TYPE),
    ],
)

TAG_SYNONYM = Source(
    endpoints=["tag_synonyms"],
    id_field="from_tag",
    item_schema="from_tag STRING, to_tag STRING",
    fields=[],
)
