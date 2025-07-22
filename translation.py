import json
import time
import os
from googletrans import Translator

# Removed duplicate imports

def translate_section(section, translator):
    """Translate Swedish content and headings to English"""
    try:
        # Translate heading if present
        heading_trans = translator.translate(
            section['heading'], src='sv', dest='en'
        ).text if section.get('heading') else ''
        
        # Translate content if present
        content_trans = translator.translate(
            section['content'], src='sv', dest='en'
        ).text if section.get('content') else ''
        
        return {
            "section": section["section"],
            "heading": heading_trans,
            "content": content_trans,
            # Keep all other fields unchanged
            "origin_link": section.get("origin_link", ""),  # No longer modified
            "external_links": section.get("external_links", []),
            "last_updated": section.get("last_updated", "Date not found")
        }
    except Exception as e:
        print(f"Translation error in section {section.get('section', 'unknown')}: {str(e)}")
        return section  # Return original if translation fails
    
def process_jsonl(input_path, output_path):
    """Process JSONL input and translate Swedish content to English"""
    translator = Translator()
    
    try:
        with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
            total_lines = sum(1 for _ in infile)
            infile.seek(0)
            
            for line_idx, line in enumerate(infile):
                try:
                    section_data = json.loads(line.strip())
                    print(f"\nProcessing line {line_idx + 1}/{total_lines}")
                    
                    translated = translate_section(section_data, translator)
                    print(f"  - heading: '{translated['heading']}'")
                    print(f"  - origin_link: '{translated['origin_link']}'")
                    
                    outfile.write(json.dumps(translated, ensure_ascii=False) + '\n')
                    time.sleep(0.5)  # Rate limiting
                    
                except Exception as e:
                    print(f"Error processing line: {str(e)}")
                    outfile.write(line)  # Keep original line on failure
                    
    except Exception as e:
        print(f"🚨 File processing error: {str(e)}")

if __name__ == "__main__":
    input_path = 'database/gu_dv_sv.jsonl'
    output_path = 'database/gu_dv_en.jsonl'

    if not os.path.exists(input_path):
        print(f"❌ Input file not found: {input_path}")
        print("Create the file first or update the path")
    else:
        process_jsonl(input_path, output_path)