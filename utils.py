import streamlit as st
import os
import json
import re
import time
import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from sentence_transformers import SentenceTransformer, util
from urllib.parse import urlparse, urlunparse
import difflib
import textwrap
from docling.document_converter import DocumentConverter
from typing import Optional, Tuple, List, Dict
import requests
import tempfile
from validators import url as url_validator
import logging
import traceback
import PyPDF2

DATA_DIR = "database"  # your JSONL folder

def load_scraped_text(url: str, data_dir: str = DATA_DIR) -> str:
    """Load and combine scraped content for a given URL from all JSONL files in the data directory."""
    combined = []
    if not os.path.exists(data_dir):
        return ""
    for filename in os.listdir(data_dir):
        if not filename.endswith(".jsonl"):
            continue
        path = os.path.join(data_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if obj.get("origin_link") == url:
                        combined.append(obj.get("content", ""))
                except:
                    pass
    return " ".join(combined)

def fetch_rendered_text(url: str, timeout: int = 10, return_html: bool = False) -> str:
    """Fetch and parse rendered text or HTML from a URL using Selenium and BeautifulSoup.

    Args:
        url (str): The URL to fetch.
        timeout (int): Timeout for page load.
        return_html (bool): Return raw HTML if True, else processed text.

    Returns:
        str: Rendered text or HTML, or empty string on failure.
    """
    if is_pdf_url(url):
        log_error(f"Cannot fetch {url} as webpage: URL points to a PDF")
        return ""
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        driver.execute_script("""
            const buttons = document.querySelectorAll('.accordion__button, .js-accordion__button');
            buttons.forEach(button => {
                button.setAttribute('aria-expanded', 'true');
                const content = button.nextElementSibling;
                if (content && content.classList.contains('js-accordion__content')) {
                    content.style.display = 'block';
                    content.classList.remove('is-hidden');
                }
            });
        """)
        time.sleep(2)  # Wait for content to expand

        page_source = driver.page_source
        if return_html:
            return page_source

        soup = BeautifulSoup(page_source, "html.parser")
        selectors = [
            "main#main", "div#main-content", "main", "div.main-content",
            "div#content", "div.content-main", "div.page-content", "div.content"
        ]
        main_content = None
        for sel in selectors:
            main_content = soup.select_one(sel)
            if main_content:
                break
        if not main_content:
            main_content = soup.body

        noise_selectors = [
            ".breadcrumb", ".block-menu", ".layout__region--sidebar",
            "footer", ".block-page-title-block", ".site-footer",
            ".region-sidebar", ".block-system-breadcrumb-block"
        ]
        for ns in noise_selectors:
            for el in main_content.select(ns):
                el.decompose()

        text = main_content.get_text(separator=" ", strip=True)
        text = re.sub(r'\s+', ' ', text)
        return text
    except Exception as e:
        log_error(f"Failed to fetch rendered text from {url}: {str(e)}")
        return ""
    finally:
        driver.quit()

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

def parse_pdf_markdown(markdown_text: str, origin_link: str) -> List[Dict]:
    """Parse PDF markdown into sections, mimicking process_all_pdfs."""
    sections = []
    lines = markdown_text.split("\n")
    current_section = 1
    current_heading = ""
    current_content = []
    
    logging.info(f"Parsing markdown for {origin_link}")
    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            if current_heading or current_content:
                sections.append({
                    "section": current_section,
                    "heading": current_heading or "No Heading",
                    "content": "\n".join(current_content).strip(),
                    "origin_link": origin_link,
                    "external_links": extract_external_links(current_content, origin_link),
                    "last_updated": "Date not found"
                })
                logging.info(f"Created section {current_section}: {current_heading[:30]}...")
                current_section += 1
                current_content = []
            current_heading = line.replace("## ", "").replace("### ", "").strip()
        else:
            current_content.append(line)
    
    if current_heading or current_content:
        sections.append({
            "section": current_section,
            "heading": current_heading or "No Heading",
            "content": "\n".join(current_content).strip(),
            "origin_link": origin_link,
            "external_links": extract_external_links(current_content, origin_link),
            "last_updated": "Date not found"
        })
        logging.info(f"Created final section {current_section}: {current_heading[:30] or 'No Heading'}...")
    
    logging.info(f"Parsed {len(sections)} sections from {origin_link}")
    return sections

@st.cache_data
def fetch_pdf_text(source: str, is_url: bool = True) -> Optional[Tuple[str, List[Dict]]]:
    """Extract text and sections from a PDF file (URL or local path) using Docling with PyPDF2 fallback.

    Args:
        source (str): URL or local path to the PDF file.
        is_url (bool): True if source is a URL, False if local path.

    Returns:
        Optional[Tuple[str, List[Dict]]]: Concatenated text and parsed sections, or None if extraction fails.
    """
    temp_file_path = None
    try:
        if is_url:
            if not is_pdf_url(source):
                log_error(f"URL {source} is not a PDF")
                return None
            response = requests.get(source, timeout=10)
            response.raise_for_status()
            content_type = response.headers.get('content-type', '').lower()
            if 'application/pdf' not in content_type:
                log_error(f"URL {source} is not a PDF (Content-Type: {content_type})")
                return None
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(response.content)
                temp_file_path = tmp_file.name
                # Verify file integrity
                if os.path.getsize(temp_file_path) == 0:
                    log_error(f"Temporary file {temp_file_path} is empty for {source}")
                    return None
        else:
            if not os.path.exists(source):
                log_error(f"Local PDF path {source} does not exist")
                return None
            temp_file_path = source

        # Try Docling with OCR
        try:
            converter = DocumentConverter(ocr=True)
            result = converter.convert(temp_file_path)
            markdown = result.document.export_to_markdown()
            sections = parse_pdf_markdown(markdown, source)
            text = " ".join(sec["content"] for sec in sections if sec.get("content"))
            text = re.sub(r'\s+', ' ', text).strip()
            logging.info(f"Extracted {len(text)} characters and {len(sections)} sections from PDF {source} using Docling")
            return text, sections
        except Exception as docling_error:
            log_error(f"Docling failed for {source}: {str(docling_error)}\n{traceback.format_exc()}")

            # Fallback to PyPDF2
            try:
                with open(temp_file_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + " "
                    text = re.sub(r'\s+', ' ', text).strip()
                    if not text:
                        log_error(f"PyPDF2 extracted no text from {source}")
                        return None
                    sections = parse_pdf_markdown(text, source)
                    logging.info(f"Extracted {len(text)} characters and {len(sections)} sections from PDF {source} using PyPDF2")
                    return text, sections
            except Exception as pypdf_error:
                log_error(f"PyPDF2 fallback failed for {source}: {str(pypdf_error)}\n{traceback.format_exc()}")
                return None

    except Exception as e:
        log_error(f"Failed to process PDF {source}: {str(e)}\n{traceback.format_exc()}")
        return None
    finally:
        if is_url and temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                log_error(f"Failed to delete temporary file {temp_file_path}: {str(e)}\n{traceback.format_exc()}")

def normalize_url(url: str) -> str:
    """Normalize a URL by removing query params and fragments, preserving case for paths."""
    try:
        parsed = urlparse(url)
        normalized = urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip('/'), '', '', ''))
        return normalized
    except Exception as e:
        log_error(f"URL normalization failed for {url}: {str(e)}\n{traceback.format_exc()}")
        return url
    
