from __future__ import annotations

from pathlib import Path

QA_ROOT = Path(".compozy/tasks/scraping-metadata-refresh/qa")
PLAN_PATH = QA_ROOT / "test-plans" / "scraping-metadata-refresh-test-plan.md"
REGRESSION_PATH = QA_ROOT / "test-plans" / "scraping-metadata-refresh-regression.md"
BUG_TEMPLATE_PATH = QA_ROOT / "issues" / "BUG-template.md"
CHARTER_DIR = QA_ROOT / "test-plans" / "charters"
CASE_DIR = QA_ROOT / "test-cases"


def test_scraping_metadata_refresh_qa_tree_exists() -> None:
    assert PLAN_PATH.is_file()
    assert REGRESSION_PATH.is_file()
    assert BUG_TEMPLATE_PATH.is_file()
    assert CHARTER_DIR.is_dir()
    assert CASE_DIR.is_dir()


def test_scraping_metadata_refresh_plan_has_required_sections() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")

    for heading in [
        "## Executive Summary",
        "## Personas Covered",
        "## Journeys Mapped",
        "## Charters Planned",
        "## CFR Scope",
        "## Test Strategy",
        "## Automation Strategy",
        "## Entry Criteria",
        "## Exit Criteria",
        "## Retesting vs Regression",
        "## Risk Assessment",
        "## Timeline and Deliverables",
    ]:
        assert heading in text

    for persona in ["New User", "Mobile User", "Accessibility-Reliant", "Power User", "Recovering User"]:
        assert persona in text

    for journey in [
        "J-01: Add a Booking listing with contextual query params",
        "J-02: Add an Airbnb listing and trust visible metadata",
        "J-03: Duplicate submission without hidden refresh",
        "J-04: Admin refresh missing metadata",
        "J-05: Recover from failed upstream metadata fetch",
        "J-06: Confirm cards render trustworthy price metadata only when available",
    ]:
        assert journey in text


def test_charters_are_complete_and_one_tour_each() -> None:
    charter_files = sorted(CHARTER_DIR.glob("CH-*.md"))
    assert [path.name for path in charter_files] == [
        "CH-01-booking-submission-feature.md",
        "CH-02-booking-recovery-network.md",
        "CH-03-duplicate-back-button.md",
        "CH-04-messy-paste-garbage.md",
        "CH-05-price-trust-locale.md",
        "CH-06-autofill-admin.md",
    ]

    for path in charter_files:
        text = path.read_text(encoding="utf-8")
        assert "mission:" in text
        assert "persona:" in text
        assert "surface:" in text
        assert "tour:" in text
        assert text.count("tour:") == 1
        assert "time_box_minutes:" in text
        assert "must_try:" in text
        assert "must_avoid:" in text


def test_all_test_case_files_have_automation_metadata() -> None:
    case_files = sorted(CASE_DIR.glob("*.md"))
    assert case_files

    personas = set()
    journey_ids = set()
    cfr_categories = set()

    for path in case_files:
        text = path.read_text(encoding="utf-8")
        assert "**Automation Target:**" in text
        assert "**Automation Status:**" in text
        assert "**Automation Command/Spec:**" in text
        assert "**Automation Notes:**" in text

        if "Automation Status:** Missing" in text or "Automation Status:** Blocked" in text:
            assert "Automation Notes:" in text

        for persona in [
            "New User",
            "Power User",
            "Casual User",
            "Mobile User",
            "Accessibility-Reliant",
            "Recovering User",
        ]:
            if f"**Persona:** {persona}" in text or f"Persona | {persona}" in text:
                personas.add(persona)

        for journey_id in [f"J-{idx:02d}" for idx in range(1, 7)]:
            if journey_id in text:
                journey_ids.add(journey_id)

        for category in [
            "Usability",
            "Accessibility",
            "Perceived-Performance",
            "Compatibility",
            "Error-Recoverability",
            "Production-Parity",
        ]:
            if f"**CFR Category:** {category}" in text:
                cfr_categories.add(category)

    assert {"TC-JOURNEY-001", "TC-JOURNEY-002", "TC-JOURNEY-003", "TC-JOURNEY-004", "TC-JOURNEY-005", "TC-JOURNEY-006"} <= {
        path.stem for path in case_files if path.stem.startswith("TC-JOURNEY-")
    }
    assert {"TC-FUNC-001", "TC-FUNC-002", "TC-FUNC-003", "TC-FUNC-004"} <= {
        path.stem for path in case_files if path.stem.startswith("TC-FUNC-")
    }
    assert {"TC-TOUR-001", "TC-TOUR-002", "TC-TOUR-003", "TC-TOUR-004", "TC-TOUR-005", "TC-TOUR-006"} <= {
        path.stem for path in case_files if path.stem.startswith("TC-TOUR-")
    }
    assert {"SMOKE-001", "SMOKE-002"} <= {path.stem for path in case_files if path.stem.startswith("SMOKE-")}
    assert {"TC-REG-001", "TC-REG-002", "TC-REG-003", "TC-REG-004"} <= {
        path.stem for path in case_files if path.stem.startswith("TC-REG-")
    }
    assert {"TC-UI-001", "TC-UI-002"} <= {path.stem for path in case_files if path.stem.startswith("TC-UI-")}
    assert {"TC-CFR-001", "TC-CFR-002", "TC-CFR-003", "TC-CFR-004", "TC-CFR-005", "TC-CFR-006"} <= {
        path.stem for path in case_files if path.stem.startswith("TC-CFR-")
    }

    assert {"New User", "Mobile User", "Accessibility-Reliant"} <= personas
    assert journey_ids == {f"J-{idx:02d}" for idx in range(1, 7)}
    assert cfr_categories == {
        "Usability",
        "Accessibility",
        "Perceived-Performance",
        "Compatibility",
        "Error-Recoverability",
        "Production-Parity",
    }


def test_regression_suite_includes_required_tiers_and_journeys() -> None:
    text = REGRESSION_PATH.read_text(encoding="utf-8")

    for heading in ["## Smoke Tier", "## Targeted Tier", "## Full Tier", "## Sanity Tier"]:
        assert heading in text

    for journey in ["J-01", "J-02", "J-03", "J-04", "J-05", "J-06"]:
        assert journey in text

    assert "Missing" in text


def test_bug_template_matches_required_issue_fields() -> None:
    text = BUG_TEMPLATE_PATH.read_text(encoding="utf-8")

    for field in [
        "**Impact (user-side):**",
        "**Severity:**",
        "**Priority:**",
        "**Type:**",
        "**Status:**",
        "**Persona Affected:**",
        "**Journey Step:**",
        "## Environment",
        "## Summary",
        "## Reproduction",
        "## Expected",
        "## Root cause",
        "## Fix",
        "## Verification",
        "## Impact",
        "## Related",
    ]:
        assert field in text
