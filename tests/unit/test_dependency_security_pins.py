"""
Security pins for patched dependencies.

These packages were bumped to versions that close the referenced advisories
(GHSA/PYSEC entries). This test guards the manifest minima so the fixes are
not silently relaxed by future dependency edits.
"""
import json
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Fixed versions required to address the advisories.
PYTHON_MINIMUM = {
    "langgraph": "0.3.15",
    "langchain-core": "1.2.5",
    "sentence-transformers": "5.6.0",
}

FRONTEND_FIXED = {
    "js-yaml": "4.3.2",
}


def _version_key(version: str) -> tuple:
    return tuple(int(part) for part in version.split("."))


def _pyproject_pin(package: str) -> str:
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        data = tomllib.load(fh)
    for dependency in data["project"]["dependencies"]:
        name = dependency.split(">=", 1)[0].strip(' "\'')
        if name == package:
            return dependency.split(">=", 1)[1].strip(' "\'')
    raise AssertionError(f"{package} missing from pyproject.toml")


def test_python_dependency_security_pins():
    """Python manifests must not drop below the patched versions."""
    for package, fixed in PYTHON_MINIMUM.items():
        declared = _pyproject_pin(package)
        assert _version_key(declared) >= _version_key(fixed), (
            f"{package} pinned at {declared}; the CVE fix requires >= {fixed}"
        )


def test_frontend_lockfile_security_pins():
    """Frontend lockfile must resolve patched transitive versions."""
    lock_path = REPO_ROOT / "frontend" / "package-lock.json"
    lock = json.loads(lock_path.read_text())
    for package, fixed in FRONTEND_FIXED.items():
        entry = lock["packages"][f"node_modules/{package}"]
        assert entry["version"] == fixed, (
            f"{package} at {entry['version']}; the CVE fix requires {fixed}"
        )
