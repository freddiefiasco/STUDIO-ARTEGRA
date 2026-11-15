# Windows and NVIDIA compatibility

This alpha targets native x64 Windows 10 22H2 (build 19045) and Windows 11 22H2
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
use the supplied setup into a new folder. Driver installation and Windows updates
remain user-controlled.

## Desktop GPU targets

| GPU | Typical dedicated VRAM | CUDA capability | Current qualification |
| --- | ---: | ---: | --- |
| RTX 5090 | 32 GB | 12.0 | Actual Standard/Fast reference checks on this GPU |
| RTX 5080 | 16 GB | 12.0 | Compatibility target; physical-card validation pending |
| RTX 4090 | 24 GB | 8.9 | Compatibility target; physical-card validation pending |
| RTX 4080 | 16 GB | 8.9 | Compatibility target; physical-card validation pending |
| RTX 3090 | 24 GB | 8.6 | Compatibility target; physical-card validation pending |
| RTX 3080 | 10 or 12 GB | 8.6 | Experimental small-memory target; physical-card validation pending |

Specifications: [NVIDIA GPU comparison](https://www.nvidia.com/en-us/geforce/graphics-cards/compare/)
and [CUDA compute capabilities](https://developer.nvidia.com/cuda/gpus).
Laptop variants have different memory and power limits. Diagnostics report detected
dedicated memory; this release retains the reference recipe on every card. Multiple cards do not add
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

The initial Minimum candidate completed but failed visual quality review on the test crop. Automatic deployment of unqualified profiles is withheld. A separately prepared conservative candidate preserves original tiles and numerical settings; it has not yet passed image verification.

The following describes the investigated strategy, not a qualification of every target card.

The investigated candidate used smaller refinement tiles and single-tile batches,
with low-VRAM loading and aggressive model offload. That candidate is excluded
from this release after its visual failure. The released path retains the
original reference tiles and loading policy on every card. Smaller tiles can alter output pixels
and seam behavior; they are a compatibility tradeoff, not a claim of reference
pixel identity. CPU offload moves inactive weights to system RAM and incurs PCIe
transfer time. Preview, full-image preprocessing, and model weights still need
memory even when the refinement tiles are small.

Allow generous physical RAM: 64 GB is the recommended starting point for this
model stack. The planner retains its conservative available-RAM admission checks;
32 GB physical-RAM systems are currently refused for ordinary renders: the planner baseline exceeds their default application budget. A pagefile does not
satisfy that physical-RAM check or replace dedicated GPU memory.

Leave the Windows pagefile system-managed on a drive with sufficient free space.
Observe both available physical RAM and Task Manager's **Committed** usage. The
pagefile expands the commit limit and can prevent allocation failures, but heavy
paging can make a render extremely slow. The app reads available memory and
commit headroom; it does not resize the pagefile or change Windows settings.
[Microsoft explains pagefiles and commit limits](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file).

Quantized weights are not silently substituted. They require a separately
verified checkpoint, compatible operators on each target architecture, publisher
terms, and output-quality comparisons. A smaller quantized model can save weight
memory but does not eliminate activation, preprocessing, or CPU-RAM requirements.
This build retains the known model files and makes its memory tradeoffs explicit.

## Installation and troubleshooting

- Install per user or extract the portable ZIP to a writable folder. Settings,
  output, models, and the engine runtime are separate from the application files.
- Use a short local runtime path, especially where Windows long paths are disabled.
  Spaces and Unicode paths are supported; deeply nested package paths may still
  reach the Windows path limit. See [Python's long-path guidance](https://docs.python.org/3.13/using/windows.html#removing-the-max-path-limitation).
- If startup reports a missing Microsoft runtime DLL, install the official
  [Visual C++ x64 Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
  and retry. Avoid downloading individual DLLs from third parties.
- On an out-of-memory error, close other GPU workloads, reduce the input size,
  use 2× output first, and check physical RAM and commit headroom. The app keeps
  failures visible; it does not silently discard output quality or resize input.
- Capture the app's redacted diagnostic bundle for installation or driver failures.
  Testing on Windows 11 and RTX 5090 does not certify Windows 10 or every target
  GPU; actual tested scope is recorded in [VALIDATION.md](VALIDATION.md).
