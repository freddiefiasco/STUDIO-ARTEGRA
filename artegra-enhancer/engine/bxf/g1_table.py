"""The G1 classification tables (written by tools/gate_g1.py --write; do not edit by hand): one table per environment
(engine/bxf/g1.py ENV_KEYS), sizes and classifications only; the processor string is the only machine fact a table
carries. engine/bxf/g1.py applies a table only in the environment it records. TABLE is the first table, for
readers of the one-table form."""
import json

TABLES = json.loads(r'''
[
 {
  "about": "engine design 2.4 and bxf-chk-1: banded only where every production-class shape gave 0 differing values and no failing shape is at least as large as a clean one; covered only on the measured band geometry (domain)",
  "band_heights": [
   288,
   576,
   1152,
   2304
  ],
  "below_normal_priority": true,
  "environment": {
   "cpu_capability": "AVX512",
   "numpy": "2.2.6",
   "numpy_simd": [
    "AVX",
    "AVX2",
    "AVX512BITALG",
    "AVX512BW",
    "AVX512CD",
    "AVX512DQ",
    "AVX512F",
    "AVX512IFMA",
    "AVX512VBMI",
    "AVX512VBMI2",
    "AVX512VL",
    "AVX512VNNI",
    "AVX512VPOPCNTDQ",
    "AVX512_CLX",
    "AVX512_CNL",
    "AVX512_ICL",
    "AVX512_SKX",
    "F16C",
    "FMA3",
    "MMX",
    "POPCNT",
    "SSE",
    "SSE2",
    "SSE3",
    "SSE41",
    "SSE42",
    "SSSE3"
   ],
   "processor": "AMD64 Family 26 Model 8 Stepping 1, AuthenticAMD",
   "scipy": "1.16.3",
   "torch": "2.9.1+cpu"
  },
  "gate": "G1",
  "narrow_widths": [
   128,
   131,
   197,
   293,
   437,
   653,
   977,
   1459,
   2183,
   3271,
   4903,
   5600
  ],
  "ops": {
   "E2 tbb r=1": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 tbb r=24": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 tbb r=3": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 tbb r=64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 tbb r=8": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 uniform_filter size=129 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 uniform_filter size=129 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 uniform_filter size=17 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 uniform_filter size=17 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 uniform_filter size=3 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 uniform_filter size=3 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 uniform_filter size=49 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 uniform_filter size=49 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 uniform_filter size=7 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E2 uniform_filter size=7 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 g s=10.392304845413264": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 g s=128.9961239727768": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 g s=16.97056274847714": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 g s=193.49418595916518": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 g s=25.45584412271571": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 g s=48.98979485566356": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 g s=73.48469228349535": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 pool_mean f=12": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 pool_mean f=18": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 pool_mean f=2": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 pool_mean f=3": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 pool_mean f=32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 pool_mean f=4": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 pool_mean f=48": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 pool_mean f=6": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E3 pool_mean f=8": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E4 avg_pool2d of a mapped input": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E4 reflection_pad2d out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E4 upsample_bicubic2d out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E4 upsample_bilinear2d out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E4 zoom order=0 f64 out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E5 median": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E5 percentile q=0": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E5 percentile q=100": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E5 percentile q=35": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E5 percentile q=50": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E5 percentile q=75": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E5 percentile q=90": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E5 percentile q=98.5": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E5 percentile q=99.9": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E5 strided 4M sample": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E6 bincount bands": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E6",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E6 keep table": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E6",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E6 label out=mapped": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E6",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E9 torch pow 1/2.4 out=mapped channels-last": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E9 torch pow 2.4 out=mapped channels-last": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "E9 torch pow 2.4 out=mapped contiguous": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "G lab[...,1:] s=1.0": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "G lab[...,1:] s=2.0": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 8,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "arith f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=12": {
    "band_numel_min": 1664,
    "band_rows_min": 13,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        13
       ]
      ],
      "2304": [
       [
        128,
        13
       ]
      ],
      "288": [
       [
        128,
        13
       ]
      ],
      "576": [
       [
        128,
        13
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 12,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "binary_dilation it=2": {
    "band_numel_min": 384,
    "band_rows_min": 3,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        3
       ]
      ],
      "2304": [
       [
        128,
        3
       ]
      ],
      "288": [
       [
        128,
        3
       ]
      ],
      "576": [
       [
        128,
        3
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 2,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "binary_dilation it=3": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "binary_dilation it=4": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "binary_dilation it=40": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 40,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "binary_dilation it=5": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "binary_dilation it=6": {
    "band_numel_min": 896,
    "band_rows_min": 7,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        7
       ]
      ],
      "2304": [
       [
        128,
        7
       ]
      ],
      "288": [
       [
        128,
        7
       ]
      ],
      "576": [
       [
        128,
        7
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 6,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "binary_erosion it=2": {
    "band_numel_min": 384,
    "band_rows_min": 3,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        3
       ]
      ],
      "2304": [
       [
        128,
        3
       ]
      ],
      "288": [
       [
        128,
        3
       ]
      ],
      "576": [
       [
        128,
        3
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 2,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "binary_opening it=40": {
    "band_numel_min": 10368,
    "band_rows_min": 81,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        81
       ]
      ],
      "2304": [
       [
        128,
        81
       ]
      ],
      "288": [
       [
        128,
        81
       ]
      ],
      "576": [
       [
        128,
        81
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 80,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter chanview s=2.0": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 8,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter hwc (1,1,0)": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=0.8": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=1.0": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=1.5": {
    "band_numel_min": 896,
    "band_rows_min": 7,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        7
       ]
      ],
      "2304": [
       [
        128,
        7
       ]
      ],
      "288": [
       [
        128,
        7
       ]
      ],
      "576": [
       [
        128,
        7
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 6,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=12.0": {
    "band_numel_min": 6272,
    "band_rows_min": 49,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        49
       ]
      ],
      "2304": [
       [
        128,
        49
       ]
      ],
      "288": [
       [
        128,
        49
       ]
      ],
      "576": [
       [
        128,
        49
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 48,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=16.0": {
    "band_numel_min": 8320,
    "band_rows_min": 65,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        65
       ]
      ],
      "2304": [
       [
        128,
        65
       ]
      ],
      "288": [
       [
        128,
        65
       ]
      ],
      "576": [
       [
        128,
        65
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 64,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=2.0": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 8,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=2.5": {
    "band_numel_min": 1408,
    "band_rows_min": 11,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        11
       ]
      ],
      "2304": [
       [
        128,
        11
       ]
      ],
      "288": [
       [
        128,
        11
       ]
      ],
      "576": [
       [
        128,
        11
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 10,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=2.8284271247461903": {
    "band_numel_min": 1536,
    "band_rows_min": 12,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        12
       ]
      ],
      "2304": [
       [
        128,
        12
       ]
      ],
      "288": [
       [
        128,
        12
       ]
      ],
      "576": [
       [
        128,
        12
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 11,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=3.0": {
    "band_numel_min": 1664,
    "band_rows_min": 13,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        13
       ]
      ],
      "2304": [
       [
        128,
        13
       ]
      ],
      "288": [
       [
        128,
        13
       ]
      ],
      "576": [
       [
        128,
        13
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 12,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=4.0": {
    "band_numel_min": 2176,
    "band_rows_min": 17,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        17
       ]
      ],
      "2304": [
       [
        128,
        17
       ]
      ],
      "288": [
       [
        128,
        17
       ]
      ],
      "576": [
       [
        128,
        17
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 16,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=4.242640687119286": {
    "band_numel_min": 2304,
    "band_rows_min": 18,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        18
       ]
      ],
      "2304": [
       [
        128,
        18
       ]
      ],
      "288": [
       [
        128,
        18
       ]
      ],
      "576": [
       [
        128,
        18
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 17,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=6.0": {
    "band_numel_min": 3200,
    "band_rows_min": 25,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        25
       ]
      ],
      "2304": [
       [
        128,
        25
       ]
      ],
      "288": [
       [
        128,
        25
       ]
      ],
      "576": [
       [
        128,
        25
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 24,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=6.928203230275509": {
    "band_numel_min": 3712,
    "band_rows_min": 29,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        29
       ]
      ],
      "2304": [
       [
        128,
        29
       ]
      ],
      "288": [
       [
        128,
        29
       ]
      ],
      "576": [
       [
        128,
        29
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 28,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "gaussian_filter s=8.0": {
    "band_numel_min": 4224,
    "band_rows_min": 33,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        33
       ]
      ],
      "2304": [
       [
        128,
        33
       ]
      ],
      "288": [
       [
        128,
        33
       ]
      ],
      "576": [
       [
        128,
        33
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 32,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "matmul 3x3 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter 11": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "maximum_filter 15": {
    "band_numel_min": 1024,
    "band_rows_min": 8,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        8
       ]
      ],
      "2304": [
       [
        128,
        8
       ]
      ],
      "288": [
       [
        128,
        8
       ]
      ],
      "576": [
       [
        128,
        8
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 7,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "maximum_filter 31": {
    "band_numel_min": 2048,
    "band_rows_min": 16,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        16
       ]
      ],
      "2304": [
       [
        128,
        16
       ]
      ],
      "288": [
       [
        128,
        16
       ]
      ],
      "576": [
       [
        128,
        16
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 15,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "maximum_filter 7": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "maximum_filter chanview 11": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "minimum_filter 11": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "minimum_filter 15": {
    "band_numel_min": 1024,
    "band_rows_min": 8,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        8
       ]
      ],
      "2304": [
       [
        128,
        8
       ]
      ],
      "288": [
       [
        128,
        8
       ]
      ],
      "576": [
       [
        128,
        8
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 7,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "minimum_filter 31": {
    "band_numel_min": 2048,
    "band_rows_min": 16,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        16
       ]
      ],
      "2304": [
       [
        128,
        16
       ]
      ],
      "288": [
       [
        128,
        16
       ]
      ],
      "576": [
       [
        128,
        16
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 15,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "minimum_filter 7": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "np.gradient": {
    "band_numel_min": 256,
    "band_rows_min": 2,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        2
       ]
      ],
      "2304": [
       [
        128,
        2
       ]
      ],
      "288": [
       [
        128,
        2
       ]
      ],
      "576": [
       [
        128,
        2
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 1,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "np.hypot": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "pool binary_dilation n=2": {
    "band_numel_min": 4081583,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        7001,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 0,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 8,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     7001,
     14000
    ]
   },
   "pool binary_dilation n=4": {
    "band_numel_min": 4081583,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        7001,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 0,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 8,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     7001,
     14000
    ]
   },
   "pool gaussian_filter n=2": {
    "band_numel_min": 4081583,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        7001,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 0,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 8,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     7001,
     14000
    ]
   },
   "pool gaussian_filter n=4": {
    "band_numel_min": 4081583,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        7001,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 0,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 8,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     7001,
     14000
    ]
   },
   "pool gradient_mag n=2": {
    "band_numel_min": 4081583,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        7001,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 0,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 8,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     7001,
     14000
    ]
   },
   "pool gradient_mag n=4": {
    "band_numel_min": 4081583,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        7001,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 0,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 8,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     7001,
     14000
    ]
   },
   "pool maximum_filter n=2": {
    "band_numel_min": 4081583,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        7001,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 0,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 8,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     7001,
     14000
    ]
   },
   "pool maximum_filter n=4": {
    "band_numel_min": 4081583,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        7001,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 0,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 8,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     7001,
     14000
    ]
   },
   "reduce channels f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "shadow_toe_u8": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch _blur s=4.0 (_sep conv)": {
    "band_numel_min": 20517,
    "band_rows_min": 15,
    "cls": "E8",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 1075,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        593
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ],
      "2304": [
       [
        128,
        1169
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ],
      "288": [
       [
        128,
        161
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ],
      "576": [
       [
        128,
        305
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 52,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      40
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 52,
    "narrow_tested": 144,
    "reach": 14,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 1075,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "torch _blur s=6.0 (_sep conv)": {
    "band_numel_min": 21494,
    "band_rows_min": 22,
    "cls": "E8",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 1444,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        600
       ],
       [
        977,
        22
       ]
      ],
      "2304": [
       [
        128,
        1176
       ],
       [
        977,
        22
       ]
      ],
      "288": [
       [
        128,
        168
       ],
       [
        977,
        22
       ]
      ],
      "576": [
       [
        128,
        312
       ],
       [
        977,
        22
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 48,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      55
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 48,
    "narrow_tested": 144,
    "reach": 21,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 1444,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "torch _sep s=1.5 gradient": {
    "band_numel_min": 19584,
    "band_rows_min": 7,
    "cls": "E8",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 9768,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        585
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ],
      "2304": [
       [
        128,
        1161
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ],
      "288": [
       [
        128,
        153
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ],
      "576": [
       [
        128,
        297
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 68,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      120
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 68,
    "narrow_tested": 144,
    "reach": 6,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 9768,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "torch exact ops": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch exp f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch mean(1) of |r - x|": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch pow 1/2.4 channels-last": {
    "band_numel_min": 18816,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 265,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 450,
    "errors": 0,
    "failing_shapes": 239,
    "first_difference": {
     "T": 577,
     "W": 5600,
     "differing": [
      102
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": false,
    "narrow_differing": 131,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 450,
    "verdict": "whole",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch pow 2.4 channels-last": {
    "band_numel_min": 18816,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 575,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 855,
    "errors": 0,
    "failing_shapes": 239,
    "first_difference": {
     "T": 577,
     "W": 5600,
     "differing": [
      264
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": false,
    "narrow_differing": 131,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 855,
    "verdict": "whole",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc arctan2 chanview f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc arctan2 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc cbrt f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc cos sin f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc exp f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc exp toe f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc power 1/2.4 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc power 2.4 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc power 3 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc remainder degrees f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc sign f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc square sqrt f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc tanh f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.agreement": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 47,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 40,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 1,
    "tested": 179,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     32000
    ]
   },
   "v4.band_energy (1,6,4)": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 40,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "v4.chroma_hc2 warm": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 41,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 14000,
      "2304": 14000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 8,
    "rows": [
     577,
     583,
     723,
     867,
     1153,
     1159,
     1443,
     1731,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 3,
    "tested": 173,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     32000
    ]
   },
   "v4.chroma_mm": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 38,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 14000,
      "2304": 7001,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 40,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     1731,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 4,
    "tested": 170,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     32000
    ]
   },
   "v4.fin_post srcwarm": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 41,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 14000,
      "2304": 14000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 8,
    "rows": [
     577,
     583,
     723,
     867,
     1153,
     1159,
     1443,
     1731,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 3,
    "tested": 173,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     32000
    ]
   },
   "v4.hsv": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.lab2rgb": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 119,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 1,
    "tested": 251,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.locE k=0": {
    "band_numel_min": 1536,
    "band_rows_min": 12,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        12
       ]
      ],
      "2304": [
       [
        128,
        12
       ]
      ],
      "288": [
       [
        128,
        12
       ]
      ],
      "576": [
       [
        128,
        12
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 11,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "v4.locE k=1": {
    "band_numel_min": 3712,
    "band_rows_min": 29,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 48,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        29
       ]
      ],
      "2304": [
       [
        128,
        29
       ]
      ],
      "288": [
       [
        128,
        29
       ]
      ],
      "576": [
       [
        128,
        29
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 28,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 192,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "v4.luma": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.rgb2lab": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 119,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 1,
    "tested": 251,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.smooth01": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.to_u8": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.warm_gate": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 120,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     723,
     1153,
     1159,
     1443,
     2305,
     2311,
     2883,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 0,
    "tested": 252,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     11200,
     14000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   }
  },
  "process_counts": [
   1,
   2,
   4
  ]
 },
 {
  "about": "engine design 2.4 and bxf-chk-1: banded only where every production-class shape gave 0 differing values and no failing shape is at least as large as a clean one; covered only on the measured band geometry (domain)",
  "band_heights": [
   288,
   576,
   1152,
   2304
  ],
  "below_normal_priority": true,
  "environment": {
   "cpu_capability": "AVX512",
   "numpy": "2.5.4",
   "numpy_simd": [
    "AVX",
    "AVX2",
    "AVX512BF16",
    "AVX512BITALG",
    "AVX512BW",
    "AVX512CD",
    "AVX512DQ",
    "AVX512F",
    "AVX512IFMA",
    "AVX512VBMI",
    "AVX512VBMI2",
    "AVX512VL",
    "AVX512VNNI",
    "AVX512VPOPCNTDQ",
    "AVX512_CLX",
    "AVX512_CNL",
    "AVX512_ICL",
    "AVX512_SKX",
    "BMI",
    "BMI2",
    "CX16",
    "F16C",
    "FMA3",
    "GFNI",
    "LAHF",
    "LZCNT",
    "MMX",
    "MOVBE",
    "POPCNT",
    "SSE",
    "SSE2",
    "SSE3",
    "SSE41",
    "SSE42",
    "SSSE3",
    "VAES",
    "VPCLMULQDQ",
    "X86_V2",
    "X86_V3",
    "X86_V4"
   ],
   "processor": "AMD64 Family 26 Model 8 Stepping 1, AuthenticAMD",
   "scipy": "1.18.1",
   "torch": "2.14.1+cu132"
  },
  "gate": "G1",
  "narrow_widths": [
   128,
   131,
   197,
   293,
   437,
   653,
   977,
   1459,
   2183,
   3271,
   4903,
   5600
  ],
  "ops": {
   "E2 tbb r=1": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 tbb r=24": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 tbb r=3": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 tbb r=64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 tbb r=8": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=129 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=129 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=17 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=17 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=3 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=3 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=49 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=49 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=7 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=7 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=10.392304845413264": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=128.9961239727768": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=16.97056274847714": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=193.49418595916518": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=25.45584412271571": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=48.98979485566356": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=73.48469228349535": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=12": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=18": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=2": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=3": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=4": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=48": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=6": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=8": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E4 avg_pool2d of a mapped input": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E4 reflection_pad2d out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E4 upsample_bicubic2d out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E4 upsample_bilinear2d out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E4 zoom order=0 f64 out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 median": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=0": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=100": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=35": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=50": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=75": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=90": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=98.5": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=99.9": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 strided 4M sample": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E6 bincount bands": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E6",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E6 keep table": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E6",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E6 label out=mapped": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E6",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E9 torch pow 1/2.4 out=mapped channels-last": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E9 torch pow 2.4 out=mapped channels-last": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E9 torch pow 2.4 out=mapped contiguous": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "G lab[...,1:] s=1.0": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "G lab[...,1:] s=2.0": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 8,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "arith f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=12": {
    "band_numel_min": 1664,
    "band_rows_min": 13,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        13
       ]
      ],
      "2304": [
       [
        128,
        13
       ]
      ],
      "288": [
       [
        128,
        13
       ]
      ],
      "576": [
       [
        128,
        13
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 12,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=2": {
    "band_numel_min": 384,
    "band_rows_min": 3,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        3
       ]
      ],
      "2304": [
       [
        128,
        3
       ]
      ],
      "288": [
       [
        128,
        3
       ]
      ],
      "576": [
       [
        128,
        3
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 2,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=3": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=4": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=40": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 40,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=5": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=6": {
    "band_numel_min": 896,
    "band_rows_min": 7,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        7
       ]
      ],
      "2304": [
       [
        128,
        7
       ]
      ],
      "288": [
       [
        128,
        7
       ]
      ],
      "576": [
       [
        128,
        7
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 6,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_erosion it=2": {
    "band_numel_min": 384,
    "band_rows_min": 3,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        3
       ]
      ],
      "2304": [
       [
        128,
        3
       ]
      ],
      "288": [
       [
        128,
        3
       ]
      ],
      "576": [
       [
        128,
        3
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 2,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_opening it=40": {
    "band_numel_min": 10368,
    "band_rows_min": 81,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        81
       ]
      ],
      "2304": [
       [
        128,
        81
       ]
      ],
      "288": [
       [
        128,
        81
       ]
      ],
      "576": [
       [
        128,
        81
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 80,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter chanview s=2.0": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 8,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter hwc (1,1,0)": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=0.8": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=1.0": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=1.5": {
    "band_numel_min": 896,
    "band_rows_min": 7,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        7
       ]
      ],
      "2304": [
       [
        128,
        7
       ]
      ],
      "288": [
       [
        128,
        7
       ]
      ],
      "576": [
       [
        128,
        7
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 6,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=12.0": {
    "band_numel_min": 6272,
    "band_rows_min": 49,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        49
       ]
      ],
      "2304": [
       [
        128,
        49
       ]
      ],
      "288": [
       [
        128,
        49
       ]
      ],
      "576": [
       [
        128,
        49
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 48,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=16.0": {
    "band_numel_min": 8320,
    "band_rows_min": 65,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        65
       ]
      ],
      "2304": [
       [
        128,
        65
       ]
      ],
      "288": [
       [
        128,
        65
       ]
      ],
      "576": [
       [
        128,
        65
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 64,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=2.0": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 8,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=2.5": {
    "band_numel_min": 1408,
    "band_rows_min": 11,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        11
       ]
      ],
      "2304": [
       [
        128,
        11
       ]
      ],
      "288": [
       [
        128,
        11
       ]
      ],
      "576": [
       [
        128,
        11
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 10,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=2.8284271247461903": {
    "band_numel_min": 1536,
    "band_rows_min": 12,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        12
       ]
      ],
      "2304": [
       [
        128,
        12
       ]
      ],
      "288": [
       [
        128,
        12
       ]
      ],
      "576": [
       [
        128,
        12
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 11,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=3.0": {
    "band_numel_min": 1664,
    "band_rows_min": 13,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        13
       ]
      ],
      "2304": [
       [
        128,
        13
       ]
      ],
      "288": [
       [
        128,
        13
       ]
      ],
      "576": [
       [
        128,
        13
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 12,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=4.0": {
    "band_numel_min": 2176,
    "band_rows_min": 17,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        17
       ]
      ],
      "2304": [
       [
        128,
        17
       ]
      ],
      "288": [
       [
        128,
        17
       ]
      ],
      "576": [
       [
        128,
        17
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 16,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=4.242640687119286": {
    "band_numel_min": 2304,
    "band_rows_min": 18,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        18
       ]
      ],
      "2304": [
       [
        128,
        18
       ]
      ],
      "288": [
       [
        128,
        18
       ]
      ],
      "576": [
       [
        128,
        18
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 17,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=6.0": {
    "band_numel_min": 3200,
    "band_rows_min": 25,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        25
       ]
      ],
      "2304": [
       [
        128,
        25
       ]
      ],
      "288": [
       [
        128,
        25
       ]
      ],
      "576": [
       [
        128,
        25
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 24,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=6.928203230275509": {
    "band_numel_min": 3712,
    "band_rows_min": 29,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        29
       ]
      ],
      "2304": [
       [
        128,
        29
       ]
      ],
      "288": [
       [
        128,
        29
       ]
      ],
      "576": [
       [
        128,
        29
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 28,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=8.0": {
    "band_numel_min": 4224,
    "band_rows_min": 33,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        33
       ]
      ],
      "2304": [
       [
        128,
        33
       ]
      ],
      "288": [
       [
        128,
        33
       ]
      ],
      "576": [
       [
        128,
        33
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 32,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "matmul 3x3 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter 11": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter 15": {
    "band_numel_min": 1024,
    "band_rows_min": 8,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        8
       ]
      ],
      "2304": [
       [
        128,
        8
       ]
      ],
      "288": [
       [
        128,
        8
       ]
      ],
      "576": [
       [
        128,
        8
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 7,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter 31": {
    "band_numel_min": 2048,
    "band_rows_min": 16,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        16
       ]
      ],
      "2304": [
       [
        128,
        16
       ]
      ],
      "288": [
       [
        128,
        16
       ]
      ],
      "576": [
       [
        128,
        16
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 15,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter 7": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter chanview 11": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "minimum_filter 11": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "minimum_filter 15": {
    "band_numel_min": 1024,
    "band_rows_min": 8,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        8
       ]
      ],
      "2304": [
       [
        128,
        8
       ]
      ],
      "288": [
       [
        128,
        8
       ]
      ],
      "576": [
       [
        128,
        8
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 7,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "minimum_filter 31": {
    "band_numel_min": 2048,
    "band_rows_min": 16,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        16
       ]
      ],
      "2304": [
       [
        128,
        16
       ]
      ],
      "288": [
       [
        128,
        16
       ]
      ],
      "576": [
       [
        128,
        16
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 15,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "minimum_filter 7": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "np.gradient": {
    "band_numel_min": 256,
    "band_rows_min": 2,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        2
       ]
      ],
      "2304": [
       [
        128,
        2
       ]
      ],
      "288": [
       [
        128,
        2
       ]
      ],
      "576": [
       [
        128,
        2
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 1,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "np.hypot": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "pool binary_dilation n=2": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 56,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000
    ]
   },
   "pool binary_dilation n=4": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 56,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000
    ]
   },
   "pool gaussian_filter n=2": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 56,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000
    ]
   },
   "pool gaussian_filter n=4": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 56,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000
    ]
   },
   "pool gaussian_filter s=4.242640687119286 n=2": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 56,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000
    ]
   },
   "pool gaussian_filter s=4.242640687119286 n=4": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 56,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000
    ]
   },
   "pool gradient_mag n=2": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 56,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000
    ]
   },
   "pool gradient_mag n=4": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 56,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000
    ]
   },
   "pool maximum_filter n=2": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 56,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000
    ]
   },
   "pool maximum_filter n=4": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 8,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 14000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 56,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000
    ]
   },
   "reduce channels f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "shadow_toe_u8": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch _blur s=4.0 (_sep conv)": {
    "band_numel_min": 20517,
    "band_rows_min": 15,
    "cls": "E8",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 2477,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        593
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ],
      "2304": [
       [
        128,
        1169
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ],
      "288": [
       [
        128,
        161
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ],
      "576": [
       [
        128,
        305
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 52,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      111
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 52,
    "narrow_tested": 144,
    "reach": 14,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 2477,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch _blur s=6.0 (_sep conv)": {
    "band_numel_min": 21494,
    "band_rows_min": 22,
    "cls": "E8",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 2440,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        600
       ],
       [
        977,
        22
       ]
      ],
      "2304": [
       [
        128,
        1176
       ],
       [
        977,
        22
       ]
      ],
      "288": [
       [
        128,
        168
       ],
       [
        977,
        22
       ]
      ],
      "576": [
       [
        128,
        312
       ],
       [
        977,
        22
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 48,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      87
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 48,
    "narrow_tested": 144,
    "reach": 21,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 2440,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch _sep s=1.5 gradient": {
    "band_numel_min": 19584,
    "band_rows_min": 7,
    "cls": "E8",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 9835,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        585
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ],
      "2304": [
       [
        128,
        1161
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ],
      "288": [
       [
        128,
        153
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ],
      "576": [
       [
        128,
        297
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 68,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      122
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 68,
    "narrow_tested": 144,
    "reach": 6,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 9835,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch exact ops": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3680,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch exp f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch mean(1) of |r - x|": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch pow 1/2.4 channels-last": {
    "band_numel_min": 18816,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 265,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 450,
    "errors": 0,
    "failing_shapes": 247,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      1
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": false,
    "narrow_differing": 131,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 8,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 450,
    "verdict": "whole",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch pow 2.4 channels-last": {
    "band_numel_min": 18816,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 575,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 855,
    "errors": 0,
    "failing_shapes": 247,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      13
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": false,
    "narrow_differing": 131,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 8,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 855,
    "verdict": "whole",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc arctan2 chanview f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc arctan2 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc cbrt f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc cos sin f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc exp f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc exp toe f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc power 1/2.4 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc power 2.4 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc power 3 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc remainder degrees f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc sign f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc square sqrt f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc tanh f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.agreement": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 101,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 40,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3680,
     3912,
     4480,
     4609,
     4615,
     4704,
     4784,
     4872,
     5008,
     5392,
     5696,
     5763,
     6448,
     6680
    ],
    "skipped": 1,
    "target_differing": 0,
    "target_tested": 54,
    "tested": 233,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.band_energy (1,6,4)": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 40,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.chroma_hc2 warm": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 82,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 16800,
      "2304": 14000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 8,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     867,
     896,
     928,
     992,
     1032,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1416,
     1443,
     1496,
     1552,
     1600,
     1664,
     1731,
     1840,
     1936,
     2305,
     2311,
     2400,
     2480,
     2704,
     2883,
     3224,
     3392,
     3459,
     4376,
     4609,
     4615,
     4704,
     5763
    ],
    "skipped": 12,
    "target_differing": 0,
    "target_tested": 41,
    "tested": 214,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.chroma_mm": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 16800,
      "2304": 8000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 40,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     928,
     1024,
     1032,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1416,
     1443,
     1496,
     1552,
     1664,
     1731,
     2240,
     2305,
     2311,
     2400,
     2704,
     2883,
     3224,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 17,
    "target_differing": 0,
    "target_tested": 34,
    "tested": 204,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.fin_post srcwarm": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 82,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 16800,
      "2304": 14000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 8,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     867,
     896,
     928,
     992,
     1032,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1416,
     1443,
     1496,
     1552,
     1600,
     1664,
     1731,
     1840,
     1936,
     2305,
     2311,
     2400,
     2480,
     2704,
     2883,
     3224,
     3392,
     3459,
     4376,
     4609,
     4615,
     4704,
     5763
    ],
    "skipped": 12,
    "target_differing": 0,
    "target_tested": 41,
    "tested": 214,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.hsv": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3680,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.lab2rgb": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 173,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3680,
     3912,
     4480,
     4609,
     4615,
     4704,
     4784,
     4872,
     5008,
     5392,
     5696,
     5763,
     6448,
     6680
    ],
    "skipped": 1,
    "target_differing": 0,
    "target_tested": 54,
    "tested": 305,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.locE k=0": {
    "band_numel_min": 1536,
    "band_rows_min": 12,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        12
       ]
      ],
      "2304": [
       [
        128,
        12
       ]
      ],
      "288": [
       [
        128,
        12
       ]
      ],
      "576": [
       [
        128,
        12
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 11,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.locE k=1": {
    "band_numel_min": 3712,
    "band_rows_min": 29,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        29
       ]
      ],
      "2304": [
       [
        128,
        29
       ]
      ],
      "288": [
       [
        128,
        29
       ]
      ],
      "576": [
       [
        128,
        29
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 28,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.luma": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.rgb2lab": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 173,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3680,
     3912,
     4480,
     4609,
     4615,
     4704,
     4784,
     4872,
     5008,
     5392,
     5696,
     5763,
     6448,
     6680
    ],
    "skipped": 1,
    "target_differing": 0,
    "target_tested": 54,
    "tested": 305,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.smooth01": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.to_u8": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.warm_gate": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3680,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   }
  },
  "process_counts": [
   1,
   2,
   4
  ],
  "target_planes": [
   [
    5600,
    7008
   ],
   [
    7000,
    4376
   ],
   [
    8000,
    5008
   ],
   [
    8000,
    8000
   ],
   [
    11200,
    14000
   ],
   [
    14000,
    8752
   ],
   [
    16000,
    10000
   ],
   [
    16000,
    16000
   ],
   [
    16800,
    21000
   ],
   [
    21000,
    13128
   ],
   [
    22400,
    28000
   ],
   [
    28000,
    17504
   ],
   [
    32000,
    20000
   ],
   [
    32000,
    32000
   ]
  ]
 },
 {
  "about": "engine design 2.4 and bxf-chk-1: banded only where every production-class shape gave 0 differing values and no failing shape is at least as large as a clean one; covered only on the measured band geometry (domain)",
  "band_heights": [
   288,
   576,
   1152,
   2304
  ],
  "below_normal_priority": true,
  "environment": {
   "cpu_capability": "AVX512",
   "numpy": "2.5.4",
   "numpy_simd": [
    "AVX",
    "AVX2",
    "AVX512BF16",
    "AVX512BITALG",
    "AVX512BW",
    "AVX512CD",
    "AVX512DQ",
    "AVX512F",
    "AVX512IFMA",
    "AVX512VBMI",
    "AVX512VBMI2",
    "AVX512VL",
    "AVX512VNNI",
    "AVX512VPOPCNTDQ",
    "AVX512_CLX",
    "AVX512_CNL",
    "AVX512_ICL",
    "AVX512_SKX",
    "BMI",
    "BMI2",
    "CX16",
    "F16C",
    "FMA3",
    "GFNI",
    "LAHF",
    "LZCNT",
    "MMX",
    "MOVBE",
    "POPCNT",
    "SSE",
    "SSE2",
    "SSE3",
    "SSE41",
    "SSE42",
    "SSSE3",
    "VAES",
    "VPCLMULQDQ",
    "X86_V2",
    "X86_V3",
    "X86_V4"
   ],
   "processor": "AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD",
   "scipy": "1.18.1",
   "torch": "2.14.1+cu132"
  },
  "gate": "G1",
  "merge": {
   "disagreements": [],
   "rule": "banded only where both are; domain the intersection",
   "tables": 2
  },
  "narrow_widths": [
   128,
   131,
   197,
   293,
   437,
   653,
   977,
   1459,
   2183,
   3271,
   4903,
   5600
  ],
  "ops": {
   "E2 tbb r=1": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 tbb r=24": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 tbb r=3": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 tbb r=64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 tbb r=8": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=129 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=129 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=17 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=17 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=3 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=3 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=49 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=49 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=7 f32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E2 uniform_filter size=7 f64": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E2",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=10.392304845413264": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=128.9961239727768": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=16.97056274847714": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=193.49418595916518": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=25.45584412271571": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=48.98979485566356": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 g s=73.48469228349535": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=12": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=18": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=2": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=3": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=32": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=4": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=48": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=6": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E3 pool_mean f=8": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E3",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E4 avg_pool2d of a mapped input": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E4 reflection_pad2d out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E4 upsample_bicubic2d out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E4 upsample_bilinear2d out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E4 zoom order=0 f64 out=mapped": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E4",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 median": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=0": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=100": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=35": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=50": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=75": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=90": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=98.5": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 percentile q=99.9": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E5 strided 4M sample": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E5",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E6 bincount bands": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E6",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E6 keep table": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E6",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E6 label out=mapped": {
    "band_numel_min": 73856,
    "band_rows_min": 577,
    "cls": "E6",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        577
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E9 torch pow 1/2.4 out=mapped channels-last": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E9 torch pow 2.4 out=mapped channels-last": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "E9 torch pow 2.4 out=mapped contiguous": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "G lab[...,1:] s=1.0": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "G lab[...,1:] s=2.0": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 8,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "arith f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=12": {
    "band_numel_min": 1664,
    "band_rows_min": 13,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        13
       ]
      ],
      "2304": [
       [
        128,
        13
       ]
      ],
      "288": [
       [
        128,
        13
       ]
      ],
      "576": [
       [
        128,
        13
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 12,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=2": {
    "band_numel_min": 384,
    "band_rows_min": 3,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        3
       ]
      ],
      "2304": [
       [
        128,
        3
       ]
      ],
      "288": [
       [
        128,
        3
       ]
      ],
      "576": [
       [
        128,
        3
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 2,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=3": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=4": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=40": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 40,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=5": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_dilation it=6": {
    "band_numel_min": 896,
    "band_rows_min": 7,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        7
       ]
      ],
      "2304": [
       [
        128,
        7
       ]
      ],
      "288": [
       [
        128,
        7
       ]
      ],
      "576": [
       [
        128,
        7
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 6,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_erosion it=2": {
    "band_numel_min": 384,
    "band_rows_min": 3,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        3
       ]
      ],
      "2304": [
       [
        128,
        3
       ]
      ],
      "288": [
       [
        128,
        3
       ]
      ],
      "576": [
       [
        128,
        3
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 2,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "binary_opening it=40": {
    "band_numel_min": 10368,
    "band_rows_min": 81,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        81
       ]
      ],
      "2304": [
       [
        128,
        81
       ]
      ],
      "288": [
       [
        128,
        81
       ]
      ],
      "576": [
       [
        128,
        81
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 80,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter chanview s=2.0": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 8,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter hwc (1,1,0)": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=0.8": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=1.0": {
    "band_numel_min": 640,
    "band_rows_min": 5,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        5
       ]
      ],
      "2304": [
       [
        128,
        5
       ]
      ],
      "288": [
       [
        128,
        5
       ]
      ],
      "576": [
       [
        128,
        5
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 4,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=1.5": {
    "band_numel_min": 896,
    "band_rows_min": 7,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        7
       ]
      ],
      "2304": [
       [
        128,
        7
       ]
      ],
      "288": [
       [
        128,
        7
       ]
      ],
      "576": [
       [
        128,
        7
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 6,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=12.0": {
    "band_numel_min": 6272,
    "band_rows_min": 49,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        49
       ]
      ],
      "2304": [
       [
        128,
        49
       ]
      ],
      "288": [
       [
        128,
        49
       ]
      ],
      "576": [
       [
        128,
        49
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 48,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=16.0": {
    "band_numel_min": 8320,
    "band_rows_min": 65,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        65
       ]
      ],
      "2304": [
       [
        128,
        65
       ]
      ],
      "288": [
       [
        128,
        65
       ]
      ],
      "576": [
       [
        128,
        65
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 64,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=2.0": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 8,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=2.5": {
    "band_numel_min": 1408,
    "band_rows_min": 11,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        11
       ]
      ],
      "2304": [
       [
        128,
        11
       ]
      ],
      "288": [
       [
        128,
        11
       ]
      ],
      "576": [
       [
        128,
        11
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 10,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=2.8284271247461903": {
    "band_numel_min": 1536,
    "band_rows_min": 12,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        12
       ]
      ],
      "2304": [
       [
        128,
        12
       ]
      ],
      "288": [
       [
        128,
        12
       ]
      ],
      "576": [
       [
        128,
        12
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 11,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=3.0": {
    "band_numel_min": 1664,
    "band_rows_min": 13,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        13
       ]
      ],
      "2304": [
       [
        128,
        13
       ]
      ],
      "288": [
       [
        128,
        13
       ]
      ],
      "576": [
       [
        128,
        13
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 12,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=4.0": {
    "band_numel_min": 2176,
    "band_rows_min": 17,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        17
       ]
      ],
      "2304": [
       [
        128,
        17
       ]
      ],
      "288": [
       [
        128,
        17
       ]
      ],
      "576": [
       [
        128,
        17
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 16,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=4.242640687119286": {
    "band_numel_min": 2304,
    "band_rows_min": 18,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        18
       ]
      ],
      "2304": [
       [
        128,
        18
       ]
      ],
      "288": [
       [
        128,
        18
       ]
      ],
      "576": [
       [
        128,
        18
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 17,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=6.0": {
    "band_numel_min": 3200,
    "band_rows_min": 25,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        25
       ]
      ],
      "2304": [
       [
        128,
        25
       ]
      ],
      "288": [
       [
        128,
        25
       ]
      ],
      "576": [
       [
        128,
        25
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 24,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=6.928203230275509": {
    "band_numel_min": 3712,
    "band_rows_min": 29,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        29
       ]
      ],
      "2304": [
       [
        128,
        29
       ]
      ],
      "288": [
       [
        128,
        29
       ]
      ],
      "576": [
       [
        128,
        29
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 28,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "gaussian_filter s=8.0": {
    "band_numel_min": 4224,
    "band_rows_min": 33,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        33
       ]
      ],
      "2304": [
       [
        128,
        33
       ]
      ],
      "288": [
       [
        128,
        33
       ]
      ],
      "576": [
       [
        128,
        33
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 32,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "matmul 3x3 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter 11": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter 15": {
    "band_numel_min": 1024,
    "band_rows_min": 8,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        8
       ]
      ],
      "2304": [
       [
        128,
        8
       ]
      ],
      "288": [
       [
        128,
        8
       ]
      ],
      "576": [
       [
        128,
        8
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 7,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter 31": {
    "band_numel_min": 2048,
    "band_rows_min": 16,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        16
       ]
      ],
      "2304": [
       [
        128,
        16
       ]
      ],
      "288": [
       [
        128,
        16
       ]
      ],
      "576": [
       [
        128,
        16
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 15,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter 7": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "maximum_filter chanview 11": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "minimum_filter 11": {
    "band_numel_min": 768,
    "band_rows_min": 6,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        6
       ]
      ],
      "2304": [
       [
        128,
        6
       ]
      ],
      "288": [
       [
        128,
        6
       ]
      ],
      "576": [
       [
        128,
        6
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 5,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "minimum_filter 15": {
    "band_numel_min": 1024,
    "band_rows_min": 8,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        8
       ]
      ],
      "2304": [
       [
        128,
        8
       ]
      ],
      "288": [
       [
        128,
        8
       ]
      ],
      "576": [
       [
        128,
        8
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 7,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "minimum_filter 31": {
    "band_numel_min": 2048,
    "band_rows_min": 16,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        16
       ]
      ],
      "2304": [
       [
        128,
        16
       ]
      ],
      "288": [
       [
        128,
        16
       ]
      ],
      "576": [
       [
        128,
        16
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 15,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "minimum_filter 7": {
    "band_numel_min": 512,
    "band_rows_min": 4,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        4
       ]
      ],
      "2304": [
       [
        128,
        4
       ]
      ],
      "288": [
       [
        128,
        4
       ]
      ],
      "576": [
       [
        128,
        4
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 3,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "np.gradient": {
    "band_numel_min": 256,
    "band_rows_min": 2,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        2
       ]
      ],
      "2304": [
       [
        128,
        2
       ]
      ],
      "288": [
       [
        128,
        2
       ]
      ],
      "576": [
       [
        128,
        2
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 1,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "np.hypot": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "pool binary_dilation n=2": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "pool binary_dilation n=4": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "pool gaussian_filter n=2": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "pool gaussian_filter n=4": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "pool gaussian_filter s=4.242640687119286 n=2": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "pool gaussian_filter s=4.242640687119286 n=4": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "pool gradient_mag n=2": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "pool gradient_mag n=4": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     736,
     744,
     752,
     784,
     800,
     840,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 120,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "pool maximum_filter n=2": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "pool maximum_filter n=4": {
    "band_numel_min": 74624,
    "band_rows_min": 583,
    "cls": "pool",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 16,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "any": [
       [
        128,
        583
       ]
      ]
     },
     "key": "any",
     "w_max": {
      "any": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "custom",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 48,
    "reach": 0,
    "rows": [
     583,
     1159,
     2311,
     4615
    ],
    "skipped": 0,
    "tested": 64,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7001,
     14000,
     21000,
     32000
    ]
   },
   "reduce channels f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "shadow_toe_u8": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch _blur s=4.0 (_sep conv)": {
    "band_numel_min": 20517,
    "band_rows_min": 15,
    "cls": "E8",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 2477,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        593
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ],
      "2304": [
       [
        128,
        1169
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ],
      "288": [
       [
        128,
        161
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ],
      "576": [
       [
        128,
        305
       ],
       [
        977,
        21
       ],
       [
        1459,
        15
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 52,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      111
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 52,
    "narrow_tested": 144,
    "reach": 14,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 2477,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch _blur s=6.0 (_sep conv)": {
    "band_numel_min": 21494,
    "band_rows_min": 22,
    "cls": "E8",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 2440,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        600
       ],
       [
        977,
        22
       ]
      ],
      "2304": [
       [
        128,
        1176
       ],
       [
        977,
        22
       ]
      ],
      "288": [
       [
        128,
        168
       ],
       [
        977,
        22
       ]
      ],
      "576": [
       [
        128,
        312
       ],
       [
        977,
        22
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 48,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      87
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 48,
    "narrow_tested": 144,
    "reach": 21,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 2440,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch _sep s=1.5 gradient": {
    "band_numel_min": 19584,
    "band_rows_min": 7,
    "cls": "E8",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 9835,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        585
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ],
      "2304": [
       [
        128,
        1161
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ],
      "288": [
       [
        128,
        153
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ],
      "576": [
       [
        128,
        297
       ],
       [
        2183,
        13
       ],
       [
        3271,
        7
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 68,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      122
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 68,
    "narrow_tested": 144,
    "reach": 6,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 9835,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch exact ops": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3680,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch exp f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch mean(1) of |r - x|": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch pow 1/2.4 channels-last": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 130,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 237,
    "errors": 0,
    "failing_shapes": 230,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      1
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "whole",
     "whole"
    ],
    "monotone": false,
    "narrow_differing": 126,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 8,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 237,
    "verdict": "whole",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "torch pow 2.4 channels-last": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E9",
    "core_differing_max": 320,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 474,
    "errors": 0,
    "failing_shapes": 230,
    "first_difference": {
     "T": 577,
     "W": 128,
     "differing": [
      13
     ],
     "h": 288
    },
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "whole",
     "whole"
    ],
    "monotone": false,
    "narrow_differing": 126,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 8,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 474,
    "verdict": "whole",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc arctan2 chanview f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc arctan2 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc cbrt f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc cos sin f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc exp f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc exp toe f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc power 1/2.4 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc power 2.4 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc power 3 f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc remainder degrees f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc sign f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc square sqrt f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "ufunc tanh f32": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.agreement": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 101,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 40,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3680,
     3912,
     4480,
     4609,
     4615,
     4704,
     4784,
     4872,
     5008,
     5392,
     5696,
     5763,
     6448,
     6680
    ],
    "skipped": 1,
    "target_differing": 0,
    "target_tested": 54,
    "tested": 233,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.band_energy (1,6,4)": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 40,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.chroma_hc2 warm": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 82,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 16800,
      "2304": 14000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 8,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     867,
     896,
     928,
     992,
     1032,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1416,
     1443,
     1496,
     1552,
     1600,
     1664,
     1731,
     1840,
     1936,
     2305,
     2311,
     2400,
     2480,
     2704,
     2883,
     3224,
     3392,
     3459,
     4376,
     4609,
     4615,
     4704,
     5763
    ],
    "skipped": 12,
    "target_differing": 0,
    "target_tested": 41,
    "tested": 214,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.chroma_mm": {
    "band_numel_min": 5248,
    "band_rows_min": 41,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 72,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        41
       ]
      ],
      "2304": [
       [
        128,
        41
       ]
      ],
      "288": [
       [
        128,
        41
       ]
      ],
      "576": [
       [
        128,
        41
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 16800,
      "2304": 8000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 40,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     928,
     1024,
     1032,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1416,
     1443,
     1496,
     1552,
     1664,
     1731,
     2240,
     2305,
     2311,
     2400,
     2704,
     2883,
     3224,
     3459,
     4609,
     4615,
     5763
    ],
    "skipped": 17,
    "target_differing": 0,
    "target_tested": 34,
    "tested": 204,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.fin_post srcwarm": {
    "band_numel_min": 1152,
    "band_rows_min": 9,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 82,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        9
       ]
      ],
      "2304": [
       [
        128,
        9
       ]
      ],
      "288": [
       [
        128,
        9
       ]
      ],
      "576": [
       [
        128,
        9
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 16800,
      "2304": 14000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 8,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     867,
     896,
     928,
     992,
     1032,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1416,
     1443,
     1496,
     1552,
     1600,
     1664,
     1731,
     1840,
     1936,
     2305,
     2311,
     2400,
     2480,
     2704,
     2883,
     3224,
     3392,
     3459,
     4376,
     4609,
     4615,
     4704,
     5763
    ],
    "skipped": 12,
    "target_differing": 0,
    "target_tested": 41,
    "tested": 214,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.hsv": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3680,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.lab2rgb": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 173,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3680,
     3912,
     4480,
     4609,
     4615,
     4704,
     4784,
     4872,
     5008,
     5392,
     5696,
     5763,
     6448,
     6680
    ],
    "skipped": 1,
    "target_differing": 0,
    "target_tested": 54,
    "tested": 305,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.locE k=0": {
    "band_numel_min": 1536,
    "band_rows_min": 12,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        12
       ]
      ],
      "2304": [
       [
        128,
        12
       ]
      ],
      "288": [
       [
        128,
        12
       ]
      ],
      "576": [
       [
        128,
        12
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 11,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.locE k=1": {
    "band_numel_min": 3712,
    "band_rows_min": 29,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 104,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        29
       ]
      ],
      "2304": [
       [
        128,
        29
       ]
      ],
      "288": [
       [
        128,
        29
       ]
      ],
      "576": [
       [
        128,
        29
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 144,
    "reach": 28,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 248,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.luma": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.rgb2lab": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 173,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3680,
     3912,
     4480,
     4609,
     4615,
     4704,
     4784,
     4872,
     5008,
     5392,
     5696,
     5763,
     6448,
     6680
    ],
    "skipped": 1,
    "target_differing": 0,
    "target_tested": 54,
    "tested": 305,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.smooth01": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.to_u8": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     5984,
     6176,
     6216,
     6448,
     6656,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   },
   "v4.warm_gate": {
    "band_numel_min": 128,
    "band_rows_min": 1,
    "cls": "E1",
    "core_differing_max": 0,
    "core_heights": [
     288,
     576,
     1152,
     2304
    ],
    "core_tested": 176,
    "differing_max": 0,
    "domain": {
     "frontier": {
      "1152": [
       [
        128,
        1
       ]
      ],
      "2304": [
       [
        128,
        1
       ]
      ],
      "288": [
       [
        128,
        1
       ]
      ],
      "576": [
       [
        128,
        1
       ]
      ]
     },
     "key": "height",
     "w_max": {
      "1152": 32000,
      "2304": 32000,
      "288": 32000,
      "576": 32000
     }
    },
    "errors": 0,
    "failing_shapes": 0,
    "first_difference": null,
    "heights": [
     288,
     576,
     1152,
     2304
    ],
    "kind": "local",
    "merged_verdicts": [
     "banded",
     "banded"
    ],
    "monotone": true,
    "narrow_differing": 0,
    "narrow_tested": 132,
    "reach": 0,
    "rows": [
     577,
     583,
     608,
     632,
     640,
     672,
     688,
     704,
     723,
     736,
     744,
     752,
     784,
     800,
     840,
     1153,
     1159,
     1248,
     1264,
     1328,
     1360,
     1376,
     1416,
     1443,
     1472,
     1496,
     1504,
     1552,
     1568,
     1600,
     1608,
     1664,
     2305,
     2311,
     2400,
     2480,
     2528,
     2568,
     2656,
     2704,
     2720,
     2760,
     2883,
     2992,
     3088,
     3200,
     3224,
     3328,
     3392,
     3459,
     3680,
     3872,
     4352,
     4609,
     4615,
     4704,
     4784,
     4872,
     4960,
     5008,
     5392,
     5696,
     5763,
     6216,
     6448,
     6680,
     6784
    ],
    "skipped": 0,
    "target_differing": 0,
    "target_tested": 56,
    "tested": 308,
    "value_differing_max": 0,
    "verdict": "banded",
    "widths": [
     128,
     131,
     197,
     293,
     437,
     653,
     977,
     1459,
     2183,
     3271,
     4903,
     5600,
     7000,
     7001,
     8000,
     11200,
     14000,
     16000,
     16800,
     21000,
     22400,
     28000,
     32000
    ]
   }
  },
  "process_counts": [
   1,
   2,
   4
  ],
  "target_planes": [
   [
    5600,
    7008
   ],
   [
    7000,
    4376
   ],
   [
    8000,
    5008
   ],
   [
    8000,
    8000
   ],
   [
    11200,
    14000
   ],
   [
    14000,
    8752
   ],
   [
    16000,
    10000
   ],
   [
    16000,
    16000
   ],
   [
    16800,
    21000
   ],
   [
    21000,
    13128
   ],
   [
    22400,
    28000
   ],
   [
    28000,
    17504
   ],
   [
    32000,
    20000
   ],
   [
    32000,
    32000
   ]
  ]
 }
]
''')
TABLE = TABLES[0] if TABLES else None
