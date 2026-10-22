"""Read only the bounded installation fields from Battle.net's protobuf index."""
from pathlib import Path
import re


def _fields(data):
    position, result, count = 0, {}, 0

    def integer():
        nonlocal position
        value = 0
        for shift in range(0, 70, 7):
            if position >= len(data):
                raise ValueError('Incomplete installation index')
            byte = data[position]
            position += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError('Invalid installation index integer')

    while position < len(data):
        count += 1
        if count > 50000:
            raise ValueError('Too many installation fields')
        tag = integer()
        field, wire = tag >> 3, tag & 7
        if not field:
            raise ValueError('Invalid installation field')
        if wire == 0:
            value = integer()
        elif wire in (1, 2, 5):
            size = integer() if wire == 2 else (8 if wire == 1 else 4)
            if size > len(data) - position:
                raise ValueError('Incomplete installation field')
            value = data[position:position + size]
            position += size
        else:
            raise ValueError('Unsupported installation index field')
        result.setdefault(field, []).append(value)
    return result


def installations(path):
    with Path(path).open('rb') as handle:
        data = handle.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('Installation index too large')
    fields = _fields(data)
    # Current indexes contain repeated ProductInstall messages; old ones may
    # contain one ProductInstall directly. These three strings are all we use.
    messages = fields.get(1, [])
    first = fields.get(1, [b''])[0]
    if isinstance(first, bytes) and re.fullmatch(rb'[a-zA-Z0-9_.-]+', first):
        messages = [data]
    result = []
    for message in messages:
        if not isinstance(message, bytes):
            raise ValueError('Invalid product installation')
        entry = _fields(message)
        def blob(fields, number):
            value = fields.get(number, [b''])[0]
            if not isinstance(value, bytes):
                raise ValueError('Invalid product installation field')
            return value
        settings = _fields(blob(entry, 3))
        uid = blob(entry, 1).decode('utf-8')
        product = blob(entry, 2).decode('utf-8')
        root = blob(settings, 1).decode('utf-8')
        state = _fields(blob(entry, 4))
        base_state = _fields(blob(state, 1))
        if entry.get(7, [0])[0] or base_state.get(1, [1])[0] == 0:
            continue
        if uid and root:
            result.append((uid, product, root))
    return result
