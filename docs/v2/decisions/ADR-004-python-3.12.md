# ADR-004: v2 targets Python 3.12

Status: accepted (4 Oct 2026, on the owner's instruction to complete Week 1).

Context: v1's `.python-version` says 3.11.15, while `ci.yml`, the README badge and the Lambda image use 3.12 (the Lambda base image's glibc could not install the pinned wheels on 3.11). The v1 checks on 4 Oct 2026 ran on 3.12.14 and passed (42 tests).

Decision: v2 pins Python 3.12 (plan allows 3.11 or 3.12). `.python-version` is updated when the v2 environment is created. v1 model pickles stay tied to the exact pins in `requirements.txt` (scikit-learn 1.8.0).

Consequences: one interpreter for CI, Lambda and local work. Any change of the scikit-learn pin requires re-verifying the v1 `.joblib` models.
