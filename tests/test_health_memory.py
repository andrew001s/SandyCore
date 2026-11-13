import unittest
from types import SimpleNamespace
from unittest.mock import mock_open, patch

from app.controllers.http.test_router import _get_rss_mb


class HealthMemoryTests(unittest.TestCase):
    def test_memory_is_unavailable_without_proc_or_resource(self):
        with patch("builtins.open", side_effect=FileNotFoundError), patch.dict(
            "sys.modules", {"resource": None}
        ):
            self.assertEqual(_get_rss_mb(), 0.0)

    def test_linux_reads_current_rss_from_proc(self):
        with patch("builtins.open", mock_open(read_data="VmRSS:\t2048 kB\n")):
            self.assertEqual(_get_rss_mb(), 2.0)

    def test_resource_fallback_converts_platform_units(self):
        for platform, peak_rss in (("linux", 2048), ("darwin", 2097152)):
            with self.subTest(platform=platform):
                resource = SimpleNamespace(
                    RUSAGE_SELF=0,
                    getrusage=lambda _: SimpleNamespace(ru_maxrss=peak_rss),
                )
                with patch("builtins.open", side_effect=FileNotFoundError), patch.dict(
                    "sys.modules", {"resource": resource}
                ), patch("sys.platform", platform):
                    self.assertEqual(_get_rss_mb(), 2.0)
