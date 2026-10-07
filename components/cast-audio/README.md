# Cast Audio 0.1.1

A Caelestia plugin that casts the selected PipeWire output monitor to a local Google Cast receiver. All applications playing through that output are included. Other outputs are not mixed together. Microphones are excluded. Local playback stays enabled; default devices and volume routing are never changed.

## Verified integration and its limitation

Inspected the installed `$XDG_CONFIG_HOME/quickshell/caelestia` against commit `e34b6957fad5ce9395841b65be9e3df180ccd65c` on 2026-10-07. The installed source has no Git directory; the inspected files match the pinned reference byte for byte. See [inspection and patch notes](patches/README.md).

Quick Toggles are a fixed `DelegateChooser` in `shell/modules/utilities/cards/Toggles.qml`. `Config.utilities.quickToggles` configures IDs/enabled state, but does not register new delegates. Nexus's `QuickTogglesPage.qml` also lists fixed IDs. The plugin loader creates a plugin's `main.qml` beneath `PluginLoader`; it exposes no Quick Toggle registration method.

This package uses the supported `caelestia-plugin` loader and provides a Caelestia-styled Cast control window. `patches/quick-toggles.patch` adds a native Cast icon to Caelestia KDE's existing Quick Toggles rows and a Cast Audio visibility setting in Nexus. Clicking the icon opens the receiver controls; it highlights while connecting/casting. The icon disappears when the plugin is unloaded or disabled. This is an explicit two-file host modification, not an upstream registration API. Installing from the store alone never applies the host patch; see [deployment and rollback](patches/README.md). The window stays closed at startup until opened through the icon or IPC.

External plugin files could not resolve `qs.*` imports in the inspected Quickshell 0.3.1 runtime. The UI uses the verified installed `Caelestia.Config.Tokens` and `Caelestia.Services.PaletteManager.tPalette` exports, standard Qt Quick controls, and Quickshell windows/processes/IPC. The bundled monochrome SVG is tinted from the palette without requiring a GPU shader.

## Dependencies

Required executables, declared in `manifest.json`:

| Executable | Requirement |
| --- | --- |
| `quickshell` | Existing compatible Caelestia host; tested with 0.3.1 |
| `python3` | Python 3.11 or newer; helper uses only its standard library |
| `pactl` | JSON output and `get-default-sink`; reachable PipeWire PulseAudio compatibility server |
| `ffmpeg` | PulseAudio input and `libmp3lame` encoder enabled |
| `catt` | Version 0.13.2 or newer; tested with 0.13.3 |

Install missing tools manually using your trusted dependency-management workflow. They must be on the PATH inherited by `caelestia-shell.service`. An existing private user environment can supply `catt`; no global Python installation is needed. Restarting a terminal does not update the running shell's PATH.

Dev Manager's current manifest/install contract allows privately prepared Python packages only for Python components, whereas this plugin requires the `quickshell` runtime. Accordingly, the plugin declares `catt` as a required executable and uses its established command interface. `catt`'s separate installation manages its PyChromecast/zeroconf dependencies. No Python distributions are imported into the shell or automatically installed by this component. Missing `catt` is a real dependency error; save a draft until it is available rather than ignoring validation.

### Resolving “Incompatible / Broken” with missing catt

Open the component's Dependencies or Validation details. If the only error is `Missing system executable: catt (install manually)`, this is a missing tool, not an incompatible Caelestia commit or broken source. Newer Dev Manager source labels this case `Missing Dependencies`.

For this inspected desktop, both Dev Manager and the running shell have `$HOME/.local/bin` on PATH. The following optional manual setup installs the tested catt release into its own user environment and copies its console launcher into that directory. It does not install a system package or modify global Python. Review and run the commands yourself; the plugin never runs them. Stop if either destination already exists, rather than overwriting unrelated files.

