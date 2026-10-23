"""GET /public-config: the flags the web pages read to choose a flow before the visitor acts."""


def test_public_config_defaults_to_otp_required(client, monkeypatch):
    monkeypatch.delenv("DAZY_OTP_DISABLED", raising=False)
    r = client.get("/api/v1/public-config")  # no auth needed
    assert r.status_code == 200 and r.json()["otpRequired"] is True
    assert r.headers["cache-control"] == "no-store"  # a Render change must show on the next page load


def test_public_config_reports_otp_disabled(client, monkeypatch):
    monkeypatch.setenv("DAZY_OTP_DISABLED", "1")
    assert client.get("/api/v1/public-config").json()["otpRequired"] is False
    monkeypatch.setenv("DAZY_OTP_DISABLED", "no")  # only explicit truthy values disable it
    assert client.get("/api/v1/public-config").json()["otpRequired"] is True


def test_public_config_exposes_nothing_else(client):
    assert set(client.get("/api/v1/public-config").json()) == {"otpRequired", "advanceAmount"}


def test_public_config_reports_the_advance(client, auth_headers):
    assert client.get("/api/v1/public-config").json()["advanceAmount"] == 500.0  # the seeded default
    client.put("/api/v1/admin/cms/booking_advance_amount", json={"value": "750"}, headers=auth_headers)
    assert client.get("/api/v1/public-config").json()["advanceAmount"] == 750.0
    client.put("/api/v1/admin/cms/booking_advance_amount", json={"value": "0"}, headers=auth_headers)
    assert client.get("/api/v1/public-config").json()["advanceAmount"] == 0.0  # 0 = no advance option
