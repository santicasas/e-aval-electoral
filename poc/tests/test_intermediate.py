"""Intermediate storage/retrieve services (mobile signing): protocol of the official servlets."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.intermediate import RETRIEVE_PATH, STORAGE_PATH, Store, err, make_router  # noqa: E402

FORM = {"Content-Type": "application/x-www-form-urlencoded"}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(clock):
    app = FastAPI()
    app.include_router(make_router(Store(ttl=60, max_bytes=100, max_items=3, clock=clock)))
    return TestClient(app)


def put(client, id_="abc123", data="SGVsbG8", extra=""):
    return client.post(STORAGE_PATH, content=f"op=put&v=1_0&id={id_}&dat={data}{extra}", headers=FORM)


def get(client, id_="abc123"):
    # the page retrieves with POST and a form body, with an iteration counter
    return client.post(RETRIEVE_PATH, content=f"op=get&v=1_0&id={id_}&it=0", headers=FORM)


def test_check_operations(client):
    assert client.get(STORAGE_PATH, params={"op": "check"}).text == "OK"
    assert client.get(RETRIEVE_PATH, params={"op": "check"}).text == "OK"


def test_put_then_get_roundtrip_and_one_time_read(client):
    assert put(client).text == "OK"
    r = get(client)
    assert r.text.strip() == "SGVsbG8" and r.headers["content-type"].startswith("text/plain")
    assert get(client).text.strip() == err("ERR-06")  # deleted after the first read


def test_get_by_query_string_also_works(client):
    put(client)
    assert client.get(RETRIEVE_PATH, params={"op": "get", "v": "1_0", "id": "abc123"}).text.strip() == "SGVsbG8"


def test_not_yet_available_is_err06_so_the_page_keeps_polling(client):
    assert get(client, "nothere").text.lower().startswith("err-06")


def test_missing_expired_and_read_are_indistinguishable(client, clock):
    put(client)
    clock.now = 61
    expired = get(client).text
    assert expired == get(client, "never-existed").text


def test_overwrite_supports_the_wait_then_result_pattern(client):
    put(client, data="#wait")
    put(client, data="RESULT")
    assert get(client).text.strip() == "RESULT"


def test_data_is_url_decoded_like_the_java_servlet(client):
    put(client, data="a%2Bb%3D")
    assert get(client).text.strip() == "a+b="


@pytest.mark.parametrize("body,code", [
    ("v=1_0&id=x&dat=y", "ERR-00"),
    ("op=put&id=x&dat=y", "ERR-20"),
    ("op=zap&v=1_0&id=x&dat=y", "ERR-01"),
    ("op=put&v=1_0&dat=y", "ERR-05"),
])
def test_storage_errors(client, body, code):
    assert client.post(STORAGE_PATH, content=body, headers=FORM).text.strip() == err(code)


@pytest.mark.parametrize("bad_id", ["a.b", "a/b", "a%5Cb", "..", "a b", "x" * 129])
def test_invalid_ids_are_rejected(client, bad_id):
    assert put(client, id_=bad_id).text.strip() == err("ERR-06")
    assert get(client, id_=bad_id).text.strip() == err("ERR-06")


def test_missing_data_stores_the_error_so_the_client_sees_it(client):
    client.post(STORAGE_PATH, content="op=put&v=1_0&id=abc123", headers=FORM)
    assert get(client).text.strip() == err("ERR-02")


def test_oversized_data_stores_err07(client):
    assert put(client, data="x" * 200).text == "OK"
    assert get(client).text.strip() == err("ERR-07")


def test_item_limit(client):
    for i in range(3):
        assert put(client, id_=f"id{i}").text == "OK"
    assert put(client, id_="id3").text.strip() == err("ERR-07")
    assert put(client, id_="id0", data="new").text == "OK"  # overwriting an existing id is still allowed


def test_retrieve_errors(client):
    assert client.post(RETRIEVE_PATH, content="v=1_0&id=x", headers=FORM).text.strip() == err("ERR-00")
    assert client.post(RETRIEVE_PATH, content="op=get&id=x", headers=FORM).text.strip() == err("ERR-20")
    assert client.post(RETRIEVE_PATH, content="op=put&v=1_0&id=x", headers=FORM).text.strip() == err("ERR-01")
    assert client.post(RETRIEVE_PATH, content="op=get&v=1_0", headers=FORM).text.strip() == err("ERR-05")


def test_integrated_in_the_poc_app_with_no_store_headers():
    from server.app import app

    c = TestClient(app)
    r = c.get(STORAGE_PATH, params={"op": "check"})
    assert r.text == "OK" and r.headers["cache-control"] == "no-store"
    assert "content-security-policy" in r.headers