```bash
(
    set -eu
    cast_env="${XDG_DATA_HOME:-$HOME/.local/share}/cast-audio/dependencies/catt"
    if test -e "$cast_env" || test -L "$cast_env" || test -e "$HOME/.local/bin/catt" || test -L "$HOME/.local/bin/catt"; then
        echo "A destination already exists; inspect it before installing catt." >&2
        exit 1
    fi
    # A real lib64 directory prevents venv from creating its compatibility symlink.
    mkdir -p "$cast_env/lib64" "$HOME/.local/bin"
    python3 -m venv --copies "$cast_env"
    "$cast_env/bin/python" -m pip install --only-binary=:all: 'catt==0.13.3'
    install -m 755 "$cast_env/bin/catt" "$HOME/.local/bin/catt"
    "$HOME/.local/bin/catt" --version
)
```

Use trusted, non-symlinked XDG paths. The environment must remain at that path because the console launcher refers to its interpreter. If wheel installation fails, no launcher is copied; inspect the private environment and pip error before retrying. Then press Refresh in Dev Manager and review Install → Enable. The explicit shell restart remains `systemctl --user restart caelestia-shell.service`; these dependency commands neither install the plugin nor restart the shell.

## Install and use

1. Open Dev Manager → **Component Store** → **Refresh**, select **Cast Audio**, then choose **Install**. Review the source and permissions. Alternatively, paste the complete package into Create / Import, analyze it and create development source before installing through Components.
2. Resolve any missing dependencies. Review Install to create the separate installed snapshot. The manager initially hides its discovery metadata.
3. Enable the component. If Nexus separately disabled it, enable it there too. Reload explicitly with `systemctl --user restart caelestia-shell.service`.
4. Put the computer and Google Cast receiver on the same local network. Open **Quick Toggles → Cast Audio** if the host bridge is deployed, or run `quickshell -c caelestia ipc call castAudio open`. Wait for discovery (or press **Refresh devices**), then click the receiver's name to start. The first connection may take up to a minute. A busy receiver is refused; stop its existing session through its current controller first.
5. Stop casting ends capture and closes the server immediately, then attempts to stop the matching receiver session. Closing the window keeps casting.

Reopen the window using the Quick Toggles Cast icon or `quickshell -c caelestia ipc call castAudio open`. The host icon always opens the selector, including while casting; use **Stop casting** in the selector to stop. The plugin also supplies `castAudio toggle` and `castAudio stop` IPC functions. These are plugin-defined handlers using standard Quickshell IPC. Nexus → Utilities → Quick toggles → Connectivity → Cast Audio hides/shows the icon.

If the window does not appear, check that Cast Audio is enabled in Components (and not disabled in Nexus), restart the shell explicitly, then run the open command above. If no receiver appears, check that it is powered on and on the same LAN; try Refresh devices. Guest Wi-Fi/client isolation can block discovery or streaming. See Audio and network behavior below for firewall and receiver limits.

Advanced settings select the current default output or a specific available output monitor, MP3 bitrate, remembering the receiver and discovery deadline. Changes apply to the next connection. Remembering a receiver does not itself start casting. Reconnect at startup is disabled by default and explicitly labeled as starting audio capture; when enabled, it tries the remembered receiver once after successful startup discovery. It does not repeatedly reclaim a lost/replaced session.

## Audio and network behavior

`PipeWire output monitor → FFmpeg → memory-only live MP3 HTTP stream → catt/PyChromecast → Google Cast default media receiver`.

Defaults: MP3, 192 kbit/s, 48 kHz, stereo. Available bitrates: 128/192/256/320 kbit/s. MP3 was selected for broad receiver compatibility and reliable MIME handling in the verified CLI. AAC/HLS is not implemented in 0.1.0. Google documents MP3 support for its audio receivers in [Supported media](https://developers.google.com/cast/docs/media). Receiver buffers add several seconds of latency, sometimes more; there is no measured latency estimate or zero-latency claim.

The HTTP server exists only while connecting/casting. It binds one private IPv4 address selected by the route to the receiver, on an ephemeral port, rather than all interfaces. It accepts only the receiver's discovered address and that local address (needed for `catt`'s media inspection). A random 192-bit path changes for each session. There is no directory listing, configuration endpoint or remote-control API. Audio is unencrypted HTTP on the LAN and is never recorded to disk. Queues are bounded; slow readers disconnect instead of accumulating audio indefinitely. No HTTP URL/token or captured audio is logged.

