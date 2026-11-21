"""The names people read for the two modes. The API, stored jobs, settings and graphs keep the ids "standard" and
"fast": Redux is the API mode "standard" and Bolt is "fast"."""

MODE_LABELS = {'standard': 'Redux', 'fast': 'Bolt'}
MODE_TEXT = {'standard': '', 'fast': 'Quicker, with a slightly different look. Use Redux for finals.'}
CHOOSE_MODE = 'Choose a mode: Redux or Bolt.'


def mode_label(mode):
    return MODE_LABELS.get(mode, MODE_LABELS['standard'])


# 5.0.2: the two engines, named plainly (engine design sections 2.10 and 3.1). A plan, a stored plan or a record without an
# `engine` key is the Classic engine's (5.0.1's records); the Large-image engine's plans carry engine 'banded'.
CLASSIC, LARGE_IMAGE = 'classic', 'large-image'
ENGINE_LABELS = {CLASSIC: 'Classic', LARGE_IMAGE: 'Large-image'}


def engine_of(plan):
    """'classic' or 'large-image' for a Plan, a stored plan dict or an API plan dict (with `executor`)."""
    if isinstance(plan, dict):
        if plan.get('executor') in ENGINE_LABELS:
            return plan['executor']
        return LARGE_IMAGE if plan.get('engine') == 'banded' else CLASSIC
    return LARGE_IMAGE if getattr(plan, 'engine', CLASSIC) == 'banded' else CLASSIC


def engine_label(plan):
    return ENGINE_LABELS[engine_of(plan)]


def executor(plan, ok=None):
    """Which engine will run a plan (the /api/plan answer's `executor`): engine_of(plan), or None when the plan is refused."""
    if ok is None:
        ok = plan.get('ok') if isinstance(plan, dict) else getattr(plan, 'ok', False)
    return engine_of(plan) if ok else None


def memory_class_label(machine_class):
    """'48 GB', '64 GB' or '128 GB' for a Large-image plan's machine class (engine/banded_plan.MACHINE_CLASSES), else ''."""
    from engine import banded_plan
    return (banded_plan.MACHINE_CLASSES.get(machine_class) or {}).get('label', '')


def controls_doc(doc):
    """controls.describe() with the mode names people read (the engine keeps its own internal labels)."""
    out = dict(doc)
    out['modes'] = [dict(m, label=MODE_LABELS.get(m.get('key'), m.get('label')), text=MODE_TEXT.get(m.get('key'), m.get('text')))
                    for m in doc.get('modes') or []]
    return out
