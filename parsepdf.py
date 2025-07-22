from docling.document_converter import DocumentConverter
import re
import json
import os
import hashlib
from contextlib import redirect_stdout
import io
from urllib.parse import urlparse, urljoin
from utils import load_scraped_text, semantic_similarity  # Import required utils

def parse_pdf_markdown(markdown_text, origin_link):
    """
    Parse PDF markdown with fallback for documents without clear headings
    and maintain detailed terminal output
    """
    sections = []
    lines = markdown_text.split("\n")
    current_section = 1
    current_heading = ""
    current_content = []
    
    # Keep old-style logging
    print("1/4 🧾 Starting PDF markdown parsing")
    print("2/4 📥 Reading markdown content")
    
    for line in lines:
        # Detect Markdown headers
        if line.startswith("## ") or line.startswith("### "):
            # Save previous section if we have content
            if current_heading or current_content:
                sections.append({
                    "section": current_section,
                    "heading": current_heading or "No Heading",
                    "content": "\n".join(current_content).strip(),
                    "origin_link": origin_link,
                    "external_links": extract_external_links(current_content, origin_link),
                    "last_updated": "Date not found"
                })
                print(f"📝 Created section {current_section}: {current_heading[:30]}...")
                current_section += 1
                current_content = []
            
            # Extract new heading
            current_heading = line.replace("## ", "").replace("### ", "").strip()
        else:
            current_content.append(line)
    
    # Save final section (even if no heading found)
    if current_heading or current_content:
        sections.append({
            "section": current_section,
            "heading": current_heading or "No Heading",
            "content": "\n".join(current_content).strip(),
            "origin_link": origin_link,
            "external_links": extract_external_links(current_content, origin_link),
            "last_updated": "Date not found"
        })
        print(f"📝 Created final section {current_section}: {current_heading[:30]}..." if current_heading else f"📝 Created final section {current_section}: No Heading")
    
    # Restore old-style progress indicators
    print("3/4 🔗 Extracting external links")
    # External links are already extracted during section creation
    
    print(f"4/4 ✅ Returning {len(sections)} sections")
    print(f"📄 Created {len(sections)} sections from {origin_link}")
    
    return sections

def extract_external_links(text_lines, base_url):
    """Extract external links from text content (supports both Markdown and plain text)"""
    text = " ".join(text_lines)
    
    # First extract Markdown-style links [text](url)
    markdown_links = re.findall(r"\[(.*?)\]\((https?://.*?)\)", text)
    result = set(url[1] for url in markdown_links if url[1].startswith("http"))
    
    # Then extract plain text URLs
    plain_urls = re.findall(r'https?://[^\s>]+', text)
    result.update(plain_urls)
    
    # Filter out URLs from base domain
    domain = urlparse(base_url).netloc
    filtered = [url for url in result if not url.startswith(f"https://{domain}") and not url.startswith(f"http://{domain}")]
    
    return filtered

def process_all_pdfs(pdf_paths, output_jsonl, log_area, log_buffer):
    """Process all PDFs with enhanced logging, original URL tracking, and semantic analysis"""
    similarity_results = []  # Store similarity results for PDFs
    with redirect_stdout(log_buffer):
        print(f"1/7 📁 Setting up output directory: {os.path.dirname(output_jsonl)}")
        os.makedirs(os.path.dirname(output_jsonl), exist_ok=True)
        print(f"2/7 🔍 Checking existing file: {output_jsonl}")
        
        file_exists = os.path.isfile(output_jsonl)
        existing_hashes = set()
        existing_links = set()

        if file_exists:
            print(f"3/7 🔍 Loading existing data from {output_jsonl}")
            with open(output_jsonl, "r", encoding="utf-8") as f_check:
                for line in f_check:
                    try:
                        data = json.loads(line)
                        h = hashlib.md5((data["content"] + data["origin_link"]).encode()).hexdigest()
                        existing_hashes.add(h)
                        existing_links.add(data["origin_link"])
                    except:
                        continue
        else:
            print("3/7 🧹 Creating new database for PDFs")

        print("4/7 🧾 Starting PDF processing")
        log_area.code(log_buffer.getvalue())

        with open(output_jsonl, "a", encoding="utf-8") as f:
            for local_path, original_url in pdf_paths:  # Now receives tuple (local path + original URL)
                print(f"\n{'=' * 50}")
                print(f"🚀 Processing PDF: {original_url}")
                print(f"5/7 📄 Converting {local_path} to markdown")
                log_area.code(log_buffer.getvalue())
                
                if original_url in existing_links:
                    print(f"⏩ Skipping already-processed PDF: {original_url}")
                    log_area.code(log_buffer.getvalue())
                    similarity_results.append({
                        "url": original_url,
                        "score": None,
                        "status": "skipped"
                    })
                    continue

                try:
                    converter = DocumentConverter()
                    result = converter.convert(local_path)
                    markdown = result.document.export_to_markdown()
                    
                    print(f"6/7 🔗 Parsing content from {original_url}")
                    log_area.code(log_buffer.getvalue())
                    
                    pdf_sections = parse_pdf_markdown(markdown, original_url)
                    new_sections = 0
                    
                    # Aggregate content for similarity check
                    scraped_for_similarity = " ".join(sec["content"] for sec in pdf_sections if sec.get("content"))
                    
                    # Fetch existing content from database for comparison
                    existing_content = load_scraped_text(original_url)
                    
                    if scraped_for_similarity and existing_content:
                        similarity = semantic_similarity(existing_content, scraped_for_similarity)
                        similarity_results.append({
                            "url": original_url,
                            "score": similarity,
                            "status": "scraped"
                        })
                        print(f"📊 Semantic similarity score: {similarity:.3f}")
                    elif scraped_for_similarity:
                        similarity_results.append({
                            "url": original_url,
                            "score": None,
                            "status": "no_existing_content"
                        })
                        print("⚠️ No existing content in database for similarity check")
                    else:
                        similarity_results.append({
                            "url": original_url,
                            "score": None,
                            "status": "no_content"
                        })
                        print("⚠️ No content extracted from PDF for similarity check")
                    
                    for section in pdf_sections:
                        h = hashlib.md5((section["content"] + section["origin_link"]).encode()).hexdigest()
                        if h in existing_hashes:
                            continue
                        existing_hashes.add(h)
                        existing_links.add(original_url)
                        f.write(json.dumps(section, ensure_ascii=False) + "\n")
                        new_sections += 1
                    
                    print(f"7/7 💾 Saved {new_sections} new sections from {original_url}")
                    log_area.code(log_buffer.getvalue())
                    
                except Exception as e:
                    print(f"❌ Error processing {original_url}: {str(e)}")
                    log_area.code(log_buffer.getvalue())
                    similarity_results.append({
                        "url": original_url,
                        "score": None,
                        "status": "error"
                    })
    
    return similarity_results  # Return similarity results for display