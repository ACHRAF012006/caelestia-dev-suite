"""Authority disclosure derived from validated plans, separate from runtime claims."""


def permissions(plan):
    manifest, entries = plan['manifest'], plan['files']
    result = [{'category': 'Files installed', 'detail': f'{len(entries)} exact files; {len(plan["remove"])} old owned files removed'},
              {'category': 'Backup', 'detail': 'Every replaced/removed owned file is backed up before mutation'}]
    if plan.get('prepared'):
        result.append({'category': 'Python environment', 'detail': 'Private component environment, copied as owned files; manager/global environment is not used as the component environment'})
    if manifest['type'] == 'user-service':
        result.append({'category': 'systemd user service', 'detail': 'Exact generated cdm-' + manifest['id'] + '.service; independent user-systemd lifetime'})
    if manifest['type'] in {'caelestia-plugin', 'qml-component'}:
        result.append({'category': 'Caelestia integration', 'detail': 'Real shell plugin discovery, outside the manager process'})
    if plan.get('desktop_shortcut'):
        result.append({'category': 'Desktop shortcut', 'detail': plan['desktop_shortcut']['path']})
    host = plan.get('host_integration')
    if host:
        result.append({'category': 'Host files touched', 'detail': ', '.join(host['after'])})
        result.append({'category': 'Shell restart', 'detail': host['summary']})
    if manifest.get('portable_data'):
        result.append({'category': 'Persistent data declaration', 'detail': 'Declared locations only; this installation does not collect, restore or migrate personal data'})
    result.append({'category': 'Runtime access', 'detail': 'Independent component code runs with your user permissions. Network/audio/file access is not sandbox-enforced by the manager; source permissions are disclosures.'})
    return result


def describe(plan):
    return '\n'.join(item['category'] + ': ' + item['detail'] for item in permissions(plan))
