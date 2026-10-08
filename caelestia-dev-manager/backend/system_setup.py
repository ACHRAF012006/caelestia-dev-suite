"""Fixed Cast Audio machine preparation; never run component-provided hooks."""
import json
from pathlib import Path
import shutil
import subprocess

from backend.paths import SafetyError, no_symlinks

NETWORKS = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
PACKAGES = {"arch": {"ffmpeg": "ffmpeg", "pactl": "libpulse", "parec": "libpulse"},
            "debian": {"ffmpeg": "ffmpeg", "pactl": "pulseaudio-utils", "parec": "pulseaudio-utils"}}


def supported(manifest):
    return (manifest["id"] == "cast-audio" and manifest["runtime"] == "quickshell"
            and manifest["type"] == "caelestia-plugin"
            and manifest.get("integration", {}).get("target") == "caelestia-quick-toggles")


def distribution(path=Path("/etc/os-release")):
    values = {}
    try:
        for line in path.read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator: values[key] = value.strip('"\'')
    except OSError:
        pass
    names = {values.get("ID", ""), *values.get("ID_LIKE", "").split()}
    return "arch" if names & {"arch", "cachyos", "manjaro"} else "debian" if names & {"debian", "ubuntu"} else "unsupported"


def stream_port(paths):
    settings = no_symlinks(paths.config / "cast-audio/settings.json")
    try:
        if settings.stat().st_size > 16384: raise SafetyError("Cast Audio settings are too large")
        port = json.loads(settings.read_text())["stream_port"]
    except FileNotFoundError:
        return 48200
    except (ValueError, KeyError, TypeError):
        raise SafetyError("Fix invalid Cast Audio stream-port settings before machine setup") from None
    if type(port) is not int or port != 0 and not 1024 <= port <= 65535:
        raise SafetyError("Invalid Cast Audio stream port")
    return port


def firewall_commands(port, config=Path("/etc/ufw/ufw.conf"), rules=Path("/etc/ufw/user.rules")):
    if not port or not Path("/usr/bin/ufw").is_file(): return [], ""
    try:
        active = any(line.strip() == "ENABLED=yes" for line in config.read_text().splitlines())
    except OSError:
        active = False
    if not active: return [], ""
    try: contents = rules.read_text()
    except OSError: contents = ""
    commands = []
    for network in NETWORKS:
        # UFW represents `to any` with 0.0.0.0/0 in its persistent tuple.
        marker = f"### tuple ### allow tcp {port} 0.0.0.0/0 any {network} in"
        if not any(line == marker or line.startswith(marker + " ") for line in contents.splitlines()):
            commands.append(["/usr/bin/ufw", "allow", "in", "proto", "tcp", "from", network,
                             "to", "any", "port", str(port), "comment", "Cast Audio LAN stream"])
    note = (f"Allow private-network receivers to reach TCP {port} on this PC, regardless of its address. "
            "The stream still accepts only the selected receiver and a private session URL. "
            "Router/VLAN policies are configured separately. Firewall preparation persists after uninstall.")
    return commands, note


def plan(manifest, paths):
    if not supported(manifest): return {"commands": [], "summary": ""}
    family = distribution()
    missing = [name for name in manifest.get("dependencies", {}).get("system", []) if not shutil.which(name)]
    mapping = PACKAGES.get(family, {})
    unsupported = [name for name in missing if name not in mapping]
    if unsupported:
        raise SafetyError("Install these host prerequisites first: " + ", ".join(unsupported) +
                          ". Automatic Cast audio-tool setup supports Arch/CachyOS and Debian/Ubuntu.")
    packages = sorted({mapping[name] for name in missing})
    commands, summary = [], []
    if packages:
        command = (["/usr/bin/pacman", "-S", "--needed", "--noconfirm"] if family == "arch" else
                   ["/usr/bin/apt-get", "install", "-y"])
        commands.append([*command, *packages])
        summary.append("Install missing audio tools using " + Path(command[0]).name + ": " + ", ".join(packages) + ".")
    firewall, note = firewall_commands(stream_port(paths))
    commands.extend(firewall)
    if firewall: summary.append(note)
    if commands: summary.append("KDE will request administrator authentication. No component installation scripts are executed.")
    return {"commands": commands, "summary": "\n\n".join(summary)}


def apply(current, expected):
    if current != expected: raise SafetyError("Machine setup changed since review; review it again")
    if not current["commands"]: return
    if not Path("/usr/bin/pkexec").is_file() or not Path("/usr/bin/python3").is_file():
        raise SafetyError("Machine preparation needs pkexec and system Python for native administrator authentication")
    # One native authentication. Literal argv comes exclusively from fixed
    # manager recipes, never shell text or source-supplied installation code.
    program = "import subprocess\n" + "\n".join(
        "subprocess.run(" + repr(command) + ", check=True)" for command in current["commands"])
    try:
        subprocess.run(["/usr/bin/pkexec", "/usr/bin/python3", "-I", "-c", program],
                       check=True, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as error:
        from backend.dependencies import clean_output
        detail = clean_output(getattr(error, "stderr", "") or str(error))
        raise SafetyError("Machine setup did not complete. Installation has not proceeded. " + detail +
                          " Completed package/rule changes may remain; retry checks the current state.") from None
