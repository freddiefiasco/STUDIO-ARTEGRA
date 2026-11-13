"""Run order implementation."""


OUTPUT = frozenset({'SaveImage'})


def _is_link(v):
    """comfy_execution/graph_utils.is_link, as written there."""
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], (int, float))


def order(graph, cached=()):
    """Node ids in the order ComfyUI 0.42.4 would execute them (every SaveImage is an output to execute)."""
    cached = set(cached)
    pending, block_count, blocking = {}, {}, {}

    def add_strong_link(a, sock, b):
        if a not in cached:
            add_node(a)
            if b not in blocking[a]:
                blocking[a][b] = {}
                block_count[b] += 1
            blocking[a][b][sock] = True

    def add_node(start):
        ids, links = [start], []
        while ids:
            u = ids.pop()
            if u in pending:
                continue
            pending[u] = True
            block_count[u] = 0
            blocking[u] = {}
            for v in graph[u]['inputs'].values():
                if _is_link(v):
                    if v[0] not in cached:
                        ids.append(v[0])
                    links.append((v[0], v[1], u))
        for link in links:
            add_strong_link(*link)

    for k, v in graph.items():
        if v['class_type'] in OUTPUT:
            add_node(k)

    def is_out(n):
        return graph[n]['class_type'] in OUTPUT

    out = []
    while pending:
        ready = [n for n in pending if block_count[n] == 0]
        if not ready:
            raise ValueError('the graph has a dependency cycle')
        pick = next((n for n in ready if is_out(n)), None)
        if pick is None:
            pick = next((n for n in ready if any(is_out(b) for b in blocking[n])), None)
        if pick is None:
            pick = next((n for n in ready if any(is_out(b1) for b in blocking[n] for b1 in blocking[b])), None)
        if pick is None:
            pick = ready[0]
        out.append(pick)
        del pending[pick]
        for b in blocking[pick]:
            block_count[b] -= 1
        del blocking[pick]
    return out


def sampler_order(graph, cached=()):
    """The KSampler node ids in the order they run."""
    return [n for n in order(graph, cached) if graph[n]['class_type'] == 'KSampler']


def pass_order(graph, samplers, cached=()):
    """The pass names of a stage graph ({'structure': id, 'detail': id}, graph_v5t's info['samplers']) in run order."""
    by_id = {str(v): k for k, v in (samplers or {}).items()}
    return [by_id[n] for n in sampler_order(graph, cached) if n in by_id]
