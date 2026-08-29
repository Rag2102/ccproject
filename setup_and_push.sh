#!/usr/bin/env bash
# Fetches/regenerates the 3 large Azure files, sets up Git LFS to track them
# (.gitattributes already does this -- see there), and pushes everything to
# https://github.com/Rag2102/ccproject.
#
# Run this from a REAL terminal on your Mac (not through Claude's sandboxed
# workspace, which has no internet access and no git credentials) -- your
# normal Terminal.app or iTerm, wherever you're already signed in to GitHub
# (SSH key or `gh auth login` / credential manager).
#
# Prereqs this script checks for: git, git-lfs (installs via Homebrew if
# missing and Homebrew is present), python3 with pandas/numpy/scikit-learn
# (only needed to regenerate 2 of the 3 large files -- see below).
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1. Git LFS =="
if ! git lfs version >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "Installing git-lfs via Homebrew..."
    brew install git-lfs
  else
    echo "git-lfs not found and Homebrew isn't available. Install it manually"
    echo "(https://git-lfs.com) then re-run this script." >&2
    exit 1
  fi
fi
git lfs install

echo
echo "== 2. Fetching/regenerating the 3 large Azure files =="
mkdir -p data/raw/azure
if [ ! -f data/raw/azure/vmtable.csv.gz ]; then
  echo "Downloading the ~156MB Azure Public Dataset V1 VM table (Microsoft's own GitHub release, CC BY 4.0)..."
  curl -L -o data/raw/azure/vmtable.csv.gz \
    https://github.com/Azure/AzurePublicDataset/releases/download/dataset-v1/trace_data_vmtable_vmtable.csv.gz
else
  echo "data/raw/azure/vmtable.csv.gz already present, skipping download."
fi

if [ ! -f data/processed/azure_vms_clean.csv.gz ] || [ ! -f data/processed/azure_vms_with_costs.csv.gz ]; then
  echo "Regenerating the 2 derived files by re-running this project's own pipeline scripts..."
  echo "(needs: pip install -r requirements.txt)"
  ( cd scripts && python3 01_preprocess.py && python3 04_workload_criticality_cost.py )
else
  echo "Derived files already present, skipping regeneration."
fi

echo
echo "== 3. Git init + commit + push =="
git init
git add .
git commit -m "Initial commit: VM mitigation policy project (code, docs, real data, live demo)"
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/Rag2102/ccproject.git
git push -u origin main

echo
echo "Done. Repo: https://github.com/Rag2102/ccproject"
