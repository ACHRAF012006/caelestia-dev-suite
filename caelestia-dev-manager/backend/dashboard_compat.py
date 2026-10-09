"""Host-specific knowledge for the pinned Caelestia KDE v2.5.1 dashboard.

Transform only pristine, checksum-verified source. Future host ports belong here.
"""
import json
from backend import timer_integration as timer

COMMIT, FILES = timer.COMMIT, timer.FILES
VERSION = '2.5.1'


def sources(originals, pages, with_timer, paths):
    result = timer.panel_sources(originals) if with_timer else dict(originals)
    if not pages:
        return result
    content = result['modules/dashboard/Content.qml']
    # Timer retains its existing ordering and notch contract. Its activity is now
    # determined by page identity, since it is no longer necessarily the last tab.
    if with_timer:
        content = content.replace('root.dashboardTabs.length - 1', 'root.dashboardTabs.findIndex(tab => tab.id === "timer")')
        content = content.replace('allTabs.push({ component: timerComponent,', 'allTabs.push({ id: "timer", component: timerComponent,')
    blocks, entries = [], []
    for index, (owner, page) in enumerate(sorted(pages.items(), key=lambda entry: (entry[1]['order'], entry[1]['id'], entry[0]))):
        symbol = 'cdmPage' + str(index)
        # The manager calculates both the destination and the file URL.
        url = (paths.config / 'caelestia/plugins' / owner / page['component']).as_uri()
        page_id, title, icon, plugin_id = map(json.dumps, (page['id'], page['title'], page['icon'], owner))
        blocks.append(f'''    Component {{
        id: {symbol}
        Item {{
            implicitWidth: Math.min(pageLoader.item?.implicitWidth ?? Tokens.sizes.dashboard.mediaTabWidth,
                Math.max(1, root.screenState.modelData.width - Tokens.padding.large * 4))
            implicitHeight: Math.min(pageLoader.item?.implicitHeight ?? Tokens.sizes.dashboard.mediaTabHeight,
                Math.max(1, root.screenState.modelData.height - Tokens.padding.large * 8))
            Loader {{
                anchors.fill: parent
                id: pageLoader
                objectName: "cdmDashboardPageLoader"
                property bool ready: false
                readonly property var controller: {{
                    PluginLoader.loadedCount;
                    return PluginLoader.pluginInstances[{plugin_id}] ?? null;
                }}
                readonly property bool presentationActive: root.visibilities.dashboard && root.dashboardTabs[root.screenState.dashboardTab]?.id === {page_id}
                function loadPage() {{
                    if (controller) setSource({json.dumps(url)}, {{controller: controller, presentationActive: Qt.binding(() => pageLoader.presentationActive)}});
                    else source = "";
                }}
                onControllerChanged: if (ready) loadPage()
                Component.onCompleted: {{ ready = true; loadPage(); }}
            }}
        }}
    }}''')
        entries.append(f'        if (PluginLoader.pluginInstances[{plugin_id}]) allTabs.push({{ id: {page_id}, component: {symbol}, iconName: {icon}, text: {title}, enabled: true }});')
    content = content.replace('    readonly property var dashboardTabs: {',
        '    // BEGIN Dev Manager dashboard pages v1\n' + '\n'.join(blocks) + '\n    // END Dev Manager dashboard pages v1\n\n    readonly property var dashboardTabs: {\n        PluginLoader.loadedCount;', 1)
    content = content.replace('        return allTabs.filter(tab => tab.enabled);', '\n'.join(entries) + '\n        return allTabs.filter(tab => tab.enabled);', 1)
    result['modules/dashboard/Content.qml'] = content
    return result
