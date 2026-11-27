# Windows and NVIDIA compatibility

Artegra Enhancer (Beta) targets native x64 Windows 10 22H2 (build 19045) and Windows 11 22H2
(build 22621) or newer. The installer and runtime setup check the OS and native
CPU architecture before installation. Windows 7/8, older Windows 10 releases,
Windows 11 21H2, 32-bit Windows, and Windows on ARM are outside this build's
support target. Windows Server remains unqualified for the desktop app.

The target follows the pinned CUDA 13.2 platform list. Qt 6.12 itself supports
Windows 10 from 1809 and Windows 11; it is the final Qt release supporting Windows
10. Python 3.13 also supports Windows 10. These upstream requirements establish a
compatibility basis, not proof that every installation works.
Sources: [CUDA 13.2 Windows requirements](https://docs.nvidia.com/cuda/archive/13.2.0/cuda-installation-guide-microsoft-windows/index.html),
[Qt 6.12 platforms](https://doc.qt.io/qt-6/supported-platforms.html),
[Python 3.13 on Windows](https://docs.python.org/3.13/using/windows.html).

Windows 10's ordinary support ended on 14 October 2025. Application compatibility
does not supply Windows security updates: maintain an eligible ESU enrollment or
use a supported Windows 11 release. See [Microsoft's Windows lifecycle](https://learn.microsoft.com/en-us/lifecycle/products/windows-10-home-and-pro)
and [current ESU options](https://www.microsoft.com/en-us/windows/extended-security-updates).

## Drivers and runtime

Use a current NVIDIA Studio driver from branch 595 or newer for the pinned
PyTorch 2.14.1 + CUDA 13.2 runtime. NVIDIA permits CUDA 13.x minor-version
compatibility on branch 580 or newer, but older branches may lack newer driver
features or PTX support. Driver checks reject versions below 580 and explain the
595 recommendation for 580–594; a passing version check alone does not certify
the GPU. Sources: [CUDA driver branches](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html)
and [minor-version compatibility limits](https://docs.nvidia.com/deploy/cuda-compatibility/latest/minor-version-compatibility.html).

The app uses its separate, pinned Python and PyTorch installation. A pre-existing
system Python, ComfyUI, or CUDA Toolkit does not need upgrading. Optional
SageAttention, xformers, and locally compiled kernels are not enabled. Never mix
third-party CUDA DLLs or packages into this runtime to resolve a startup error;
use Settings → Repair installation. Driver installation and Windows updates
remain user-controlled.

## Desktop GPU targets

| GPU | Typical dedicated VRAM | CUDA capability | Current qualification |
| --- | ---: | ---: | --- |
| RTX 5090 | 32 GB | 12.0 | Tested: Redux and Bolt reference checks on this GPU |
| RTX 5080 | 16 GB | 12.0 | Compatibility target; physical-card validation pending |
| RTX 4090 | 24 GB | 8.9 | Compatibility target; physical-card validation pending |
| RTX 4080 | 16 GB | 8.9 | Compatibility target; physical-card validation pending |
| RTX 3090 | 24 GB | 8.6 | Compatibility target; physical-card validation pending |
| RTX 3080 | 10 or 12 GB | 8.6 | Experimental small-memory target; physical-card validation pending |

Specifications: [NVIDIA GPU comparison](https://www.nvidia.com/en-us/geforce/graphics-cards/compare/)
and [CUDA compute capabilities](https://developer.nvidia.com/cuda/gpus).
Laptop variants have different memory and power limits. Auto selects Save GPU
memory when detected dedicated capacity is 24 GiB or less; larger or unknown
capacities retain the original recipe. Either recipe can be selected explicitly.
Multiple cards do not add
their VRAM together for one image. Restricting a 5090 to a smaller memory budget
tests an allocation policy; it cannot reproduce another card's kernels, driver
behavior, bandwidth, or performance. Under Windows WDDM, another process's allocation may also be paged or accounted for differently by CUDA. A separate pressure process therefore does not establish a hard per-process VRAM limit or certify a 10 GB card.

The actual pinned Windows PyTorch wheel reports `sm_75`, `sm_80`, `sm_86`,
`sm_90`, `sm_100`, and `sm_120`. Its native `sm_86` code covers Ampere;
NVIDIA's same-major, higher-minor binary compatibility rule provides a basis for
Ada 8.9 using compatible 8.x kernels. Native `sm_120` code covers these Blackwell
targets. A small FP16 CUDA operation passed on the actual RTX 5090. This checks
the installed runtime, not every operator or GPU in the table.
[NVIDIA's binary compatibility rule](https://docs.nvidia.com/cuda/ampere-compatibility-guide/index.html).

## Memory strategy

The initial Minimum candidate completed but failed visual quality review. It
changed several tile sizes and numerical options together; the exact cause was
not isolated. Those transformations remain excluded.

**Save GPU memory** (internally Balanced) retains 1024-pixel diffusion tiles,
1024-pixel VAE tiles, 512-pixel upscaler tiles, the original weights and all
numerical options. It changes window batching from two to one, requests low-VRAM
model loading and reserves 1 GiB for other GPU use. **Original settings** retains
the original graph and launch flags. Auto selects between these as described above.
Changing the choice requires an idle engine and restarts affected warm workers.

Selected Redux and Bolt outputs passed visual review. Differences from the
original recipe remain, so this is not a pixel-identity claim. CPU offload moves
model work to system RAM and incurs transfer time; it can make processing slower.
Full-image preparation, preview and model weights still need memory.

Controlled checks use a native PyTorch allocator limit plus matching engine
headroom, rather than a separate GPU-pressure process. Redux passed 14 GiB and 8 GiB
allocator limits, and Bolt passed an 8 GiB limit at 768 by 768 input and 1536 by
1536 output. These checks constrain the caching allocator on RTX 5090; other
CUDA allocations, driver overhead and physical-card behaviour are separate.
The QA limit is not installed as a hidden production setting. See
[PyTorch's allocator limit](https://docs.pytorch.org/docs/2.14/generated/torch.cuda.memory.set_per_process_memory_fraction.html)
and [the measured validation report](VALIDATION.md).

Artegra Enhancer needs 32 GB of system memory or more (31 GB as Windows reports
it). Before each image it checks the memory the image needs against the budget
it may use: 29.2 GB on a 32 GB PC, so a 32 GB PC makes small upscales only, such
as Redux 2× of a 1920 × 1080 image. A larger pagefile does not raise the budget
or replace dedicated GPU memory.

Leave the Windows pagefile system-managed on a drive with sufficient free space.
Observe both available physical RAM and Task Manager's **Committed** usage. The
pagefile expands the commit limit and can prevent allocation failures, but heavy
paging can make a render extremely slow. The app reads available memory and
commit headroom; it does not resize the pagefile or change Windows settings.
[Microsoft explains pagefiles and commit limits](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file).

The process commitment limit and resident RAM are different: selected constrained
renders used roughly 28–30.5 GiB of commitment and 16–19 GiB resident memory.
A bounded, single-image spillover option could use existing pagefile headroom,
but it would also need coordinated worker limits, live headroom checks and
separate validation on a 32 GB machine. It is not enabled in this release.

Quantized weights are not silently substituted. They require a separately
verified checkpoint, compatible operators on each target architecture, publisher
terms, and output-quality comparisons. A smaller quantized model can save weight
memory but does not eliminate activation, preprocessing, or CPU-RAM requirements.
This build retains the known model files and makes its memory tradeoffs explicit.

## Installation and troubleshooting

- Use the Windows installer and keep its recommended location. It installs for
  your Windows account and prepares the required software and models automatically.
  Settings, outputs and enhancement files stay separate from the app. No terminal
  commands, engine extraction folder or separate Microsoft runtime installation
  are part of normal setup.
- If you choose another drive for the AI files, prefer a local SSD and a short
  folder path. Spaces and Unicode paths are supported; deeply nested paths may
  still reach the Windows path limit. The default location avoids unnecessary
  nesting. See [Python's long-path guidance](https://docs.python.org/3.13/using/windows.html#removing-the-max-path-limitation).
- For missing or damaged installation files, use **Settings → Repair installation**.
  Do not download individual DLLs or copy software into the app's folders.
  If repair cannot finish, save support details from the same Settings panel.
- On an out-of-memory error, close other GPU workloads, reduce the input size,
  use 2× output first, and check physical RAM and commit headroom. The app keeps
  failures visible; it does not silently discard output quality or resize input.
- Use **Settings → Save support details** for installation or driver failures.
  Testing on Windows 11 and RTX 5090 does not certify Windows 10 or every target
  GPU; actual tested scope is recorded in [VALIDATION.md](VALIDATION.md).
