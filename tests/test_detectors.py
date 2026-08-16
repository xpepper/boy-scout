from detectors import detect_test_coverage_gap


def test_test_coverage_gap_is_recorded_as_a_file_level_finding(tmp_path):
    """A missing test file is a property of the whole file, so the finding
    must carry no line anchor rather than a fabricated lines 1-1 range.
    """
    source = tmp_path / "invoice.py"
    source.write_text("def apply_discount():\n    return 0\n")

    findings = detect_test_coverage_gap(str(source), {}, str(tmp_path))

    assert len(findings) == 1
    assert findings[0]["locations"] == []
