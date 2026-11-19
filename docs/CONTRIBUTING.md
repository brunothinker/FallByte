# Contributing to FallByte

Thank you for your interest in contributing to **FallByte**! To keep the codebase clean, reliable, and easy to maintain, please follow the guidelines below before submitting a Pull Request.

For an overview of the project structure, modules, and design boundaries, read [ARCHITECTURE.md](ARCHITECTURE.md). By participating you agree to follow our [Code of Conduct](../CODE_OF_CONDUCT.md). To report a vulnerability, see [SECURITY.md](../SECURITY.md).

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

3. **Install dependencies** (the dev file already includes `pytest` and `pytest-cov`):

   ```bash
   pip install -r tests/requirements-dev.txt
   ```

4. **Run the application** from source to verify everything works:

   ```bash
   python main.py
   ```

   *(FFmpeg static binaries are bundled with the repository, so no external media engine installation is required.)*

## Where things go

| You are changing... | Code lives in | Tests live in |
|---|---|---|
| Image / video / audio processing | `src/image/`, `src/video/`, `src/audio/` | `tests/image/`, `tests/video/`, `tests/audio/` |
| Batch runner, naming, cleanup, config | `src/utils/` | `tests/batch/`, `tests/utils/` |
| Pages, controllers, components, i18n | `ui/` | `tests/ui/` |

Keep all processing logic inside `src/` and **never import `ui` from `src/`**. The `src/audio/` package must not import `src.video` or `src.image` (enforced by a test). Expose engine features to the UI only through a controller in `ui/controllers/`.

## Pull Request Requirements

### 1. Tests & `pytest`

* **New features & bug fixes require tests:** any new functionality, bug fix, or behavioral change must include unit/integration tests in the matching folder under `tests/` (see the table above).

* **All tests must pass.** Run the full suite locally before opening a PR:

  ```bash
  pytest
  ```

  You can also run only part of it, for example `pytest tests/ui` or `pytest tests/audio tests/batch tests/image tests/utils tests/video`.

* Tests that need FFmpeg use the bundled binary and skip themselves when an encoder is missing.

### 2. Internationalization (i18n) Rules

If your change adds, modifies, or removes any user-facing text in the UI:

* **Mandatory:** update both `resources/locales/en.yaml` and `resources/locales/_template.yaml` with the same keys.

* **Other locales (`pt.yaml`, `es.yaml`, ...):** translating everything is ideal but not mandatory. If you only update English and the template, **explicitly mention in your PR description which locale files still need translation**. A locale that is out of sync with the template is skipped at startup and the app falls back to English.

* Placeholders such as `{count}` or `{formats}` must match `en.yaml` in every language.

* Make sure `pytest tests/ui/test_i18n.py` passes.

### 3. Code Style (PEP 8 / Ruff)

* New and modified code should follow **PEP 8** and pass **Ruff**:

  ```bash
  ruff check .
  ruff format --check .
  ```

* Some legacy parts of the codebase are still being cleaned up, so existing warnings in files you did not touch will not block a PR. Just do not add new ones.

### 4. Commits & Pull Request Descriptions

* **Keep PRs focused.** Avoid bundling unrelated changes.

* **Detailed commits:** use [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat(audio): ...`, `fix(ui): ...`, `refactor(i18n): ...`) and explain the *why* in the body when the change is non-trivial.

* **Thorough PR description:** state clearly
  * **What** was changed and **why**.
  * **Which files/modules** were affected.
  * **How** it was tested (confirm `pytest` passed).
  * Any pending translation keys if only `en.yaml` and `_template.yaml` were updated.

## Checklist Before Submitting

- [ ] Unit/integration tests were added or updated for the changes
- [ ] Full test suite passes (`pytest`)
- [ ] Processing logic stays in `src/` and `src/` does not import `ui`
- [ ] `resources/locales/en.yaml` and `_template.yaml` are updated (pending locales are noted in the PR description)
- [ ] New/modified code follows PEP 8 and passes `ruff check .`
- [ ] No new type errors (Pyright / Pylance) were introduced in `src/` or `ui/` modules
- [ ] Commit messages and PR description clearly explain all changes