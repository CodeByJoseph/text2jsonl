from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import re
import hashlib

def scrape_url(url):
    """
    Enhanced scraper for University of Gothenburg sites with:
    1. Proper origin link handling
    2. Complete external link extraction
    3. Date extraction from time elements
    4. JSONL output format with file existence check
    5. Support for multiple site structures
    """
    # Configure Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    # Set up Chrome driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        print(f"1/9 🌐 Loading URL: {url}")
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        print("2/9 ✅ Page loaded successfully")
        
        # Expand all accordions using JavaScript - works for both sites
        print("3/9 ⚡ Expanding all content sections with JavaScript")
        driver.execute_script("""
            // Try student portal accordions
            const studentButtons = document.querySelectorAll('.accordion__button');
            studentButtons.forEach(button => {
                button.setAttribute('aria-expanded', 'true');
                const content = button.nextElementSibling;
                if (content && content.classList.contains('js-accordion__content')) {
                    content.style.display = 'block';
                    content.classList.remove('is-hidden');
                }
            });
            
            // Try library accordions
            const libraryButtons = document.querySelectorAll('.js-accordion__button');
            libraryButtons.forEach(button => {
                button.setAttribute('aria-expanded', 'true');
                const content = button.nextElementSibling;
                if (content && content.classList.contains('js-accordion__content')) {
                    content.style.display = 'block';
                    content.classList.remove('is-hidden');
                }
            });
        """)
        time.sleep(2)  # Wait for content to render
        
        # Get page HTML with expanded content
        page_source = driver.page_source
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')
        print("4/9 🔧 Page parsed with BeautifulSoup")
        
        # Prepare data storage
        base_url = urljoin(url, "/")  # Use the URL's base
        sections = []
        content_hashes = set()
        
        # Find main content container - flexible approach
        main_content = None
        possible_main_selectors = [
            'main#main',  # Student portal
            'div#main-content',  # Library site
            'main',  # General main element
            'div.main-content', 
            'div#content',
            'div.content-main',
            'div.page-content',
            'div.content'
        ]
        
        for selector in possible_main_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                print(f"5/9 📋 Main content container found using: {selector}")
                break
        
        if not main_content:
            print("❌ Could not find main content container, using body as fallback")
            main_content = soup.body
        
        # Extract date from time element if available
        date_element = soup.select_one('time')
        page_date = date_element.get_text(strip=True) if date_element else "Date not found"
        print(f"6/9 📅 Extracted page date: {page_date}")
        
        # Remove unwanted sections - flexible selectors
        unwanted_selectors = [
            '.breadcrumb', 
            '.block-menu', 
            '.layout__region--sidebar', 
            'footer', 
            '.block-page-title-block',
            '.site-footer',  # Library site
            '.region-sidebar',  # Library site
            '.block-system-breadcrumb-block'  # Library site
        ]
        
        for selector in unwanted_selectors:
            for unwanted in main_content.select(selector):
                unwanted.decompose()
        
        # Find all potential content sections
        content_sections = []
        
        # 1. Find accordion items - both sites
        content_sections.extend(main_content.select('.accordion__item, .accordion-item'))
        
        # 2. Find headings with content
        for heading in main_content.find_all(['h2', 'h3', 'h4', 'h1']):  # Include h1
            # Find the closest parent section
            parent_section = heading.find_parent(['section', 'div', 'article', 'details'])
            if parent_section and parent_section not in content_sections:
                content_sections.append(parent_section)
        
        # 3. Find other content containers
        content_containers = [
            '.paragraph', 
            '.block', 
            '.content',
            '.content-wrapper',  # Library site
            '.field--type-text-with-summary'  # Library site
        ]
        for selector in content_containers:
            content_sections.extend(main_content.select(selector))
        
        print(f"7/9 🔍 Found {len(content_sections)} potential content sections")
        
        # Process each section
        section_counter = 1
        for section in content_sections:
            try:
                # Skip empty sections
                if not section.get_text(strip=True):
                    continue
                
                # Extract heading - try to find the most relevant heading
                heading = ""
                heading_elem = section.find(['h1', 'h2', 'h3', 'h4'])  # Include h1
                if heading_elem:
                    heading = heading_elem.get_text(strip=True)
                else:
                    # Try to find heading in previous sibling
                    prev = section.find_previous_sibling(['h1', 'h2', 'h3', 'h4'])
                    if prev:
                        heading = prev.get_text(strip=True)
                
                # Extract content text
                content_text = section.get_text(separator=' ', strip=True)
                content_text = re.sub(r'\s+', ' ', content_text).strip()
                
                # Skip sections with minimal content
                if len(content_text) < 100:
                    continue
                
                # Generate content hash to detect duplicates
                content_hash = hashlib.md5(content_text.encode()).hexdigest()
                if content_hash in content_hashes:
                    continue
                content_hashes.add(content_hash)
                
                # Extract links
                links = []
                for link in section.find_all('a', href=True):
                    href = link['href']
                    if not href.startswith(('#', 'javascript')):
                        absolute_url = urljoin(base_url, href)
                        if absolute_url not in links:
                            links.append(absolute_url)
                
                # Create section dictionary
                section_data = {
                    'section': section_counter,
                    'heading': heading,
                    'content': content_text,
                    'origin_link': url,
                    'external_links': links,
                    'last_updated': page_date
                }
                
                # Add to results
                sections.append(section_data)
                section_counter += 1
                print(f"📝 Added section: {heading[:30]}..." if heading else "📝 Added section with no heading")
                
            except Exception as e:
                print(f"⚠️ Error processing section: {str(e)}")
        
        if sections:
            print(f"8/9 ✅ Successfully scraped {len(sections)} distinct sections from {url}")
        else:
            print("⚠️ No sections found on the page")
            
        return sections

    except Exception as e:
        print(f"⚠️ Error occurred while scraping {url}: {str(e)}")
        return []

    finally:
        driver.quit()
        print("9/9 🧹 Browser closed")

