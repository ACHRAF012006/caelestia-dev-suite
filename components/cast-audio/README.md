# Cast Audio 0.3.0

Cast the selected PipeWire output monitor to a Google Cast receiver from a **separate expandable row below Caelestia KDE Quick Toggles**. Click its arrow to smoothly expand or collapse the receiver list, then choose a receiver inline. The Settings button opens a separate settings application. Microphones are excluded; local playback and default audio routing are preserved.

## Installation and panel integration

Use **Caelestia Dev Manager 0.5.0 or newer**. Open Component Store → Refresh → Cast Audio → Install/Update and review source, permissions and host changes. Installation prepares the declared Cast libraries, missing audio tools and an active UFW firewall after review and native administrator authentication where needed. New installations automatically add the receiver row, enable the plugin and restart Caelestia KDE. Updates preserve your enabled/disabled choice. No manual shell patch or icon registration step is needed.

This is a manager-owned adapter for the verified Caelestia KDE commit `e34b6957fad5ce9395841b65be9e3df180ccd65c`, not a public registration API. It checks two exact host files, preserves their originals in a private receipt and includes changes in transaction recovery. It recognizes the previous 0.1.1 native icon deployment and replaces it with the row. Unrecognized host changes block installation instead of being overwritten. See [adapter details](patches/README.md).

External plugin files could not resolve `qs.*` imports in the inspected Quickshell 0.3.1 runtime. The UI uses installed `Caelestia.Config.Tokens` and `Caelestia.Services.PaletteManager.tPalette`, standard Qt Quick controls and Quickshell IPC/processes.

## Dependencies

The compatible Caelestia KDE host and Python 3.11+ must already be installed. Dev Manager 0.5 prepares `catt==0.13.3` and its dependencies in a private component environment during Install. The installed helpers run `_venv/bin/python -m catt.cli`; no global `catt` launcher, global pip installation or manager environment is required. Settings uses the same installed interpreter. Installed audio continues independently of Dev Manager.

On Arch/CachyOS, missing `ffmpeg` and `pactl` are installed using the fixed `ffmpeg`/`libpulse` package mapping. Debian/Ubuntu uses `ffmpeg`/`pulseaudio-utils`. This preparation is reviewed and uses KDE's native administrator authentication. Other missing host tools and unsupported distributions receive explicit setup instructions. No component-supplied install hooks run. A failed or cancelled preparation prevents payload installation; previously completed package/rule changes may remain and retry checks their current state.

The default stream port is **48200**. If UFW is already enabled, installation prepares incoming TCP rules from the three private IPv4 ranges to **any local destination**, using your saved fixed port. The rules contain no computer or speaker IP. The HTTP server still binds the current route-selected address and only serves the selected receiver's private session URL. An inactive firewall is never enabled. Other firewall implementations and router policies require their own configuration. Rules and system packages remain after plugin uninstall. Changing the fixed port requires rerunning Install/Update to prepare its rule; port 0 requires manual firewall setup.

## Open and use

1. Open Caelestia's **Quick Toggles** panel and expand the **Cast Audio** row beneath the toggle buttons.
2. Choose a discovered receiver or a saved IP receiver. Refresh rescans the local network. Busy receivers are refused; stop their existing session through its current controller first.
3. Use **Stop casting** to end capture. Collapsing the menu or closing Settings keeps playback running. The receiver volume slider controls the active session.
4. Press **Settings** to select the output monitor, bitrate, discovery deadline and receiver preferences. Stop casting before saving changes.
5. For another VLAN, enter its receiver name and private IPv4 address, press **Add receiver**, then **Save settings**. The receiver appears in the inline menu immediately. An optional fixed stream port simplifies firewall rules.

Open the menu from a terminal with `quickshell -c caelestia ipc call castAudio open`. This opens the existing Utilities drawer and expands the row. Open Settings with `quickshell -c caelestia ipc call castAudio settings`. `castAudio toggle` expands/collapses the row; `castAudio stop` stops playback. Nexus → Utilities → Quick toggles → Connectivity → Cast Audio controls row visibility. If Nexus disabled the plugin itself, enable it there too.

Remembering a receiver does not start capture. **Reconnect at startup (starts audio capture)** is off by default and tries the remembered receiver once; it never repeatedly reclaims a replaced session. Settings errors retain unsaved changes so you can correct and retry.

## Other VLANs and Google accounts

Manual IPs bypass multicast discovery, but still require routing and firewall access. Allow computer → receiver TCP 8009, device-info TCP 8008/8443 as required by the receiver, and receiver → computer on the audio stream port. Use 0 for an automatically selected port or 1024–65535 for a fixed port. Installation prepares an active UFW firewall as described above; the running app does not change router policies.

