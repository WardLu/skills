import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
sys.path.insert(0, str(ROOT / "evals"))
from check_report import check_report


class AgentPrivacyCheckContractTests(unittest.TestCase):
    def test_skill_metadata_is_complete_and_discriminating(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        frontmatter, body = text.split("---\n", 2)[1:]
        self.assertRegex(frontmatter, r"(?m)^name:\s*agent-privacy-check\s*$")
        description = re.search(r"(?m)^description:\s*(.+)$", frontmatter)
        self.assertIsNotNone(description)
        self.assertIn("what an agent can see", description.group(1))
        self.assertIn("Low, Medium, High, or Critical", description.group(1))
        self.assertNotIn("[TODO", text)
        for heading in (
            "## Scope gate",
            "## Safe audit boundary",
            "## Audit workflow",
            "### 4. Test the three-part combination",
            "### 5. Rate the risk",
            "## Report contract",
        ):
            self.assertIn(heading, body)

    def test_referenced_documents_exist(self):
        text = SKILL.read_text(encoding="utf-8")
        references = set(re.findall(r"\(references/([A-Za-z0-9_.-]+\.md)\)", text))
        self.assertGreaterEqual(
            references,
            {
                "evidence-collection.md",
                "risk-model.md",
                "report-template.md",
                "platform-notes.md",
                "sources.md",
            },
        )
        for name in references:
            self.assertTrue((ROOT / "references" / name).is_file(), name)

    def test_risk_model_covers_required_levels_and_combination_states(self):
        text = (ROOT / "references" / "risk-model.md").read_text(encoding="utf-8")
        for level in ("Low", "Medium", "High", "Critical"):
            self.assertIn(f"| {level} |", text)
        for state in ("Confirmed", "Likely", "Not demonstrated", "Unknown"):
            self.assertIn(f"| {state} |", text)
        self.assertIn("Secret Source", text)
        self.assertIn("External Sink", text)
        self.assertIn("Untrusted Content", text)
        for sink_class in (
            "Trusted processing destination",
            "Third-party processing or retention destination",
            "Agent-controlled external action",
            "Attacker-controlled or mutable destination",
        ):
            self.assertIn(sink_class, text)
        self.assertIn("Available describes capability, not an event.", text)

    def test_report_template_keeps_evidence_on_conclusions_and_repairs(self):
        text = (ROOT / "references" / "report-template.md").read_text(encoding="utf-8")
        for field in (
            "Evidence basis",
            "Actual transmission",
            "Approval and retention",
            "Evidence or trigger",
            "Verification",
            "Claim references",
        ):
            self.assertIn(field, text)

    def test_sources_keep_owasp_mapping_as_an_adaptation(self):
        text = (ROOT / "references" / "sources.md").read_text(encoding="utf-8")
        self.assertIn(
            "https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html",
            text,
        )
        self.assertIn(
            "https://owasp.org/www-project-agentic-skills-top-10/",
            text,
        )
        self.assertIn("not an OWASP category", text)
        self.assertIn("does not reproduce OWASP's taxonomy", text)
        self.assertIn("Public review", text)

    def test_bilingual_readmes_have_install_and_locale_links(self):
        for name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("agent-privacy-check", text)
            self.assertIn("README.md", text)
            self.assertIn("README.zh-CN.md", text)
            self.assertIn("npx skills add", text)
            self.assertIn("0.1.0", text)
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.1.0")

    def test_evaluation_cases_are_synthetic_and_cover_all_levels(self):
        cases = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 4)
        self.assertEqual(
            {case["expected"]["overall_risk"] for case in cases},
            {"Low", "Medium", "High", "Critical"},
        )
        self.assertEqual(
            {case["expected"]["combination"] for case in cases},
            {"Confirmed", "Not demonstrated", "Unknown"},
        )
        self.assertEqual(
            {case["platform"] for case in cases},
            {"Codex", "Claude Code", "Generic agent"},
        )
        for case in cases:
            self.assertRegex(case["id"], r"^[a-z0-9-]+$")
            self.assertTrue(case["artifacts"])
            serialized = json.dumps(case, ensure_ascii=False)
            self.assertNotRegex(serialized, r"(?i)(sk-[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{12,})")
            self.assertNotIn("-----BEGIN", serialized)

    def test_report_checker_covers_the_user_visible_contract(self):
        report = """
        # Agent Privacy Check
        Overall risk: Low
        Confidence: High
        Scope: current project
        Evidence: E1, E2
        ## What the agent can see
        ## Where data can leave
        ## Three-part combination
        Secret Source: Not found
        External Sink: Not found
        Untrusted Content: Available
        Result: Not demonstrated
        Actual transmission: Not found
        ## Worst credible consequence
        ## What to fix first
        """
        case = {
            "expected": {
                "overall_risk": "Low",
                "combination": "Not demonstrated",
                "actual_transmission": "Not found",
            }
        }
        self.assertEqual(check_report(report, case), [])

    def test_report_checker_rejects_incomplete_or_secret_bearing_report(self):
        synthetic_value = "sk-" + ("x" * 20)
        report = f"Overall risk: Critical\nSecret Source: {synthetic_value}"
        findings = check_report(report)
        self.assertIn("missing required report area: scope", findings)
        self.assertIn("report contains a credential-shaped string", findings)
        self.assertIn("missing required report area: confidence", findings)
        self.assertIn("missing required report area: transmission", findings)


if __name__ == "__main__":
    unittest.main()