def validate_url(url: str) -> bool:
    """Validate if the input string is a valid HTTP/HTTPS URL.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if the URL is valid, False otherwise.
    """
    if not url:
        return False
    try:
        pattern = r'^https?://[^\s/$.?#[].*\.[a-zA-Z]{2,}(?:/.*)?$'
        if not re.match(pattern, url):
            log_error(f"URL {url} failed regex validation")
            return False
        result = url_validator(url)
        if not result:
            log_error(f"URL {url} failed validators check: {result}")
            return False
        return True
    except Exception as e:
        log_error(f"URL validation failed for {url}: {str(e)}")
        return False
    
def is_pdf_url(url: str) -> bool:
    """Check if a URL likely points to a PDF file.

    Args:
        url (str): The URL to check.

    Returns:
        bool: True if the URL ends with .pdf or has PDF content type.
    """
    if url.lower().endswith('.pdf'):
        return True
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        content_type = response.headers.get('content-type', '').lower()
        is_pdf = 'application/pdf' in content_type
        if not is_pdf:
            log_error(f"URL {url} is not a PDF (Content-Type: {content_type})")
        return is_pdf
    except Exception as e:
        log_error(f"Failed to check content type for {url}: {str(e)}")
        return False

# Add this helper function outside your main function
def log_error(message: str) -> None:
    """Log errors to file with timestamp."""
    os.makedirs("logs", exist_ok=True)
    with open("logs/fetch_errors.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()} - {message}\n")


