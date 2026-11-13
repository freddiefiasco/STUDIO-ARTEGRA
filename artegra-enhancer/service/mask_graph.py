"""Mask graph implementation."""


from engine import graph_v5t

SAM_CLASSES = ('CheckpointLoaderSimple', 'LoadImage', 'CLIPTextEncode', 'SAM3_Detect', 'ClaudeMaskUnion', 'ClaudeProtectGate',
               'MaskToImage', 'SaveImage')


def build(input_name, terms, sam_settings, prefix, release_terms=()):
    if not terms:
        raise ValueError('at least one protect term is needed for a mask graph')
    return graph_v5t.build_gate_preview(input_name, list(terms), list(release_terms or []), sam_settings, prefix)
