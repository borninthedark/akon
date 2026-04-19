# Akon - Kernel & Module Artifact Builder
# Usage:
#   make build-kernel PROFILE=mainline VERSION=6.19.12
#   make build-kernel SOURCE=copr COPR=bieszczaders/kernel-cachyos VERSION=6.19.12
#   make build-zfs VERSION=6.19.12 ZFS=2.3.1
#   make build-all PROFILE=stable VERSION=6.19.12 ZFS=2.3.1
#   make publish-local-all VERSION=6.19.12 ZFS=2.3.1
#   make local PROFILE=mainline VERSION=6.19.12 ZFS=2.3.1

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Defaults
FEDORA   ?= 43
PROFILE  ?=
SOURCE   ?= fedora-srpm
COPR     ?=
URL      ?=
REGISTRY ?= ghcr.io
OWNER    ?= borninthedark
OUTPUT   ?= $(CURDIR)/output

# Derived
KERNEL_RPM_DIR := $(OUTPUT)/kernel-rpms
MODULE_RPM_DIR := $(OUTPUT)/module-rpms

# Profile or explicit source
_SOURCE_ARGS = $(if $(PROFILE),--profile "$(PROFILE)",--source "$(SOURCE)")
_COPR_ARGS   = $(if $(COPR),--copr "$(COPR)")
_URL_ARGS    = $(if $(URL),--url "$(URL)")

.PHONY: help test lint list-profiles \
        build-kernel build-zfs build-all \
        publish-kernel publish-zfs publish-all \
        publish-local-kernel publish-local-zfs publish-local-all \
        local clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-24s %s\n", $$1, $$2}'

# ---------- Info ----------

list-profiles: ## List available kernel and module profiles
	@echo "Kernel profiles:"
	@uv run python -m tools.profiles list kernel | sed 's/^/  /'
	@echo ""
	@echo "Module profiles:"
	@uv run python -m tools.profiles list module | sed 's/^/  /'

# ---------- Test & Lint ----------

test: ## Run pytest
	uv run pytest

lint: ## Run pre-commit hooks on all files
	uv run pre-commit run --all-files

# ---------- Build ----------

build-kernel: ## Build kernel RPMs (VERSION= required, PROFILE= or SOURCE=)
	@test -n "$(VERSION)" || { echo "ERROR: VERSION is required"; exit 1; }
	uv run python -m tools.build_kernel \
		$(_SOURCE_ARGS) \
		--version "$(VERSION)" \
		--fedora "$(FEDORA)" \
		$(_COPR_ARGS) \
		$(_URL_ARGS) \
		--output "$(KERNEL_RPM_DIR)"

build-zfs: ## Build ZFS module RPMs (VERSION= ZFS= required)
	@test -n "$(VERSION)" || { echo "ERROR: VERSION is required"; exit 1; }
	@test -n "$(ZFS)" || { echo "ERROR: ZFS version is required"; exit 1; }
	uv run python -m tools.build_module \
		--module zfs \
		--kernel-version "$(VERSION)" \
		--zfs-version "$(ZFS)" \
		--fedora "$(FEDORA)" \
		--kernel-rpms "$(KERNEL_RPM_DIR)" \
		--output "$(MODULE_RPM_DIR)"

build-all: build-kernel build-zfs ## Build kernel + ZFS module RPMs

# ---------- Publish to GHCR ----------

publish-kernel: ## Push kernel RPMs to GHCR (VERSION= required)
	@test -n "$(VERSION)" || { echo "ERROR: VERSION is required"; exit 1; }
	uv run python -m tools.publish \
		--type kernel \
		--version "$(VERSION)" \
		--fedora "$(FEDORA)" \
		--registry "$(REGISTRY)" \
		--owner "$(OWNER)" \
		--rpm-dir "$(KERNEL_RPM_DIR)"

publish-zfs: ## Push ZFS module RPMs to GHCR (VERSION= ZFS= required)
	@test -n "$(VERSION)" || { echo "ERROR: VERSION is required"; exit 1; }
	@test -n "$(ZFS)" || { echo "ERROR: ZFS version is required"; exit 1; }
	uv run python -m tools.publish \
		--type module \
		--module zfs \
		--version "$(VERSION)-fc$(FEDORA)-zfs-$(ZFS)" \
		--fedora "$(FEDORA)" \
		--registry "$(REGISTRY)" \
		--owner "$(OWNER)" \
		--rpm-dir "$(MODULE_RPM_DIR)"

publish-all: publish-kernel publish-zfs ## Push all artifacts to GHCR

# ---------- Publish to local registry ----------

publish-local-kernel: ## Push kernel RPMs to local registry (localhost:5000)
	@test -n "$(VERSION)" || { echo "ERROR: VERSION is required"; exit 1; }
	uv run python -m tools.publish \
		--type kernel \
		--version "$(VERSION)" \
		--fedora "$(FEDORA)" \
		--registry "localhost:5000" \
		--owner "$(OWNER)" \
		--rpm-dir "$(KERNEL_RPM_DIR)"

publish-local-zfs: ## Push ZFS module RPMs to local registry (localhost:5000)
	@test -n "$(VERSION)" || { echo "ERROR: VERSION is required"; exit 1; }
	@test -n "$(ZFS)" || { echo "ERROR: ZFS version is required"; exit 1; }
	uv run python -m tools.publish \
		--type module \
		--module zfs \
		--version "$(VERSION)-fc$(FEDORA)-zfs-$(ZFS)" \
		--fedora "$(FEDORA)" \
		--registry "localhost:5000" \
		--owner "$(OWNER)" \
		--rpm-dir "$(MODULE_RPM_DIR)"

publish-local-all: publish-local-kernel publish-local-zfs ## Push all to local registry

# ---------- Composite ----------

local: build-all publish-local-all ## Build + publish all to local registry

# ---------- Housekeeping ----------

readme: ## Regenerate README.md from project state
	uv run python -m tools.generate_readme

clean: ## Remove build output
	rm -rf "$(OUTPUT)"
