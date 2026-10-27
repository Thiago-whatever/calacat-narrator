"""Simulator → /ingest: the Function key travels in a header, read from the environment."""

import pytest

from calacat_narrator import simulator
from calacat_narrator.simulator import main


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_cli_sends_function_key_from_environment(tmp_path, monkeypatch) -> None:
    sent = []
    monkeypatch.setattr(
        simulator, "urlopen", lambda request, timeout: sent.append(request) or _Response()
    )
    monkeypatch.setattr(simulator.time, "sleep", lambda seconds: None)
    monkeypatch.setenv(simulator.INGEST_KEY_ENV, "test-key")

    main(
        [
            "--seed",
            "3",
            "--duration-s",
            "24",
            "--output",
            str(tmp_path / "m.jsonl"),
            "--ingest-url",
            "https://fn.example.test/api/ingest",
        ]
    )

    assert sent
    assert all(request.get_header("X-functions-key") == "test-key" for request in sent)


def test_cli_posts_without_key_when_unset_and_hints_on_401(tmp_path, monkeypatch) -> None:
    def unauthorized(request, timeout):
        assert request.get_header("X-functions-key") is None
        raise simulator.HTTPError(request.full_url, 401, "Unauthorized", None, None)

    monkeypatch.setattr(simulator, "urlopen", unauthorized)
    monkeypatch.delenv(simulator.INGEST_KEY_ENV, raising=False)

    with pytest.raises(RuntimeError, match=simulator.INGEST_KEY_ENV):
        main(
            [
                "--seed",
                "3",
                "--duration-s",
                "24",
                "--output",
                str(tmp_path / "m.jsonl"),
                "--ingest-url",
                "http://localhost:7071/api/ingest",
            ]
        )
