# Agent Privacy Check

[![Validate skills](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/WardLu/skills/actions/workflows/validate-skills.yml) [![Version 0.1.0](https://img.shields.io/badge/version-0.1.0-2563eb.svg)](VERSION) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

Agent Privacy Check gives ordinary users a plain-language answer about an AI
agent's privacy boundary. It checks what the agent can reach, where data could
leave, whether untrusted content can steer a sensitive action, the worst
credible consequence, and what to fix first.

It is designed for Codex, Claude Code, and other agent runtimes. The report
separates what is configured, what was observed, and what remains unknown.

[English](README.md) · [简体中文](README.zh-CN.md)

## What it answers

- What files, conversations, credentials, browser state, tools, and services
  the agent can reach.
- Which model providers, APIs, webhooks, browsers, connectors, logs, or other
  agents could receive data.
- Whether the three-part combination is present: Secret Source, External Sink,
  and Untrusted Content.
- What an attacker or accidental instruction could do in the worst case.
- Which containment, least-privilege, isolation, approval, and monitoring
  changes should happen first.

## The three-part check

| Question | Plain-language meaning |
| --- | --- |
| Secret Source | Can the agent read something private or valuable, such as an API key, SSH key, browser session, customer record, or confidential document? |
| External Sink | Can it send data outside the trusted boundary through a model request, HTTP call, upload, email, chat, Git push, connector, or telemetry service? |
| Untrusted Content | Can a web page, email, issue, pull request, downloaded file, Skill, memory item, or tool result influence what it does? |

The combination is reported as Confirmed, Likely, Not demonstrated, or
Unknown. A reachable path is reported separately from evidence that a leak
actually happened. A named provider receiving the intended context is a data
flow to document, but it is not automatically an attacker-controlled sink.

## Risk levels

| Level | Plain-language meaning |
| --- | --- |
| Low | Narrow, controlled access with no material source, sink, or audit blind spot in the reviewed scope. |
| Medium | A meaningful gap or uncertainty exists, but the reviewed path is limited or not yet high-impact. |
| High | Broad access, shell or write authority, external writes, missing isolation or approval, or a Likely dangerous combination creates a realistic serious-harm path. |
| Critical | A real leak or compromise is evidenced, or the Confirmed three-part combination can carry sensitive data to an external sink under attacker-influenced instructions. |

These levels are this Skill's operational rubric. They are not an OWASP score,
legal conclusion, or security certification.

## Use it

Install it in the current project (recommended):

~~~bash
cd /path/to/project
npx skills add WardLu/skills --skill agent-privacy-check
~~~

Use --global only when you intentionally want this Skill across projects; that
increases the set of runs it can influence. Use --yes only after reviewing the
source and accepting the install prompt behavior.

Ask for a read-only review with a named scope. For example:

~~~text
Use Agent Privacy Check in read-only mode. Audit this project's agent setup and tell me what it can see, where data can leave, whether Secret Source + External Sink + Untrusted Content are connected, the worst credible consequence, and the first three fixes. Mark every claim as observed, available, not found, or unknown.
~~~

For a better result, name the platform, project or Skill, selected config
directory, and any boundary that is explicitly in scope.

## Results and boundaries

The report includes the scope, access map, egress map, untrusted-content map,
dangerous-combination result, risk level and confidence, worst credible
consequence, ordered remediation, evidence, and unknowns.

The audit is read-only by default. It does not print secret values, test
exfiltration with real data, install or remove Skills, change permissions,
rotate credentials, upload files, commit, push, publish, or deploy without
separate authorization. A configured capability is not presented as proof that
the agent used it.

## References

The workflow is informed by the
[OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
and the
[OWASP Agentic Skills Top 10](https://owasp.org/www-project-agentic-skills-top-10/).
See [references/sources.md](references/sources.md) for the adaptation boundary.

<details>
<summary>For maintainers</summary>

Run the offline contract tests with:

~~~bash
python3 -m unittest discover -s tests -v
~~~

The synthetic evaluation cases live in [evals/cases.json](evals/cases.json).
They are review fixtures for checking whether an agent produces a complete,
evidence-labeled report; they contain no real credentials or user data.

</details>

## License

MIT. See [LICENSE](../LICENSE).
