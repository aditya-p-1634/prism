from app.api.v1.research_evidence import get_spatial_event_evidence


def test_phase18_endpoint_returns_non_operational_evidence():
    response = get_spatial_event_evidence()
    assert response.request_id
    assert response.confidence == 0.0
    assert response.data["historical_event"]["temporal_join_status"] == "NOT_JOINED"
    assert response.data["interpretation"]["operational_claim_allowed"] is False
