"""Published market partitions; an option never implies national completeness."""

TED_COUNTRIES = {
    "GBR": "GB", "ITA": "IT", "SWE": "SE", "FIN": "FI", "DNK": "DK", "NOR": "NO", "ISL": "IS",
    "DEU": "DE", "ESP": "ES", "GRC": "GR", "BEL": "BE", "NLD": "NL", "FRA": "FR", "CHE": "CH",
    "AUT": "AT", "IRL": "IE", "PRT": "PT", "POL": "PL", "EST": "EE", "LVA": "LV", "LTU": "LT",
    "CZE": "CZ", "ROU": "RO", "BGR": "BG", "HRV": "HR", "HUN": "HU", "LUX": "LU", "CYP": "CY",
    "MLT": "MT", "SVN": "SI", "SVK": "SK",
}
# Includes the Caribbean islands and CARICOM's mainland members. A regional
# publication is not attributed to a bank's headquarters or to every member.
CARIBBEAN_COUNTRIES = [
    "AG", "AI", "AW", "BB", "BL", "BQ", "BS", "BZ", "CU", "CW", "DM", "DO", "GD", "GP", "GY", "HT",
    "JM", "KN", "KY", "LC", "MF", "MQ", "MS", "PR", "SR", "SX", "TC", "TT", "VC", "VG", "VI",
    "CARIBBEANREGIONAL",
]
MARKETS = {country: [country] for country in ["GB", "US", "CA", *TED_COUNTRIES.values(), *CARIBBEAN_COUNTRIES]}
MARKETS["CARIBBEAN"] = CARIBBEAN_COUNTRIES
MARKETS["NORTHAMERICA"] = ["US", "CA"]
MARKETS["NORDICS"] = ["SE", "FI", "DK", "NO", "IS"]
MARKETS["BENELUX"] = ["BE", "NL", "LU"]
MARKETS["DACH"] = ["DE", "AT", "CH"]
