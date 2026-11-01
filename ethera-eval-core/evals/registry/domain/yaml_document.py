"""Reading an eval.yaml text into plain values, refusing what the Manifest format forbids.

Role: `read_document(text)` turns the text into a mapping of plain values (`str`, lists,
  mappings, and `NON_STRING` for every other scalar) or returns its single document-level
  problem: `malformed`, `unsupported_syntax` or `duplicate_key` (contract §3.3 "Document level",
  D-018, C-5, C-6, C-11).
Used by: `evals.registry.domain.manifest`.
Depends on: PyYAML's safe loader (`yaml.SafeLoader`): its parser for events, its composer for
  nodes, its YAML 1.1 resolver for scalar types — never a constructor of Python objects.
Key invariants: only the safe loader is ever used (D-018); nothing is constructed, so no tag can
  run code. Events are checked BEFORE composing: aliases, anchors and tags are refused and the
  depth is bounded (≤ 10, the top-level mapping being level 1) before the recursive composer
  runs, so no alias expansion or deep nesting can exhaust memory or the stack. A plain scalar is
  a string iff the YAML 1.1 resolver says so (`no`, `on`, `1:30`, `2026-10-30` are not); a
  quoted scalar always is. Problems name a path or `document`, never a submitted value. Pure:
  no I/O, no logging.
"""

from typing import Final, final

import yaml
from yaml import events, nodes

from evals.registry.domain.problems import ManifestProblem, ProblemType, document_problem

MAX_DEPTH = 10
STRING_TAG = "tag:yaml.org,2002:str"


@final
class NonStringScalar:
    """A scalar YAML 1.1 types as something other than a string (bool, null, number, date)."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "NON_STRING"


NON_STRING: Final = NonStringScalar()

type YamlValue = str | NonStringScalar | list[YamlValue] | dict[str, YamlValue]
type YamlMapping = dict[str, YamlValue]


def read_document(text: str) -> YamlMapping | ManifestProblem:
    """The document's top-level mapping, or its one document-level problem."""
    try:
        stream = list(yaml.parse(text, Loader=yaml.SafeLoader))
    except yaml.YAMLError:
        return document_problem(ProblemType.MALFORMED)
    problem = _event_problem(stream)
    if problem is not None:
        return problem
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:  # pragma: no cover - the events above already parsed
        return document_problem(ProblemType.MALFORMED)
    if not isinstance(root, nodes.MappingNode):  # pragma: no cover - checked on the events
        return document_problem(ProblemType.MALFORMED)
    if _has_non_string_key(root):
        return document_problem(ProblemType.UNSUPPORTED_SYNTAX)
    duplicate = _duplicate_key_path(root, "")
    if duplicate is not None:
        return ManifestProblem(duplicate, ProblemType.DUPLICATE_KEY)
    return _mapping(root)


def _event_problem(stream: list[events.Event]) -> ManifestProblem | None:
    documents = sum(isinstance(event, events.DocumentStartEvent) for event in stream)
    if documents != 1 or _depth(stream) > MAX_DEPTH:
        return document_problem(ProblemType.MALFORMED)
    top = next(e for e in stream if isinstance(e, events.NodeEvent))
    if not isinstance(top, events.MappingStartEvent):
        return document_problem(ProblemType.MALFORMED)
    for event in stream:
        if isinstance(event, events.AliasEvent):
            return document_problem(ProblemType.UNSUPPORTED_SYNTAX)
        if isinstance(event, events.NodeEvent) and event.anchor is not None:
            return document_problem(ProblemType.UNSUPPORTED_SYNTAX)
        if isinstance(event, events.ScalarEvent | events.CollectionStartEvent) and _tag(event):
            return document_problem(ProblemType.UNSUPPORTED_SYNTAX)
    return None


def _tag(event: events.ScalarEvent | events.CollectionStartEvent) -> bool:
    """Whether the node carries an explicit tag (`!!str`, `!local`, even a bare `!`)."""
    return event.tag is not None


def _depth(stream: list[events.Event]) -> int:
    depth = deepest = 0
    for event in stream:
        if isinstance(event, events.CollectionStartEvent):
            depth += 1
            deepest = max(deepest, depth)
        elif isinstance(event, events.CollectionEndEvent):
            depth -= 1
    return deepest


def _children(node: nodes.Node) -> list[nodes.Node]:
    if isinstance(node, nodes.SequenceNode):
        return list(node.value)
    if isinstance(node, nodes.MappingNode):
        return [value for _, value in node.value]
    return []


def _has_non_string_key(node: nodes.Node) -> bool:
    """Whether any mapping key is not a string scalar (a merge key `<<` is not one)."""
    if isinstance(node, nodes.MappingNode):
        for key, _ in node.value:
            if not isinstance(key, nodes.ScalarNode) or key.tag != STRING_TAG:
                return True
    return any(_has_non_string_key(child) for child in _children(node))


def _duplicate_key_path(node: nodes.Node, path: str) -> str | None:
    """The path of the first repeated key, depth first in document order."""
    if isinstance(node, nodes.MappingNode):
        seen: set[str] = set()
        for key, value in node.value:
            key_path = join(path, key.value)
            if key.value in seen:
                return key_path
            seen.add(key.value)
            found = _duplicate_key_path(value, key_path)
            if found is not None:
                return found
    elif isinstance(node, nodes.SequenceNode):
        for index, item in enumerate(node.value):
            found = _duplicate_key_path(item, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def join(path: str, key: str) -> str:
    """The path of `key` inside the mapping at `path` (`""` is the top level)."""
    return key if not path else f"{path}.{key}"


def _value(node: nodes.Node) -> YamlValue:
    if isinstance(node, nodes.MappingNode):
        return _mapping(node)
    if isinstance(node, nodes.SequenceNode):
        return [_value(item) for item in node.value]
    return node.value if node.tag == STRING_TAG else NON_STRING


def _mapping(node: nodes.MappingNode) -> YamlMapping:
    return {key.value: _value(value) for key, value in node.value}
