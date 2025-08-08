from docling.document_converter import DocumentConverter
import sys

def main():
    # Check if argument is provided
    if len(sys.argv) != 2:
        print("❌ Usage: python pdfscrape.py <pdf_path_or_url>")
        print("   Example: python pdfscrape.py https://arxiv.org/pdf/2408.09869")
        print("   Example: python pdfscrape.py ./document.pdf")
        sys.exit(1)
    
    # Get source from command line argument
    source = sys.argv[1]
    
    print(f"📄 Converting: {source}")
    
    try:
        # Create converter and convert
        converter = DocumentConverter()
        result = converter.convert(source)
        
        # Output the markdown
        print(result.document.export_to_markdown())
        
    except Exception as e:
        print(f"❌ Error converting PDF: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()