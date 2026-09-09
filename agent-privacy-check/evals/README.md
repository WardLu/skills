# Evaluation Cases

These cases are synthetic review fixtures for Agent Privacy Check. Give one
case to an independent agent together with the Skill and its named platform,
then check whether the result:

- answers what the agent can see and where data can leave;
- separates Observed, Available, Not found, and Unknown;
- identifies the Secret Source, External Sink, and Untrusted Content;
- distinguishes a reachable path from an observed leak;
- assigns the expected risk level without inventing evidence;
- explains a concrete worst case and orders practical fixes.

The expected values in cases.json are guidance for evaluation, not an
implementation of the Skill's judgment. An evaluator may report a mismatch
when the evidence is interpreted differently, but must explain the reasoning.
Do not add real credentials, private URLs, user data, or production artifacts
to these cases.

For a deterministic completeness check on a generated Markdown report, run:

~~~bash
python3 evals/check_report.py /path/to/report.md --case scoped-local-read
~~~

The checker verifies required sections, evidence labels, the three named
elements, expected case labels, and obvious credential-shaped strings. It is a
format and fixture check, not a security oracle or a replacement for human
review.

For a deterministic completeness check on a generated Markdown report, run:

~~~bash
python3 evals/check_report.py /path/to/report.md --case scoped-local-read
~~~

The checker verifies required sections, evidence labels, the three named
elements, expected case labels, and obvious credential-shaped strings. It is a
format and fixture check, not a security oracle or a replacement for human
review.
