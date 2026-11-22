"""The committed G1 table a proof row's machine runs under, set on the planner as the service sets it (build wave 3,
contracts.g1u), so that a plan the proof harness builds and registers equals, constant for constant, the plan the service
makes on that machine.

The planner's module attributes (engine/banded_plan.py): BXF_TABLE, an object with engine/bxf/g1's table interface, and
BXF_TABLE_SOURCE ('committed', 'local', 'committed+local' or None). The service assigns them from g1.load() on the engine's
own environment; a set BXF_TABLE always decides the finish tier ('bxf' when it applies, else 'tier3'), and BXF_AVAILABLE
counts only while BXF_TABLE is None. A proof row runs on a machine whose CPU class G1 measured, so its table is a committed
one: g1.Table over the engine/bxf/g1_table.py TABLES entry, read with that entry's own environment (it applies by
construction; the machine's own environment is checked against it on the machine, check_environment). use() also keeps
BXF_AVAILABLE True, so a build whose planner predates BXF_TABLE (it ignores the attribute) still counts the banded
finish's figures: on such a build the two settings give the same plan; on a build with the wiring, the table decides.

Which TABLES entry a machine takes is the caller's (the internal row table names its machines); this module takes the
index. Sizes and library versions only: no machine name is written here."""
import hashlib
import json

SOURCE = 'committed'


def tables():
    """The build's committed tables (engine/bxf/g1.committed_tables), one per environment G1 measured."""
    from engine.bxf import g1
    return g1.committed_tables()


def environment_sha256(env):
    return hashlib.sha256(json.dumps(env, sort_keys=True, separators=(',', ':')).encode('utf8')).hexdigest()


def committed(index):
    """g1.Table over TABLES[index], read with that entry's own environment (so it applies). Raises IndexError for an index
    this build has no table for, ValueError for an entry without an environment."""
    from engine.bxf import g1
    tabs = tables()
    if not 0 <= int(index) < len(tabs):
        raise IndexError(f'this build has {len(tabs)} committed G1 tables; there is no TABLES[{index}]')
    data = tabs[int(index)]
    env = dict(data.get('environment') or {})
    if not env:
        raise ValueError(f'TABLES[{index}] records no environment')
    t = g1.Table(data, env=env)
    if not t.applies:
        raise ValueError(f'TABLES[{index}] does not apply under its own environment: {t.why_not()}')
    return t


def record(index, table=None):
    """The registered record of the table a row runs under: its index, source, the environment it was measured in (with
    the environment's sha256), its gate and band heights, and the number of ops it classes banded."""
    t = table if table is not None else committed(index)
    data = getattr(t, 'data', {}) or {}
    env = dict(data.get('environment') or getattr(t, 'env', {}) or {})
    ops = data.get('ops') or {}
    return {'index': int(index), 'source': SOURCE, 'applies': bool(getattr(t, 'applies', False)),
            'environment': env, 'environment_sha256': environment_sha256(env), 'gate': data.get('gate'),
            'band_heights': list(data.get('band_heights') or []),
            'ops_banded': sum(1 for v in ops.values() if (v or {}).get('verdict') == 'banded'), 'ops': len(ops),
            'rule': 'contracts.g1u: banded_plan.BXF_TABLE = this table, BXF_TABLE_SOURCE = committed (a set table decides '
                    'the finish tier; BXF_AVAILABLE True as well, for a planner that predates the attribute)'}


def use(index=None, table=None, source=SOURCE):
    """Set the planner's table as the service would on the row's machine (contracts.g1u) and return its record. index:
    the TABLES entry (committed()); table: any object with g1's table interface instead (tests). Every plan made after
    this call in this process counts that table: call it again after the app's modules are reloaded."""
    from engine import banded_plan
    if table is None:
        if index is None:
            raise ValueError('use() needs a TABLES index or a table')
        table = committed(index)
    banded_plan.BXF_TABLE = table
    banded_plan.BXF_TABLE_SOURCE = source
    banded_plan.BXF_AVAILABLE = True
    rec = record(-1 if index is None else index, table)
    rec['source'] = source
    return rec


def in_force():
    """What the planner counts now: {'table_set', 'source', 'bxf_available', 'environment_sha256'} (None where unset)."""
    from engine import banded_plan
    t = getattr(banded_plan, 'BXF_TABLE', None)
    env = (getattr(t, 'data', None) or {}).get('environment') if t is not None else None
    return {'table_set': t is not None, 'source': getattr(banded_plan, 'BXF_TABLE_SOURCE', None),
            'bxf_available': bool(getattr(banded_plan, 'BXF_AVAILABLE', False)),
            'environment_sha256': environment_sha256(env) if env else None}


def check_registered(rec):
    """None when the registered record `rec` names a committed table of this build with the same environment, else the
    reason (a packet whose table changed since it was registered must not run)."""
    try:
        now = record(rec['index'])
    except (KeyError, IndexError, ValueError, TypeError) as e:
        return f'the registered G1 table is not in this build: {e}'
    if now['environment_sha256'] != rec.get('environment_sha256'):
        return f"TABLES[{rec['index']}]'s environment differs from the registered one"
    return None


def check_environment(rec, env):
    """The machine's own g1.environment() (`env`, read in the engine's runtime on the machine) against the registered
    table's environment: {'equal', 'differs': [keys], 'rule'}. Equal means the worker's g1.load() picks this table."""
    from engine.bxf import g1
    want = rec.get('environment') or {}
    differs = [k for k in g1.ENV_KEYS if (env or {}).get(k) != want.get(k)]
    return {'equal': not differs, 'differs': differs,
            'rule': "the machine's g1.environment() in the engine's runtime equals the registered table's on every key "
                    'of engine/bxf/g1.ENV_KEYS'}
