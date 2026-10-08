import json
from pathlib import Path
from unittest.mock import patch

import pytest

from backend import system_setup
from backend.paths import SafetyError


def cast_manifest():
    return {"id": "cast-audio", "type": "caelestia-plugin", "runtime": "quickshell",
            "integration": {"target": "caelestia-quick-toggles"},
            "dependencies": {"system": ["python3", "quickshell", "ffmpeg", "pactl", "parec"]}}


def test_fixed_audio_package_mapping_and_no_partial_arch_upgrade(manager, monkeypatch):
    monkeypatch.setattr(system_setup, "distribution", lambda: "arch")
    monkeypatch.setattr(system_setup.shutil, "which", lambda name: "/usr/bin/" + name if name in ("python3", "quickshell") else None)
    monkeypatch.setattr(system_setup, "firewall_commands", lambda port: ([], ""))
    setup = system_setup.plan(cast_manifest(), manager.paths)
    assert setup["commands"] == [["/usr/bin/pacman", "-S", "--needed", "--noconfirm", "ffmpeg", "libpulse"]]
    assert "administrator authentication" in setup["summary"]
    unknown = cast_manifest(); unknown["dependencies"]["system"].append("made-up-tool")
    with pytest.raises(SafetyError, match="made-up-tool"): system_setup.plan(unknown, manager.paths)
    unknown["id"] = "another-component"
    assert system_setup.plan(unknown, manager.paths)["commands"] == []


def test_firewall_rules_use_private_sources_and_any_local_destination(tmp_path):
    config, rules = tmp_path / "ufw.conf", tmp_path / "user.rules"
    config.write_text("ENABLED=yes\n")
    rules.write_text("### tuple ### allow tcp 48200 0.0.0.0/0 any 10.0.0.0/8 in comment=demo\n")
    real_is_file = Path.is_file
    with patch.object(Path, "is_file", lambda self: True if str(self) == "/usr/bin/ufw" else real_is_file(self)):
        commands, summary = system_setup.firewall_commands(48200, config, rules)
        assert len(commands) == 2
        for command in commands:
            assert command[command.index("to") + 1] == "any"
            assert command[command.index("from") + 1] in system_setup.NETWORKS
            assert "10.2.2.100" not in command and "10.2.3.246" not in command
        assert "regardless of its address" in summary
        assert system_setup.firewall_commands(0, config, rules)[0] == []
        config.write_text("ENABLED=no\n")
        assert system_setup.firewall_commands(48200, config, rules)[0] == []


def test_configured_stream_port_and_reject_changed_review(manager, monkeypatch):
    assert system_setup.stream_port(manager.paths) == 48200
    folder = manager.paths.config / "cast-audio"; folder.mkdir(parents=True)
    settings = folder / "settings.json"
    settings.write_text(json.dumps({"stream_port": 49321}))
    assert system_setup.stream_port(manager.paths) == 49321
    settings.write_text(json.dumps({"stream_port": True}))
    with pytest.raises(SafetyError): system_setup.stream_port(manager.paths)
    called = []
    monkeypatch.setattr(system_setup.subprocess, "run", lambda *args, **kwargs: called.append(args))
    with pytest.raises(SafetyError, match="changed since review"):
        system_setup.apply({"commands": [["new"]]}, {"commands": [["old"]]})
    assert not called


def test_single_native_authentication_fixed_argv_and_cancelled_preparation(monkeypatch):
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    called = []
    monkeypatch.setattr(system_setup.subprocess, "run", lambda args, **kwargs: called.append(args))
    setup = {"commands": [["/usr/bin/ufw", "allow", "48200/tcp"]], "summary": "test"}
    system_setup.apply(setup, setup)
    assert len(called) == 1
    assert called[0][:4] == ["/usr/bin/pkexec", "/usr/bin/python3", "-I", "-c"]
    assert "subprocess.run" in called[0][4]
    import subprocess
    def denied(*args, **kwargs): raise subprocess.CalledProcessError(126, args[0], stderr="Authentication cancelled")
    monkeypatch.setattr(system_setup.subprocess, "run", denied)
    with pytest.raises(SafetyError, match="Installation has not proceeded"):
        system_setup.apply(setup, setup)
