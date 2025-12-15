from companies.models import company_document_upload_path, Company, CompanyDocument

def test_company_document_upload_path():
    class Itt:
        company = mock = type("C", (), {"slug": "acme"})
        content_type = "CODING"

    path = company_document_upload_path(Itt(), "doc.pdf")
    assert "companies/acme/" in path

def test_company_str_methods():
    c = Company(name="ACME")
    assert str(c) == "ACME"

    cd = CompanyDocument()
    cd.company = c
    cd.content_type = "CODING"
    cd.status = "completed"
    # __str__ should include company name and content type
    assert "ACME" in str(cd)
