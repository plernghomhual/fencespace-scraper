import ast
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


TARGET_FEDERATION_SCRAPERS = [
    "scrape_fed_hun.py",
    "scrape_fed_kor.py",
    "scrape_fed_chn.py",
    "scrape_fed_jpn.py",
    "scrape_fed_rus.py",
    "scrape_fed_pol.py",
    "scrape_fed_ukr.py",
    "scrape_fed_rou.py",
    "scrape_fed_esp.py",
    "scrape_fed_egy.py",
    "scrape_fed_ned.py",
    "scrape_fed_bel.py",
    "scrape_fed_sui.py",
    "scrape_fed_aut.py",
    "scrape_fed_swe.py",
    "scrape_fed_den.py",
    "scrape_fed_nor.py",
    "scrape_fed_fin.py",
    "scrape_fed_aus.py",
    "scrape_fed_nzl.py",
    "scrape_fed_bra.py",
    "scrape_fed_arg.py",
    "scrape_fed_hkg.py",
    "scrape_fed_sgp.py",
    "scrape_fed_isr.py",
]


ROOT = Path(__file__).resolve().parents[1]


def _direct_requests_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(), filename=str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"get", "post"}
            and isinstance(func.value, ast.Name)
            and func.value.id == "requests"
        ):
            lines.append(node.lineno)
    return lines


def test_federation_request_waits_for_domain_and_records_success(monkeypatch):
    import fed_rankings_common

    calls: list[tuple[Any, ...]] = []

    class Response:
        status_code = 200

    def fake_wait(domain):
        calls.append(("wait", domain))

    def fake_success(domain):
        calls.append(("success", domain))

    def fake_get(url, **kwargs):
        calls.append(("get", url, kwargs["timeout"]))
        return Response()

    monkeypatch.setattr(fed_rankings_common._federation_limiter, "wait", fake_wait)
    monkeypatch.setattr(fed_rankings_common._federation_limiter, "record_success", fake_success)
    monkeypatch.setattr(fed_rankings_common.requests, "get", fake_get)

    response = fed_rankings_common.federation_request("get", "https://example.org/rankings", timeout=12)

    assert isinstance(response, Response)
    assert calls == [
        ("wait", "example.org"),
        ("get", "https://example.org/rankings", 12),
        ("success", "example.org"),
    ]


def test_target_federation_scrapers_use_limited_request_wrapper():
    offenders = {
        filename: _direct_requests_calls(ROOT / filename)
        for filename in TARGET_FEDERATION_SCRAPERS
    }
    offenders = {filename: lines for filename, lines in offenders.items() if lines}

    assert offenders == {}
