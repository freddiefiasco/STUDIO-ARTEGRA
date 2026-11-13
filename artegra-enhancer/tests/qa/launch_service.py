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
    from service.app import main as service_main
    return service_main()


if __name__ == "__main__":
    raise SystemExit(main())
