"""What is read from the raw API responses, and what each field becomes.

Each table has:
- endpoints: folders in data/raw to read
- id_field: the raw field that identifies a record
- item_schema: the raw fields to parse (anything else in the response is ignored)
- fields: one line per field to clean, in the form
      (raw field, clean column, kind, required)
  `kind` says how the value is cleaned, see clean_field() in normalize.py. A row whose required
  field is missing is rejected.
"""

from __future__ import annotations

QUESTION = {
    "endpoints": ["questions", "questions_linked", "questions_by_id"],
    "id_field": "question_id",
    "item_schema": (
        "question_id BIGINT, title STRING, body STRING, tags ARRAY<STRING>, score BIGINT, "
        "view_count BIGINT, answer_count BIGINT, comment_count BIGINT, creation_date BIGINT, "
        "closed_date BIGINT, closed_reason STRING, link STRING, "
        "owner STRUCT<user_type: STRING>, "
        "closed_details STRUCT<original_questions: ARRAY<STRUCT<question_id: BIGINT>>>"
    ),
    "fields": [
        ("question_id", "question_id", "id", True),
        ("title", "title", "title", True),
        ("body", "body_text", "body", True),
        ("tags", "tags", "tags", True),
        ("score", "score", "score", True),
        ("view_count", "view_count", "count", False),
        ("answer_count", "api_answer_count", "count", False),
        ("comment_count", "api_comment_count", "count", False),
        ("creation_date", "creation_date", "date", True),
        ("closed_date", "closed_date", "date", False),
        ("closed_reason", "closed_reason", "closed_reason", False),
        ("link", "link", "link", False),
        ("owner.user_type", "owner_user_type", "user_type", False),
    ],
}

ANSWER = {
    "endpoints": ["answers"],
    "id_field": "answer_id",
    "item_schema": (
        "answer_id BIGINT, question_id BIGINT, body STRING, score BIGINT, is_accepted BOOLEAN, "
        "comment_count BIGINT, creation_date BIGINT, owner STRUCT<user_type: STRING>"
    ),
    "fields": [
        ("answer_id", "answer_id", "id", True),
        ("question_id", "question_id", "id", True),
        ("body", "body_text", "body", True),
        ("score", "score", "score", True),
        ("is_accepted", "is_accepted", "boolean", True),
        ("creation_date", "creation_date", "date", True),
        ("owner.user_type", "owner_user_type", "user_type", False),
    ],
}

COMMENT = {
    "endpoints": ["question_comments", "answer_comments"],
    "id_field": "comment_id",
    "item_schema": (
        "comment_id BIGINT, post_id BIGINT, body STRING, score BIGINT, creation_date BIGINT, "
        "owner STRUCT<user_type: STRING>"
    ),
    "fields": [
        ("comment_id", "comment_id", "id", True),
        ("post_id", "post_id", "id", True),
        ("body", "text", "comment_text", True),
        ("score", "score", "score", True),
        ("creation_date", "creation_date", "date", True),
        ("owner.user_type", "owner_user_type", "user_type", False),
    ],
}

# Only used as a lookup table for the tags of questions, so there is nothing to clean.
TAG_SYNONYM = {
    "endpoints": ["tag_synonyms"],
    "id_field": "from_tag",
    "item_schema": "from_tag STRING, to_tag STRING",
    "fields": [],
}
