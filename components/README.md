# Published components

Each folder contains an independently installed schema-1 component.

- **TouchDeck 0.1.1** (`touchdeck/`): touchscreen dashboard, PipeWire mixer and MPRIS media controls.
- **[Cast Audio 0.5.1](cast-audio/README.md)** (`cast-audio/`): Fast/Balanced live AAC/HLS, desktop/app selection and MP3 compatibility casting from a compact Caelestia KDE receiver menu with inline source choices with a separate Settings app, manual receiver IPs and fixed stream ports. Requires Dev Manager 0.5.1+ for automatic panel integration. Casts a desktop output or one app playback stream to a local/routed Google Cast receiver. Requires a compatible Caelestia shell and Python; installation prepares private catt dependencies and known audio tools.

- **[Animated Timer 0.1.2](animated-timer/README.md)** (`animated-timer/`): native dashboard Timer tab, animated hourglass, wheel/keyboard/accelerating-arrow time editor, per-monitor top notch and persistent completion alarm with Stop actions. Requires Timer-capable Dev Manager 0.6.0+ and the pinned Caelestia KDE v2.5.1 host.

Add future components as `components/<id>/` with manifest.json, README.md, source and SVG assets.
Keep dependencies and permissions declared. Never commit environments, user data, credentials, symlinks or installer hooks.
Dev Manager discovers these folders through Component Store and downloads source only after review.
See [the component specification](../caelestia-dev-manager/docs/COMPONENT_SPEC.md) and [store documentation](../caelestia-dev-manager/docs/COMPONENT_STORE.md).
