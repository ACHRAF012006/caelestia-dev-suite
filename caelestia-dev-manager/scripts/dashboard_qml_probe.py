#!/usr/bin/env python3
"""Real dashboard, generic pages and Timer on two isolated virtual KWin outputs.

Copies installed host source; only the copy is transformed. Private XDG directories
and D-Bus sessions prevent production shell changes and user data access.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
HOST = Path.home() / '.config/quickshell/caelestia'
PROBE = r'''
pragma ComponentBehavior: Bound
import QtQuick
import QtTest
import Quickshell
import qs.services
import qs.components
import Caelestia
import Caelestia.Config
import qs.modules.dashboard as Dashboard

ShellRoot {
    id: root
    property var controller: null
    property var timerController: null
    property int stage: 0
    property int waits: 0
    property string noteId: ""
    property string taskId: ""
    property var windows: []
    property bool deferredObserved: false
    property var delayedModel: null
    SignalSpy { id: retained; signalName: "countChanged" }
    Connections {
        target: root.controller
        function onChanged(kind, id, entry) {
            if (root.stage === 22 && kind === "tasks" && id === root.taskId && entry?.completed) {
                Qt.callLater(() => {
                    root.check(root.child(root.windows[0].notesPage, "notesTasksTasksList").count === 3, "completed row retained during animation");
                    root.deferredObserved = true;
                });
            }
        }
    }
    function check(ok, message) { if (!ok) { console.error("PROBE FAILED: " + message); Qt.exit(1); } }
    function child(parent, name) { return CUtils.findChild(parent, name); }
    QtObject {
        id: fixture
        property var notes: ({})
        property var tasks: ({})
        property var settings: ({noteSort: "updated", taskSort: "manual", showCompleted: false})
        signal reset()
        signal changed(string kind, string recordId, var entry)
        function records(kind) { return kind === "notes" ? notes : tasks; }
    }
    function verifyLargeModels() {
        const stamp = "2026-10-09T12:00:00.000+00:00";
        for (let i = 0; i < 300; ++i) fixture.notes["n" + i] = {id: "n" + i, title: "Note " + i, text: "body", tags: ["tag"], pinned: i === 150, archived: i === 299, createdAt: stamp, updatedAt: stamp, searchText: "note " + i + " body tag"};
        for (let i = 0; i < 2000; ++i) fixture.tasks["t" + i] = {id: "t" + i, title: "Task " + i, details: "body", tags: [], completed: i % 2 === 0, order: i * 1024, due: {date: i % 2 === 0 ? "2099-01-01" : "", time: ""}, priority: i % 4, subtasks: [], createdAt: stamp, updatedAt: stamp, searchText: "task " + i + " body"};
        const component = Qt.createComponent(Quickshell.env("NOTES_PROBE_PLUGIN") + "/models/FilteredModel.qml");
        check(component.status === Component.Ready, component.errorString());
        const notes = component.createObject(root, {controller: fixture, kind: "notes"});
        check(notes.model.count === 299 && notes.model.get(0).recordId === "n150", "large notes, pinned first, archive exclusion");
        retained.target = notes.model; retained.clear();
        notes.query = "body tag"; check(notes.model.count === 299, "multi-word in-memory search");
        check(retained.count === 0, "unchanged search results keep model rows");
        notes.filter = "archived"; check(notes.model.count === 1, "archive filter");
        notes.filter = "active"; notes.query = "note 149"; check(notes.model.count === 1, "large title search");
        notes.sortOrder = "title"; notes.query = ""; check(notes.model.get(0).recordId === "n150", "pinned remains first when sorted");
        fixture.notes["n150"] = Object.assign({}, fixture.notes["n150"], {title: "Refreshed pinned note"}); fixture.reset();
        check(notes.model.get(0).entry.title === "Refreshed pinned note", "snapshot refresh updates retained records");
        const tasks = component.createObject(root, {controller: fixture, kind: "tasks"});
        check(tasks.model.count === 1000, "2000-task open filter");
        tasks.filter = "all"; check(tasks.model.count === 2000, "all tasks includes completed");
        tasks.filter = "completed"; check(tasks.model.count === 1000, "large completed filter");
        tasks.filter = "upcoming"; check(tasks.model.count === 0, "upcoming excludes completed");
        tasks.filter = "all";
        const old = tasks.model.get(0).recordId;
        const changed = Object.assign({}, fixture.tasks["t1"], {title: "Edited", searchText: "edited body"});
        fixture.tasks["t1"] = changed; fixture.changed("tasks", "t1", changed);
        check(tasks.model.count === 2000 && tasks.model.get(0).recordId === old && tasks.model.get(tasks.positions["t1"]).entry.title === "Edited", "single-record update in large model");
        const moved = Object.assign({}, changed, {completed: true}); fixture.tasks["t1"] = moved; fixture.changed("tasks", "t1", moved);
        check(tasks.model.get(tasks.positions["t1"]).group === "Completed", "incremental completion movement");
        delete fixture.tasks["t1"]; fixture.changed("tasks", "t1", null); check(tasks.model.count === 1999 && tasks.positions["t1"] === undefined, "incremental deletion");
        const dated = Object.assign({}, fixture.tasks["t3"], {due: {date: "2099-01-01", time: ""}});
        fixture.tasks["t3"] = dated; fixture.changed("tasks", "t3", dated);
        tasks.day = "2099-01-02";
        check(tasks.model.get(tasks.positions["t3"]).group === "Today", "midnight refresh updates retained task groups");
        retained.target = null;
        root.delayedModel = component.createObject(root, {controller: fixture, kind: "tasks", completionDelay: 180});
        const before = root.delayedModel.model.count;
        const completed = Object.assign({}, fixture.tasks["t3"], {completed: true});
        fixture.tasks["t3"] = completed; fixture.changed("tasks", "t3", completed);
        check(root.delayedModel.model.count === before && root.delayedModel.model.get(root.delayedModel.positions["t3"]).entry.completed, "completion updates row before deferred removal");
        const undo = Object.assign({}, completed, {completed: false}); fixture.tasks["t3"] = undo; fixture.changed("tasks", "t3", undo);
        notes.destroy(); tasks.destroy();
    }
    Component.onCompleted: {
        const component = Qt.createComponent(Quickshell.env("NOTES_PROBE_PLUGIN") + "/main.qml");
        check(component.status === Component.Ready, component.errorString());
        controller = component.createObject(root);
        check(controller !== null, "controller creation");
        const timer = Qt.createComponent(Quickshell.env("TIMER_PROBE_PLUGIN") + "/main.qml");
        check(timer.status === Component.Ready, timer.errorString());
        timerController = timer.createObject(root);
        const calendar = Qt.createComponent(Quickshell.env("CALENDAR_PROBE_PLUGIN") + "/main.qml").createObject(root);
        PluginLoader.pluginInstances = {"notes-tasks": controller, "animated-timer": timerController, "probe-calendar": calendar};
        PluginLoader.loadedCount = 3;
    }
    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: monitor
            required property ShellScreen modelData
            screen: modelData
            Config.screen: modelData.name
            visible: true
            implicitWidth: modelData.width
            implicitHeight: modelData.height
            property var visibilities: DrawerVisibilities { dashboard: true; overview: false }
            property var screenState: ScreenState { modelData: monitor.modelData }
            property var content: null
            property var notesPage: null
            TestCase { id: inputTest; name: "NotesInput"; when: false }
            Rectangle {
                id: canvas
                z: 100; visible: false
                width: Tokens.sizes.dashboard.mediaTabWidth; height: Tokens.sizes.dashboard.mediaTabHeight * 2
                color: Colours.palette.m3surfaceContainerLow
                property var page: null
            }
            function typeIn(field, value) {
                field.forceActiveFocus();
                inputTest.keyClick(Qt.Key_A, Qt.ControlModifier);
                for (const letter of value) inputTest.keyClick(letter, Qt.NoModifier, 0);
            }
            function tilesMatch() {
                const grid = root.child(notesPage, "notesTasksNotesList");
                for (let i = 0; i < grid.count; ++i) {
                    const tile = grid.itemAtIndex(i);
                    if (tile) {
                        root.check(tile.recordId === grid.model.get(i).recordId, "stable grid delegate after insertion/filter");
                        root.check(tile.opacity > 0.99 && tile.scale > 0.99, "reused grid cell restores visual state");
                        const card = root.child(tile, "notesTasksNoteCard");
                        root.check(card.entry.id === tile.recordId && card.entry.title === root.controller.notes[tile.recordId].title, "card uses current controller record");
                    }
                }
            }
            Item {
                anchors.fill: parent
                property var screen: monitor.modelData
                property real topMargin: 0
            Dashboard.Wrapper {
                id: wrapper
                anchors.horizontalCenter: parent.horizontalCenter
                screenState: monitor.screenState
                visibilities: monitor.visibilities
            }
            }
            Component.onCompleted: root.windows.push(monitor)
            function nativeContent() {
                for (const item of wrapper.children) if (item.item && item.item.dashboardTabs !== undefined) return item.item;
                return null;
            }
            function verify(stage) {
                if (stage === 1) {
                    content = nativeContent();
                    root.check(content !== null, "native content loads");
                    const ids = content.dashboardTabs.filter(tab => tab.id).map(tab => tab.id);
                    root.check(JSON.stringify(ids) === JSON.stringify(["timer", "notes-tasks", "probe-calendar"]), "deterministic native tabs");
                    screenState.dashboardTab = content.dashboardTabs.findIndex(tab => tab.id === "notes-tasks");
                } else if (stage === 2) {
                    // Find the page through its own stable debug object name.
                    notesPage = root.child(wrapper, "notesTasksPage");
                    root.check(notesPage !== null && notesPage.controller === root.controller, "shared native controller");
                    root.check(notesPage.presentationActive, "presentation binding");
                    root.check(notesPage.width <= modelData.width, "logical screen width clamp");
                } else if (stage === 3) {
                    const list = root.child(notesPage, "notesTasksNotesList");
                    root.check(list.count === 1, "notes visible on every monitor");
                    root.check(!root.child(notesPage, "notesTasksNotesPane").selectedId, "external creation does not steal editor focus");
                    root.check(root.child(notesPage, "notesTasksTasksList").count === 2, "tasks visible on every monitor");
                    root.child(notesPage, "notesTasksSearch").text = "sharedtag";
                } else if (stage === 4) {
                    root.check(root.child(notesPage, "notesTasksNotesList").count === 1, "tag search note");
                    root.check(root.child(notesPage, "notesTasksTasksList").count === 0, "tag search tasks");
                    root.child(notesPage, "notesTasksSearch").text = "";
                    root.child(notesPage, "notesTasksNotesPane").openRecord(root.noteId);
                    root.child(notesPage, "notesTasksTasksPane").openRecord(root.taskId);
                } else if (stage === 5) {
                    root.check(root.child(notesPage, "notesTasksNoteBody").text === "A shared thought", "inline note editor");
                    const tasks = root.child(notesPage, "notesTasksTasksPane");
                    root.check(tasks.selectedId === root.taskId, "task editor");
                    tasks.selectedId = "";
                    root.child(notesPage, "notesTasksNotesPane").selectedId = "";
                    notesPage.width = 380; notesPage.height = 600;
                } else if (stage === 6) {
                    const noteList = root.child(notesPage, "notesTasksNotesList");
                    root.check(noteList.itemAtIndex(0) !== null && noteList.itemAtIndex(0).height > 0, "note delegate survives search/reuse");
                    root.check(notesPage.narrow, "responsive stacked layout");
                    const notes = root.child(notesPage, "notesTasksNotesPane"), tasks = root.child(notesPage, "notesTasksTasksPane");
                    root.check(tasks.mapToItem(notesPage, 0, 0).y > notes.mapToItem(notesPage, 0, 0).y, "narrow panes stack");
                    root.check(notes.width > 0 && tasks.width <= notesPage.width, "stacked panes stay inside page");
                    const capture = root.child(notesPage, "notesTasksCapture");
                    root.child(notesPage, "notesTasksAdd").clicked();
                    root.check(root.child(notesPage, "notesTasksQuickCapture").kind === "notes", "plus defaults to note capture");
                    root.child(notesPage, "notesTasksQuickCapture").open("tasks");
                    capture.text = "Enter-created task"; capture.accepted();
                } else if (stage === 7) {
                    root.check(Object.values(root.controller.tasks).some(t => t.title === "Enter-created task"), "Enter quick capture");
                    root.child(notesPage, "notesTasksTasksPane").filter = "completed";
                } else if (stage === 8) {
                    root.check(root.child(notesPage, "notesTasksTasksList").count === 2, "completed filter");
                    root.child(notesPage, "notesTasksTasksPane").filter = "today";
                } else if (stage === 9) {
                    root.check(root.child(notesPage, "notesTasksTasksList").count === 1, "today filter");
                    root.child(notesPage, "notesTasksTasksPane").filter = "upcoming";
                } else if (stage === 10) {
                    root.check(root.child(notesPage, "notesTasksTasksList").count === 0, "upcoming excludes completed");
                    root.child(notesPage, "notesTasksTasksPane").filter = "all";
                    root.child(notesPage, "notesTasksTasksPane").selectedId = root.taskId;
                    const editor = root.child(notesPage, "notesTasksTaskEditor");
                    editor.advanced = true;
                } else if (stage === 11) {
                    const editor = root.child(notesPage, "notesTasksTaskEditor");
                    root.check(editor.entry.subtasks.length === 1, "subtasks rendered");
                    notesPage.settingsOpen = true;
                } else if (stage === 12) {
                    notesPage.settingsOpen = false;
                    // Native notch still opens Timer at its actual index.
                    wrapper.openTimerTab();
                    root.check(screenState.dashboardTab === content.dashboardTabs.findIndex(tab => tab.id === "timer"), "Timer notch routing");
                    screenState.dashboardTab = content.dashboardTabs.findIndex(tab => tab.id === "notes-tasks");
                    notesPage.width = Tokens.sizes.dashboard.mediaTabWidth; notesPage.height = notesPage.implicitHeight;
                    root.child(notesPage, "notesTasksTasksPane").selectedId = "";
                    root.child(notesPage, "notesTasksQuickCapture").close();
                } else if (stage === 16) {
                    root.child(notesPage, "notesTasksTasksPane").filter = "active";
                    if (modelData === Quickshell.screens[0]) {
                        canvas.page = Qt.createComponent(Quickshell.env("NOTES_PROBE_PLUGIN") + "/DashboardPage.qml").createObject(canvas, {controller: root.controller});
                        canvas.page.width = Qt.binding(() => canvas.width); canvas.page.height = Qt.binding(() => canvas.height);
                        canvas.visible = true;
                    }
                } else if (stage === 17) {
                    root.check(!root.delayedModel.model.get(root.delayedModel.positions["t3"]).entry.completed && !Object.keys(root.delayedModel.pending).length, "rapid completion undo settles without removal");
                    tilesMatch();
                    const screenshot = Quickshell.env("NOTES_PROBE_SCREENSHOT");
                    if (screenshot && modelData === Quickshell.screens[0]) canvas.grabToImage(result => result.saveToFile(screenshot));
                } else if (stage === 18 && modelData === Quickshell.screens[0]) {
                    canvas.width = 380; canvas.height = 760;
                } else if (stage === 19 && modelData === Quickshell.screens[0]) {
                    const screenshot = Quickshell.env("NOTES_PROBE_SCREENSHOT");
                    if (screenshot) canvas.grabToImage(result => result.saveToFile(screenshot.replace(/\.png$/, "-narrow.png")));
                } else if (stage === 20 && modelData === Quickshell.screens[0]) {
                    canvas.visible = false;
                    notesPage.width = Tokens.sizes.dashboard.mediaTabWidth; notesPage.height = notesPage.implicitHeight;
                    const pane = root.child(notesPage, "notesTasksNotesPane");
                    pane.openRecord(root.noteId);
                    typeIn(root.child(notesPage, "notesTasksNoteTitle"), "Edited title");
                    typeIn(root.child(notesPage, "notesTasksNoteBody"), "Edited body");
                    inputTest.keyClick(Qt.Key_Return, Qt.ControlModifier);
                } else if (stage === 21 && modelData === Quickshell.screens[0]) {
                    root.check(root.controller.notes[root.noteId].title === "Edited title" && root.controller.notes[root.noteId].text === "Edited body", "keyboard inline editing autosaves");
                    root.check(!root.child(notesPage, "notesTasksNotesPane").selectedId, "Ctrl+Enter closes inline editor");

                    root.child(notesPage, "notesTasksNotesPane").tag = "linux";
                } else if (stage === 22 && modelData === Quickshell.screens[0]) {
                    root.check(root.child(notesPage, "notesTasksNotesList").count === 1, "exact tag filter");
                    const pane = root.child(notesPage, "notesTasksNotesPane"); pane.tag = "";
                    const tasks = root.child(notesPage, "notesTasksTasksPane"), list = root.child(notesPage, "notesTasksTasksList");
                    tasks.filter = "active";
                    const button = root.child(list.itemAtIndex(0), "notesTasksComplete");
                    root.check(button !== null, "task checkbox exists"); button.clicked();
                } else if (stage === 23 && modelData === Quickshell.screens[0]) {
                    root.check(root.deferredObserved && root.controller.tasks[root.taskId].completed, "task completion action persisted after visual hold");
                    root.check(root.child(notesPage, "notesTasksTasksList").count === 2, "completion leaves open view after animation");
                    root.controller.edit("tasks", root.taskId, {completed: false});
                    notesPage.requestDelete("notes", root.noteId);
                    root.child(notesPage, "notesTasksConfirmDelete").clicked();
                } else if (stage === 24 && modelData === Quickshell.screens[0]) {
                    root.check(!root.controller.notes[root.noteId] && !root.child(notesPage, "notesTasksNotesPane").selectedId, "delete removes note and closes editor");
                    root.check(!root.controller.tasks[root.taskId].completed, "uncomplete retained task");
                    const pinned = Object.values(root.controller.notes).find(n => n.title === "A calmer workspace");
                    root.controller.send({action: "duplicate", kind: "notes", id: pinned.id});
                    GlobalConfig.appearance.font.scale = 1.3;
                    notesPage.width = 380; notesPage.height = 600;
                    root.child(notesPage, "notesTasksSearch").text = "linux";
                } else if (stage === 25 && modelData === Quickshell.screens[0]) {
                    tilesMatch();
                    root.check(!root.child(notesPage, "notesTasksNotesPane").selectedId && !root.child(canvas.page, "notesTasksNotesPane").selectedId, "duplicate reply does not open unrelated page editors");
                    const search = root.child(notesPage, "notesTasksSearch");
                    root.check(root.child(notesPage, "notesTasksNotesList").count === 1, "debounced search with font scaling");
                    root.check(search.mapToItem(notesPage, search.width, 0).x <= notesPage.width, "expanded search fits narrow page");
                    const tile = root.child(notesPage, "notesTasksNotesList").itemAtIndex(0), card = root.child(tile, "notesTasksNoteCard");
                    root.check(card.height <= tile.height && card.width <= notesPage.width, "scaled-font note stays within its cell");
                    search.text = ""; GlobalConfig.appearance.font.scale = 1;
                    GlobalConfig.appearance.anim.durations.scale = 0;
                } else if (stage === 26 && modelData === Quickshell.screens[0]) {
                    root.check(!root.controller.motion, "global animation scale respected");
                    GlobalConfig.appearance.anim.durations.scale = 1;
                    notesPage.forceActiveFocus(); inputTest.keyClick(Qt.Key_F, Qt.ControlModifier);
                    root.check(root.child(notesPage, "notesTasksSearch").activeFocus, "Ctrl+F focuses expanding search");
                    notesPage.forceActiveFocus(); inputTest.keyClick(Qt.Key_N, Qt.ControlModifier | Qt.ShiftModifier);
                    root.check(root.child(notesPage, "notesTasksQuickCapture").kind === "tasks", "Ctrl+Shift+N captures tasks");
                    notesPage.forceActiveFocus(); inputTest.keyClick(Qt.Key_N, Qt.ControlModifier);
                    root.check(root.child(notesPage, "notesTasksQuickCapture").kind === "notes" && root.child(notesPage, "notesTasksCapture").activeFocus, "Ctrl+N focuses note capture");
                    typeIn(root.child(notesPage, "notesTasksCapture"), "Keyboard captured note"); inputTest.keyClick(Qt.Key_Return, Qt.ControlModifier);
                } else if (stage === 27 && modelData === Quickshell.screens[0]) {
                    const note = Object.values(root.controller.notes).find(n => n.text === "Keyboard captured note");
                    root.check(!!note && root.child(notesPage, "notesTasksNotesPane").selectedId === note.id, "Ctrl+Enter captures and opens the requesting editor");
                    root.check(!root.child(root.windows[1].notesPage, "notesTasksNotesPane").selectedId && !root.child(canvas.page, "notesTasksNotesPane").selectedId, "capture reply remains local to the requesting page");
                    root.controller.send({action: "flush"});
                }
            }
        }
    }
    Timer {
        interval: 350; repeat: true; running: true
        onTriggered: {
            if (!root.controller?.healthy || !root.timerController?.healthy || root.windows.length !== 2) {
                if (++root.waits > 25) { console.error("PROBE FAILED: helpers/outputs not ready " + root.controller?.error); Qt.exit(1); }
                return;
            }
            if (root.stage === 0) {
                root.check(root.controller.notes["legacy-note"].text === "Version 1 retained" && root.controller.tasks["legacy-task"].completed, "existing v1 notes and tasks load unchanged");
                root.timerController.send({action: "preferences", values: {sound: false, notification: false}});
            }
            ++root.stage;
            for (const window of root.windows) window.verify(root.stage);
            if (root.stage === 2) {
                root.controller.send({action: "create", kind: "notes", values: {title: "Native notes", text: "A shared thought", tags: ["sharedtag"]}});
                const d = new Date(); const day = d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
                root.controller.send({action: "create", kind: "tasks", values: {title: "Today task", due: {date: day, time: ""}}});
                root.controller.send({action: "create", kind: "tasks", values: {title: "Upcoming task", due: {date: "2099-01-01", time: ""}}});
            } else if (root.stage === 3) {
                root.noteId = Object.values(root.controller.notes).find(n => n.title === "Native notes").id;
                root.taskId = Object.values(root.controller.tasks).find(t => t.title === "Today task").id;
                root.controller.send({action: "subtask-create", kind: "tasks", id: root.taskId, title: "First step"});
            } else if (root.stage === 6) {
                const id = Object.values(root.controller.tasks).find(t => t.title === "Upcoming task").id;
                root.controller.edit("tasks", id, {completed: true});
            } else if (root.stage === 13) {
                root.check(root.controller.motion, "default animations");
                root.controller.send({action: "settings", values: {animation: false, compact: true}});
            } else if (root.stage === 14) {
                root.check(!root.controller.motion && root.controller.settings.compact, "reduced animation and compact preferences");
                root.controller.send({action: "flush"});
            } else if (root.stage === 15) {
                root.check(!root.controller.saving, "debounced persistence acknowledged");
                root.verifyLargeModels();
                root.controller.send({action: "settings", values: {animation: true, compact: false}});
                for (const values of [
                    {title: "A calmer workspace", text: "Less noise. More room to think.\n\nBuild a dashboard that feels like home.", tags: ["ideas", "dev"], pinned: true},
                    {title: "Weekend plans", text: "Take a long walk\nPick up coffee\nMake something small", tags: ["life"]},
                    {title: "Things to explore", text: "An offline reading corner.\nA small garden.\nAn evening without notifications.", tags: ["ideas"]},
                    {title: "Linux setup", text: "Keep the useful bits.\nDocument the rest.", tags: ["linux", "dev"]}
                ]) root.controller.send({action: "create", kind: "notes", values: values});
                const d = new Date(); const day = d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
                root.controller.send({action: "create", kind: "tasks", values: {title: "Clear the desk", completed: true, due: {date: day, time: ""}}});
                const captures = Object.values(root.controller.tasks).filter(t => t.title === "Enter-created task");
                captures.forEach((t, i) => root.controller.edit("tasks", t.id, {title: i === 0 ? "Sketch a new idea" : "Take a short walk"}));
                root.controller.send({action: "flush"});
            } else if (root.stage === 28) {
                root.check(!root.controller.saving, "UI changes flushed before shell restart");
                console.log("DASHBOARD QML PROBE PASSED: two monitors, scale 1.25, native tabs, Timer routing, notes/tasks/search/edit/subtasks/quick capture/settings/stacking, keyboard CRUD, delayed completion/undo, scaled fonts, global reduced motion, 300-note/2000-task models");
                Qt.quit();
            }
        }
    }
}
'''


RESTART_PROBE = r'''
import QtQuick
import Quickshell

ShellRoot {
    id: root
    property var controller: null
    property int attempts: 0
    Component.onCompleted: controller = Qt.createComponent(Quickshell.env("NOTES_PROBE_PLUGIN") + "/main.qml").createObject(root)
    Timer {
        interval: 100; repeat: true; running: true
        onTriggered: {
            if (!root.controller?.healthy) { if (++root.attempts > 50) { console.error("PROBE FAILED: restart helper " + root.controller?.error); Qt.exit(1); } return; }
            const expected = JSON.parse(Quickshell.env("NOTES_PROBE_EXPECTED"));
            const byId = (a, b) => a.id.localeCompare(b.id);
            const same = JSON.stringify(Object.values(root.controller.notes).sort(byId)) === JSON.stringify(expected.notes.sort(byId))
                && JSON.stringify(Object.values(root.controller.tasks).sort(byId)) === JSON.stringify(expected.tasks.sort(byId))
                && JSON.stringify(root.controller.settings) === JSON.stringify(expected.settings);
            if (!same) { console.error("PROBE FAILED: shell restart snapshot mismatch"); Qt.exit(1); }
            else { console.log("NOTES SHELL RESTART PASSED: v1 data and all UI edits/settings retained"); Qt.quit(); }
        }
    }
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    from backend.dashboard_compat import sources, FILES
    from backend.paths import Paths
    with tempfile.TemporaryDirectory(prefix='cdm-dashboard-probe-') as temporary:
        temp = Path(temporary)
        copied = temp / 'shell'
        shutil.copytree(HOST, copied, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        paths = Paths.sandbox(temp / 'xdg')
        plugins = paths.config / 'caelestia/plugins'
        shutil.copytree(ROOT / 'plugins/notes-tasks', plugins / 'notes-tasks', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT / 'plugins/animated-timer', plugins / 'animated-timer', ignore=shutil.ignore_patterns('__pycache__'))
        calendar = plugins / 'probe-calendar'; calendar.mkdir()
        (calendar / 'main.qml').write_text('import Quickshell\nScope {}\n')
        (calendar / 'DashboardPage.qml').write_text('import QtQuick\nItem { required property var controller; property bool presentationActive: true; implicitWidth: 400; implicitHeight: 300 }\n')
        page = {'id': 'notes-tasks', 'title': 'Notes', 'icon': 'edit_note', 'component': 'DashboardPage.qml', 'order': 50}
        pages = {'notes-tasks': page, 'probe-calendar': {**page, 'id': 'probe-calendar', 'title': 'Calendar', 'order': 60}}
        originals = {n: (ROOT / 'tests/fixtures/caelestia-kde' / n).read_text() for n in FILES}
        for name, value in sources(originals, pages, True, paths).items(): (copied / name).write_text(value)
        (copied / 'Probe.qml').write_text(PROBE)
        stamp = "2026-10-01T12:00:00.000+00:00"
        legacy = {"schemaVersion": 1, "revision": 2, "settings": {"defaultSection": "both", "showCompleted": False, "taskSort": "manual", "noteSort": "updated", "animation": True, "compact": False, "confirmDelete": True},
                  "notes": [{"id": "legacy-note", "title": "Older note", "content": {"format": "plain", "text": "Version 1 retained"}, "tags": ["legacy"], "pinned": False, "archived": True, "createdAt": stamp, "updatedAt": stamp, "extensions": {}}],
                  "tasks": [{"id": "legacy-task", "title": "Older completed task", "details": "", "tags": [], "completed": True, "completedAt": stamp, "order": 1024, "due": {"date": "", "time": ""}, "priority": 0, "subtasks": [], "recurrence": None, "projectId": None, "createdAt": stamp, "updatedAt": stamp, "extensions": {}}]}
        personal = paths.data / 'caelestia-components/notes-tasks'; personal.mkdir(parents=True)
        (personal / 'data.json').write_text(json.dumps(legacy), encoding='utf-8')
        env = dict(os.environ, QT_QPA_PLATFORM='wayland', QSG_RHI_BACKEND='software', QT_QUICK_BACKEND='software', QS_DISABLE_CRASH_HANDLER='1',
                   QML2_IMPORT_PATH=str(Path.home() / '.local/lib/qt6/qml') + ':' + str(copied),
                   NOTES_PROBE_PLUGIN=(plugins / 'notes-tasks').as_uri(), TIMER_PROBE_PLUGIN=(plugins / 'animated-timer').as_uri(), CALENDAR_PROBE_PLUGIN=calendar.as_uri())
        for key, directory in [('XDG_CONFIG_HOME', paths.config), ('XDG_DATA_HOME', paths.data), ('XDG_STATE_HOME', paths.state), ('XDG_CACHE_HOME', temp / 'cache'), ('XDG_RUNTIME_DIR', temp / 'runtime')]:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700); env[key] = str(directory)
        scheme = Path.home() / '.local/state/caelestia/scheme.json'
        if scheme.is_file():
            theme = paths.state / 'caelestia'; theme.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(scheme, theme / 'scheme.json')
        if args.screenshot: env['NOTES_PROBE_SCREENSHOT'] = str(args.screenshot.resolve())
        env['WAYLAND_DISPLAY'] = 'dashboard-test'; env.pop('DISPLAY', None)
        with open(temp / 'kwin.log', 'w') as log:
            compositor = subprocess.Popen(['dbus-run-session', '--', 'kwin_wayland', '--virtual', '--no-lockscreen', '--no-global-shortcuts', '--no-kactivities', '--output-count', '2', '--width', '1440', '--height', '900', '--scale', '1.25', '--socket', 'dashboard-test'], env=env, stdout=log, stderr=log, start_new_session=True)
            process = None
            try:
                for _ in range(100):
                    if (temp / 'runtime/dashboard-test').exists(): break
                    if compositor.poll() is not None: raise RuntimeError((temp / 'kwin.log').read_text())
                    time.sleep(0.05)
                process = subprocess.Popen(['dbus-run-session', '--', 'quickshell', '--no-color', '--path', str(copied / 'Probe.qml')], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
                try: stdout, stderr = process.communicate(timeout=25)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    stdout, stderr = process.communicate(timeout=5)
            finally:
                for p in (process, compositor):
                    if p and p.poll() is None: os.killpg(p.pid, signal.SIGTERM); p.wait(timeout=5)
        output = stdout + stderr
        restart_output = ''
        if process.returncode == 0 and 'DASHBOARD QML PROBE PASSED' in output and 'PROBE FAILED' not in output:
            sys.path.insert(0, str(plugins / 'notes-tasks/helper'))
            from domain import Model
            from storage import decode
            expected = Model(decode((personal / 'data.json').read_bytes())).snapshot()
            assert any(n['id'] == 'legacy-note' and n['text'] == 'Version 1 retained' for n in expected['notes'])
            assert any(n['text'] == 'Keyboard captured note' for n in expected['notes'])
            assert not any(n['title'] == 'Edited title' for n in expected['notes'])
            (copied / 'Restart.qml').write_text(RESTART_PROBE)
            env['NOTES_PROBE_EXPECTED'] = json.dumps(expected)
            # Headless offscreen is sufficient: this check exercises the new shell controller/helper.
            restart_env = dict(env, QT_QPA_PLATFORM='offscreen')
            restarted = subprocess.run(['quickshell', '--no-color', '--path', str(copied / 'Restart.qml')], env=restart_env, capture_output=True, text=True, timeout=10)
            restart_output = restarted.stdout + restarted.stderr
            output += restart_output
        errors = ('TypeError:', 'ReferenceError:', 'Cannot assign', 'Error loading', 'is not a type', 'Binding loop', 'PROBE FAILED', 'Unable to assign', 'Cannot create delegate', 'Required property', 'recursive rearrange', 'Cannot override FINAL')
        success = process.returncode == 0 and 'DASHBOARD QML PROBE PASSED' in output and 'NOTES SHELL RESTART PASSED' in output and not any(e in output for e in errors)
        print(output if not success else '\n'.join(line for line in output.splitlines() if 'DASHBOARD QML PROBE' in line or 'NOTES SHELL RESTART' in line or 'notes-tasks/' in line))
        return 0 if success else 1


if __name__ == '__main__': raise SystemExit(main())
