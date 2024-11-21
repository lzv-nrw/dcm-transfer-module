# Changelog

## [2.0.1] - 2024-11-21

### Changed

- updated package metadata, Dockerfiles, and README

## [2.0.0] - 2024-10-16

### Changed

- **Breaking:** implemented changes of API v2 (`ae6dd725`)
- migrated to `dcm-common` (scalable orchestration and related components; latest `DataModel`) (`ae6dd725`)

## [1.0.2] - 2024-07-26

### Fixed

- fixed typo in environment configuration-section of README (`d5badb77`)
- fixed progress-message (missing space) (`9c6e8bb2`)

## [1.0.0] - 2024-07-24

### Changed

- improved report.progress.verbose and log messages (`1fbafcfa`, `47b19dbc`)
- made SSH/rsync options configurable via env (`d2a2586f`)
- **Breaking:** updated to API v1 (`5104fb5d`, `a8ef319d`)

### Fixed

- fixed bad values for `data.success` in intermediate reports (`a8ef319d`)
- fixed incorrect values in self-description (`5104fb5d`)
- fixed typo in error message (`f16042bd`)

## [0.1.0] - 2024-07-01

### Changed

- initial release of dcm-transfer-module
