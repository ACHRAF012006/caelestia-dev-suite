"""Domain operations independent of QML and persistence representation.

Reserved extension objects preserve future recurrence, project, attachment,
calendar and sync data. Commands patch individual fields, never entire records.
"""
import copy
from datetime import date, datetime, time, timezone
import re
import uuid
from storage import StorageError, DEFAULT_SETTINGS


def now(): return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def text(value, limit=1000000):
    if not isinstance(value, str) or len(value) > limit or '\0' in value: raise StorageError('Invalid or oversized text')
    return value


def tags(value):
    if not isinstance(value, list) or len(value) > 100 or any(not isinstance(tag, str) for tag in value): raise StorageError('Invalid tags')
    return list(dict.fromkeys(text(tag.strip(), 80) for tag in value if isinstance(tag, str) and tag.strip()))


def validate_settings(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_SETTINGS): raise StorageError('Unknown settings')
    options = {'defaultSection': ('both', 'notes', 'tasks'), 'taskSort': ('manual', 'due', 'priority', 'created'), 'noteSort': ('updated', 'created', 'title')}
    for key, val in value.items():
        if key in options:
            if val not in options[key]: raise StorageError('Invalid ' + key)
        elif type(val) is not bool: raise StorageError('Invalid ' + key)


def valid_due(value):
    if not isinstance(value, dict) or set(value) != {'date', 'time'}: raise StorageError('Due requires date and time')
    if value['date']:
        if not isinstance(value['date'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value['date']): raise StorageError('Use YYYY-MM-DD for dates')
        try: date.fromisoformat(value['date'])
        except ValueError as error: raise StorageError('Invalid due date') from error
    elif value['date'] != '': raise StorageError('Invalid due date')
    if value['time']:
        if not value['date'] or not isinstance(value['time'], str) or not re.fullmatch(r'\d{2}:\d{2}', value['time']): raise StorageError('Time requires a date and HH:MM')
        try: time.fromisoformat(value['time'])
        except ValueError as error: raise StorageError('Invalid due time') from error
    elif value['time'] != '': raise StorageError('Invalid due time')
    return dict(value)


def valid_subtasks(value):
    if not isinstance(value, list) or len(value) > 1000: raise StorageError('Invalid subtasks')
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {'id', 'title', 'completed'} or not isinstance(item['id'], str) or not item['id'] or item['id'] in seen or type(item['completed']) is not bool: raise StorageError('Invalid subtask')
        text(item['title'], 10000); seen.add(item['id'])
    return copy.deepcopy(value)


def validate_task(row):
    if type(row.get('completed')) is not bool or not isinstance(row.get('completedAt'), str) or type(row.get('priority')) is not int or row['priority'] not in (0, 1, 2, 3) or type(row.get('order')) is not int:
        raise StorageError('Invalid task state/priority/order')
    valid_due(row.get('due')); valid_subtasks(row.get('subtasks')); text(row.get('details'))


def search_text(kind, row):
    parts = [row['title'], ' '.join(row['tags'])]
    if kind == 'notes': parts.append(row['content']['text'])
    else: parts += [row['details'], ' '.join(s['title'] for s in row['subtasks'])]
    return '\n'.join(parts).lower()


def presentation(kind, row):
    """Wire DTO, not the persisted document. Cache search text once per edit."""
    value = copy.deepcopy(row)
    if kind == 'notes': value['text'] = row['content']['text']; value.pop('content')
    value['searchText'] = search_text(kind, row)
    return value


class Model:
    def __init__(self, document):
        self.document = document
        self.rows = {kind: {r['id']: r for r in document[kind]} for kind in ('notes', 'tasks')}
        self.max_order = max((r['order'] for r in document['tasks']), default=0)

    def snapshot(self):
        return {'type': 'snapshot', 'revision': self.document['revision'], 'settings': dict(self.document['settings']),
                **{kind: [presentation(kind, r) for r in rows.values()] for kind, rows in self.rows.items()}}

    def persisted(self):
        return {**self.document, **{kind: list(rows.values()) for kind, rows in self.rows.items()}}

    def command(self, message):
        if not isinstance(message, dict): raise StorageError('Command must be an object')
        action = message.get('action')
        changes = []
        if action == 'settings':
            value = message.get('values'); validate_settings(value)
            if all(self.document['settings'].get(k) == v for k, v in value.items()): return None
            self.document['settings'].update(value)
        else:
            kind = message.get('kind')
            if kind not in self.rows: raise StorageError('Unknown record kind')
            rows = self.rows[kind]
            if action == 'create':
                stamp = now(); identifier = uuid.uuid4().hex
                row = {'id': identifier, 'title': '', 'tags': [], 'createdAt': stamp, 'updatedAt': stamp, 'extensions': {}}
                if kind == 'notes': row.update(content={'format': 'plain', 'text': ''}, pinned=False, archived=False)
                else:
                    self.max_order += 1024
                    row.update(details='', completed=False, completedAt='', order=self.max_order,
                               due={'date': '', 'time': ''}, priority=0, subtasks=[], recurrence=None, projectId=None)
                self.patch(kind, row, message.get('values', {}))
                rows[identifier] = row; changes.append((kind, identifier, row))
            else:
                identifier = message.get('id')
                if identifier not in rows: raise StorageError('Record no longer exists')
                row = copy.deepcopy(rows[identifier])
                if action == 'edit':
                    self.patch(kind, row, message.get('values', {}))
                    if row == rows[identifier]: return None
                    row['updatedAt'] = now(); rows[identifier] = row; changes.append((kind, identifier, row))
                elif isinstance(action, str) and action.startswith('subtask-') and kind == 'tasks':
                    sub_id = message.get('subtaskId')
                    if action == 'subtask-create':
                        row['subtasks'].append({'id': uuid.uuid4().hex, 'title': text(message.get('title'), 10000), 'completed': False})
                    else:
                        sub = next((item for item in row['subtasks'] if item['id'] == sub_id), None)
                        if sub is None: raise StorageError('Subtask no longer exists')
                        if action == 'subtask-toggle': sub['completed'] = not sub['completed']
                        elif action == 'subtask-edit': sub['title'] = text(message.get('title'), 10000)
                        elif action == 'subtask-delete': row['subtasks'].remove(sub)
                        else: raise StorageError('Unknown subtask operation')
                    valid_subtasks(row['subtasks'])
                    row['updatedAt'] = now(); rows[identifier] = row; changes.append((kind, identifier, row))
                elif action == 'delete':
                    del rows[identifier]; changes.append((kind, identifier, None))
                elif action == 'duplicate' and kind == 'notes':
                    row['id'] = uuid.uuid4().hex; row['createdAt'] = row['updatedAt'] = now(); row['archived'] = False
                    rows[row['id']] = row; changes.append((kind, row['id'], row))
                elif action == 'reorder' and kind == 'tasks':
                    ordered = sorted(rows.values(), key=lambda r: (r['order'], r['id']))
                    ordered.remove(rows[identifier])
                    before = message.get('before')
                    if before is not None and before not in rows: raise StorageError('Reorder destination no longer exists')
                    position = next((i for i, r in enumerate(ordered) if r['id'] == before), len(ordered))
                    ordered.insert(position, row)
                    for i, task in enumerate(ordered):
                        order = (i + 1) * 1024
                        if task['order'] != order:
                            task = {**task, 'order': order, 'updatedAt': now()}; rows[task['id']] = task; changes.append((kind, task['id'], task))
                    self.max_order = len(ordered) * 1024
                    if not changes: return None
                else: raise StorageError('Unsupported action')
        self.document['revision'] += 1
        return {'type': 'delta', 'revision': self.document['revision'],
                'changes': [{'kind': k, 'id': i, 'row': presentation(k, r) if r else None} for k, i, r in changes],
                'settings': dict(self.document['settings']) if action == 'settings' else None,
                'requestId': message.get('requestId', '')}

    def patch(self, kind, row, values):
        allowed = {'title', 'tags', 'text', 'pinned', 'archived'} if kind == 'notes' else {'title', 'tags', 'details', 'completed', 'due', 'priority', 'subtasks'}
        if not isinstance(values, dict) or set(values) - allowed: raise StorageError('Unknown editable fields')
        for key, value in values.items():
            if key in ('title', 'details', 'text'):
                value = text(value, 10000 if key == 'title' else 1000000)
                if key == 'text': row['content'] = {**row['content'], 'text': value}; continue
            elif key == 'tags': value = tags(value)
            elif key in ('pinned', 'archived', 'completed'):
                if type(value) is not bool: raise StorageError('Invalid flag')
                if key == 'completed' and row['completed'] != value: row['completedAt'] = now() if value else ''
            elif key == 'due': value = valid_due(value)
            elif key == 'subtasks': value = valid_subtasks(value)
            elif key == 'priority':
                if type(value) is not int or value not in (0, 1, 2, 3): raise StorageError('Invalid priority')
            row[key] = value
