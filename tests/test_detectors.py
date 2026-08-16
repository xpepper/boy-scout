from detectors import detect_duplication, detect_test_coverage_gap

_DUPLICATED = '''\
def load_alpha(path):
    handle = open(path)
    raw = handle.read()
    handle.close()
    parsed = raw.split(",")
    cleaned = [item.strip() for item in parsed]
    return cleaned


def load_beta(path):
    handle = open(path)
    raw = handle.read()
    handle.close()
    parsed = raw.split(",")
    cleaned = [item.strip() for item in parsed]
    return cleaned
'''

_DISTINCT = '''\
def widen(value):
    scaled = value * 3
    return scaled


def narrow(text):
    trimmed = text.strip()
    return trimmed


def combine(left, right):
    joined = f"{left}:{right}"
    return joined


def explode(payload):
    pieces = payload.split("|")
    return pieces
'''


def test_duplication_detects_a_repeated_block(tmp_path):
    source = tmp_path / "loader.py"
    source.write_text(_DUPLICATED)

    findings = detect_duplication(str(source), {})

    assert len(findings) == 1
    assert findings[0]["type"] == "duplication"
    assert len(findings[0]["locations"]) == 2


def test_duplication_reports_nothing_for_distinct_blocks(tmp_path):
    source = tmp_path / "distinct.py"
    source.write_text(_DISTINCT)

    assert detect_duplication(str(source), {}) == []


def test_duplication_verifies_block_content_before_reporting(tmp_path, monkeypatch):
    """Bucketing by hash is only a candidate filter. With every window forced
    into the same bucket, the detector must still compare the actual text and
    report nothing rather than trust the hash.
    """
    source = tmp_path / "distinct.py"
    source.write_text(_DISTINCT)
    monkeypatch.setattr("builtins.hash", lambda _obj: 0)

    assert detect_duplication(str(source), {}) == []


def test_test_coverage_gap_is_recorded_as_a_file_level_finding(tmp_path):
    """A missing test file is a property of the whole file, so the finding
    must carry no line anchor rather than a fabricated lines 1-1 range.
    """
    source = tmp_path / "invoice.py"
    source.write_text("def apply_discount():\n    return 0\n")

    findings = detect_test_coverage_gap(str(source), {}, str(tmp_path))

    assert len(findings) == 1
    assert findings[0]["locations"] == []
