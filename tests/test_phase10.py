"""Phase 10: public architecture, results, model card, and usage guide.

These tests check that the generated documents equal what the stored records
produce, that their numbers trace to record fields, that the generator is
standard-library only and never reads the per-draft outcomes of the frozen test
record, that every printed command exists, and that hand-written text carries no
number of its own. Nothing here scores a draft, fits a model, or runs a one-shot
command.
"""

from __future__ import annotations

import ast
import copy
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from med_docs import blocks, cli, documents, facts, records, render
from med_docs import version as docs_version
from med_docs.records import RecordError

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SRC = ROOT / "src"

NEW_DOCUMENTS = (
    "ARCHITECTURE.md",
    "DEMO_WALKTHROUGH.md",
    "LIMITATIONS_AND_FUTURE_WORK.md",
    "MODEL_CARD.md",
    "README.md",
    "RESULTS.md",
    "USAGE_GUIDE.md",
)
HAND_WRITTEN = (ROOT / "README.md",) + tuple(DOCS / name for name in NEW_DOCUMENTS if name != "RESULTS.md")
GENERATED_BLOCK_DOCS = {
    ROOT / "README.md": {"headline"},
    DOCS / "ARCHITECTURE.md": {"artifact_table", "image_table"},
    DOCS / "MODEL_CARD.md": {"card_model", "card_training", "card_evaluation", "card_operating_point", "card_results", "card_failures", "card_versions"},
    DOCS / "DEMO_WALKTHROUGH.md": {f"demo_step_{i}" for i in range(1, 7)},
    DOCS / "LIMITATIONS_AND_FUTURE_WORK.md": {"limit_evidence"},
}


@pytest.fixture(scope="module")
def loaded():
    return records.load(ROOT)


@pytest.fixture(scope="module")
def derived(loaded):
    return facts.derive(loaded)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _scratch_root(tmp_path: Path, test_record: str = "copy") -> Path:
    """The records and the block documents, copied under a temporary root."""
    root = tmp_path / "root"
    for group in records.SOURCES.values():
        for rel in group:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, target)
    for path in (*documents.BLOCKS, *documents.FULL):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / path, target)
    shutil.copy(ROOT / "artifacts/med-policy-v2/policy.json", root / "artifacts/med-policy-v2/policy.json")
    return root


# ---------------------------------------------------------- public documents


def test_the_phase_10_documents_exist_and_pass_the_public_docs_scan():
    import test_public_docs as scan

    for name in NEW_DOCUMENTS:
        assert (DOCS / name).is_file(), name
    assert (ROOT / "README.md").is_file()
    scanned = {path.resolve() for path in scan._markdown_files()}
    for path in HAND_WRITTEN + (DOCS / "RESULTS.md",):
        assert path.resolve() in scanned, f"{path} is not scanned for private terms and broken links"
    scan.test_public_docs_avoid_private_terms_and_broken_links()


def test_project_context_is_not_referenced_by_any_public_file():
    private = ("project_context", "handoff_notes", "phase10.md")
    public = [ROOT / "README.md", *sorted(DOCS.rglob("*.md")), *sorted((SRC / "med_docs").glob("*.py")), ROOT / "tests" / "test_phase10.py"]
    # The scan below names the terms it looks for, so this file is excused for them.
    for path in public:
        if path.name == "test_phase10.py":
            continue
        text = _text(path)
        for term in private:
            assert term not in text, f"{path.relative_to(ROOT)} mentions {term}"
    assert "project_context/" in _text(ROOT / ".gitignore")


def test_the_documentation_index_links_every_public_document():
    index = _text(DOCS / "README.md")
    linked = {(DOCS / target.split("#")[0]).resolve() for target in re.findall(r"\]\(([^)]+\.md[^)]*)\)", index) if not target.startswith("http")}
    missing = [str(path.relative_to(ROOT)) for path in sorted(DOCS.rglob("*.md")) if path != DOCS / "README.md" and path.resolve() not in linked]
    assert missing == [], f"documents the index does not list: {missing}"
    assert (ROOT / "README.md").resolve() in linked
    assert "docs/README.md" in _text(ROOT / "README.md")


