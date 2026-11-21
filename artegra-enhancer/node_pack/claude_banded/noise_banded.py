"""The Brownian cache of the Large-image engine's sampler path (engine design section 2.7; T5, gate G7).

dpmpp_2m_sde draws its noise from ComfyUI's BrownianTreeNoiseSampler, whose torchsde BrownianTree keeps an LRU cache of 45
latent-size increments (torchsde 0.2.6 BrownianInterval's default cache_size) on the CPU: 11.25 B per render pixel. Gate G7
(tools/gate_g7.py) compares the draws with the cache at 45 and at 8 over a 30-step karras schedule at three latent sizes;
only if they are bit-identical does a plan set brownian_cache 8 (engine/banded_plan.BROWNIAN_CAPPED, a later item).

ClaudeSpotTilesBanded's `brownian_cache` input (default 45: nothing is installed, the classic's behaviour) installs, for one
sampling run, a subclass of the stock sampler that caps each tree's cache right after the trees are made and before any draw
(the class-factory pattern of the classic noise prefetch, node_pack/claude_creative/noise.py:44-56). With noise_prefetch on,
the classic prefetch class is made on top of the capped class, so its first background draw already sees the cap. The stock
class is put back after the run. The classic noise class, the classic graph and every classic plan are unchanged."""
import logging

from . import _engine, PlaneRef, NotBuilt, _out, _progress, _RUN, _DIR, _classic_pack

DEFAULT_CACHE = 45              # torchsde 0.2.6's own cache_size: no change
PROVEN_TORCHSDE = ('0.2.6',)    # the torchsde G7 ran on (its internals are what cap_tree sets)


def cap_tree(tree, cache_size):
    """Cap one torchsde BrownianTree's increment cache at `cache_size` entries. Only before its first query."""
    try:
        iv = tree._interval
        cache = iv._increment_and_space_time_levy_area_cache
    except AttributeError as e:
        raise RuntimeError('this torchsde is not the one the Brownian cache cap was proven with') from e
    if len(cache):
        raise RuntimeError('the Brownian tree was queried before its cache could be capped')
    iv._cache_size = int(cache_size)
    iv._increment_and_space_time_levy_area_cache = type(cache)(max_size=int(cache_size))


def make_class(base, cache_size):
    """The stock BrownianTreeNoiseSampler (or a subclass of it) with every tree's cache capped."""
    class CappedBrownianTreeNoiseSampler(base):
        """The stock BrownianTreeNoiseSampler, with each Brownian tree's increment cache capped before its first draw."""
        _claude_brownian_cache = int(cache_size)

        def __init__(self, x, sigma_min, sigma_max, seed=None, transform=lambda x: x, cpu=False):
            super().__init__(x, sigma_min, sigma_max, seed=seed, transform=transform, cpu=cpu)
            for tree in self.tree.trees:
                cap_tree(tree, cache_size)

    return CappedBrownianTreeNoiseSampler


class Handle:
    def __init__(self, ks, base, cls, cache_size):
        self.ks, self.base, self.cls, self.cache_size = ks, base, cls, cache_size

    def uninstall(self):
        if self.ks.BrownianTreeNoiseSampler is self.cls:
            self.ks.BrownianTreeNoiseSampler = self.base
        return {'brownian_cache': self.cache_size}


class _PrefetchHandle:
    """The classic prefetch's Handle, with the cache size added to its statistics."""

    def __init__(self, inner, cache_size):
        self.inner, self.cache_size = inner, cache_size

    def uninstall(self):
        st = self.inner.uninstall()
        st['brownian_cache'] = self.cache_size
        return st


def classic_noise():
    import importlib
    return importlib.import_module(_classic_pack().__name__ + '.noise')


def install(sigmas, cache_size, prefetch=False):
    """Install the capped sampler (and the classic prefetch on top when `prefetch`) for one sampling run; returns a handle
    (call uninstall() in a finally block). cache_size 45 is refused here: the fork installs nothing then. Unlike the classic
    prefetch (a speed lever, skipped when another noise-sampler patch is active), the cap is a memory lever the plan counts,
    so a cap that cannot be installed stops the run."""
    import comfy.k_diffusion.sampling as ks
    import torchsde
    cache_size = int(cache_size)
    if cache_size == DEFAULT_CACHE or not 1 <= cache_size < DEFAULT_CACHE:
        raise ValueError(f'brownian_cache must be 1 to {DEFAULT_CACHE - 1} to install a cap (got {cache_size})')
    if getattr(torchsde, '__version__', None) not in PROVEN_TORCHSDE:
        raise RuntimeError(f'the Brownian cache cap was proven with torchsde {PROVEN_TORCHSDE[0]}; this engine has '
                           f'{getattr(torchsde, "__version__", "an unknown version")}')
    base = ks.BrownianTreeNoiseSampler
    if (getattr(base, '_claude_prefetch', False) or getattr(base, '_claude_brownian_cache', None) is not None
            or base.__module__ != ks.__name__ or base.__name__ != 'BrownianTreeNoiseSampler'):
        logging.info('ClaudeSpotTilesBanded brownian_cache: another noise sampler patch is active: %r', base)
        raise RuntimeError('the Brownian cache cap could not be installed: another noise sampler patch is active')
    capped = make_class(base, cache_size)
    if prefetch:
        nz = classic_noise()
        run = nz._Run(sigmas)
        cls = nz.make_class(capped, run)
        handle = _PrefetchHandle(nz.Handle(ks, base, cls, run), cache_size)
    else:
        cls = capped
        handle = Handle(ks, base, cls, cache_size)
    ks.BrownianTreeNoiseSampler = cls
    return handle
