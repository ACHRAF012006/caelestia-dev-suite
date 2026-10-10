"""Closed manager-owned registry: component manifests cannot load adapter code."""
from dataclasses import dataclass
from types import MappingProxyType
from backend.paths import SafetyError
from backend.installers import (StandaloneAppInstaller, ScriptInstaller, UserServiceInstaller,
                                CaelestiaPluginInstaller, KDEIntegrationInstaller)
from backend import quick_toggle_integration as cast, timer_integration as timer, dashboard_integration as dashboard


@dataclass(frozen=True)
class Capability:
    name: str
    installer: type
    destinations: str
    runtime: str
    limitations: str

@dataclass(frozen=True)
class HostAdapter:
    module: object
    target: str
    legacy_ids: tuple = ()

    def participates(self, paths, manifest):
        if manifest.get('id') in self.legacy_ids or manifest.get('integration', {}).get('target') == self.target: return True
        selector = getattr(self.module, 'participates', None)
        return bool(selector and selector(paths, manifest))


class CapabilityRegistry:
    def __init__(self):
        self.types = MappingProxyType({
            'standalone-app': Capability('application', StandaloneAppInstaller, 'component payload, user launcher, desktop entry', 'independent process', 'Best-effort fork/re-exec detection'),
            'script': Capability('script', ScriptInstaller, 'component payload, user launcher', 'independent process', 'No arbitrary shell installation hooks'),
            'user-service': Capability('service', UserServiceInstaller, 'component payload, exact user systemd unit', 'systemd --user', 'External service state is not atomically journaled'),
            'caelestia-plugin': Capability('caelestia-plugin', CaelestiaPluginInstaller, 'exact user plugin root', 'real Caelestia', 'Discovery enablement does not prove loaded QML health'),
            'qml-component': Capability('qml-component', CaelestiaPluginInstaller, 'exact user plugin root', 'real Caelestia', 'Only caelestia-plugin target'),
            'kde-integration': Capability('kde-integration', KDEIntegrationInstaller, 'none', 'unsupported', 'No reviewed adapter'),
        })
        # Priority is intentional: shared dashboard membership supersedes Timer-only
        # routing, and removal resolves from receipts rather than new declarations.
        self.routes = (HostAdapter(cast, cast.TARGET, ('cast-audio',)),
                       HostAdapter(dashboard, 'caelestia-dashboard'),
                       HostAdapter(timer, timer.TARGET, ('animated-timer',)))
        self.hosts = tuple(route.module for route in self.routes)
        self.targets = MappingProxyType({route.target: route.module for route in self.routes})
        self.proposals = MappingProxyType({'cast-audio': cast, dashboard.ID: dashboard, 'animated-timer': timer})

    def installer(self, paths, manifest):
        try: return self.types[manifest['type']].installer(paths)
        except KeyError as error: raise SafetyError('Unsupported component capability') from error

    def validate_manifest(self, manifest):
        target = manifest.get('integration', {}).get('target')
        if target not in (*self.targets, None, 'caelestia-plugin'): raise SafetyError('integration.target: unsupported integration target')
        if target in self.targets and (manifest['type'] != 'caelestia-plugin' or manifest['runtime'] != 'quickshell'):
            raise SafetyError('integration.target: host adapters require a Caelestia Quickshell plugin')
        if target == cast.TARGET and manifest['id'] != 'cast-audio': raise SafetyError('Quick Toggles adapter supports Cast Audio only')
        if target == timer.TARGET and manifest['id'] != 'animated-timer': raise SafetyError('Timer adapter supports animated-timer only')
        from backend.dashboard_contract import declaration
        if target == 'caelestia-dashboard':
            if manifest['id'] in {'animated-timer', 'cast-audio'}: raise SafetyError('Legacy integrated components must retain their compatibility targets')
            declaration(manifest['integration'].get('dashboard'))
        elif 'dashboard' in manifest.get('integration', {}): raise SafetyError('dashboard declaration requires the caelestia-dashboard target')

    def requested(self, manifest): return manifest.get('integration', {}).get('target') in self.targets

    def host_plan(self, paths, manifest):
        for route in self.routes:
            if route.participates(paths, manifest): return route.module.plan(paths, manifest)
        return None

    def host_action(self, action, paths, proposal):
        if proposal is None: return None
        if action not in {'check', 'apply', 'recover'}: raise SafetyError('Unsupported adapter action')
        try: adapter = self.proposals[proposal['id']]
        except (KeyError, TypeError) as error: raise SafetyError('Unknown manager-owned host adapter plan') from error
        return getattr(adapter, action)(paths, proposal)

    def receipt_path(self, paths, component_id):
        if component_id == 'cast-audio': return cast.receipt_path(paths)
        shared, _ = dashboard.read_receipt(paths)
        if shared and (component_id in shared['pages'] or component_id == 'animated-timer' and shared['timer']): return dashboard.receipt_path(paths)
        return timer.receipt_path(paths) if component_id == 'animated-timer' else dashboard.receipt_path(paths)


capabilities = CapabilityRegistry()
