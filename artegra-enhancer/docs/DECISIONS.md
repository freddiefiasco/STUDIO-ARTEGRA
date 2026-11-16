# Release decisions

## 13 November 2026

- Build from the existing implementation and publish a pruned standalone source repository on GitHub.
- The final source selection is the v5 early preview, with Fast enabled. It supersedes the earlier selection of v4.
- Keep Standard's image graph and the selected Fast recipe intact. Do not enable single-image Fast splitting or Faster.
- Use a fresh Qt Quick host and separate per-user settings and authenticated local service.
- Publish source with fresh history. Do not carry internal history, deployment scripts, private records or model weights.
- Retain ownership of project code while identifying the GPL node package and third-party components separately.
- Leave model auto-download disabled until the outstanding model-licence questions are resolved.
- Binary pilot qualification and final pilot terms remain outstanding. Source publication does not assert completion of those gates.

## 17 November 2026: 5.0.0-beta.1

- The product becomes Artegra Enhancer (Beta), version 5.0.0-beta.1. The internal names that set the state folder and the settings namespace stay, so an alpha upgrades in place.
- The final v5 tab, service and finish-time logic are merged into the standalone with a three-way merge (base: the early v5 preview). The standalone's host contract, memory profiles and privacy scrub are kept. The engine and node pack are unchanged because the final v5 did not change them.
- Standard is renamed Redux and Fast is renamed Bolt wherever a person reads them. Redux is the API mode `standard`; Bolt is `fast`. The engine keeps its own labels; the service gives the new ones.
- A single Bolt image shares two cards only on the proven hardware: two identical desktop RTX 5090 cards with the original memory settings.
- Check for updates is manual only. There is no background check.
- The installer registers an uninstaller with two optional clean-up choices, both off by default. Images are never in scope. The consent files (LICENSE.txt and the model manifest) are unchanged so the upgrade needs no new consent.
- The pilot notice becomes the beta notice, marked as a draft for legal review.

