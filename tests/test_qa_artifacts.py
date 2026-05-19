from __future__ import annotations

from pathlib import Path

import pytest


QA_DIR = Path(".compozy/tasks/group-house-voting/qa")
EXPECTED_FILES = [
    "personas.md",
    "journeys.md",
    "charters.md",
    "test-cases.md",
    "regression-suite.md",
    "bug-report-template.md",
    "design-checklist.md",
]
TECHSPEC_ENDPOINTS = [
    "GET /invite/{token}",
    "POST /register",
    "GET /login",
    "POST /login",
    "POST /logout",
    "GET /",
    "POST /houses",
    "POST /houses/{id}/vote",
    "GET /admin",
    "POST /admin/rotate-invite",
]


def _read(name: str) -> str:
    return (QA_DIR / name).read_text(encoding="utf-8")


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _assert_markdownish(text: str) -> None:
    assert text.strip()
    assert _first_nonempty_line(text).startswith("#")


def test_qa_artifact_files_exist_and_look_like_markdown() -> None:
    for name in EXPECTED_FILES:
        path = QA_DIR / name
        assert path.exists(), name
        text = path.read_text(encoding="utf-8")
        assert text.strip(), name
        _assert_markdownish(text)


def test_personas_document_covers_both_personas() -> None:
    text = _read("personas.md")

    assert "The Organizer" in text
    assert "The Friend" in text
    assert "Device and context assumptions" in text
    assert "Shared Assumptions" in text


def test_journeys_document_covers_all_primary_flows() -> None:
    text = _read("journeys.md")

    for heading in [
        "Joining the Group",
        "Adding a House",
        "Voting",
        "Inviting Members",
        "Rotating the Invite Link",
    ]:
        assert heading in text
    assert text.count("E2E follow-up: yes") >= 5


def test_charters_document_covers_known_risks() -> None:
    text = _read("charters.md")

    for heading in [
        "OG Fetch Failures",
        "Duplicate URL Detection",
        "Invite Token Rotation",
        "Vote Toggle De-Sync",
        "Mobile Viewport Rendering",
    ]:
        assert heading in text
    assert text.count("E2E follow-up: yes") >= 5


def test_test_cases_cover_every_techspec_endpoint() -> None:
    text = _read("test-cases.md")

    for endpoint in TECHSPEC_ENDPOINTS:
        assert endpoint in text
    assert text.count("## TC-") >= 15


def test_regression_suite_maps_six_core_feature_areas() -> None:
    text = _read("regression-suite.md")

    for area in [
        "Invitation and account creation",
        "House submission",
        "House list and ranking",
        "Voting",
        "Admin panel and invite control",
        "Mobile-first UX and error states",
    ]:
        assert area in text


def test_regression_suite_mentions_all_critical_requirement_links() -> None:
    text = _read("regression-suite.md")

    for requirement in [
        "Single shareable invite link controlled by the admin",
        "Rotate invite link with one click and invalidate the old link immediately",
        "Register with name, email, and password from a valid invite link",
        "Accept only Airbnb and Booking.com URLs",
        "Normalize URLs and prevent duplicate listings",
        "Fetch OG metadata and surface retryable failures",
        "Sort houses by vote count descending, then by submission date",
        "Render card image, title, description, price, source badge, vote count, and vote button",
        "Enforce one vote per user per house",
        "Show the invite link and copy action in the admin panel",
        "Keep the UI mobile-first and usable at phone width",
    ]:
        assert requirement in text


def test_design_checklist_mentions_tokens_and_mobile_viewport() -> None:
    text = _read("design-checklist.md")

    assert "--color-primary" in text
    assert "375px" in text
    assert "No hardcoded hex values" in text


@pytest.mark.integration
def test_qa_output_directory_contains_expected_files() -> None:
    assert QA_DIR.exists()
    for name in EXPECTED_FILES:
        path = QA_DIR / name
        assert path.exists(), name
        assert path.read_text(encoding="utf-8").strip(), name


@pytest.mark.integration
def test_regression_suite_flags_e2e_follow_up_cases() -> None:
    text = _read("regression-suite.md")
    for case_id in [
        "TC-INV-01",
        "TC-INV-02",
        "TC-REG-01",
        "TC-REG-02",
        "TC-HOUSE-01",
        "TC-HOUSE-02",
        "TC-HOUSE-03",
        "TC-HOUSE-04",
        "TC-VOTE-01",
        "TC-VOTE-02",
        "TC-ADMIN-01",
        "TC-ADMIN-02",
        "TC-UI-01",
    ]:
        assert case_id in text
    assert text.count("yes") >= 10


@pytest.mark.integration
def test_bug_report_template_includes_persona_and_severity_fields() -> None:
    text = _read("bug-report-template.md")

    assert "Persona:" in text
    assert "Severity:" in text
    assert "The Organizer" in text
    assert "The Friend" in text
