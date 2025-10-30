## v1.0.2 (2025-10-30)

- fix: correct release workflow YAML and bump metadata to 1.0.2

## v1.0.1 (2025-10-30)

- chore: bump add-on metadata to version 1.0.1

## v1.0.0 (2025-10-30)

- feat!: generalise add-on to “Website Price Tracker (MQTT)” with configurable naming, refreshed docs and repository metadata

## v0.0.15 (2025-10-29)

- chore: bump add-on config.yaml to v0.0.15 (github-actions[bot])

## v0.0.14 (2025-10-28)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.19] - 2025-10-30
### Changed
- website_price_tracker/app/app.py (line 64) now accepts an optional product_name, defaults to “Website Price Tracker”, binds it into logging, discovery payloads, and the MQTT refresh button so every entity reads <product_name> … instead of the former Jura wording, while keeping the manual refresh workflow intact. website_price_tracker/config.yaml (line 1) / website_price_tracker/manifest.json (line 1) rebrand the add-on to “Website Price Tracker (MQTT)”, bump to v1.0.0, switch the default base topic to price_tracker, expose product_name in the schema, and use a neutral icon; the sample site list is now generic. website_price_tracker/rootfs/etc/services.d/app/run and …/finish print the new add-on name during start/stop, matching the device details advertised to MQTT. Repository metadata and docs (README.md (line 1), website_price_tracker/README.md (line 1), repository.yaml (line 1)) were rewritten around the general-purpose scope and now reference the suggested GitHub repo name mqtt-website-price-tracker. CI and changelogs (.github/workflows/release.yml (line 41), CHANGELOG.md (line 1), website_price_tracker/CHANGELOG.md (line 1)) track the renamed folder, new version, and document the rebrand plus dynamic refresh button naming. #major (Sven Kortekaas)
## [0.0.18] - 2025-10-30
### Changed
- On-connect logging now handles Paho’s ReasonCode without forcing it through int(), so the callback no longer crashes, and the MQTT force-refresh thread keeps working without colliding with the coroutine loop. (Sven Kortekaas)
## [0.0.17] - 2025-10-30
### Added
- Added an MQTT-discovered refresh button so forcing an update publishes immediately through the scraper loop. (Sven Kortekaas)
## [0.0.16] - 2025-10-29
### Changed
- chore: align changelog content and automate release updates #patch (Sven Kortekaas)
## [0.0.14] - 2025-10-28
### Fixed
- Guard minimum and maximum price validation to avoid rejecting valid retailer data.

## [0.0.13] - 2025-10-28
### Fixed
- Apply per-site price scaling for Koffiestore so inflated prices are corrected before validation.

## [0.0.12] - 2025-10-28
### Added
- Structured logging and Home Assistant logbook integration for price updates.

## [0.0.11] - 2025-10-28
### Fixed
- Resolve indentation issues that prevented error details from being reported correctly.

## [0.0.10] - 2025-10-28
### Fixed
- Correct JSON-LD cent extraction and add plausibility bounds to ignore off-range prices.

## [0.0.9] - 2025-10-28
### Fixed
- Replace deprecated `asyncio.get_event_loop()` usage to keep the add-on compatible with newer Python versions.

## [0.0.8] - 2025-10-28
### Removed
- Delete a leftover temporary patch file from the repository.

## [0.0.7] - 2025-10-28
### Changed
- Synchronize the add-on `config.yaml` version with `manifest.json` during releases.

## [0.0.6] - 2025-10-28
### Fixed
- Build the add-on inside a virtual environment and mark run scripts as executable to fix container startup.

## [0.0.5] - 2025-10-26
### Fixed
- Update configuration schema to match Home Assistant requirements by removing headers and correcting integer ranges.

## [0.0.4] - 2025-10-26
### Changed
- Refresh repository metadata to reflect the public GitHub project details.

## [0.0.3] - 2025-10-26
### Changed
- Quote add-on metadata fields in `config.yaml` to satisfy Home Assistant's schema validation.

## [0.0.2] - 2025-10-26
### Changed
- Migrate repository metadata from `repository.json` to `repository.yaml`.

## [0.0.1] - 2025-10-26
### Added
- Initial release with MQTT-based price scraping for the Jura S8 across multiple Dutch retailers.
- Publish MQTT Discovery sensors including price history for Home Assistant dashboards.

[Unreleased]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.19...HEAD
[0.0.19]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.18...v0.0.19
[0.0.18]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.17...v0.0.18
[0.0.17]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.16...v0.0.17
[0.0.16]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.15...v0.0.16
[0.0.15]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.14...v0.0.15
[0.0.14]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.13...v0.0.14
[0.0.13]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.12...v0.0.13
[0.0.12]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.11...v0.0.12
[0.0.11]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.10...v0.0.11
[0.0.10]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.9...v0.0.10
[0.0.9]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.8...v0.0.9
[0.0.8]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.7...v0.0.8
[0.0.7]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.6...v0.0.7
[0.0.6]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.5...v0.0.6
[0.0.5]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.4...v0.0.5
[0.0.4]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/SvenKortekaas/juras8pricetracker/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/SvenKortekaas/juras8pricetracker/releases/tag/v0.0.1