@st.cache_resource(show_spinner=False)
def load_model():
    """Load the SentenceTransformer model for semantic similarity."""
    return SentenceTransformer('all-MiniLM-L6-v2')

model = load_model()

def semantic_similarity(text1: str, text2: str) -> float:
    """Calculate semantic similarity between two texts using SentenceTransformer."""
    emb1 = model.encode(text1, convert_to_tensor=True)
    emb2 = model.encode(text2, convert_to_tensor=True)
    score = util.pytorch_cos_sim(emb1, emb2).item()
    return score

def get_status(similarity: float) -> str:
    """Return a status message based on the similarity score."""
    if similarity is None:
        return "❌ No scraped data or error occurred"
    if similarity > 0.95:
        return "✅ Excellent match"
    elif similarity > 0.85:
        return "🟡 Minor differences"
    elif similarity > 0.70:
        return "🟠 Partial match"
    else:
        return "🔴 Poor match — consider reviewing scraped data"


def load_all_urls(data_dir: str = DATA_DIR) -> list:
    """Load all unique URLs from JSONL files in the data directory."""
    urls = set()
    if not os.path.exists(data_dir):
        return []
    for filename in os.listdir(data_dir):
        if not filename.endswith(".jsonl"):
            continue
        path = os.path.join(data_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    url = obj.get("origin_link")
                    if url:
                        urls.add(url)
                except:
                    pass
    return sorted(urls)

def extract_links(html: str, current_domain: str) -> List[str]:
    """Extract external links from HTML, excluding links from the current domain."""
    soup = BeautifulSoup(html, 'html.parser')
    links = [a.get('href') for a in soup.find_all('a', href=True)]
    external_links = []
    for link in links:
        try:
            if urlparse(link).netloc and urlparse(link).netloc != current_domain:
                external_links.append(link)
        except:
            continue
    return list(set(external_links))

# Function to update session state
def update_state(key: str, value: any, state: dict = st.session_state):
    """Update a key in the Streamlit session state."""
    state[key] = value

# Function to parse live content into sections
def parse_live_content(html: str, url: str) -> List[Dict]:
    """Parse HTML content into sections with headings and metadata."""
    soup = BeautifulSoup(html, 'html.parser')
    sections = []
    section_counter = 1

    # Find main content
    possible_main_selectors = [
        'main#main', 'div#main-content', 'main', 'div.main-content',
        'div#content', 'div.content-main', 'div.page-content', 'div.content'
    ]
    main_content = None
    for selector in possible_main_selectors:
        main_content = soup.select_one(selector)
        if main_content:
            break
    if not main_content:
        main_content = soup.body

    # Remove unwanted sections
    unwanted_selectors = [
        '.breadcrumb', '.block-menu', '.layout__region--sidebar',
        'footer', '.block-page-title-block', '.site-footer',
        '.region-sidebar', '.block-system-breadcrumb-block'
    ]
    for selector in unwanted_selectors:
        for unwanted in main_content.select(selector):
            unwanted.decompose()

    # Find content sections
    content_sections = []
    content_sections.extend(main_content.select('.accordion__item, .accordion-item'))
    for heading in main_content.find_all(['h1', 'h2', 'h3', 'h4']):
        parent_section = heading.find_parent(['section', 'div', 'article', 'details'])
        if parent_section and parent_section not in content_sections:
            content_sections.append(parent_section)
    content_containers = ['.paragraph', '.block', '.content', '.content-wrapper', '.field--type-text-with-summary']
    for selector in content_containers:
        content_sections.extend(main_content.select(selector))

    # Process sections
    for section in content_sections:
        if not section.get_text(strip=True):
            continue
        heading_elem = section.find(['h1', 'h2', 'h3', 'h4'])
        heading = heading_elem.get_text(strip=True) if heading_elem else ""
        if not heading:
            prev = section.find_previous_sibling(['h1', 'h2', 'h3', 'h4'])
            if prev:
                heading = prev.get_text(strip=True)
        content_text = section.get_text(separator=' ', strip=True).strip()
        if len(content_text) < 100:
            continue
        section_data = {
            "section": section_counter,
            "heading": heading,
            "content": content_text,
            "origin_link": url,
            "external_links": extract_links(str(section), urlparse(url).netloc),
            "last_updated": "Date not found"
        }
        sections.append(section_data)
        section_counter += 1

    return sections

# Database selector function
def find_matching_databases(url: str, data_dir: str = "database") -> List[str]:
    """Find .jsonl databases containing the given URL.

    Args:
        url (str): The URL to search for.
        data_dir (str): Directory containing .jsonl files.

    Returns:
        List[str]: List of database filenames containing the URL.
    """
    matching_dbs = []
    normalized_url = normalize_url(url)
    if not os.path.exists(data_dir):
        log_error(f"Database directory {data_dir} does not exist")
        return matching_dbs

    for filename in os.listdir(data_dir):
        if filename.endswith(".jsonl"):
            file_path = os.path.join(data_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_url = entry.get('origin_link', '')
                        if normalize_url(entry_url) == normalized_url:
                            matching_dbs.append(filename)
                            logging.info(f"Found {url} in {filename}")
                            break
                    except json.JSONDecodeError:
                        log_error(f"Invalid JSON in {file_path}: {line}")
    logging.info(f"Found {len(matching_dbs)} databases for {url}: {matching_dbs}")
    return matching_dbs


def generate_diff_html(live_text: str, scraped_text: str, width: int = 120) -> str:
    """Generate HTML diff table comparing live and scraped text."""
    live_lines = textwrap.wrap(live_text, width=width)
    scraped_lines = textwrap.wrap(scraped_text, width=width)
    differ = difflib.HtmlDiff()
    diff_html = differ.make_table(
        fromlines=live_lines,
        tolines=scraped_lines,
        fromdesc='Live Website',
        todesc='Scraped Data',
        context=True,
        numlines=2
    )
    scrollable_container = f"""
    <div style='
        overflow: auto;
        height: 300px;
        border: 1px solid #ccc;
        padding: 10px;
        background-color: #ffffff;
        color: #000000;
    '>
    <style>
    table.diff {{ font-family: Courier; font-size: 14px; border: medium; color: #000000; }}
    .diff_header {{ background-color: #e0e0e0; color: #000000; }}
    .diff_next {{ background-color: #c0c0c0; color: #000000; }}
    td.diff_added {{ background-color: #aaffaa; color: #000000; }}
    td.diff_chg {{ background-color: #ffff77; color: #000000; }}
    td.diff_sub {{ background-color: #ffaaaa; color: #000000; }}
    </style>
    {diff_html}
    </div>
    """
    return scrollable_container

def display_sections(sections: list, title: str, origin_link: str) -> None:
    """Display sections with headings and metadata in a Streamlit container."""
    with st.container():
        st.markdown(f"<h2 style='text-align: center;'>{title}</h2>", unsafe_allow_html=True)
        for section in sections:
            st.markdown(f"### Section {section['section']}: {section['heading']}")
            st.write(section['content'])
            st.markdown("---")
        
        if sections:
            st.markdown("#### Page Metadata")
            st.write(f"**Origin Link**: {origin_link}")
            external_links = set()
            for section in sections:
                external_links.update(section.get('external_links', []))
            if external_links:
                st.write("**External Links**:")
                for link in external_links:
                    st.write(f"- {link}")
            st.write(f"**Last Updated**: {sections[0].get('last_updated', 'Date not found')}")

def load_scraped_sections(url: str, db_path: str) -> Tuple[List[Dict], str]:
    """Load sections and concatenated text from a JSONL file for a given URL.

    Args:
        url (str): The URL to match.
        db_path (str): Path to the .jsonl file.

    Returns:
        Tuple[List[Dict], str]: List of matching sections and concatenated text.
    """
    sections = []
    text = ""
    normalized_url = normalize_url(url)
    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entry_url = entry.get('origin_link', '')
                    if normalize_url(entry_url) == normalized_url:
                        sections.append(entry)
                        content = entry.get('content', '')
                        text += content + " "
                        logging.info(f"Matched entry in {db_path}: {entry_url}")
                    else:
                        logging.info(f"Skipped entry in {db_path}: {entry_url}")
                except json.JSONDecodeError:
                    log_error(f"Invalid JSON in {db_path}: {line}")
        text = re.sub(r'\s+', ' ', text).strip()
        logging.info(f"Loaded {len(sections)} sections for {url} from {db_path}")
        return sections, text
    except Exception as e:
        log_error(f"Failed to load {db_path}: {str(e)}")
        return [], ""
    
    