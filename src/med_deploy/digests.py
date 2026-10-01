"""Anchor the SHA-256 of the published files that no other checksum covers.

`policy.json` holds the checksums of the model and the feature manifest, the
feature manifest holds the checksums of the feature files, and the dataset
manifest holds those of the tables. Nothing holds a checksum of `policy.json`
itself or of the two stored validation files the review screen reads, so an
altered cutoff or a rewritten validation table that kept its shape would pass a
structural check. This records their digests once, after proving each equals the
SHA-256 of the blob at a named commit of the published history (by default
`main`, before Phase 9), so the expected values do not come from the working
tree they protect. `check-bundle` compares against the record.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from med_deploy.bundle import UNANCHORED, sha256_file
from med_deploy.records import now_utc
from med_deploy.version import DEFAULT_PATHS, DEPLOY_VERSION


class DigestError(RuntimeError):
    """A file does not equal its published blob, or git cannot say."""


def record_digests(root: Path, git_ref: str = "main") -> dict:
    root = Path(root).resolve()
    policy_dir = (root / DEFAULT_PATHS["policy"]).parent
    commit = subprocess.run(["git", "rev-parse", "--verify", f"{git_ref}^{{commit}}"], cwd=root, capture_output=True, text=True)
    if commit.returncode != 0:
        raise DigestError(f"cannot resolve {git_ref}: {commit.stderr.strip()}")
    commit_id = commit.stdout.strip()
    names = sorted({name for scope_names in UNANCHORED.values() for name in scope_names})
    files = {}
    for name in names:
        path = policy_dir / name
        relative = path.relative_to(root).as_posix()
        blob = subprocess.run(["git", "show", f"{commit_id}:{relative}"], cwd=root, capture_output=True)
        if blob.returncode != 0:
            raise DigestError(f"{relative} is not in commit {commit_id[:12]}: {blob.stderr.decode().strip()}")
        published = hashlib.sha256(blob.stdout).hexdigest()
        current = sha256_file(path)
        if published != current:
            raise DigestError(f"{relative} in the working tree ({current[:16]}...) is not the blob at {commit_id[:12]} ({published[:16]}...)")
        files[relative] = {"sha256": current, "bytes": path.stat().st_size}
    return {
        "kind": "bundle_digests",
        "deploy_version": DEPLOY_VERSION,
        "date_utc": now_utc(),
        "why": "nothing else checksums these files: policy.json holds the model and feature-manifest checksums but no checksum of itself, and the two validation files are read by the review screen",
        "verified_against": {"git_ref": git_ref, "commit": commit_id, "how": "each digest equals the SHA-256 of the blob at that commit"},
        "scopes": {scope: [f"{policy_dir.relative_to(root).as_posix()}/{name}" for name in names_] for scope, names_ in UNANCHORED.items()},
        "files": files,
    }
