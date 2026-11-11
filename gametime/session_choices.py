"""Per-purpose opening allowances, separate from measured activity sessions."""
import re
import uuid


def defaults(t=lambda text: text):
    return {'question': str(t('Why are you opening this?')), 'allocation': 'shared', 'options': [
        {'id': uuid.uuid4().hex, 'label': str(t('For work')), 'limit': None},
        {'id': uuid.uuid4().hex, 'label': str(t('Just checking')), 'limit': 2}]}


def validate(value):
    if not isinstance(value, dict) or set(value) not in ({'question', 'options'}, {'question', 'options', 'allocation'}):
        raise ValueError('Invalid opening choices.')
    if value.get('allocation','shared') not in ('shared','activity'): raise ValueError('Choose shared or separate session allowances.')
    question, options = value['question'], value['options']
    if not isinstance(question, str) or not question.strip() or len(question) > 180 or '\0' in question:
        raise ValueError('Enter a question of up to 180 characters.')
    if not isinstance(options, list) or not 2 <= len(options) <= 8:
        raise ValueError('Add between 2 and 8 choices.')
    seen = set()
    for option in options:
        if not isinstance(option, dict) or set(option) != {'id', 'label', 'limit'}:
            raise ValueError('Invalid opening choices.')
        identity, label, limit = option['id'], option['label'], option['limit']
        if (not isinstance(identity, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', identity) or identity in seen
                or not isinstance(label, str) or not label.strip() or len(label) > 120 or '\0' in label):
            raise ValueError('Give each choice a name of up to 120 characters.')
        if limit is not None and (type(limit) is not int or not 1 <= limit <= 10000):
            raise ValueError('Choose a session limit between 1 and 10000.')
        seen.add(identity)
    return value


def allowance_activity(members, atom, scope):
    """One configured member keeps one allowance, including its subdomains."""
    from .activity_identity import app_identity, site_identity
    from .focus import matches
    game, app, site = atom
    if scope == 'site':
        site = site_identity(site)
        selected = [site_identity(m['value']) for m in members if m['kind']=='site' and matches(site,site_identity(m['value']))]
        return 'site:' + (max(selected,key=len) if selected else site)
    if game and any(m['kind']=='game' and m['value']==game or m=={'kind':'category','value':'games'} for m in members):
        return 'game:' + game
    return 'app:' + app_identity(app)


class ChoiceLedger:
    """A committed choice consumes one allowance, even if a click is retried."""
    def __init__(self, store):
        self.db = store.db
        self.db.execute('CREATE TABLE IF NOT EXISTS session_choices ('
                        'budget TEXT NOT NULL, step TEXT NOT NULL, day TEXT NOT NULL, '
                        'visit TEXT NOT NULL, choice TEXT NOT NULL, at REAL NOT NULL, '
                        "activity TEXT NOT NULL DEFAULT '', PRIMARY KEY(budget,step,visit))")
        if 'activity' not in {row[1] for row in self.db.execute('PRAGMA table_info(session_choices)')}:
            self.db.execute("ALTER TABLE session_choices ADD COLUMN activity TEXT NOT NULL DEFAULT ''")
        self.db.execute('CREATE INDEX IF NOT EXISTS session_choices_day ON session_choices(budget,step,day,choice)')
        self.cache = {}

    def counts(self, budget, step, day, activity=None):
        key = (budget, step, day, activity)
        if key not in self.cache:
            self.cache = {k: v for k, v in self.cache.items() if k[:2] != key[:2] or k[2] == day}
            self.cache[key] = dict(self.db.execute('SELECT choice,COUNT(*) FROM session_choices '
                'WHERE budget=? AND step=? AND day=?' + (' AND activity=?' if activity is not None else '') + ' GROUP BY choice',
                key if activity is not None else key[:3]))
        return self.cache[key]

    def options(self, budget, step, day, value, activity=''):
        counts = self.counts(budget, step, day, activity if value.get('allocation')=='activity' else None)
        return [dict(option, used=counts.get(option['id'], 0),
                     remaining=None if option['limit'] is None else max(0, option['limit']-counts.get(option['id'], 0)))
                for option in value['options']]

    def choose(self, budget, step, day, visit, value, choice, now, activity=''):
        validate(value)
        option = next((item for item in value['options'] if item['id'] == choice), None)
        if option is None: return False
        with self.db:
            existing = self.db.execute('SELECT choice FROM session_choices WHERE budget=? AND step=? AND visit=?',
                                       (budget, step, visit)).fetchone()
            if existing: return existing[0] == choice
            separate=value.get('allocation')=='activity'
            used = self.db.execute('SELECT COUNT(*) FROM session_choices WHERE budget=? AND step=? AND day=? AND choice=?'+(' AND activity=?' if separate else ''),
                                   (budget, step, day, choice, activity) if separate else (budget, step, day, choice)).fetchone()[0]
            if option['limit'] is not None and used >= option['limit']: return False
            self.db.execute('INSERT INTO session_choices VALUES (?,?,?,?,?,?,?)', (budget, step, day, visit, choice, now, activity))
        self.cache = {k:v for k,v in self.cache.items() if k[:3] != (budget,step,day)}
        return True


class Visits:
    """Foreground transitions create visits; showing the choice itself does not."""
    def __init__(self): self.current = {}

    def observe(self, subjects):
        self.current = {key: value for key, value in self.current.items()
                        if subjects.get(key) == value['subject']}
        for key, subject in subjects.items():
            self.current.setdefault(key, dict(subject=subject, token=uuid.uuid4().hex, choice=None))
        return self.current

    def clear(self): self.current.clear()
