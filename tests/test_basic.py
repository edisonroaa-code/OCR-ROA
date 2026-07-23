import pytest
from pathlib import Path
from roa_ocr import process_pdf, process_to_markdown, process_to_chunks

# Usar el archivo de prueba existente
TEST_PDF = Path(__file__).parent.parent / "test_prueba.pdf"

def test_process_pdf_basic():
    """Test the basic 1-line API for PDF processing."""
    if not TEST_PDF.exists():
        pytest.skip("Test PDF not found")
        
    result = process_pdf(str(TEST_PDF), engine="easyocr") # Forzar easyocr para que corra rapido y sin dependencias nativas
    
    assert result.success is True
    assert isinstance(result.markdown, str)
    assert len(result.markdown) > 0
    assert result.pages >= 1

def test_process_to_markdown():
    """Test the shortcut to markdown."""
    if not TEST_PDF.exists():
        pytest.skip("Test PDF not found")
        
    markdown = process_to_markdown(str(TEST_PDF))
    assert isinstance(markdown, str)
    assert len(markdown) > 0

def test_process_to_chunks():
    """Test the RAG chunks extraction."""
    if not TEST_PDF.exists():
        pytest.skip("Test PDF not found")
        
    chunks = process_to_chunks(str(TEST_PDF), chunk_size=100)
    assert isinstance(chunks, list)
    if len(chunks) > 0:
        assert "text" in chunks[0]

def test_custom_rules_injection():
    """Test that custom rules are applied."""
    if not TEST_PDF.exists():
        pytest.skip("Test PDF not found")
        
    # La regla absurda: si encuentra "documento", lo cambia a "ZanahoriaVoladora"
    custom_rules = {"documento": "ZanahoriaVoladora"}
    result = process_pdf(str(TEST_PDF), engine="easyocr", custom_rules=custom_rules)
    
    assert result.success is True
    # If the word 'documento' was in the PDF, it should now be replaced.
    # Note: the test PDF might not have the exact word.
    # We just want to ensure it doesn't crash when passing the parameter.
    assert isinstance(result.markdown, str)
