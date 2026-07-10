#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPOS=(tt-common tt-auth tt-members tt-agenda tt-attendance tt-analytics tt-infra)
VERSION="${1:-}"
MODE="${2:---dry-run}"

if [[ -z "${VERSION}" ]]; then
  echo "Usage: $0 <version> [--apply|--push]"
  echo "Example: $0 0.1.0 --dry-run"
  exit 1
fi

if [[ ! "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Version must match MAJOR.MINOR.PATCH, got: ${VERSION}" >&2
  exit 1
fi

"${ROOT_DIR}/tt-infra/scripts/check_release_readiness.sh" "${VERSION}"

for repo in "${REPOS[@]}"; do
  REPO_DIR="${ROOT_DIR}/${repo}"
  TAG="v${VERSION}"
  MESSAGE="${repo} ${TAG}"

  if [[ "${MODE}" == "--dry-run" ]]; then
    echo "[dry-run] git -C ${REPO_DIR} tag -a ${TAG} -m \"${MESSAGE}\""
    if git -C "${REPO_DIR}" remote get-url origin >/dev/null 2>&1; then
      echo "[dry-run] git -C ${REPO_DIR} push origin ${TAG}"
    fi
    continue
  fi

  git -C "${REPO_DIR}" tag -a "${TAG}" -m "${MESSAGE}"
  echo "Created ${repo}:${TAG}"

  if [[ "${MODE}" == "--push" ]]; then
    git -C "${REPO_DIR}" push origin "${TAG}"
    echo "Pushed ${repo}:${TAG}"
  fi
done
