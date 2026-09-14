import json
from pathlib import Path

import httpx
import respx

from forecast_platform.aemo import NEM_SUMMARY_URL
from forecast_platform.ingest import main
from forecast_platform.store import CsvStore

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "nem_summary.json").read_text()
)


@respx.mock
def test_ingest_writes_observations_and_exits_zero(tmp_path, capsys):
    respx.get(NEM_SUMMARY_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    assert main(["--data-dir", str(tmp_path)]) == 0
    assert len(CsvStore(tmp_path).read_region("NSW1")) == 1
    assert "wrote 2" in capsys.readouterr().out


@respx.mock
def test_ingest_run_twice_writes_nothing_the_second_time(tmp_path, capsys):
    respx.get(NEM_SUMMARY_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    main(["--data-dir", str(tmp_path)])
    capsys.readouterr()
    assert main(["--data-dir", str(tmp_path)]) == 0
    assert "wrote 0" in capsys.readouterr().out


@respx.mock
def test_ingest_exits_nonzero_when_aemo_is_down(tmp_path):
    respx.get(NEM_SUMMARY_URL).mock(return_value=httpx.Response(503))
    assert main(["--data-dir", str(tmp_path)]) == 1
