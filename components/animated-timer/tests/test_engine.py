"""Portable timer engine tests: python -m pytest tests/test_engine.py."""
import importlib.util
import json
from pathlib import Path
import pytest

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('animated_timer_engine_tests', SOURCE / 'src/engine.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Clock:
    boot = 'boot-1'
    value = 1000.0
    wall_value = 100000.0
    def now(self): return self.value
    def wall(self): return self.wall_value
    def advance(self, seconds):
        self.value += seconds
        self.wall_value += seconds


@pytest.fixture
def engine(tmp_path):
    notifications = []
    engine = module.Engine(tmp_path / 'timer/state.json', Clock(), notifications.append)
    return engine, engine.clock, notifications


def test_deadline_accuracy_and_pause_resume(engine):
    e, c, _ = engine
    e.command({'action': 'configure', 'seconds': 10})
    e.command({'action': 'start'})
    c.advance(3.125)
    e.command({'action': 'pause'})
    assert e.remaining() == pytest.approx(6.875)
    c.advance(999)
    assert e.remaining() == pytest.approx(6.875)
    e.command({'action': 'resume'})
    c.advance(6.875)
    assert e.tick()
    assert e.snapshot()['state'] == 'Completed'


def test_config_and_presets_do_not_change_countdown(engine):
    e, c, _ = engine
    e.command({'action': 'start'})
    c.advance(17)
    for _ in range(30):
        e.command({'action': 'adjust', 'unit': 1, 'delta': 1})
    e.command({'action': 'preset-save', 'name': 'Custom', 'seconds': 30})
    custom = e.data['presets'][-1]
    e.command({'action': 'preset-save', 'id': custom['id'], 'name': 'Renamed', 'seconds': 45})
    assert e.data['presets'][-1]['name'] == 'Renamed'
    e.command({'action': 'preset-delete', 'id': custom['id']})
    assert e.remaining() == 1483
    assert e.data['configured'] == 3300
    e.command({'action': 'reset'})
    assert e.remaining() == 3300
    assert e.data['state'] == 'Ready'


def test_suspend_and_restart_exactly_one_completion(engine):
    e, c, events = engine
    e.command({'action': 'configure', 'seconds': 5})
    e.command({'action': 'start'})
    c.advance(3600)  # CLOCK_BOOTTIME includes suspend.
    restored = module.Engine(e.path, c, events.append)
    assert restored.data['state'] == 'Completed'
    assert len(events) == 1
    for _ in range(20): restored.tick()
    module.Engine(e.path, c, events.append)
    assert len(events) == 1


def test_running_restored_without_wall_clock_drift(engine):
    e, c, events = engine
    e.command({'action': 'start'})
    c.advance(45)
    c.wall_value += 86400
    assert module.Engine(e.path, c, events.append).remaining() == 1455
    c.boot = 'boot-2'
    c.value = 2
    assert module.Engine(e.path, c, events.append).data['state'] == 'Completed'


def test_rapid_commands_are_idempotent_and_atomic(engine):
    e, c, events = engine
    for _ in range(20): e.command({'action': 'start'})
    cycle = e.data['cycle']
    c.advance(3)
    for _ in range(20): e.command({'action': 'pause'})
    assert e.remaining() == 1497
    for _ in range(20): e.command({'action': 'resume'})
    assert e.data['cycle'] == cycle
    for _ in range(20): e.command({'action': 'reset'})
    assert e.remaining() == 1500
    e.command({'action': 'cancel'})
    assert not events


def test_auto_repeat_does_not_replay_suspend_cycles(engine):
    e, c, events = engine
    e.command({'action': 'configure', 'seconds': 2})
    e.command({'action': 'preferences', 'values': {'repeat': True}})
    e.command({'action': 'start'})
    cycle = e.data['cycle']
    c.advance(10000)
    e.tick()
    assert len(events) == 1
    assert e.data['cycle'] != cycle and e.remaining() == 2


def test_invalid_state_is_retained_for_diagnosis(engine):
    e, c, events = engine
    e.command({'action': 'start'})
    data = json.loads(e.path.read_text()); data['deadline'] = float('nan')
    e.path.write_text(json.dumps(data))
    restored = module.Engine(e.path, c, events.append)
    assert restored.data['state'] == 'Ready'
    assert len(list(e.path.parent.glob('state-invalid-*.json'))) == 1



def test_alarm_persists_until_explicit_stop_and_ignores_stale_action(engine):
    e, c, _ = engine
    e.command({'action': 'configure', 'seconds': 1})
    e.command({'action': 'start'})
    c.advance(1); e.tick()
    alarm_cycle = e.data['alarm_cycle']
    restored = module.Engine(e.path, c)
    assert restored.data['alarm_active']
    restored.command({'action': 'configure', 'seconds': 20})
    restored.command({'action': 'start'})
    assert restored.data['alarm_active']  # Editing/starting cannot dismiss the bell.
    assert restored.command({'action': 'dismiss-alarm', 'cycle': 'old'})['alarm_active']
    restored.command({'action': 'dismiss-alarm', 'cycle': alarm_cycle})
    assert not module.Engine(e.path, c).data['alarm_active']
    assert restored.data['state'] == 'Running'  # Stopping the alarm preserves a repeat cycle.


def test_legacy_completed_state_does_not_ring_on_upgrade(engine):
    e, c, _ = engine
    e.data.update(state='Completed', remaining=0)
    for key in ('alarm_active', 'alarm_cycle', 'alarm_notification', 'alarm_notification_owner'): e.data.pop(key)
    e.save()
    assert not module.Engine(e.path, c).data['alarm_active']
