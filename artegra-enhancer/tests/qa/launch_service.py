"""Launch the synthetic test service below normal scheduling priority."""
import ctypes
import os


def main():
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000):
            raise OSError(ctypes.get_last_error(), "Could not lower test service priority")
    else:
        os.nice(10)
    dev = os.environ.pop("CU_TEST_DEV_CHANNEL", None)
    if dev is not None:
        # tests only (this launcher is not part of any build): run the service as a developer build, admitting the
        # Large-image engine up to the given sizes (service/build_channel.py)
        import json
        from service import build_channel
        build_channel.CHANNEL = "dev"
        build_channel.DEV_PROVEN_MP = json.loads(dev) or None
    if os.environ.pop("CU_TEST_BXF_AVAILABLE", None) == "1":
        # tests only (5.0.2 build wave 2): plan as if the banded exact finish were available on this computer, as the
        # planner's own tests set engine/banded_plan.BXF_AVAILABLE test-locally (contract finish_tier); the shipped
        # default stays off until the start-up probe sets it, so without this every Large-image plan counts tier 3
        from engine import banded_plan
        banded_plan.BXF_AVAILABLE = True
    g1u = os.environ.pop("CU_TEST_BXF_G1U", None)
    if g1u is not None:
        # tests only (5.0.2 build wave 3, contracts.g1u): with the fake engine the start-up probe's environment read and the
        # probe itself are stand-ins (service/bxf_probe.TEST_ENVIRONMENT and TEST_PROBE): JSON {"environment": "committed:<i>"
        # (the environment of engine/bxf/g1_table.TABLES[i]), "unmatched" (one no committed table matches) or an environment
        # object, "probe": [the command that stands in for <runtime python> -I -B -S selfprobe.py]}
        import json
        from engine.bxf import g1
        from service import bxf_probe
        spec = json.loads(g1u) or {}
        env = spec.get("environment")
        if isinstance(env, str) and env.startswith("committed:"):
            env = dict(g1.committed_tables()[int(env.split(":", 1)[1])]["environment"])
        elif env == "unmatched":
            env = dict(g1.committed_tables()[-1]["environment"], processor="Test processor (no G1 table)")
        bxf_probe.TEST_ENVIRONMENT = env
        bxf_probe.TEST_PROBE = spec.get("probe")
    from service.app import main as service_main
    return service_main()


if __name__ == "__main__":
    raise SystemExit(main())