def test_the_readme_is_short_keeps_its_citations_and_states_the_package_version():
    readme = _text(ROOT / "README.md")
    assert len(readme.split()) < 3500, "the README must stay shorter than the one it replaces"
    assert "## Research basis and techniques" in readme, "four Phase 1 links anchor to this heading"
    for doi in ("10.1137/1.9781611972771.7", "10.1002/asi.22886", "10.1145/1149121.1149125", "WS08-04-001.pdf"):
        assert doi in readme
    for label in ("R1", "R2", "R3", "R4"):
        assert f"| {label}:" in readme
    pyproject = _text(ROOT / "pyproject.toml")
    package_version = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    assert tuple(int(part) for part in package_version.split(".")) >= (0, 10, 0)
    assert f"The package version is {package_version}" in readme
    assert 'med-docs = "med_docs.cli:main"' in pyproject
    assert docs_version.DOCS_VERSION in _text(DOCS / "MODEL_CARD.md")


# --------------------------------------------------------------- generation


def test_generated_documents_equal_what_the_generator_produces_from_the_records():
    assert documents.differing(ROOT) == []
    expected = documents.build(ROOT)
    assert _text(DOCS / "RESULTS.md") == expected[Path("docs/RESULTS.md")]
    for path, names in GENERATED_BLOCK_DOCS.items():
        assert set(blocks.names(_text(path))) == names, path


def test_the_command_line_regenerates_checks_and_detects_a_hand_edit(tmp_path):
    root = _scratch_root(tmp_path)
    assert cli.main(["check", "--root", str(root)]) == 0, "the committed documents are already in sync with the records"
    card = root / "docs/MODEL_CARD.md"
    card.write_text(_text(card).replace("logistic regression", "logistic regression (edited)", 1).replace("| `T_warn` |", "| `T_warn` (edited) |"), encoding="utf-8")
    results = root / "docs/RESULTS.md"
    results.write_text(_text(results) + "\nA hand-typed line.\n", encoding="utf-8")
    assert cli.main(["check", "--root", str(root)]) == 1
    assert cli.main(["report", "--root", str(root)]) == 0
    assert "hand-typed" not in _text(results)
    assert cli.main(["check", "--root", str(root)]) == 0


def test_blocks_replace_only_their_content_and_refuse_a_mismatch():
    text = "intro\n<!-- med-docs:begin one -->\nold\n<!-- med-docs:end one -->\nmiddle\n<!-- med-docs:begin two -->\n<!-- med-docs:end two -->\nend\n"
    out = blocks.apply(text, {"one": "A\nB", "two": "C"})
    assert out == "intro\n<!-- med-docs:begin one -->\nA\nB\n<!-- med-docs:end one -->\nmiddle\n<!-- med-docs:begin two -->\nC\n<!-- med-docs:end two -->\nend\n"
    assert blocks.apply(out, {"one": "A\nB", "two": "C"}) == out
    assert blocks.outside(out) == "intro\n\nmiddle\n\nend\n"
    with pytest.raises(blocks.BlockError):
        blocks.apply(text, {"one": "A"})
    with pytest.raises(blocks.BlockError):
        blocks.apply(text, {"one": "A", "two": "C", "three": "D"})


# ------------------------------------------------------ numbers and statuses


def _raw(path: str):
    return json.loads(_text(ROOT / path))


def _no_commas(text: str) -> str:
    return text.replace(",", "")


