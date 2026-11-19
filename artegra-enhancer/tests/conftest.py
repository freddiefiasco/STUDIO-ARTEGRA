"""Suite-wide test setup.

The service's memory defaults follow the computer's RAM (service/settings.py machine_ram_gb), so a suite that read the real
figure would plan differently on each machine: on GitHub's 16 GB runner 98 tests failed against the Beta. Every test sees
TEST_MACHINE_RAM_GB instead, through the environment variable that machine_ram_gb() reads first, so the pin also reaches
every service the tests start (directly, through tests/qa/launch_service.py, or through the host). A test that is about
the RAM figure itself passes its own (Settings(total_ram_gb=...) or default_ram_cap_gb(total)) or sets the variable."""
import os

TEST_MACHINE_RAM_GB = 127.37        # the workstation the suite was written and proven on
os.environ['ENHANCER_TEST_RAM_GB'] = str(TEST_MACHINE_RAM_GB)
