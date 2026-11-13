# Runtime dependency notices

The image-engine runtime is installed separately at the user’s explicit request. Its Python distribution and wheels retain their own licence files. The copies here cover the exact pinned reference versions; `license-inventory.json` records each notice hash and its origin. No model weights or model licences are included in this list.

- CPython 3.13.14: [Python licence](licenses/python/LICENSE.txt).
- ComfyUI source and bundled patch: [GNU GPL v3](licenses/comfyui/LICENSE).

Some workflow-template split wheels omit a notice file. Their declared MIT licence is supplied using the matched parent distribution’s Comfy Org notice. Source notices for packages that omit licence files are taken from the pinned upstream release; trampoline uses the upstream licence revision identified in the inventory.

| Distribution | Version | Licence notice |
| --- | --- | --- |
| aiohappyeyeballs | 2.7.1 | [Python Software Foundation License](licenses/aiohappyeyeballs/licenses/LICENSE) |
| aiohttp | 3.14.5 | [Apache-2.0 AND MIT](licenses/aiohttp/licenses/LICENSE.txt) |
| aiosignal | 1.4.0 | [Apache Software License](licenses/aiosignal/licenses/LICENSE) |
| alembic | 1.20.0 | [MIT](licenses/alembic/licenses/LICENSE) |
| annotated-doc | 0.0.5 | [MIT](licenses/annotated-doc/licenses/LICENSE) |
| annotated-types | 0.8.0 | [MIT](licenses/annotated-types/licenses/LICENSE) |
| anyio | 4.15.1 | [MIT](licenses/anyio/licenses/LICENSE) |
| attrs | 26.1.0 | [MIT](licenses/attrs/licenses/LICENSE) |
| av | 18.1.0 | [BSD-3-Clause](licenses/av/licenses/AUTHORS.py) |
| blake3 | 1.0.11 | [CC0-1.0 OR Apache-2.0](licenses/blake3/licenses/LICENSE) |
| certifi | 2026.7.22 | [Mozilla Public License 2.0 (MPL 2.0)](licenses/certifi/licenses/LICENSE) |
| charset-normalizer | 3.5.2 | [MIT](licenses/charset-normalizer/licenses/LICENSE) |
| click | 8.5.0 | [BSD-3-Clause](licenses/click/licenses/LICENSE.txt) |
| colorama | 0.4.6 | [BSD License](licenses/colorama/licenses/LICENSE.txt) |
| comfy-aimdo | 0.5.6 | [See bundled license files](licenses/comfy-aimdo/licenses/LICENSE) |
| comfy-angle | 0.1.1 | [BSD-3-Clause](licenses/comfy-angle/comfy_angle/electron-LICENSE) |
| comfy-kitchen | 0.2.39 | [Apache Software License](licenses/comfy-kitchen/licenses/LICENSE) |
| comfyui-embedded-docs | 0.5.14 | [GPL-3.0](licenses/comfyui-embedded-docs/licenses/LICENSE) |
| comfyui-frontend-package | 1.55.18 | [GPL-3.0](licenses/comfyui-frontend-package/LICENSE) |
| comfyui-workflow-templates | 0.11.94 | [MIT](licenses/comfyui-workflow-templates/licenses/LICENSE) |
| comfyui-workflow-templates-core | 0.3.385 | [MIT](licenses/comfyui-workflow-templates-core/LICENSE) |
| comfyui-workflow-templates-json | 0.1.120 | [MIT](licenses/comfyui-workflow-templates-json/LICENSE) |
| comfyui-workflow-templates-media-api | 0.3.84 | [MIT](licenses/comfyui-workflow-templates-media-api/LICENSE) |
| comfyui-workflow-templates-media-assets-01 | 0.1.48 | [MIT](licenses/comfyui-workflow-templates-media-assets-01/LICENSE) |
| comfyui-workflow-templates-media-assets-02 | 0.1.21 | [MIT](licenses/comfyui-workflow-templates-media-assets-02/LICENSE) |
| comfyui-workflow-templates-media-image | 0.3.160 | [MIT](licenses/comfyui-workflow-templates-media-image/LICENSE) |
| comfyui-workflow-templates-media-other | 0.3.229 | [MIT](licenses/comfyui-workflow-templates-media-other/LICENSE) |
| comfyui-workflow-templates-media-video | 0.3.101 | [MIT](licenses/comfyui-workflow-templates-media-video/LICENSE) |
| einops | 0.8.2 | [MIT License](licenses/einops/licenses/LICENSE) |
| filelock | 3.32.7 | [MIT](licenses/filelock/licenses/LICENSE) |
| frozenlist | 1.8.0 | [Apache-2.0](licenses/frozenlist/licenses/LICENSE) |
| fsspec | 2026.9.0 | [BSD-3-Clause](licenses/fsspec/licenses/LICENSE) |
| greenlet | 3.5.6 | [MIT AND PSF-2.0](licenses/greenlet/licenses/LICENSE) |
| h11 | 0.16.0 | [MIT License](licenses/h11/licenses/LICENSE.txt) |
| hf-xet | 1.7.0 | [Apache-2.0](licenses/hf-xet/licenses/LICENSE) |
| httpcore | 1.0.9 | [BSD-3-Clause](licenses/httpcore/licenses/LICENSE.md) |
| httpx | 0.28.1 | [BSD License](licenses/httpx/licenses/LICENSE.md) |
| huggingface-hub | 1.33.0 | [Apache Software License](licenses/huggingface-hub/licenses/LICENSE) |
| idna | 3.20 | [BSD-3-Clause](licenses/idna/licenses/LICENSE.md) |
| jinja2 | 3.1.6 | [BSD License](licenses/jinja2/licenses/LICENSE.txt) |
| kornia | 0.8.3 | [Apache Software License](licenses/kornia/licenses/LICENSE) |
| kornia-rs | 0.2.0 | [Apache Software License](licenses/kornia-rs/licenses/LICENSE) |
| mako | 1.4.3 | [MIT](licenses/mako/licenses/LICENSE) |
| markdown-it-py | 4.2.0 | [MIT License](licenses/markdown-it-py/licenses/LICENSE) |
| markupsafe | 3.0.4 | [BSD-3-Clause](licenses/markupsafe/licenses/LICENSE.txt) |
| mdurl | 0.1.2 | [MIT License](licenses/mdurl/LICENSE) |
| mpmath | 1.3.0 | [BSD License](licenses/mpmath/LICENSE) |
| multidict | 6.9.1 | [Apache License 2.0](licenses/multidict/licenses/LICENSE) |
| networkx | 3.7 | [BSD-3-Clause](licenses/networkx/licenses/LICENSE.txt) |
| numpy | 2.5.4 | [BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0](licenses/numpy/licenses/LICENSE.txt) |
| packaging | 26.3 | [Apache-2.0 OR BSD-2-Clause](licenses/packaging/licenses/LICENSE) |
| pillow | 12.3.0 | [MIT-CMU](licenses/pillow/licenses/LICENSE) |
| pip | 26.2.2 | [MIT](licenses/pip/licenses/AUTHORS.txt) |
| propcache | 0.5.4 | [Apache-2.0](licenses/propcache/licenses/LICENSE) |
| psutil | 7.2.2 | [BSD-3-Clause](licenses/psutil/LICENSE) |
| pydantic | 2.14.1 | [MIT](licenses/pydantic/licenses/LICENSE) |
| pydantic-core | 2.50.1 | [MIT](licenses/pydantic-core/licenses/LICENSE) |
| pydantic-settings | 2.16.0 | [MIT](licenses/pydantic-settings/licenses/LICENSE) |
| pygments | 2.21.0 | [BSD-2-Clause](licenses/pygments/licenses/AUTHORS) |
| pyopengl | 3.1.10 | [BSD License](licenses/pyopengl/OpenGL/DLLS/freeglut_COPYING.txt) |
| python-dotenv | 1.2.4 | [BSD-3-Clause](licenses/python-dotenv/licenses/LICENSE) |
| pyyaml | 6.0.3 | [MIT License](licenses/pyyaml/licenses/LICENSE) |
| regex | 2026.9.29 | [Apache-2.0 AND CNRI-Python](licenses/regex/licenses/LICENSE.txt) |
| requests | 2.34.2 | [Apache Software License](licenses/requests/licenses/LICENSE) |
| rich | 15.0.0 | [MIT License](licenses/rich/licenses/LICENSE) |
| safetensors | 0.8.0 | [Apache Software License](licenses/safetensors/licenses/LICENSE) |
| scipy | 1.18.1 | [BSD License](licenses/scipy/LICENSE.txt) |
| sentencepiece | 0.2.2 | [Apache-2.0](licenses/sentencepiece/LICENSE) |
| setuptools | 84.0.0 | [MIT](licenses/setuptools/licenses/LICENSE) |
| shellingham | 1.5.4 | [ISC License (ISCL)](licenses/shellingham/LICENSE) |
| simpleeval | 1.0.8 | [MIT License](licenses/simpleeval/licenses/LICENCE) |
| spandrel | 0.4.2 | [MIT](licenses/spandrel/LICENSE) |
| sqlalchemy | 2.0.54 | [MIT](licenses/sqlalchemy/licenses/AUTHORS) |
| sympy | 1.14.0 | [BSD License](licenses/sympy/licenses/AUTHORS) |
| tokenizers | 0.23.3 | [Apache-2.0](licenses/tokenizers/LICENSE) |
| torch | 2.14.1+cu132 | [Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT](licenses/torch/licenses/LICENSE) |
| torchsde | 0.2.6 | [Apache Software License](licenses/torchsde/LICENSE) |
| torchvision | 0.29.1+cu132 | [BSD](licenses/torchvision/LICENSE) |
| tqdm | 4.70.1 | [MPL-2.0 AND MIT](licenses/tqdm/licenses/LICENCE) |
| trampoline | 0.1.2 | [MIT](licenses/trampoline/LICENSE) |
| transformers | 5.19.0 | [Apache 2.0 License](licenses/transformers/licenses/LICENSE) |
| typer | 0.27.3 | [MIT](licenses/typer/licenses/LICENSE) |
| typing-extensions | 4.16.0 | [PSF-2.0](licenses/typing-extensions/licenses/LICENSE) |
| typing-inspection | 0.4.4 | [MIT](licenses/typing-inspection/licenses/LICENSE) |
| urllib3 | 2.8.0 | [MIT](licenses/urllib3/licenses/LICENSE.txt) |
| yarl | 1.25.1 | [Apache-2.0](licenses/yarl/licenses/LICENSE) |