**Google account connection is not implemented.** There is no supported account-discovery API in the Linux backend used here. Settings explains this and links to the official [Google Home APIs](https://developers.home.google.com/apis), which document Android/iOS SDKs. Account sign-in does not establish VLAN connectivity. No Google credentials are requested or stored.

## Connection sound without playback

The connection sound confirms the control connection; the receiver must separately fetch the HTTP audio stream from your computer. Release 0.3.0 reports the actual listening address/port if playback times out without a receiver request. Discovery refreshes preserve that playback error instead of replacing it with an mDNS warning. Saved receivers remain selectable when local discovery fails. Cast status queries allow up to 25 seconds for slower receivers.

Installation uses the saved fixed port (48200 by default), with portable UFW rules on the installing computer. It never uses an address from this development machine. The router must also permit **receiver → installing PC TCP stream port**, including reply traffic. This is a new connection from the receiver, separate from computer → receiver TCP 8009. Do not disable the firewall or terminate another application's listener to free a port.

A test with speaker `10.2.3.246` still failed after the PC firewall allowed its stream port and the user changed UniFi rules. A separate finite MP3 test also failed. A verified packet-header check saw Cast control traffic but no incoming stream connection; the receiver eventually reported LOAD_FAILED/idle ERROR. The speaker subsequently played Google's public sample audio stream, confirming working public media playback. The local stream remains inaccessible; this does not establish which router or private-network policy caused that failure. System-audio playback remains unverified; do not interpret a connection sound or a successful LOAD submission as working audio.

## Audio and network behavior

`PipeWire output monitor → FFmpeg → memory-only live MP3 HTTP stream → catt/PyChromecast → Google Cast default media receiver`.

Defaults: MP3, 192 kbit/s, 48 kHz, stereo. Available bitrates: 128/192/256/320 kbit/s. MP3 was selected for broad receiver compatibility and reliable MIME handling in the verified CLI. AAC/HLS is not implemented. Google documents MP3 support for its audio receivers in [Supported media](https://developers.google.com/cast/docs/media). Receiver buffers add several seconds of latency, sometimes more; there is no measured latency estimate or zero-latency claim.

The HTTP server exists only while connecting/casting. It binds one private IPv4 address selected by the route to the receiver, on an automatically selected or explicitly configured TCP port, rather than all interfaces. It accepts only the receiver's discovered address and that local address (needed for `catt`'s media inspection). A random 192-bit path changes for each session. There is no directory listing, configuration endpoint or remote-control API. Audio is unencrypted HTTP on the LAN and is never recorded to disk. Queues are bounded; slow readers disconnect instead of accumulating audio indefinitely. No HTTP URL/token or captured audio is logged.

The receiver must reach that local TCP port; a firewall or Wi-Fi client isolation can prevent playback even when discovery succeeds. Dev Manager prepares an active UFW firewall during reviewed installation; the runtime never changes router policies. Startup and manual discovery run asynchronously. Concurrent refreshes coalesce; manual requests have a 10-second cooldown. Automatic discovery runs every 90 seconds only while the receiver menu is expanded, visible and idle. Casting checks capture health locally each second and receiver/audio status approximately every 10 seconds, plus command deadlines. Lost routes, output changes, receiver replacement, FFmpeg failure and timeouts stop capture and report an error.

Discovery is local mDNS through `catt`. See Google's [Discovery troubleshooting](https://developers.google.com/cast/docs/discovery). I found no documented, appropriate Linux desktop API for enumerating Cast receivers through a Google account. Google's [Home APIs](https://developers.home.google.com/apis) describe Android/iOS SDKs; this component implements local discovery and saved private IP addresses and neither requests nor stores Google credentials.

## Limits and lifecycle

Only private/link-local IPv4 receivers with standard Cast port 8009 are connectable. Discovered nonstandard-port groups are shown disabled, because the inspected CLI's IP-address path uses port 8009. IPv6-only/public-address advertisements are omitted. Some groups consequently cannot be used in this release. `catt` keys scan output by friendly name; give receivers unique names to avoid its duplicate-name ambiguity. The discovery deadline is a bound on the entire CLI scan, not a configurable mDNS library timeout.

Each start requires a currently listed discovered or saved receiver ID. Receiver stop and volume commands check that the media URL still belongs to this session. That check and the subsequent CLI command cannot be atomic across independent controllers; avoid simultaneous commands from another sender. A replacement session is preserved when detected. If the network is lost, stopping the receiver remotely is best effort; local capture and HTTP serving still end.

The helper owns every subprocess it starts, cancels bounded operations, terminates/reaps exact child PIDs and uses Linux parent-death guards for FFmpeg/catt. It has one private per-user lock. Helper EOF, normal unload, shell exit and termination end capture. A hard shell/helper kill also removes the in-process HTTP server and triggers child parent-death termination; a receiver may remain on an expired/buffering session until it notices the stream ended. There is no broad process killing or detached HTTP-server daemon.

Preferences: `$XDG_CONFIG_HOME/cast-audio/settings.json`, mode 0600. The component's private `catt` configuration lives below the same config directory. Lock/cache paths use `$XDG_RUNTIME_DIR/cast-audio`, with `$XDG_CACHE_HOME/cast-audio` fallback. Corrupt settings safely reset in memory; an explicit save replaces the invalid file. Runtime data is outside the manager-owned executable snapshot. Dev Manager 0.4 restarts the shell automatically after enable/disable, installation/update, restore or uninstall of the integrated component. Uninstall removes the managed panel bridge and restores the verified original host files; later host edits block removal until reconciled. Its user preferences are retained.

## Verification

Run `python3 -B -m unittest discover -s tests -v` from this component. Nineteen tests cover monitor-only capture, private-IP/settings validation, saved receivers despite discovery failure, busy/replaced-session protection, cancellation, stream boundaries, fixed-port collision and private settings IPC.

On a compatible Caelestia KDE Wayland desktop, run `python3 -B tests/quick_toggle_probe.py --shell "${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/caelestia"`. The isolated native QML probe copies the host, uses temporary XDG paths and a fake controller, and verifies the separate row, expand/collapse, inline receiver selection, Settings action, Utilities opening, Nexus visibility and unload. It does not capture audio or modify the live host. No physical receiver playback or receiver-specific latency was tested.

The private settings-only Unix socket is mode 0600 and verifies the current user's peer credentials. Requests cannot start playback. Settings also supports saving preferences when the plugin is stopped. No settings HTTP endpoint or remote account control is exposed.

Original component code/artwork is MIT licensed. The optional host patches and upstream context are GPL-3.0-only Caelestia modifications. The separately installed [catt](https://github.com/skorokithakis/catt) implementation is not bundled.
