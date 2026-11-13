.pragma library

var controls = {
    "contract": "creative-upscaler-controls-v2",
    "presets": [
        {
            "name": "Light",
            "values": {
                "creativity": 10,
                "resemblance": 80,
                "restoration": 15
            },
            "text": "Adds fine detail; planting keeps its species."
        },
        {
            "name": "Default",
            "values": {
                "creativity": 50,
                "resemblance": 60,
                "restoration": 35
            },
            "text": "New detail; shapes and layout stay as they are."
        },
        {
            "name": "Strong",
            "values": {
                "creativity": 60,
                "resemblance": 56,
                "restoration": 45
            },
            "text": "Crisper materials; planting may be redrawn."
        },
        {
            "name": "Heavy",
            "values": {
                "creativity": 68,
                "resemblance": 53,
                "restoration": 55
            },
            "text": "More new detail; planting is often redrawn."
        },
        {
            "name": "Extreme",
            "values": {
                "creativity": 77,
                "resemblance": 48,
                "restoration": 65
            },
            "text": "Most new detail; check planting and fine shapes."
        }
    ],
    "sliders": [
        {
            "key": "creativity",
            "label": "Creativity",
            "low": "Faithful",
            "high": "Inventive",
            "text": "How much new detail is invented."
        },
        {
            "key": "resemblance",
            "label": "Resemblance",
            "low": "Loose",
            "high": "Exact",
            "text": "How closely shapes, edges and layout follow your original."
        },
        {
            "key": "restoration",
            "label": "Restoration",
            "low": "Keep",
            "high": "Renew",
            "text": "How much fresh detail plain surfaces and protected areas get. High values can add artefacts."
        }
    ],
    "protect": [
        {
            "key": "people",
            "label": "People",
            "hint": "Faces and bodies keep their features.",
            "default": true
        },
        {
            "key": "furniture",
            "label": "Furniture and objects",
            "hint": "Sofas, beds, chairs, benches and tables keep their shape.",
            "default": true
        },
        {
            "key": "vehicles",
            "label": "Vehicles",
            "hint": "Cars keep their bodywork and badges.",
            "default": true
        },
        {
            "key": "windows",
            "label": "Windows and glass",
            "hint": "Glazing and reflections stay clean.",
            "default": true
        },
        {
            "key": "architecture",
            "label": "Architecture",
            "hint": "Walls, roofs, floors, doors and stairs keep their geometry and materials. People and planting are still enhanced unless People is ticked.",
            "default": false
        }
    ],
    "quick_protect": [
        {
            "key": "architecture_only_people_vegetation",
            "label": "Protect architecture and only enhance people and vegetation",
            "categories": [
                "furniture",
                "vehicles",
                "windows",
                "architecture"
            ]
        }
    ],
    "scales": [
        2,
        4,
        6,
        8
    ],
    "output_formats": [
        {
            "key": "png8",
            "label": "PNG 8-bit"
        },
        {
            "key": "png16",
            "label": "PNG 16-bit"
        },
        {
            "key": "tiff16",
            "label": "TIFF 16-bit"
        },
        {
            "key": "jpeg",
            "label": "JPEG (quality 95)"
        }
    ],
    "modes": [
        {
            "key": "standard",
            "label": "Standard",
            "text": ""
        },
        {
            "key": "fast",
            "label": "Fast",
            "text": "Quicker, with a slightly different look. Use Standard for finals."
        }
    ],
    "default_seed": "20261102"
}
