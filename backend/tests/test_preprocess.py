from ml.preprocess import clean_text, prepare_records


def test_clean_text_removes_markup_and_normalizes_whitespace():
    assert clean_text("<p>Good&nbsp; ROLE</p>\n now") == "good ROLE now".lower()


def test_prepare_records_keeps_content_and_structural_flags():
    row = prepare_records([{"title": "Engineer", "description": "Build useful tools", "has_company_logo": 1}])[0]
    assert "title: engineer" in row["combined_text"]
    assert row["structured"]["flag_has_company_logo"] == 1
    assert row["structured"]["missing_salary_range"] == 1
