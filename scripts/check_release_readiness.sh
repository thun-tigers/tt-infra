#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPOS=(tt-common tt-auth tt-members tt-agenda tt-attendance tt-analytics tt-infra)
EXPECTED_VERSION="${1:-}"
HAS_FAILURE=0

if [[ -z "${EXPECTED_VERSION}" ]]; then
  echo "Usage: $0 <version>"
  echo "Example: $0 0.1.0"
  exit 1
fi

if [[ ! "${EXPECTED_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Version must match MAJOR.MINOR.PATCH, got: ${EXPECTED_VERSION}" >&2
  exit 1
fi

for repo in "${REPOS[@]}"; do
  REPO_DIR="${ROOT_DIR}/${repo}"
  echo "== ${repo} =="

  if [[ ! -d "${REPO_DIR}/.git" ]]; then
    echo "FAIL: missing git repository at ${REPO_DIR}"
    HAS_FAILURE=1
    echo
    continue
  fi

  if [[ "${repo}" == "tt-common" ]]; then
    if [[ ! -f "${REPO_DIR}/pyproject.toml" ]]; then
      echo "FAIL: missing pyproject.toml"
      HAS_FAILURE=1
      echo
      continue
    fi
    VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "${REPO_DIR}/pyproject.toml")"
  else
    if [[ ! -f "${REPO_DIR}/VERSION" ]]; then
      echo "FAIL: missing VERSION file"
      HAS_FAILURE=1
      echo
      continue
    fi
    VERSION="$(tr -d '[:space:]' < "${REPO_DIR}/VERSION")"
  fi
  BRANCH="$(git -C "${REPO_DIR}" branch --show-current)"
  STATUS="$(git -C "${REPO_DIR}" status --short)"

  if [[ "${VERSION}" != "${EXPECTED_VERSION}" ]]; then
    echo "FAIL: VERSION is ${VERSION}, expected ${EXPECTED_VERSION}"
    HAS_FAILURE=1
  else
    echo "OK: VERSION=${VERSION}"
  fi

  if [[ "${BRANCH}" != "main" ]]; then
    echo "FAIL: branch is ${BRANCH}, expected main"
    HAS_FAILURE=1
  else
    echo "OK: branch=${BRANCH}"
  fi

  if [[ -n "${STATUS}" ]]; then
    echo "WARN: worktree is not clean"
    echo "${STATUS}"
    HAS_FAILURE=1
  else
    echo "OK: worktree clean"
  fi

  if git -C "${REPO_DIR}" rev-parse -q --verify "refs/tags/v${EXPECTED_VERSION}" >/dev/null; then
    echo "WARN: tag v${EXPECTED_VERSION} already exists locally"
    HAS_FAILURE=1
  else
    echo "OK: local tag v${EXPECTED_VERSION} does not exist"
  fi

  echo
done

if [[ "${HAS_FAILURE}" -ne 0 ]]; then
  echo "Release readiness check failed."
  exit 1
fi

echo "Release readiness check passed for ${EXPECTED_VERSION}."
