import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.ingestion.sec_fetcher import (
    accession_without_dashes,
    build_archive_url,
)


class SecFetcherTest(unittest.TestCase):
    def test_build_archive_url(self):
        url = build_archive_url(
            "0000037996",
            "0000037996-24-000010",
            "f-20231231.htm",
        )

        self.assertEqual(accession_without_dashes("0000037996-24-000010"), "000003799624000010")
        self.assertIn("/Archives/edgar/data/37996/000003799624000010/", url)
        self.assertTrue(url.endswith("/f-20231231.htm"))


if __name__ == "__main__":
    unittest.main()

