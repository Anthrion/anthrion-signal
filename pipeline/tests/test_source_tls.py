import hashlib
import ssl
from importlib.resources import files

import httpx

from anthrion_signal.collectors import Http
from anthrion_signal.source_tls import DEVOLVED_API_HOSTS, INTERMEDIATE, devolved_tls_context


def test_devolved_chain_repair_still_requires_hostname_expiry_and_trusted_root():
    context = devolved_tls_context()
    assert context.check_hostname
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN
    pem = files("anthrion_signal").joinpath(INTERMEDIATE).read_text("ascii")
    assert pem.count("BEGIN CERTIFICATE") == 1
    assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest() == (
        "8c54c334b66ba4e426772af4a3f9136c19a1aec729fdb28c535c07a5a4ef22e0"
    )
    bundled = next(cert for cert in context.get_ca_certs() if cert["serialNumber"] == "397A66CC2756362E0DAA87CA6EABE3B1")
    assert bundled["issuer"] != bundled["subject"]


def test_repaired_transports_are_scoped_to_exact_https_api_hosts(monkeypatch):
    for variable in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(variable, raising=False)
        monkeypatch.delenv(variable.lower(), raising=False)
    http = Http()
    try:
        default = http.client._transport
        for host in DEVOLVED_API_HOSTS:
            assert http.client._transport_for_url(httpx.URL(f"https://{host}/v1")) is not default
            assert http.client._transport_for_url(httpx.URL(f"https://{host}.example.org/v1")) is default
            assert http.client._transport_for_url(httpx.URL(f"http://{host}/v1")) is default
        assert http.client._transport_for_url(httpx.URL("https://www.find-tender.service.gov.uk/")) is default
    finally:
        http.close()


def test_mock_transport_remains_effective_for_devolved_apis():
    http = Http(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"releases": []})))
    try:
        assert http.json(f"https://{DEVOLVED_API_HOSTS[0]}/v1/Notices") == {"releases": []}
    finally:
        http.close()