The receiver must reach that local TCP port; a firewall or Wi-Fi client isolation can prevent playback even when discovery succeeds. The component never changes firewall rules. Startup and manual discovery run asynchronously. Concurrent refreshes coalesce; manual requests have a 10-second cooldown. Automatic discovery runs every 90 seconds only while the control window is visible and idle. Casting checks capture health locally each second and receiver/audio status approximately every 10 seconds, plus command deadlines. Lost routes, output changes, receiver replacement, FFmpeg failure and timeouts stop capture and report an error.

Discovery is local mDNS through `catt`. See Google's [Discovery troubleshooting](https://developers.google.com/cast/docs/discovery). I found no documented, appropriate Linux desktop API for enumerating Cast receivers through a Google account. Google's [Home APIs](https://developers.home.google.com/apis) describe Android/iOS SDKs; this component implements local discovery only and neither requests nor stores Google credentials.

## Limits and lifecycle

Only private/link-local IPv4 receivers with standard Cast port 8009 are connectable. Discovered nonstandard-port groups are shown disabled, because the inspected CLI's IP-address path uses port 8009. IPv6-only/public-address advertisements are omitted. Some groups consequently cannot be used in this release. `catt` keys scan output by friendly name; give receivers unique names to avoid its duplicate-name ambiguity. The discovery deadline is a bound on the entire CLI scan, not a configurable mDNS library timeout.

Each start requires a currently discovered ID. Receiver stop and volume commands check that the media URL still belongs to this session. That check and the subsequent CLI command cannot be atomic across independent controllers; avoid simultaneous commands from another sender. A replacement session is preserved when detected. If the network is lost, stopping the receiver remotely is best effort; local capture and HTTP serving still end.

The helper owns every subprocess it starts, cancels bounded operations, terminates/reaps exact child PIDs and uses Linux parent-death guards for FFmpeg/catt. It has one private per-user lock. Helper EOF, normal unload, shell exit and termination end capture. A hard shell/helper kill also removes the in-process HTTP server and triggers child parent-death termination; a receiver may remain on an expired/buffering session until it notices the stream ended. There is no broad process killing or detached HTTP-server daemon.

Preferences: `$XDG_CONFIG_HOME/cast-audio/settings.json`, mode 0600. The component's private `catt` configuration lives below the same config directory. Lock/cache paths use `$XDG_RUNTIME_DIR/cast-audio`, with `$XDG_CACHE_HOME/cast-audio` fallback. Corrupt settings safely reset in memory; an explicit save replaces the invalid file. Runtime data is outside the manager-owned executable snapshot. Disable/uninstall through the manager, then explicitly reload the shell to unload the running plugin. Its user preferences are retained.

## Verification

Run from this development component: `python3 -B -m unittest discover -s tests -v`. To test the host icon on a compatible Caelestia KDE Wayland desktop, run `python3 -B tests/quick_toggle_probe.py --shell "${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/caelestia"`. The probe copies the host, applies the patch only to that temporary copy when needed, isolates XDG roots/session bus and uses a fake Cast controller; it neither captures audio nor edits the live shell. It checks the actual native icon, click handler, casting highlight, Nexus visibility and plugin unload.

Tests cover settings recovery, input/address validation, monitor-only selection, busy/replaced-session protection, timeout/cancellation cleanup, stream failure cleanup and the HTTP boundary. An isolated real FFmpeg synthetic-tone test verified live MP3 bytes, HTTP streaming and `catt` 0.13.3/yt-dlp retaining the live URL and audio MIME. The QML was instantiated using installed Quickshell/native Caelestia modules under temporary XDG roots, without network audio capture. The optional patch passes `git apply --check` against the pinned source. No physical Google Cast receiver playback or receiver-specific latency was tested.

This component contains original MIT-licensed code and artwork. The optional host patch modifies GPL-3.0-only Caelestia source and is covered by that upstream license. It invokes the separately installed [catt](https://github.com/skorokithakis/catt) CLI; no third-party Cast implementation is copied or bundled. Qt, Quickshell, Caelestia, FFmpeg and catt retain their respective licenses.
