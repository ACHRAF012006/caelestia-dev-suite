# Published components

Each folder contains an independently installed schema-1 component.

- **TouchDeck 0.1.1** (`touchdeck/`): touchscreen dashboard, PipeWire mixer and MPRIS media controls.
- **[Cast Audio 0.2.0](cast-audio/README.md)** (`cast-audio/`): Expandable Caelestia KDE receiver menu with a separate Settings app, manual receiver IPs and fixed stream ports. Requires Dev Manager 0.4+ for automatic panel integration. Casts a PipeWire output monitor to a local/routed Google Cast receiver. Requires a compatible Caelestia shell, FFmpeg, pactl and catt.

Add future components as `components/<id>/` with manifest.json, README.md, source and SVG assets.
Keep dependencies and permissions declared. Never commit environments, user data, credentials, symlinks or installer hooks.
Dev Manager discovers these folders through Component Store and downloads source only after review.
See [the component specification](../caelestia-dev-manager/docs/COMPONENT_SPEC.md) and [store documentation](../caelestia-dev-manager/docs/COMPONENT_STORE.md).
