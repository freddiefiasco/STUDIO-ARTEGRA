"""Mask graph implementation."""


from engine import graph_v5t, planner

SAM_CLASSES = ('CheckpointLoaderSimple', 'LoadImage', 'CLIPTextEncode', 'SAM3_Detect', 'ClaudeMaskUnion', 'ClaudeProtectGate',
               'MaskToImage', 'SaveImage', graph_v5t.SAM_LEAN_CLASS)


def build(input_name, terms, sam_settings, prefix, release_terms=(), size=None):
    """The protected-area preview's graph. size: the source's (width, height); above planner.SAM_STOCK_MAX_MP it takes the
    lean SAM node (5.0.2), as a pass of that size would."""
    if not terms:
        raise ValueError('at least one protect term is needed for a mask graph')
    lean = size is not None and planner.sam_lean(*size)
    return graph_v5t.build_gate_preview(input_name, list(terms), list(release_terms or []), sam_settings, prefix, lean=lean)
