"""Compatibility facade for trusted host adapters; all routing is centralized."""
from backend.quick_toggle_integration import TARGET, FILES, LEGACY, panel_sources, pristine
from backend.capabilities import capabilities


def requested(manifest): return capabilities.requested(manifest)
def plan(paths, manifest): return capabilities.host_plan(paths, manifest)
def check(paths, proposal): return capabilities.host_action('check', paths, proposal)
def apply(paths, proposal): return capabilities.host_action('apply', paths, proposal)
def recover(paths, proposal): return capabilities.host_action('recover', paths, proposal)
def receipt_path(paths, component_id='cast-audio'): return capabilities.receipt_path(paths, component_id)
