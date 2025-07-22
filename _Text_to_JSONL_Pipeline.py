import streamlit as st
import tempfile
import validators
import os
import requests
import json
import hashlib
import pandas as pd
import io
from contextlib import redirect_stdout
from meta_utils import scrape_url
from parsepdf import process_all_pdfs, parse_pdf_markdown
from docling.document_converter import DocumentConverter
from utils import load_all_urls, load_scraped_text, fetch_rendered_text, semantic_similarity, get_status

st.set_page_config(page_title="Text to JSONL Pipeline", layout="centered")
st.title("📄 Text-to-JSONL Pipeline")

st.markdown("""
Paste one or more URLs (PDF files or web pages) below. The app will scrape the content
and convert it into structured `.jsonl` format while showing semantic similarity scores.
""")

# Choose Output JSONL File
st.subheader("📁 Choose or Create Database")
database_name = st.text_input("Database file name (no extension):", value="output")
database_folder = "database"
jsonl_path = os.path.join(database_folder, f"{database_name}.jsonl")

# Display full path as markdown, database name as copyable code block
st.markdown(f"📂 Output will be saved to: `{jsonl_path}`")

# List existing databases without .jsonl extension
if os.path.exists(database_folder):
    existing_files = [os.path.splitext(f)[0] for f in os.listdir(database_folder) if f.endswith(".jsonl")]
    if existing_files:
        st.markdown("### 📚 Existing databases")
        for file in existing_files:
            st.markdown(f"- `{file}`")  # Each file as code block with copy button

# URL Input
user_input = st.text_area(
    "🔗 Enter PDF or Website URLs (one per line):",
    placeholder="https://example.com/file.pdf\nhttps://example.se/page",
    height=150
)

