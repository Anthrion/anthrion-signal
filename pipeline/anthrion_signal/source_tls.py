"""Supply the intermediate omitted by the devolved APIs, not a new trust root."""

import ssl
from importlib.resources import files


DEVOLVED_API_HOSTS = ("api.publiccontractsscotland.gov.uk", "api.sell2wales.gov.wales")
INTERMEDIATE = "certificates/sectigo-public-server-authentication-dv-r36.pem"


def devolved_tls_context(*, cafile=None):
    context = ssl.create_default_context(cafile=cafile)
    # Never allow the supplied intermediate to become a trust anchor, including
    # on Python versions which enable partial-chain verification by default.
    context.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    context.load_verify_locations(cadata=files("anthrion_signal").joinpath(INTERMEDIATE).read_text("ascii"))
    return context
