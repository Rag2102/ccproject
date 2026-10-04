# ADR-004: v2 targets Python 3.12
Status: accepted
Date: 2026-10-04

Context: v1's `.python-version` said 3.11.15, while `ci.yml`, the README badge and the Lambda image use 3.12 (the Lambda base image could not install the pinned wheels on 3.11). The v1 checks on 4 Oct 2026 ran on 3.12.14 and passed (42 tests). The plan allows 3.11 or 3.12.

Decision: v2 pins Python 3.12 (`.python-version`, `requires-python` in `pyproject.toml`). v1 model pickles stay tied to the exact pins in `requirements.txt` (scikit-learn 1.8.0).

Alternatives considered: Stay on 3.11 (rejected: it already conflicts with CI and the Lambda image).

Consequences: One interpreter for CI, Lambda and local work. Any change of the scikit-learn pin requires re-verifying the v1 `.joblib` models.