def test_the_key_numbers_trace_to_record_fields():
    results = _text(DOCS / "RESULTS.md")
    policy = _raw("artifacts/med-policy-v2/policy.json")
    latency = _raw("artifacts/med-api-latency/med-policy-v2/latency.json")
    deploy = _raw("artifacts/med-deploy-v1/latency_api_image.json")
    experiments = _raw("artifacts/med-model-v2/experiments.json")

    # The recorded test pass, read here only at its aggregate paths.
    test_tree = json.loads(_text(ROOT / "artifacts/med-policy-v2/test_evaluation.json"), object_pairs_hook=lambda pairs: {k: v for k, v in pairs if k not in docs_version.SEALED_KEYS})
    for subset in ("test_product_like",):
        policy_block = test_tree["subsets"][subset]["policy"]
        email, fi = policy_block["email"], policy_block["interventions"]
        assert f"{email['true_positives']} / {email['positives']}" in results
        assert f"{fi['false_interventions']} / {fi['legitimate_emails']:,}" in results
        low, high = email["recall_interval_exact"]["low"], email["recall_interval_exact"]["high"]
        assert f"{email['recall']:.3f} [{low:.3f}, {high:.3f}]" in results
        assert f"{fi['zero_count_upper_per_1000']:.2f}" in results
        emails = email["n"]
        assert f"| {emails:,} | {email['positives'] / emails * 1000:.2f} | {email['true_positives'] / emails * 1000:.2f} |" in results
        assert f"{(fi['warnings'] + fi['blocks']) / emails * 1000:.2f}" in results
        for cell in test_tree["subsets"][subset]["slices"]["email_by_scenario"]:
            if cell["misdirected"]:
                assert f"{cell['warned_misdirected']} / {cell['misdirected']} mistakes warned" in results

    validation = policy["validation_confusion"]["email"]
    assert f"{validation['true_positives']} / {validation['positives']}" in results
    assert f"{validation['false_positives']} / {validation['legitimate']:,}" in results
    assert f"{validation['true_positives'] / validation['n'] * 1000:.2f}" in results

    assert f"{latency['client_p95_ms']:.2f} ms" in results
    assert f"{deploy['ac05']['client_p95_ms']:.2f} ms" in results
    assert f"{deploy['concurrent_probe']['client']['p95_ms']:.2f} ms **(above the target)**" in results
    assert deploy["concurrent_probe"]["client"]["p95_ms"] > latency["target_p95_ms"]

    selected = next(run for run in experiments["runs"] if run["name"] == experiments["selected"])
    ap = selected["validation_product_like"]["email"]
    bootstrap = ap["bootstrap"]["average_precision"]
    assert f"{ap['average_precision']:.3f} [{bootstrap['low']:.3f}, {bootstrap['high']:.3f}]" in results

    table = re.findall(r"^\| (AC\d\d) \| [^|]+ \| \*\*([^*]+)\*\* \|", results, re.M)
    assert [row[0] for row in table] == [f"AC{i:02d}" for i in range(1, 11)]
    assert dict(table)["AC01"] == "insufficient evidence"
    assert dict(table)["AC04"] == "met"
    assert all(status in ("met", "not met", "insufficient evidence") or status.startswith(("met for", "partly met", "not met for")) for _, status in table)


def test_statuses_and_numbers_agree_with_the_earlier_generated_documents():
    results = _text(DOCS / "RESULTS.md")
    phase5 = _text(DOCS / "phase_5/EVALUATION_REPORT.md")
    for criterion in ("AC01", "AC02", "AC03", "AC04", "AC07"):
        earlier = re.search(rf"\| {criterion} \| \*\*([^*]+)\*\*", phase5)
        if criterion == "AC07":
            earlier = re.search(r"AC07: \*\*([^*]+)\*\*", phase5)
        now = re.search(rf"^\| {criterion} \| [^|]+ \| \*\*([^*]+)\*\*", results, re.M)
        assert earlier and now, criterion
        assert earlier.group(1) == now.group(1), f"{criterion}: Phase 5 says {earlier.group(1)!r}, results say {now.group(1)!r}"
    assert re.search(r"AC05 \*\*([^*]+)\*\*", _text(DOCS / "phase_5/EVALUATION_REPORT.md")).group(1) == "met"
    assert re.search(r"^\| AC05 \| [^|]+ \| \*\*met\*\*", results, re.M)
    # Operating-point counts printed by the Phase 5 report (thousands separators removed).
    for pair in ("8 / 20", "9 / 30", "0 / 3980", "0 / 5970"):
        assert pair in _no_commas(phase5)
        assert pair in _no_commas(results)
    assert "57.04 ms" in _text(DOCS / "phase_6/SCORING_FLOW.md") and "57.04 ms" in results
    assert "64.47 ms" in _text(DOCS / "phase_9/TEST_REPORT.md") and "64.47 ms" in results


def test_ac01_is_insufficient_evidence_and_the_misses_are_shown_plainly():
    results = _text(DOCS / "RESULTS.md")
    row = next(line for line in results.splitlines() if line.startswith("| AC01 |"))
    assert "**insufficient evidence**" in row
    section = results[results.index("**AC01 — Interruption budget"):results.index("**AC02")]
    assert "independen" in section and "one sender" in section
    for scenario in ("S01", "S04", "S11"):
        assert re.search(rf"\| \*\*{scenario}\*\* \|.*\*\*missed\*\*", results), scenario
        assert re.search(rf"\| \*\*{scenario}\*\* \| [^|]+ \| 0 / \d+ \| 0 / \d+ \| 0 / \d+ \| 0 / \d+ \|", results), scenario
    headline = blocks.extract(_text(ROOT / "README.md"), "headline")
    assert "Never warned on any subset: S01, S04, S11" in headline and "**insufficient evidence**" in headline
    for path in (DOCS / "MODEL_CARD.md", DOCS / "LIMITATIONS_AND_FUTURE_WORK.md"):
        text = _text(path)
        assert "S01" in text and "S04" in text and "S11" in text
        assert "insufficient evidence" in text or path.name == "MODEL_CARD.md"
    assert "insufficient evidence" in _text(DOCS / "MODEL_CARD.md")
    assert "Diagnostic subsets" in results and "not product-like" in results