# Helper Function for Web Scraping with Semantic Analysis
def scrape_urls_and_save(urls, output_path, log_area, log_buffer):
    """
    Scrapes URLs and saves to JSONL with real-time logging.
    Returns list of similarity results for each URL.
    """
    similarity_results = []
    with redirect_stdout(log_buffer):
        print(f"1/6 📁 Setting up output directory: {os.path.dirname(output_path)}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        print(f"2/6 🔍 Checking existing file: {output_path}")
        existing_hashes = set()
        existing_links = set()
        
        if os.path.isfile(output_path):
            print(f"3/6 🔍 Loading existing data from {output_path}")
            with open(output_path, "r", encoding="utf-8") as f_check:
                for line in f_check:
                    try:
                        data = json.loads(line)
                        h = hashlib.md5((data["content"] + data["origin_link"]).encode()).hexdigest()
                        existing_hashes.add(h)
                        existing_links.add(data["origin_link"])
                    except:
                        continue
        else:
            print("3/6 🧹 No existing file found, creating new database")

        with open(output_path, "a", encoding="utf-8") as f:
            for url in urls:
                print(f"\n{'=' * 50}")
                print(f"🚀 Starting scraping process for: {url}")
                print(f"4/6 🧾 Extracting content from {url}")
                log_area.code(log_buffer.getvalue())  # Update UI
                
                if url in existing_links:
                    print(f"⏩ Skipping already-scraped URL: {url}")
                    log_area.code(log_buffer.getvalue())
                    similarity_results.append({
                        "url": url,
                        "score": None,
                        "status": "skipped"
                    })
                    continue

                sections = scrape_url(url)
                print(f"5/6 📊 Found {len(sections)} content sections")
                log_area.code(log_buffer.getvalue())

                # Get live content for similarity check
                live_content = fetch_rendered_text(url)
                scraped_for_similarity = " ".join(sec["content"] for sec in sections if sec.get("content"))
                
                if live_content and scraped_for_similarity:
                    similarity = semantic_similarity(live_content, scraped_for_similarity)
                    similarity_results.append({
                        "url": url,
                        "score": similarity,
                        "status": "scraped"
                    })
                    print(f"📊 Semantic similarity score: {similarity:.3f}")
                else:
                    similarity_results.append({
                        "url": url,
                        "score": None,
                        "status": "no_content"
                    })
                    print(f"⚠️ Could not fetch content for similarity check: {url}")
                
                if sections:
                    df = pd.DataFrame(sections)
                    print("\n📊 Scraping results:")
                    print(df.head())

                    for section in sections:
                        h = hashlib.md5((section["content"] + section["origin_link"]).encode()).hexdigest()
                        if h in existing_hashes:
                            continue
                        existing_hashes.add(h)
                        existing_links.add(url)
                        f.write(json.dumps(section, ensure_ascii=False) + "\n")

                    print(f"6/6 💾 {'Appended' if os.path.isfile(output_path) else 'Saved'} data to {output_path}")
                    log_area.code(log_buffer.getvalue())
                else:
                    print(f"⚠️ No data scraped from this URL: {url}")
                
                log_area.code(log_buffer.getvalue())  # Update UI

    return similarity_results

# Run Button
if st.button("🚀 Run Pipeline"):
    urls = [url.strip() for url in user_input.strip().splitlines() if url.strip()]
    
    if not urls:
        st.warning("Please enter at least one valid URL.")
    else:
        # Separate URL types
        pdf_urls = [url for url in urls if url.lower().endswith(".pdf") and validators.url(url)]
        web_urls = [url for url in urls if not url.lower().endswith(".pdf") and validators.url(url)]
        invalid_urls = [url for url in urls if not validators.url(url)]

        # Show invalid URLs
        if invalid_urls:
            st.error(f"❌ Invalid URL(s): {invalid_urls}")

        # Initialize similarity results
        all_similarity_results = []

        # Process web URLs
        if web_urls:
            log_area = st.empty()
            log_buffer = io.StringIO()
            
            st.info(f"🌐 Scraping {len(web_urls)} web pages...")
            web_similarity_results = scrape_urls_and_save(web_urls, jsonl_path, log_area, log_buffer)
            all_similarity_results.extend(web_similarity_results)
            
            st.success(f"✅ Scraped and saved data from {len(web_urls)} web page(s).")

        # Process PDFs
        if pdf_urls:
            st.info("📄 Downloading and processing PDFs...")
            log_area = st.empty()
            log_buffer = io.StringIO()
            
            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_documents = []  # Store (local_path, original_url) tuples
                for url in pdf_urls:
                    local_path = os.path.join(tmpdir, os.path.basename(url))
                    try:
                        with open(local_path, "wb") as f:
                            f.write(requests.get(url).content)
                        pdf_documents.append((local_path, url))
                    except Exception as e:
                        st.error(f"Failed to download {url}: {e}")
                        all_similarity_results.append({
                            "url": url,
                            "score": None,
                            "status": "error"
                        })
                
                # Process PDFs with original URLs
                pdf_similarity_results = process_all_pdfs(pdf_documents, jsonl_path, log_area, log_buffer)
                # Ensure pdf_similarity_results is iterable
                if pdf_similarity_results is None:
                    st.warning("⚠️ No similarity results returned from PDF processing")
                    pdf_similarity_results = []
                all_similarity_results.extend(pdf_similarity_results)
                st.success(f"✅ Processed and saved data from {len(pdf_documents)} PDF file(s).")

        # Display similarity scores for both web and PDF URLs
        if all_similarity_results:
            st.markdown("### 🔍 Similarity Analysis")
            for result in all_similarity_results:
                col1, col2, col3 = st.columns([3, 1, 2])
                with col1:
                    st.markdown(f"**{result['url']}**")
                with col2:
                    score = result['score']
                    st.metric("Score", f"{score:.3f}" if score is not None else "N/A")
                with col3:
                    if result['status'] == "skipped":
                        st.info("⏩ Skipped (already processed)")
                    elif result['status'] == "no_content":
                        st.error("🔴 No content extracted")
                    elif result['status'] == "no_existing_content":
                        st.warning("🟠 No existing content for comparison")
                    elif result['status'] == "error":
                        st.error("🔴 Error processing")
                    elif result['score'] > 0.95:
                        st.success("✅ Excellent match")
                    elif result['score'] > 0.85:
                        st.info("🟡 Minor differences")
                    elif result['score'] > 0.70:
                        st.warning("🟠 Partial match")
                    else:
                        st.error("🔴 Poor match — consider re-scraping")

        # Show database summary
        if os.path.exists(jsonl_path):
            with open(jsonl_path, "r", encoding="utf-8") as f:
                line_count = sum(1 for _ in f)
            st.info(f"📄 Total entries in database: {line_count}")