"""The names people read for the two modes. The API, stored jobs, settings and graphs keep the ids "standard" and
"fast": Redux is the API mode "standard" and Bolt is "fast"."""

MODE_LABELS = {'standard': 'Redux', 'fast': 'Bolt'}
MODE_TEXT = {'standard': '', 'fast': 'Quicker, with a slightly different look. Use Redux for finals.'}
CHOOSE_MODE = 'Choose a mode: Redux or Bolt.'


def mode_label(mode):
    return MODE_LABELS.get(mode, MODE_LABELS['standard'])


def controls_doc(doc):
    """controls.describe() with the mode names people read (the engine keeps its own internal labels)."""
    out = dict(doc)
    out['modes'] = [dict(m, label=MODE_LABELS.get(m.get('key'), m.get('label')), text=MODE_TEXT.get(m.get('key'), m.get('text')))
                    for m in doc.get('modes') or []]
    return out
