"""Load the JSON contracts in clean/contracts/ and check they fit together before any Spark work.

- source_contracts.json: per entity, the raw endpoints, the item schema and raw field -> target
- target_fields.json: per target field, its data type, profile, policy and whether required
- normalization_policies.json: thresholds used by the normalizers
- table_policies.json: rules on whole tables (leaky comments, duplicates, split)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any

from .normalizers.registry import get_normalizer

ENTITIES = ("question", "answer", "comment")


@dataclass(frozen=True)
class Contracts:
    sources: dict[str, Any]
    targets: dict[str, Any]
    policies: dict[str, Any]
    tables: dict[str, Any]


def _read(name: str) -> dict[str, Any]:
    text = resources.files(__package__).joinpath("contracts", name).read_text(encoding="utf-8")
    return json.loads(text)


def load_contracts() -> Contracts:
    contracts = Contracts(
        sources=_read("source_contracts.json"),
        targets=_read("target_fields.json"),
        policies=_read("normalization_policies.json"),
        tables=_read("table_policies.json"),
    )
    validate(contracts)
    return contracts


def validate(c: Contracts) -> None:
    used_targets: set[str] = set()
    for entity in ENTITIES:
        source = c.sources[entity]
        for key in ("endpoints", "id_field", "item_schema", "fields"):
            if key not in source:
                raise ValueError(f"source contract {entity} is missing {key}")
        if source["id_field"] not in source["fields"].values():
            raise ValueError(f"{entity}: id_field {source['id_field']} is not a target field")
        for path, target in source["fields"].items():
            if target not in c.targets:
                raise ValueError(f"{entity}.{path}: unknown target field {target}")
            used_targets.add(target)

    for target, spec in c.targets.items():
        normalizer = get_normalizer(spec["target_type"], spec["profile"])
        if spec["policy"] not in c.policies:
            raise ValueError(f"target {target}: unknown policy {spec['policy']}")
        normalizer.validate_policy(spec["policy"], c.policies[spec["policy"]])
        if not isinstance(spec.get("required"), bool):
            raise ValueError(f"target {target}: required must be true or false")

    unused = sorted(set(c.targets) - used_targets)
    if unused:
        raise ValueError(f"target fields not mapped from any source: {unused}")

    ratios = c.tables["split"]["ratios"]
    if abs(sum(ratios.values()) - 1.0) > 1e-9:
        raise ValueError(f"split ratios must sum to 1, got {ratios}")
    if c.tables["split"]["large_group_split"] not in ratios:
        raise ValueError("split.large_group_split must be one of the split names")