def test_statuses_turn_to_not_met_when_a_record_stops_supporting_them(loaded):
    def status(mutated, criterion):
        return next(item["status"] for item in facts.derive(mutated)["acceptance"] if item["id"] == criterion)

    baseline = facts.derive(loaded)["acceptance"]
    assert [item["id"] for item in baseline] == [f"AC{i:02d}" for i in range(1, 11)]

    over = copy.deepcopy(loaded)
    over["test"]["subsets"]["test_product_like"]["policy"]["interventions"]["per_1000_legitimate"] = 2.0
    assert status(over, "AC01") == "not met"

    late = copy.deepcopy(loaded)
    late["policy"]["created_at"] = "2099-01-01T00:00:00Z"
    assert status(late, "AC03") == "not met"

    blocking = copy.deepcopy(loaded)
    blocking["policy"]["blocking_enabled"] = True
    assert status(blocking, "AC04") == "not met"

    slow = copy.deepcopy(loaded)
    slow["api_latency"]["client_p95_ms"] = 400.0
    assert status(slow, "AC05") == "not met"

    mean = copy.deepcopy(loaded)
    for item in mean["deploy"]["mutation"]["mutations"]:
        if item["mutation"] == "mean_instead_of_maximum":
            item["detected"] = False
    assert status(mean, "AC06") == "not met"

    open_failure = copy.deepcopy(loaded)
    open_failure["deploy"]["fixtures"]["invalid_malformed_address"]["expected"]["decision"] = "allow"
    assert status(open_failure, "AC08") == "not met"

    uncoded = copy.deepcopy(loaded)
    for recipient in uncoded["deploy"]["fixtures"]["added_recipient_warn"]["expected"]["recipients"]:
        recipient["reason_codes"] = []
    assert status(uncoded, "AC09") == "not met"

    wrong = copy.deepcopy(loaded)
    cell = next(c for c in wrong["test"]["subsets"]["test_product_like"]["slices"]["email_by_scenario"] if c["slice"] == "S03")
    cell["warned_legitimate"] = 1
    assert status(wrong, "AC07") == "not met"

    blurred = copy.deepcopy(loaded)
    blurred["deploy"]["fixtures"]["known_miss_lookalike"]["known_miss"] = False
    assert status(blurred, "AC10") == "not met"

    # A sentence the records no longer support stops the generator instead of being printed.
    drifted = copy.deepcopy(loaded)
    drifted["deploy"]["fixtures"]["known_miss_lookalike"]["expected"]["email_risk_score"] = 0.99999999
    with pytest.raises(RecordError):
        render.results(facts.derive(drifted))


def test_independence_is_never_assumed():
    assert docs_version.INDEPENDENCE_ESTABLISHED is False


# ------------------------------------------------------------ claims and tone


NEGATIVE_SECTIONS = ("what this project does not claim", "out-of-scope use", "not built")


