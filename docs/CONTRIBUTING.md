# Contributing to FallByte

Thank you for your interest in contributing to **FallByte**! To keep the codebase clean, reliable, and easy to maintain, please follow the guidelines below before submitting a Pull Request.

For an overview of the project structure, modules, and design boundaries, see [ARCHITECTURE.md](../ARCHITECTURE.md).

## Development Setup

1. **Fork and clone** the repository:

   ```bash
   git clone https://github.com/<your-username>/FallByte.git
   cd FallByte
   ```

2. **Create and activate a virtual environment** at the project root:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # .venv\Scripts\activate   # Windows
   ```

3. **Install dependencies** (along with `pytest` for running tests):

   ```bash
   pip install -r requirements.txt
   pip install pytest
   ```

4. **Run the application** from source to verify everything works:

   ```bash
   python main.py
   ```

   *(Note: FFmpeg static binaries are bundled with the repository, so no external media engine installation is required.)*

## Pull Request Requirements

Every Pull Request must meet the following criteria before it can be merged:

### 1. Tests & `pytest`

* **New features & bug fixes require tests:** Any new functionality, bug fix, or behavioral change must include corresponding unit/integration tests under `tests/` (`tests/engine/` for core logic or `tests/ui/` for interface/controllers).

* **All tests must pass:** Run the full test suite locally before opening a PR:

  ```bash
  pytest
  ```

### 2. Internationalization (i18n) Rules

If your change adds, modifies, or removes any user-facing text in the UI:

* **Mandatory:** You **must** update both `resources/locales/en.yaml` and `resources/locales/_template.yaml`.

* **Other locales (`pt.yaml`, `es.yaml`, etc.):** Updating all supported languages is ideal, but not mandatory. If you only update English and the template, **explicitly mention in your PR description which locale files still need translation**.

* Ensure `pytest tests/ui/test_i18n.py` passes with your changes.

### 3. Code Style (PEP 8 / Ruff — Recommended)

* Please try to follow **PEP 8** conventions and **Ruff** formatting/linting standards (via your IDE extension or CLI) for any new or modified code.

* Since legacy parts of the codebase are still undergoing cleanup, strict linter compliance is **not a hard requirement** to merge a PR—just do your best to keep new changes clean.

### 4. Commits & Pull Request Descriptions

* **Map your changes:** Keep PRs focused and well-scoped. Avoid bundling unrelated changes into a single PR.

* **Detailed Commits:** Write clear, descriptive commit messages following Conventional Commits (e.g., `feat(video): ...`, `fix(ui): ...`, `refactor(i18n): ...`). Include a commit body explaining the *why* when the change is non-trivial.

* **Thorough PR Description:** Your PR description must clearly detail:

  * **What** was changed and **why**.

  * **Which files/modules** were affected.

  * **How** it was tested (confirming that `pytest` passed).

  * Any pending translation keys if only `en.yaml` and `_template.yaml` were updated.

## Checklist Before Submitting

* [ ] Unit/integration tests were added or updated for the changes
* [ ] Full test suite passes (`pytest`)
* [ ] `resources/locales/en.yaml` and `_template.yaml` are updated (and pending locales are noted in the PR description, if applicable)
* [ ] New/modified code makes a best-effort attempt to follow PEP 8 / Ruff guidelines
* [ ] Commit messages and PR description clearly map and explain all changes