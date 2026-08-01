```markdown
# skills Development Patterns

> Auto-generated skill from repository analysis

## Overview

This repository demonstrates best practices for developing modular Python "skills" without a framework. It emphasizes clear documentation, consistent coding conventions, and structured workflows for adding, enhancing, and documenting skill packages. The patterns here are ideal for maintainable, collaborative Python codebases.

## Coding Conventions

- **File Naming:**  
  Use PascalCase for Python files and directories.  
  *Example:*  
  ```
  CodexCrossProviderSessionRepair/
  RepairSession.py
  ```

- **Import Style:**  
  Use relative imports within skill packages.  
  *Example:*  
  ```python
  from .RepairSession import RepairSession
  ```

- **Export Style:**  
  Use named exports (explicitly define what is exported).  
  *Example:*  
  ```python
  __all__ = ["RepairSession"]
  ```

- **Commit Messages:**  
  Follow the [Conventional Commits](https://www.conventionalcommits.org/) style.  
  - Prefixes: `docs`, `feat`
  - Example:  
    ```
    docs: update SKILL.md with new workflow
    feat: add session repair logic
    ```

## Workflows

### update-documentation-files
**Trigger:** When you want to improve, clarify, or add documentation for the repository or a skill.  
**Command:** `/update-docs`

1. Edit or add content to `README.md` at the root or within a skill directory.
2. Optionally update or add language-specific README files (e.g., `README.zh-CN.md`).
3. Update `CHANGELOG.md` and/or `SKILL.md` as needed.
4. Commit changes with a `docs:`-prefixed message.

*Example:*
```bash
# Edit documentation files
git add codex-cross-provider-session-repair/README.md
git commit -m "docs: clarify session repair steps"
```

---

### add-or-enhance-skill-package
**Trigger:** When you want to introduce a new skill or make significant updates to an existing skill's implementation and documentation.  
**Command:** `/add-skill`

1. Create or update the skill directory with necessary files (`README.md`, `SKILL.md`, scripts, tests, etc.).
2. Add or update scripts (e.g., `install.sh`, `package.py`, `repair.py`).
3. Update or add tests in the `tests/` subdirectory.
4. Update documentation files within the skill (`README.md`, `CHANGELOG.md`, `SKILL.md`, etc.).
5. Commit all changes together.

*Example:*
```bash
# Add a new skill
mkdir codex-cross-provider-session-repair
touch codex-cross-provider-session-repair/README.md
touch codex-cross-provider-session-repair/SKILL.md
touch codex-cross-provider-session-repair/scripts/repair.py
mkdir codex-cross-provider-session-repair/tests
touch codex-cross-provider-session-repair/tests/test_repair.py

git add codex-cross-provider-session-repair/
git commit -m "feat: add codex cross-provider session repair skill"
```

## Testing Patterns

- **Framework:** Not explicitly specified; use standard Python testing practices.
- **Test File Pattern:** Name test files as `*.test.*` or place them in a `tests/` subdirectory.
- **Example:**
  ```
  codex-cross-provider-session-repair/tests/test_repair.py
  ```
- **Typical Test Structure:**
  ```python
  import unittest
  from ..scripts.repair import repair_session

  class TestRepairSession(unittest.TestCase):
      def test_repair(self):
          self.assertTrue(repair_session())
  ```

## Commands

| Command      | Purpose                                                       |
|--------------|---------------------------------------------------------------|
| /update-docs | Update documentation files (README, SKILL.md, CHANGELOG, etc) |
| /add-skill   | Add or enhance a skill package with code, tests, and docs     |
```
