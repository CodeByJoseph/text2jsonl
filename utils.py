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
from urllib.parse import urlparse
import difflib
import textwrap


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

def fetch_rendered_text(url: str, timeout: int = 10, return_html=False) -> str:
    """Fetch and parse rendered text or HTML from a URL using Selenium and BeautifulSoup."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
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
        
        # Return raw HTML if requested
        if return_html:
            return page_source
            
        # Otherwise process text as usual
        soup = BeautifulSoup(page_source, "html.parser")

        selectors = [
            "main#main",
            "div#main-content",
            "main",
            "div.main-content",
            "div#content",
            "div.content-main",
            "div.page-content",
            "div.content"
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
    finally:
        driver.quit()

# Add this helper function outside your main function
def log_error(message: str):
    """Log errors to file with timestamp"""
    os.makedirs("logs", exist_ok=True)
    with open("logs/fetch_errors.log", "a") as f:
        f.write(f"{datetime.now()} - {message}\n")


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

def extract_links(html, current_domain):
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
    return list(set(external_links))  # Remove duplicates

# Function to update session state
def update_state(key: str, value: any, state: dict = st.session_state):
    """Update a key in the Streamlit session state."""
    state[key] = value

# Function to parse live content into sections
def parse_live_content(html: str, url: str) -> list:
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
def find_matching_databases(url: str, data_dir: str = DATA_DIR) -> list: 
    """Find all databases containing the given URL in origin_link"""
    matching_dbs = []
    for filename in os.listdir("database"):
        if not filename.endswith(".jsonl"):
            continue
        path = os.path.join("database", filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        if obj.get("origin_link") == url:
                            matching_dbs.append(filename)
                            break  # Only need to find one match per database
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            st.error(f"Could not access database file: {path}")
            continue
    return list(set(matching_dbs))  # Remove duplicates


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

def load_scraped_sections(url: str, db_path: str) -> tuple[list, str]:
    """Load sections and concatenated text from a JSONL file for a given URL."""
    sections = []
    text = ""
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if obj.get("origin_link") == url:
                        if not any(s['section'] == obj['section'] for s in sections):
                            sections.append(obj)
                            text += obj.get("content", "") + "\n\n"
                except json.JSONDecodeError:
                    continue
        sections.sort(key=lambda x: x['section'])
        return sections, text.strip()
    except FileNotFoundError:
        st.error(f"Could not access database file: {db_path}")
        return [], ""