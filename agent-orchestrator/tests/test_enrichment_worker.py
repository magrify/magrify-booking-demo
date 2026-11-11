from agent_orchestrator.enrichment_worker import enrich_leads, parse_csv_leads, process_payload, score_lead


def test_lead_score_is_transparent():
    result = score_lead({"name": "A", "company": "Campground SaaS", "email": "a@example.com"}, "campground SaaS owners")
    assert result["fit_label"] in {"high", "medium"}
    assert "matched_terms" in result


def test_csv_processing_and_redaction():
    payload = {"icp": "hospitality operators", "csv": "name,email,industry\nA,a@example.com,hospitality"}
    result = process_payload(payload)
    assert result["evaluation"]["lead_count"] == 1
    assert result["leads"][0]["email"] == "[EMAIL]"


def test_enrichment_limits_are_bounded():
    assert parse_csv_leads("name\nA\n")[0]["name"] == "A"
    result = enrich_leads(leads=[], icp="buyers")
    assert result["evaluation"]["lead_count"] == 0
