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
from selenium.common.exceptions import TimeoutException, WebDriverException
from sentence_transformers import SentenceTransformer, util
from urllib.parse import urlparse



DATA_DIR = "database"  # your JSONL folder

def load_scraped_text(url, data_dir=DATA_DIR):
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
    return SentenceTransformer('all-MiniLM-L6-v2')

model = load_model()

def semantic_similarity(text1, text2):
    emb1 = model.encode(text1, convert_to_tensor=True)
    emb2 = model.encode(text2, convert_to_tensor=True)
    score = util.pytorch_cos_sim(emb1, emb2).item()
    return score

def get_status(similarity: float) -> str:
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


def load_all_urls(data_dir=DATA_DIR):
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