def _sentences(text: str):
    """Sentences outside code fences, skipping sections whose whole purpose is to say what is not claimed or not built."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    negative = False
    for line in text.splitlines():
        heading = re.match(r"^#+\s+(.*)", line)
        if heading:
            negative = heading.group(1).strip().lower() in NEGATIVE_SECTIONS
            continue
        if negative:
            continue
        for chunk in re.split(r"(?<=[.!?])\s+", line):
            chunk = chunk.strip()
            if chunk:
                yield chunk


NEGATION = re.compile(r"\b(not|no|never|nothing|none|neither|nor|without|cannot|can't|doesn't|does not|did not|do not|isn't|is not|aren't|are not|rather than|instead of|unless|only if|until|need|needs|would|if|future|next step|limits|limit|claim|claims|refus\w*)\b|n't", re.I)
CLAIM_PHRASES = (
    "real-world accuracy",
    "production readiness",
    "production-ready",
    "production ready",
    "confidence-supported",
    "detection improved",
    "improved detection",
    "improves detection",
    "hosted deployment",
    "hosted service",
)


def test_no_public_document_calls_a_score_a_probability_or_claims_blocking_or_an_unearned_result():
    offenders = []
    for path in HAND_WRITTEN + (DOCS / "RESULTS.md",):
        text = _text(path)
        for sentence in _sentences(text):
            lowered = sentence.lower()
            if "probabilit" in lowered and not (NEGATION.search(sentence) or "calibrat" in lowered):
                offenders.append((path.name, "probability", sentence[:140]))
            for phrase in CLAIM_PHRASES:
                if phrase in lowered and not NEGATION.search(sentence):
                    offenders.append((path.name, phrase, sentence[:140]))
            if re.search(r"\bblocking (is|was|has been|are) (enabled|on|active)\b|\benables? blocking\b|\bwill block\b|\bblocks (misdirected|emails|sends)\b", lowered) and not re.search(r"\b(not|never|refus\w*|until|without|justif\w*|only after|must)\b", lowered):
                offenders.append((path.name, "blocking", sentence[:140]))
    assert offenders == []
    for name in ("RESULTS.md", "MODEL_CARD.md"):
        assert re.search(r"[Bb]locking (is )?disabled", _text(DOCS / name)), name
        assert "risk score" in _text(DOCS / name)
    assert "Scores are uncalibrated risk scores, not probabilities" in _text(DOCS / "RESULTS.md")


def test_hand_written_text_carries_no_number_that_a_generator_does_not_source():
    allowed_tokens = {"3.11", "3.11.14", "0.10.0"}
    offenders = []
    for path in HAND_WRITTEN:
        text = blocks.outside(_text(path))
        text = re.sub(r"```.*?```", " ", text, flags=re.S)
        text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
        for line in text.splitlines():
            if "](http" in line or re.match(r"^\| R[1-4] \|", line):
                continue  # a citation row: authors, years, volumes, and pages belong to the cited work
            line = re.sub(r"`[^`]*`", " ", line)
            line = re.sub(r"\]\([^)]*\)", "]", line)
            line = re.sub(r"^\s*\d+\.\s", "", line)  # list markers
            line = re.sub(r"^\| \d+ \|", "|", line)  # roadmap phase numbers
            line = re.sub(r"\b[Pp]hases? \d+(?: to \d+)?|\bsteps? \d+(?: to \d+)?|\bStep \d+", "", line)
            for match in re.finditer(r"(?<![\w.\-])\d[\d,]*(?:\.\d+)*%?(?![\w\-])", line):
                if match.group(0) not in allowed_tokens:
                    offenders.append((path.name, match.group(0), line.strip()[:120]))
    assert offenders == [], offenders


# --------------------------------------------------------------- commands


def _command_lines(markdown: str):
    for block in re.findall(r"```bash\n(.*?)```", markdown, re.S):
        for line in re.sub(r"\\\n\s*", " ", block).splitlines():
            if line.strip():
                yield line
    for span in re.findall(r"`(python -m med_[^`]+)`", markdown):
        yield span


def _split_commands(line: str):
    tokens = shlex.split(line, comments=True)
    command: list[str] = []
    for token in tokens + ["&&"]:
        if token == "&&":
            if command:
                yield command
            command = []
        else:
            command.append(token)


EXTERNAL_COMMANDS = {"mkdir", "source", "open", "curl", "chmod", "rm", "cd"}


def _module_source(module: str) -> str:
    return "\n".join(_text(path) for path in sorted((SRC / module).glob("*.py")))


def test_every_command_printed_in_the_usage_guide_and_the_quick_start_exists():
    pyproject = _text(ROOT / "pyproject.toml")
    extras = set(re.findall(r"^(\w+) = \[", pyproject.split("[project.optional-dependencies]")[1].split("[project.scripts]")[0], re.M))
    markers = _text(ROOT / "pyproject.toml")
    checked = 0
    for path in (ROOT / "README.md", DOCS / "USAGE_GUIDE.md", DOCS / "DEMO_WALKTHROUGH.md", DOCS / "ARCHITECTURE.md", DOCS / "MODEL_CARD.md", DOCS / "LIMITATIONS_AND_FUTURE_WORK.md"):
        for line in _command_lines(_text(path)):
            for tokens in _split_commands(line):
                while tokens and re.match(r"^[A-Z_]+=", tokens[0]):
                    tokens = tokens[1:]
                if not tokens:
                    continue
                head = tokens[0]
                label = f"{path.name}: {' '.join(tokens)}"
                if head.startswith("python"):
                    assert tokens[1] == "-m", label
                    module, rest = tokens[2], tokens[3:]
                    if module.startswith("med_"):
                        assert (SRC / module / "__main__.py").is_file(), label
                        source = _module_source(module)
                        subcommands = set(re.findall(r"add_parser\(\s*\"([\w-]+)\"", source))
                        first = next((token for token in rest if not token.startswith("-")), None)
                        if rest and not rest[0].startswith("-") and subcommands:
                            assert first in subcommands, f"{label}: no subcommand {first!r}; has {sorted(subcommands)}"
                        for token in rest:
                            if token.startswith("--"):
                                assert f'"{token.split("=")[0]}"' in source, f"{label}: no option {token}"
                        checked += 1
                    elif module == "pytest":
                        if "-m" in rest:
                            marker = rest[rest.index("-m") + 1]
                            assert marker == "not slow" and "slow:" in markers, label
                    else:
                        assert module in ("venv", "pip"), label
                elif head == "pip":
                    assert tokens[1] in ("install", "check"), label
                    if tokens[1] == "install":
                        assert (ROOT / "constraints.txt").is_file()
                        spec = next(token for token in tokens if token.startswith('.['))
                        assert set(spec[2:-1].split(",")) <= extras, label
                elif head == "docker/build.sh":
                    assert (ROOT / "docker/build.sh").is_file(), label
                elif head == "docker":
                    assert tokens[1] == "compose" and (ROOT / "compose.yaml").is_file(), label
                elif head == "streamlit":
                    pytest.fail(f"{label}: the supported way to start the screen is python -m med_ui")
                else:
                    assert head in EXTERNAL_COMMANDS, f"{label}: unknown command {head!r}"
    assert checked >= 20, "the command parser found too few project commands to be checking anything"


# ------------------------------------------- the generator's own boundaries


STANDARD_LIBRARY = set(sys.stdlib_module_names)


def test_the_generator_imports_only_the_standard_library_and_itself():
    seen = set()
    for path in sorted((SRC / "med_docs").glob("*.py")):
        tree = ast.parse(_text(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                top = name.split(".")[0]
                seen.add(top)
                assert top in STANDARD_LIBRARY or top == "med_docs", f"{path.name} imports {name}"
    assert "med_policy" not in seen
    used = set()
    for path in (SRC / "med_docs").glob("*.py"):
        for node in ast.walk(ast.parse(_text(path))):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)
    for forbidden in ("stored_results", "_context", "fit", "fit_transform", "read_csv", "joblib", "sklearn", "pandas", "numpy", "load_bundle", "assess_draft", "transform_draft"):
        assert forbidden not in used, f"the generator uses {forbidden}"


def test_running_the_generator_loads_no_scoring_fitting_or_data_reading_code():
    code = (
        "import sys\n"
        "from med_docs import documents\n"
        "documents.build('.')\n"
        "heavy = {'numpy', 'pandas', 'sklearn', 'scipy', 'joblib', 'fastapi', 'streamlit', 'httpx', 'uvicorn'}\n"
        "loaded = sorted(name for name in sys.modules if name.split('.')[0] in heavy or (name.startswith('med_') and not name.startswith('med_docs')))\n"
        "print(loaded)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]", result.stdout


SENTINEL = "SENTINEL-FROZEN-DRAFT"


def _with_outcomes(tmp_path: Path, name: str, replace) -> Path:
    """A copy of the scratch tree whose frozen record has its per-draft outcomes replaced. They are overwritten, never inspected."""
    root = _scratch_root(tmp_path / name)
    target = root / "artifacts/med-policy-v2/test_evaluation.json"
    tree = json.loads(_text(target))
    for block in tree["subsets"].values():
        block["outcomes"] = replace()
    target.write_text(json.dumps(tree), encoding="utf-8")
    return root


def test_the_per_draft_outcomes_of_the_frozen_record_are_never_read(tmp_path):
    expected = documents.build(ROOT)
    garbage = lambda: [{"draft_id": SENTINEL, "scenario_id": "S99", "email_risk": 123.0, "subject": SENTINEL, "warned": True} for _ in range(5)]  # noqa: E731
    for name, replace in (("removed", lambda: None), ("sentinel", garbage), ("nested", lambda: {"warned_mistakes": garbage(), "missed_mistakes": garbage(), "x": {"y": [garbage()]}})):
        root = _with_outcomes(tmp_path, name, replace)
        built = documents.build(root)
        assert built == expected, f"the output changed when the per-draft outcomes were replaced ({name})"
        for text in built.values():
            assert SENTINEL not in text and "S99" not in text and "123.0" not in text
    aggregates = records.test_aggregates(_with_outcomes(tmp_path, "agg", garbage) / "artifacts/med-policy-v2/test_evaluation.json")
    assert SENTINEL not in json.dumps(aggregates)
    assert set(aggregates) == {"top", "subsets"}
    for block in aggregates["subsets"].values():
        assert set(block) == {"policy", "slices"}
        assert set(block["slices"]) == {"email_by_scenario"}


def test_the_frozen_and_validation_records_are_parsed_with_the_sealed_members_dropped(monkeypatch):
    calls = []
    original = records.read_json

    def spy(path, drop=()):
        calls.append((Path(path).name, frozenset(drop)))
        return original(path, drop)

    monkeypatch.setattr(records, "read_json", spy)
    records.load(ROOT)
    for name in ("test_evaluation.json", "validation_evaluation.json"):
        dropped = [drop for called, drop in calls if called == name]
        assert dropped, f"{name} was never read"
        assert all({"outcomes", "examples"} <= drop for drop in dropped), f"{name} was parsed without dropping the per-draft members"
    tree = original(ROOT / "artifacts/med-policy-v2/test_evaluation.json", docs_version.SEALED_KEYS)
    assert all("outcomes" not in block and "examples" not in block for block in tree["subsets"].values())
    assert "examples" not in tree


class _Poison:
    """Raises on any access, so an allow-list that touched it would fail."""

    def _fail(self, *args, **kwargs):
        raise AssertionError("the sealed member was accessed")

    __getitem__ = __iter__ = __len__ = __bool__ = __repr__ = __str__ = __contains__ = __eq__ = __hash__ = _fail


def test_the_allow_list_touches_only_the_paths_it_names():
    tree = {
        "policy_version": "p",
        "policy_sha256": "h",
        "T_warn": 0.5,
        "blocking_enabled": False,
        "evaluated_at": "t",
        "subsets": {
            name: {
                "policy": {"cutoff": 0.5, "email": {"n": 1}, "recipient": {"n": 1}, "attribution": {}, "interventions": {}, "coverage": {}},
                "slices": {"email_by_scenario": [], "other": _Poison()},
                "outcomes": _Poison(),
                "examples": _Poison(),
            }
            for name in docs_version.FROZEN_SUBSETS
        },
        "examples": _Poison(),
    }
    top = records.allow_listed(tree, docs_version.TEST_TOP_PATHS)
    assert set(top) == set(docs_version.TEST_TOP_PATHS)
    for name in docs_version.FROZEN_SUBSETS:
        picked = records.allow_listed(tree["subsets"][name], docs_version.TEST_SUBSET_PATHS)
        assert set(picked) == set(docs_version.TEST_SUBSET_PATHS)
    with pytest.raises(RecordError):
        records.pick({"a": {}}, "a/b")
    for sealed in ("outcomes", "examples"):
        assert not any(path.split("/")[0] == sealed or path.split("/")[-1] == sealed for path in docs_version.TEST_SUBSET_PATHS + docs_version.TEST_TOP_PATHS)
    assert docs_version.SEALED_KEYS >= {"outcomes", "examples"}


def test_the_record_paths_equal_the_version_modules_of_the_packages_that_own_them():
    from med_api import version as api
    from med_data import version as data
    from med_deploy import version as deploy
    from med_features import version as features
    from med_models import version as models
    from med_monitor import version as monitor
    from med_policy import version as policy

    assert docs_version.DATASET_DIR == data.DATA_DIR
    assert docs_version.FEATURES_DIR == features.ARTIFACT_DIR
    assert docs_version.MODEL_DIR == models.ARTIFACT_DIR
    assert docs_version.POLICY_DIR == policy.POLICY_DIR
    assert docs_version.API_LATENCY_PATH == api.LATENCY_PATH
    assert docs_version.MONITOR_DIR == monitor.ARTIFACT_DIR
    assert docs_version.DEPLOY_DIR == deploy.ARTIFACT_DIR
    assert docs_version.SELECTION_SUBSET == policy.SELECTION_SUBSET
    assert docs_version.DIAGNOSTIC_SUBSET == policy.DIAGNOSTIC_SUBSET
    assert docs_version.FROZEN_SUBSETS == policy.TEST_SUBSETS
    loaded = records.load(ROOT)
    assert loaded["policy"]["policy_version"] == policy.POLICY_VERSION
    assert loaded["policy"]["model_version"] == models.MODEL_VERSION
    assert loaded["policy"]["feature_spec_version"] == features.FEATURE_SPEC_VERSION
    assert loaded["policy"]["dataset_version"] == data.DATASET_VERSION
    assert loaded["deploy"]["bundle"]["contract_version"] == api.API_CONTRACT_VERSION
    assert loaded["monitor"]["monitor_version"] == monitor.MONITOR_VERSION
    assert loaded["deploy"]["deploy_version"] == deploy.DEPLOY_VERSION


# ----------------------------------------------------------- the diagram


def test_the_architecture_diagram_names_the_real_components():
    text = _text(DOCS / "ARCHITECTURE.md")
    diagram = re.search(r"```mermaid\n(.*?)```", text, re.S).group(1)
    for package in ("med_data", "med_features", "med_models", "med_policy", "med_api", "med_ui", "med_monitor", "med_deploy", "med_docs"):
        assert package in diagram, package
        assert (SRC / package).is_dir(), package
    for dotted in sorted(set(re.findall(r"\bmed_[a-z]+\.[a-z_]+\b", diagram))):
        package, module = dotted.split(".")
        assert (SRC / package / f"{module}.py").is_file(), dotted
    for function in re.findall(r"\b(transform_draft|assess_draft|AssessmentService|LoadedModel)\b", diagram):
        assert any(function in _text(path) for path in SRC.glob("med_*/*.py")), function
    for directory in re.findall(r"\b((?:data|artifacts)/med-[a-z0-9\-]+)", diagram):
        assert (ROOT / directory).is_dir(), directory
    assert "med-api-v1" in diagram and "POST /assess" in diagram and "POST /feedback" in diagram
    assert "Not built" in diagram
    for capability in ("shadow mode", "canary", "live rollback", "real mail", "hosted deployment"):
        assert capability in diagram.replace("<br/>", " ") or capability in text
    not_built = text.split("## Not built")[1]
    for capability in ("shadow mode", "canary", "live rollback", "hosted deployment", "Real mail"):
        assert capability.lower() in not_built.lower(), capability
    for term in ("unable_to_assess", "strictly earlier", "training and serving"):
        assert term in text.lower().replace("training and serving parity", "training and serving"), term
    readme_diagram = re.search(r"```mermaid\n(.*?)```", _text(ROOT / "README.md"), re.S).group(1)
    for package in ("med_data", "med_features", "med_models", "med_policy", "med_api", "med_ui", "med_monitor"):
        assert package in readme_diagram, package


def test_the_model_card_labels_every_technique_and_cites_the_references():
    card = _text(DOCS / "MODEL_CARD.md")
    section = card.split("## Research basis and technique labels")[1]
    table = section.split("| Technique in this system |")[1].split("\n\n")[0].splitlines()[2:]
    cells = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in table if line.startswith("|")]
    assert cells and all(len(row) == 4 for row in cells), "every technique row has a technique, a source, a label, and a note"
    assert {row[2] for row in cells} == {"adopted", "adapted", "project extension"}, "each label is used, and no other"
    joined = "\n".join(" | ".join(row) for row in cells)
    assert re.search(r"Assess each recipient.*? \| R1 \| adapted", joined)
    assert re.search(r"TF-IDF cosine content compatibility.*? \| R1, R4 \| adapted", joined)
    assert re.search(r"Legitimate first-contact scenarios.*? \| R2 \| adapted", joined)
    for extension in ("Maximum-recipient aggregation", "zero-false-warning cutoff", "Fail-closed", "Versioned bundles"):
        assert re.search(rf"{extension}.*? \| none \| project extension", joined), extension
    assert "../README.md#research-basis-and-techniques" in card
    assert "phase_5/MODEL_CARD.md" in card
    for heading in ("Intended use", "Out-of-scope use", "Model and inputs", "Training data", "Evaluation data and the one test pass", "Operating point and how it was chosen", "Results", "Known failure modes", "Calibration status", "Fairness and privacy notes", "Monitoring, feedback, and rollback", "Versions"):
        assert f"## {heading}" in card, heading
