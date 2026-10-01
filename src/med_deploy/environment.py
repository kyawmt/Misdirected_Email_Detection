"""What is installed, and does it match constraints.txt?

Reports the interpreter, every installed third-party distribution compared
with its pin, whether pyarrow is importable (with pyarrow, pandas 3 stores
strings in Arrow and the scoring pipeline runs about three times slower with
identical results), and the string storage pandas actually uses. It reads
metadata only and imports nothing of the scoring pipeline.
"""

from __future__ import annotations

import importlib.metadata as metadata
import importlib.util
import platform
import re
from pathlib import Path

from med_deploy.version import TESTED_PYTHON

PROJECT_DISTRIBUTION = "med-data"
# Installed by the Python image or by venv, never pinned: they build and install the rest.
TOOLING = frozenset({"pip", "setuptools", "wheel"})
KEY_PACKAGES = ("numpy", "pandas", "scikit-learn", "scipy", "fastapi", "uvicorn", "httpx", "streamlit", "pyarrow", "pytest")


def normalize(name: str) -> str:
    """PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_constraints(path: Path) -> dict[str, str]:
    """`name==version` lines of a constraints file. Anything else in it is an error."""
    pins: dict[str, str] = {}
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.+!_-]*)", line)
        if not match:
            raise ValueError(f"{path}:{number}: {line!r} is not an exact name==version pin")
        name = normalize(match.group(1))
        if name == PROJECT_DISTRIBUTION:
            raise ValueError(f"{path}:{number}: the project itself must not be pinned")
        pins[name] = match.group(2)
    return pins


def installed_distributions() -> dict[str, str]:
    """Normalized name to version for every installed distribution."""
    found: dict[str, str] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata["Name"]
        if name:
            found[normalize(name)] = distribution.version
    return found


def third_party(installed: dict[str, str]) -> dict[str, str]:
    return {name: version for name, version in installed.items() if name != PROJECT_DISTRIBUTION and name not in TOOLING}


def freeze_lines() -> list[str]:
    """The installed third-party packages as `name==version` (original names, sorted like `pip freeze`)."""
    shown = {}
    for distribution in metadata.distributions():
        name = distribution.metadata["Name"]
        if name and normalize(name) != PROJECT_DISTRIBUTION and normalize(name) not in TOOLING:
            shown[name.lower()] = f"{name}=={distribution.version}"
    return [shown[key] for key in sorted(shown)]


def pandas_string_storage() -> dict | None:
    if importlib.util.find_spec("pandas") is None:
        return None
    import pandas as pd

    series = pd.Series(["a"])
    # The class that holds the strings: an Arrow-backed array when pyarrow is importable, a Python-backed one otherwise.
    return {"option": str(pd.get_option("mode.string_storage")), "series_dtype": str(series.dtype), "backend": type(series.array).__name__}


def snapshot(constraints: Path | None = None) -> dict:
    """The environment as a record. With `constraints`, every installed package is compared with its pin."""
    installed = third_party(installed_distributions())
    pyarrow = importlib.util.find_spec("pyarrow") is not None
    result: dict = {
        "kind": "environment",
        "python": platform.python_version(),
        "python_matches_tested": platform.python_version() == TESTED_PYTHON,
        "tested_python": TESTED_PYTHON,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "project_version": installed_distributions().get(PROJECT_DISTRIBUTION),
        "packages": len(installed),
        "key_packages": {name: installed[name] for name in KEY_PACKAGES if name in installed},
        "pyarrow_importable": pyarrow,
        "pyarrow_version": installed.get("pyarrow"),
        "pandas_string_storage": pandas_string_storage(),
    }
    if constraints is not None:
        pins = parse_constraints(constraints)
        result["constraints"] = {
            "file": Path(constraints).as_posix(),
            "pinned": len(pins),
            "installed_but_not_pinned": sorted(name for name in installed if name not in pins),
            "version_differs": {name: {"installed": installed[name], "pinned": pins[name]} for name in sorted(installed) if name in pins and installed[name] != pins[name]},
            "pinned_but_not_installed": sorted(name for name in pins if name not in installed),
        }
        result["matches_constraints"] = not result["constraints"]["installed_but_not_pinned"] and not result["constraints"]["version_differs"]
    return result
