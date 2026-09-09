#!/usr/bin/env python3
"""Check the observable completeness of a synthetic privacy report."""

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_MARKERS = {
    "scope": ("scope", "检查范围"),
    "what the agent can see": ("what the agent can see", "能看到什么"),
    "where data can leave": ("where data can leave", "数据能发到哪里"),
    "worst case": ("worst credible consequence", "worst case", "最坏后果"),
    "fixes": ("what to fix first", "how to fix", "整改", "怎么整改"),
    "evidence": ("evidence", "证据"),
    "confidence": ("confidence", "置信度"),
    "transmission": ("actual transmission", "实际传输"),
}
TRIAD = ("secret source", "external sink", "untrusted content")
EVIDENCE_LABELS = ("observed", "available", "not found", "unknown")
SECRET_PATTERNS = (
    re.compile(r"(?i)(?<![a-z0-9])sk-[a-z0-9]{20,}(?![a-z0-9])"),
    re.compile(r"(?i)(?<![a-z0-9])ghp_[a-z0-9]{20,}(?![a-z0-9])"),
    re.compile(r"(?i)(?<![a-z0-9])akia[0-9a-z]{16,}(?![a-z0-9])"),
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
)


def load_case(cases_path: Path, case_id: str) -> dict:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    for case in cases:
        if case.get("id") == case_id:
            return case
    raise ValueError(f"unknown case: {case_id}")


def check_report(report: str, expected: dict | None = None) -> list[str]:
    lowered = report.casefold()
    findings: list[str] = []

    for name, markers in REQUIRED_MARKERS.items():
        if not any(marker.casefold() in lowered for marker in markers):
            findings.append(f"missing required report area: {name}")

    if not re.search(r"\b(?:low|medium|high|critical)\b", lowered):
        findings.append("missing Low, Medium, High, or Critical risk level")

    for label in TRIAD:
        if label not in lowered:
            findings.append(f"missing triad element: {label}")

    if not any(label in lowered for label in EVIDENCE_LABELS):
        findings.append("missing evidence label")

    if any(pattern.search(report) for pattern in SECRET_PATTERNS):
        findings.append("report contains a credential-shaped string")

    if expected:
        expected_risk = expected["expected"]["overall_risk"].casefold()
        if expected_risk not in lowered:
            findings.append(f"missing expected risk: {expected['expected']['overall_risk']}")
        expected_combination = expected["expected"]["combination"].casefold()
        if expected_combination not in lowered:
            findings.append(
                f"missing expected combination: {expected['expected']['combination']}"
            )
        expected_transmission = expected["expected"]["actual_transmission"].casefold()
        if expected_transmission not in lowered:
            findings.append(
                "missing expected transmission status: "
                f"{expected['expected']['actual_transmission']}"
            )

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Markdown report to check")
    parser.add_argument("--case", help="Synthetic case ID whose expected labels must appear")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("cases.json"),
        help="JSON case file (default: evals/cases.json)",
    )
    args = parser.parse_args(argv)

    report = args.report.read_text(encoding="utf-8")
    expected = load_case(args.cases, args.case) if args.case else None
    findings = check_report(report, expected)
    result = {"status": "PASS" if not findings else "FAIL", "findings": findings}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
