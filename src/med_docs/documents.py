"""Which files are generated, and how.

`FULL` files are written whole from the records. `BLOCKS` files are hand-written
Markdown with generated blocks (see `med_docs.blocks`); only the blocks change.
Standard library only.
"""

from __future__ import annotations

from pathlib import Path

from med_docs import blocks, facts as facts_module, records, render
from med_docs.version import DOCS_DIR, README_PATH

FULL = {DOCS_DIR / "RESULTS.md": render.results}
BLOCKS = {
    README_PATH: render.readme_blocks,
    DOCS_DIR / "ARCHITECTURE.md": render.architecture_blocks,
    DOCS_DIR / "MODEL_CARD.md": render.model_card_blocks,
    DOCS_DIR / "DEMO_WALKTHROUGH.md": render.demo_blocks,
    DOCS_DIR / "LIMITATIONS_AND_FUTURE_WORK.md": render.limitations_blocks,
}


def generated_paths() -> list[Path]:
    return sorted([*FULL, *BLOCKS])


def build(root: Path | str = ".", loaded: dict | None = None) -> dict[Path, str]:
    """The text every generated file should hold, computed from the records under `root`."""
    root = Path(root)
    derived = facts_module.derive(loaded if loaded is not None else records.load(root))
    out: dict[Path, str] = {}
    for path, render_whole in FULL.items():
        out[path] = render_whole(derived)
    for path, render_blocks in BLOCKS.items():
        target = root / path
        if not target.is_file():
            raise records.RecordError(f"{path} does not exist; a document with generated blocks is written by hand first, with a marker pair for each block")
        out[path] = blocks.apply(target.read_text(encoding="utf-8"), render_blocks(derived), source=str(path))
    return out


def differing(root: Path | str = ".") -> list[Path]:
    root = Path(root)
    expected = build(root)
    return [path for path, text in expected.items() if not (root / path).is_file() or (root / path).read_text(encoding="utf-8") != text]
