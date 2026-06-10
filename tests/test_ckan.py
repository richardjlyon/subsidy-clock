import httpx

from subsidy_engine.ckan import fetch_all_records


def make_client(pages: dict[int, list[dict]], total: int) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(dict(request.url.params)["offset"])
        return httpx.Response(200, json={
            "success": True,
            "result": {"total": total, "records": pages.get(offset, [])},
        })

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_paginates_until_total():
    pages = {0: [{"_id": 1}, {"_id": 2}], 2: [{"_id": 3}]}
    client = make_client(pages, total=3)
    records = fetch_all_records("res-id", client=client, page_size=2)
    assert [r["_id"] for r in records] == [1, 2, 3]


def test_fetch_single_short_page():
    client = make_client({0: [{"_id": 1}]}, total=1)
    assert len(fetch_all_records("res-id", client=client, page_size=100)) == 1


def test_fetch_raises_on_truncated_result():
    # server claims 5 records but stops serving after 1
    client = make_client({0: [{"_id": 1}]}, total=5)
    try:
        fetch_all_records("res-id", client=client, page_size=1)
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "1 of 5" in str(e)


def test_fetch_uses_given_api_base():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"success": True,
                                         "result": {"total": 0, "records": []}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch_all_records("res-id", client=client, api_base="https://api.neso.energy/api/3/action")
    assert seen["url"].startswith("https://api.neso.energy/api/3/action/datastore_search")


def test_dataset_resources():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "package_show" in str(request.url)
        return httpx.Response(200, json={"success": True, "result": {
            "resources": [{"id": "abc", "name": "Daily Balancing Costs 2026-2027",
                           "format": "CSV"}]}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    from subsidy_engine.ckan import dataset_resources
    res = dataset_resources("some-dataset", client=client)
    assert res == [{"id": "abc", "name": "Daily Balancing Costs 2026-2027", "format": "CSV"}]
