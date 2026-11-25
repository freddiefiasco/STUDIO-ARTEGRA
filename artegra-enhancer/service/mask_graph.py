"""Mask graph implementation."""


from engine import graph_v5t, vram_model

SAM_CLASSES = ('CheckpointLoaderSimple', 'LoadImage', 'CLIPTextEncode', 'SAM3_Detect', 'ClaudeMaskUnion', 'ClaudeProtectGate',
               'MaskToImage', 'SaveImage', graph_v5t.SAM_LEAN_CLASS)


def build(input_name, terms, sam_settings, prefix, release_terms=(), size=None, card_totals=None, profile='reference'):
    """The protected-area preview's graph. size: the source's (width, height); above planner.SAM_STOCK_MAX_MP it takes the
    lean SAM node (5.0.2), as a pass of that size would. card_totals: the totals (GiB) of the card(s) the preview runs on,
    under the engine's memory `profile`: on a card of 24 GB or less the lean node also runs wherever the stock step does not
    fit it (engine/vram_model.card_sam_lean; any card that needs it decides). None: the size alone decides."""
    if not terms:
        raise ValueError('at least one protect term is needed for a mask graph')
    lean = size is not None and any(vram_model.card_sam_lean(size[0], size[1], t, profile)
                                    for t in (card_totals or [None]))
    return graph_v5t.build_gate_preview(input_name, list(terms), list(release_terms or []), sam_settings, prefix, lean=lean)
