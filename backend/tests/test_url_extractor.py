import pytest

from services import url_extractor
from services.url_extractor import JobPageParser, _validate_public_https_url, _job_posting


def test_job_post_json_ld_is_detected():
    parser = JobPageParser()
    parser.feed('<script type="application/ld+json">{"@type":"JobPosting","title":"Designer"}</script>')
    assert _job_posting(parser.json_ld)["title"] == "Designer"


def test_url_checker_only_accepts_public_https_urls():
    with pytest.raises(ValueError, match="HTTPS"):
        _validate_public_https_url("http://example.com/jobs")
    with pytest.raises(ValueError, match="public internet host"):
        _validate_public_https_url("https://127.0.0.1/private")


def test_extract_job_post_prefers_jobposting_json_ld(monkeypatch):
    description = "Join our team to build reliable products with clear expectations and a fair interview process. " * 2
    html = '<html><head><title>Careers</title><script type="application/ld+json">{"@type":"JobPosting","title":"Product Designer","description":"<p>' + description + '</p>","hiringOrganization":{"name":"Sample Co"},"jobLocation":{"address":{"addressLocality":"Pune"}}}</script></head><body>Generic site text</body></html>'
    monkeypatch.setattr(url_extractor, "_fetch_html", lambda _url: ("https://jobs.example.org/designer", html))
    result = url_extractor.extract_job_post("https://jobs.example.org/designer")
    assert result["title"] == "Product Designer"
    assert result["company_name"] == "Sample Co"
    assert result["location"] == "Pune"
    assert "clear expectations" in result["description"]


def test_analyze_url_extracts_then_scores_listing(registered_client, monkeypatch):
    import routes.prediction_routes as route_module
    monkeypatch.setattr(route_module, "extract_job_post", lambda _url: {"title": "Designer", "company_name": "Good Co", "location": "Remote", "description": "A public job post with readable details.", "source_url": "https://jobs.example.org/designer"})
    monkeypatch.setattr(route_module, "predict", lambda _record: {"prediction": "REAL", "fake_probability": .12, "confidence": .88, "risk_level": "LOW", "explanations": [], "notice": "Test"})
    response = registered_client.post("/api/analyze-url", json={"url": "https://jobs.example.org/designer"})
    assert response.status_code == 200
    assert response.get_json()["source_listing"]["company_name"] == "Good Co"
    assert response.get_json()["fake_percent"] == 12


def test_analyze_url_rejects_blank_url(client):
    response = client.post("/api/analyze-url", json={"url": ""})
    assert response.status_code == 400
