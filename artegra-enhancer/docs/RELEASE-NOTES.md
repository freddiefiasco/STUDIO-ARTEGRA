# Artegra Enhancer 0.1.0-alpha.3

Adds a conservative **Save GPU memory** option to the standalone v5 Creative Upscaler, with Standard and Fast modes.

**Auto** selects memory saving on cards with 24 GB or less. **Original settings** preserves the original recipe, and either choice can be selected manually. Preferences persist; changes require an idle engine and restart affected warm workers safely.

Memory saving processes one tile window at a time and requests CPU model loading. Original tile sizes, model weights and numerical options are retained. Selected outputs passed visual review with small pixel differences. CPU offloading can be substantially slower when memory is tight. The earlier smaller-tile Minimum experiment remains excluded after its visual failure; no quantized replacements or weights are bundled.

The updated source passed 403 tests plus 33 subtests on a separate Windows node. Seven image submissions completed this polish pass. Standard and Fast passed visual review under an 8 GiB allocator budget, with whole-GPU peaks around 8.3 GiB. Standard matched its 14 GiB result exactly. Details are in the validation report. Testing an allocation budget on RTX 5090 does not certify a physical RTX 3080/3090, 4080/4090 or 5080.

Targets native x64 Windows 10 22H2 or Windows 11 22H2+. Physical verification remains Windows 11 and RTX 5090. 64 GB system RAM is recommended; ordinary renders on 32 GB systems are refused by the current conservative default budget. Pagefile, driver and Windows settings remain user-controlled.

Models download from publishers after acceptance of their terms. See the installation guide, compatibility matrix and validation report for measured scope and limits. This is an unsigned alpha; verify the published checksums and review output before delivery.
