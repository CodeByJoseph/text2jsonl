from docling.document_converter import DocumentConverter

source = "https://www.gu.se/sites/default/files/2025-03/Utbildningsplanht25-Datavetenskapligt%20program%20_%20180%2C0%20hp%20_%20N1COS.pdf"  # document per local path or URL
converter = DocumentConverter()
result = converter.convert(source)
print(result.document.export_to_markdown())  # output: "## Docling Technical Report[...]"