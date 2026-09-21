"""Published market partitions; an option never implies national completeness."""

TED_COUNTRIES = {
    "GBR": "GB", "ITA": "IT", "SWE": "SE", "FIN": "FI", "DNK": "DK", "NOR": "NO", "ISL": "IS",
    "DEU": "DE", "ESP": "ES", "GRC": "GR", "BEL": "BE", "NLD": "NL", "FRA": "FR", "CHE": "CH",
    "AUT": "AT", "IRL": "IE", "PRT": "PT", "POL": "PL", "EST": "EE", "LVA": "LV", "LTU": "LT",
    "CZE": "CZ", "ROU": "RO", "BGR": "BG", "HRV": "HR", "HUN": "HU", "LUX": "LU", "CYP": "CY",
    "MLT": "MT", "SVN": "SI", "SVK": "SK",
}
MARKETS = {country: [country] for country in ["GB", "US", "CA", *TED_COUNTRIES.values()]}
MARKETS["NORTHAMERICA"] = ["US", "CA"]
MARKETS["NORDICS"] = ["SE", "FI", "DK", "NO", "IS"]
MARKETS["BENELUX"] = ["BE", "NL", "LU"]
MARKETS["DACH"] = ["DE", "AT", "CH"]
