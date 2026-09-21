import pytest

from anthrion_signal.discovery import prefilter


@pytest.mark.parametrize("title,description,accepted", [
    ("UNACORN Automated Cross-Domain Semantic Intelligence Fusion (GraphRAG)",
     "Active call for solution briefs under a Commercial Solutions Opening.", True),
    ("Media Monitoring Software",
     "The Senedd requires software solutions to support media monitoring, press office management, "
     "social media management and social media listening activities. Suppliers may bid for individual lots.", True),
    ("CALL QUEUE MANAGEMENT SYSTEM",
     "Information is sought on modern Call Queue Management solutions replacing the current platform "
     "and operating with Microsoft Teams telephony.", True),
    ("PR agency services", "Provide PR staff using the supplier's media monitoring software.", False),
    ("Telephone answering service", "The contractor must have its own call queue management system.", False),
    ("Print services", "Media monitoring software and GraphRAG are not required.", False),
    ("Servers and customer communications",
     "Lot 1: Supply server hardware. Lot 2: Implement a call queue management system.", True),
])
def test_specific_digital_terms_preserve_use_negation_and_mixed_lots(signal, config, title, description, accepted):
    signal.title, signal.description, signal.cpv_codes = title, description, []
    original = (signal.id, signal.title, signal.description)
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    assert (signal.prefilter_score >= 12 and not signal.exclusion_reasons) is accepted
    assert (signal.id, signal.title, signal.description) == original
