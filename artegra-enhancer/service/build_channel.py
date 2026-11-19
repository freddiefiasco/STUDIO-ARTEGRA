"""The build channel (engine design section 3, gate G0g). 'release' in the source tree and in every packaged build; only a
developer build made by tools/make_dev_build.py says 'dev'.

A developer build, and only a developer build:
- accepts a job's `dev_force_engine: 'banded'`, which runs the Classic engine's own plan through the Large-image engine (the
  1:1 comparison Max's rule needs; never the default, never set by any setting or by the app itself);
- may admit Large-image plans up to DEV_PROVEN_MP for its own proof runs (the release figures stay
  engine/banded_plan.BANDED_PROVEN_MP).
A release build refuses a job that carries the field, at submit, in plain words."""
CHANNEL = 'release'
DEV_PROVEN_MP = None
DEV_SETTING_REFUSED = 'This developer setting is not available in this build.'
FORCE_VALUES = ('banded',)


def is_dev():
    return CHANNEL == 'dev'


def apply_dev_proven():
    """In a developer build with DEV_PROVEN_MP, admit the Large-image engine up to those sizes for this process."""
    if not is_dev() or not DEV_PROVEN_MP:
        return False
    from engine import banded_plan
    banded_plan.BANDED_PROVEN_MP.update({k: float(v) for k, v in DEV_PROVEN_MP.items() if k in banded_plan.BANDED_PROVEN_MP})
    return True
