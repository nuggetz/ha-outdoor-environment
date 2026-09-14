"""Guards for the locally defined unit strings.

The component declares its own unit literals instead of importing the deprecated
``CONCENTRATION_*`` aliases (issue #11) or the ``UnitOfDensity`` / ``UnitOfRatio``
members, which only exist from HA 2026.7.0 and would raise the declared minimum.
Both halves of that trade-off need a guard: the literals must keep matching the
enums, and the deprecated names must not come back.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from homeassistant.const import UnitOfDensity

from custom_components.outdoor_environment.const import (
    UNIT_MICROGRAMS_PER_CUBIC_METER,
    UNIT_PARTS_PER_MILLION,
)

_COMPONENT = pathlib.Path(__file__).parent.parent


def test_micrograms_matches_homeassistant_enum():
    """Our literal must be byte-identical to the enum, or statistics would split."""
    member = getattr(UnitOfDensity, "MICROGRAMS_PER_CUBIC_METER", None)
    if member is None:
        pytest.skip("UnitOfDensity.MICROGRAMS_PER_CUBIC_METER needs HA 2026.7.0+")
    assert UNIT_MICROGRAMS_PER_CUBIC_METER == member.value


def test_parts_per_million_matches_homeassistant_enum():
    try:
        from homeassistant.const import UnitOfRatio
    except ImportError:
        pytest.skip("UnitOfRatio needs HA 2026.7.0+")
    assert UNIT_PARTS_PER_MILLION == UnitOfRatio.PARTS_PER_MILLION.value


def test_no_deprecated_concentration_constants_are_referenced():
    """Re-importing them would log a deprecation warning on every recent HA."""
    offenders: list[str] = []
    for path in sorted(_COMPONENT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name.startswith("CONCENTRATION_"):
                        offenders.append(f"{path.name}:{node.lineno} {alias.name}")
                continue
            if name and name.startswith("CONCENTRATION_"):
                offenders.append(f"{path.name}:{node.lineno} {name}")
    assert not offenders, f"deprecated constants are back: {offenders}"
