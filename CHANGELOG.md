# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

## [1.0.0-alpha.0](https://github.com/do-mgix/evove-by-roko/compare/v1.0.0-alpha...v1.0.0-alpha.0) (2026-02-07)


### Features

* implementation of base user agenda service ([2b8edec](https://github.com/do-mgix/evove-by-roko/commit/2b8edec6635238501990b132a82df953c496dfe5))
* web client cancel button ([d70bced](https://github.com/do-mgix/evove-by-roko/commit/d70bcedc7abc039045b96cba507f4d205a18280a))


### Bug Fixes

* refactor on token daily refill method and lock implementation ([26b519f](https://github.com/do-mgix/evove-by-roko/commit/26b519fb0a1000f9e902b509f1227645c48f9790))

## [1.0.0-alpha] - 05-02-2026 
### Added
- Base structure of user agenda service
- Web Client: Cancel button

### Changed
- Token Refill method moved to user.py

### Fixed
- Gitignore fixes to ignore local user json files
- Gitignore fix to igonre local development tests folder
- Added lock to user.json to avoid token conflicts at multi-client system

### Removed 
-
