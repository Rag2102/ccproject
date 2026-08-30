# Lambda container image for the live-demo API (GET /api/meta, POST
# /api/predict). Build from the REPO ROOT so this can COPY the webapp,
# models, and small reference-data files it needs:
#
#   docker build -f cloud/api/Dockerfile -t vm-mitigation-api .
#
# See cloud/README.md for the full build -> push (ECR) -> deploy flow.
FROM public.ecr.aws/lambda/python:3.12

# NOTE on the base image version: this was originally :3.11 (Amazon Linux 2,
# glibc 2.26). numpy's wheels for this platform are built tagged
# manylinux_2_28 (requires glibc >= 2.28), so on AL2 pip couldn't find a
# matching wheel and fell back to compiling numpy from source -- which then
# failed outright because AL2's yum-installable gcc tops out at 7.3.1, and
# numpy's build requires gcc >= 9.3. Rather than fight AL2's ancient
# toolchain (Software Collections / devtoolset gymnastics), the actual fix
# is one line: the :3.12 base image is Amazon Linux 2023 (glibc 2.34), so
# pip resolves numpy's prebuilt manylinux_2_28 wheel directly and never
# needs a compiler at all. No yum/gcc install step needed as a result.

COPY cloud/api/requirements.txt ./
# Upgrade pip first: the Lambda base image's bundled pip is old enough that
# it doesn't recognize newer manylinux platform tags on some packages
# (numpy in particular), which makes it silently fall back to building from
# source -- slow, and likely to fail outright since this minimal base image
# has no C/Fortran toolchain. A current pip resolves the prebuilt wheel
# instead of trying to compile one.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# App code: the Flask app (unchanged from the Render deployment) plus the
# core.py it shares with it, and the small policy/GQAT-Net modules it
# imports at load time.
COPY webapp ./webapp
COPY scripts/policy.py scripts/gqat_net_numpy.py scripts/numpy_nn.py ./scripts/

# Trained models (small: ~300KB and ~260KB -- see docs/task11_summary.md /
# the joblib cache-clearing fix for why they're this small).
COPY models ./models

# Only the small reference-data files core.py actually reads at import time.
# Deliberately NOT copying data/raw or the 3 large Git-LFS files (~550MB
# combined) -- core.py never touches them (see requirements.txt at the repo
# root for the same reasoning applied to the webapp's own dependency list).
COPY data/processed/hazard_lookup_table.csv \
     data/processed/gqat_net_vs_histgbm_comparison.csv \
     data/processed/simulation_headline_summary.csv \
     data/processed/correlated_assignment_sweep.csv \
     data/processed/size_tier_profile.json \
     ./data/processed/

COPY cloud/api/lambda_function.py ./

CMD ["lambda_function.handler"]
