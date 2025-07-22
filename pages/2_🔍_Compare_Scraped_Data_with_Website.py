import streamlit as st
import difflib
import textwrap
import json
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from utils import fetch_rendered_text, load_scraped_text, semantic_similarity, extract_links

st.set_page_config(page_title="🧪 Compare Scraped vs Live Content", layout="wide")
st.title("🧪 Compare Scraped Content with Live Website")

# Initialize session state
if 'state' not in st.session_state:
    st.session_state.state = {
        'scraped_text': None,
        'live_text': None,
        'similarity': None,
        'scraped_sections': [],
        'live_sections': [],
        'show_full_screen_scraped': False,
        'show_full_screen_live': False,
        'url_input': '',
        'matching_dbs': [],
        'selected_db': None
    }

# Function to update session state
def update_state(key, value):
    st.session_state.state[key] = value

# Function to parse live content into sections
def parse_live_content(html, url):
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
def find_matching_databases(url):
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

# URL input section
url_input = st.text_input("Enter URL to compare scraped content with live page:", 
                          value=st.session_state.state['url_input'])
if url_input != st.session_state.state['url_input']:
    # Reset state when URL changes
    update_state('url_input', url_input)
    update_state('scraped_text', None)
    update_state('live_text', None)
    update_state('similarity', None)
    update_state('scraped_sections', [])
    update_state('live_sections', [])
    update_state('matching_dbs', [])
    update_state('selected_db', None)
    
    # Find matching databases
    if url_input:
        with st.spinner("🔍 Searching databases for matching URL..."):
            matching_dbs = find_matching_databases(url_input)
            update_state('matching_dbs', matching_dbs)
            # Automatically select the first database if only one is found
            if len(matching_dbs) == 1:
                update_state('selected_db', matching_dbs[0])

# Database selector function
if url_input and st.session_state.state['matching_dbs']:
    if len(st.session_state.state['matching_dbs']) > 1:
        st.info(f"Found {len(st.session_state.state['matching_dbs'])} databases with this URL")
        selected_db = st.selectbox(
            "Select database to use for comparison:",
            options=[""] + st.session_state.state['matching_dbs'],
            format_func=lambda x: x or "Select a database",
            key="db_selector"
        )
        if selected_db != st.session_state.state['selected_db']:
            # Reset data when database selection changes
            update_state('selected_db', selected_db)
            update_state('scraped_text', None)
            update_state('scraped_sections', [])
    elif len(st.session_state.state['matching_dbs']) == 1:
        # Ensure single database is consistently selected
        if st.session_state.state['selected_db'] != st.session_state.state['matching_dbs'][0]:
            update_state('selected_db', st.session_state.state['matching_dbs'][0])
            update_state('scraped_text', None)
            update_state('scraped_sections', [])
else:
    st.warning("No matching databases found for this URL")

# Load scraped data based on selection
if url_input and st.session_state.state['selected_db'] and st.session_state.state['scraped_text'] is None:
    with st.spinner("📚 Loading scraped content..."):
        # Initialize fresh containers
        scraped_sections = []
        scraped_text = ""
        
        # Load content from the selected database
        path = os.path.join("database", st.session_state.state['selected_db'])
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        if obj.get("origin_link") == url_input:
                            # Skip if section number already exists to avoid duplicates
                            if not any(s['section'] == obj['section'] for s in scraped_sections):
                                scraped_sections.append(obj)
                                scraped_text += obj.get("content", "") + "\n\n"
                    except json.JSONDecodeError:
                        continue
            # Sort sections by section number
            scraped_sections.sort(key=lambda x: x['section'])
            if not scraped_sections:
                st.warning(f"No matching entries found for {url_input} in {st.session_state.state['selected_db']}")
            else:
                st.success(f"Loaded {len(scraped_sections)} sections from {st.session_state.state['selected_db']}")
        except FileNotFoundError:
            st.error(f"Could not access database file: {path}")
        
        # Update state with collected data
        update_state('scraped_sections', scraped_sections)
        update_state('scraped_text', scraped_text.strip())

# Show compare button if we have scraped content
if st.session_state.state['scraped_text']:
    if st.button("🔍 Fetch and compare live page"):
        with st.spinner("🌐 Fetching live page content..."):
            live_html = fetch_rendered_text(url_input, return_html=True)
            update_state('live_text', fetch_rendered_text(url_input))
            update_state('live_sections', parse_live_content(live_html, url_input))
            update_state('similarity', semantic_similarity(
                st.session_state.state['scraped_text'],
                st.session_state.state['live_text']
            ))

# Display comparison results if available
if st.session_state.state['live_text']:
    st.success(f"Live content size: {len(st.session_state.state['live_text'])} characters")
    st.success(f"Scraped content size: {len(st.session_state.state['scraped_text'])} characters")
    
    if st.session_state.state['similarity']:
        st.metric(label="Semantic Similarity Score (0 to 1)", 
                 value=f"{st.session_state.state['similarity']:.3f}")

        # Similarity interpretation
        sim_score = st.session_state.state['similarity']
        if sim_score > 0.95:
            st.success("✅ Excellent match")
        elif sim_score > 0.85:
            st.info("🟡 Minor differences")
        elif sim_score > 0.70:
            st.warning("🟠 Partial match")
        else:
            st.error("🔴 Poor match — consider reviewing scraped data")

        # Generate diff
        live_lines = textwrap.wrap(st.session_state.state['live_text'], width=120)
        scraped_lines = textwrap.wrap(st.session_state.state['scraped_text'], width=120)
        differ = difflib.HtmlDiff()
        diff_html = differ.make_table(
            fromlines=live_lines,
            tolines=scraped_lines,
            fromdesc='Live Website',
            todesc='Scraped Data',
            context=True,
            numlines=2
        )

        # Display diff visualization
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
        st.markdown(scrollable_container, unsafe_allow_html=True)

        # Content preview
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📄 Live Website Text")
            st.text_area("Live Text Preview", st.session_state.state['live_text'], height=300)
            if st.button("🖥️ View Live Text Full Screen"):
                update_state('show_full_screen_live', True)
        with col2:
            st.subheader("📄 Scraped Text")
            st.text_area("Scraped Text Preview", st.session_state.state['scraped_text'], height=300)
            if st.button("🖥️ View Scraped Text Full Screen"):
                update_state('show_full_screen_scraped', True)

# Full-screen view for live content
if st.session_state.state['show_full_screen_live'] and st.session_state.state['live_sections']:
    with st.container():
        st.markdown("<h2 style='text-align: center;'>Live Website Content Details</h2>", unsafe_allow_html=True)
        for section in st.session_state.state['live_sections']:
            st.markdown(f"### Section {section['section']}: {section['heading']}")
            st.write(section['content'])
            st.markdown("---")
        
        if st.session_state.state['live_sections']:
            st.markdown("#### Page Metadata")
            st.write(f"**Origin Link**: {st.session_state.state['live_sections'][0]['origin_link']}")
            external_links = set()
            for section in st.session_state.state['live_sections']:
                external_links.update(section.get('external_links', []))
            if external_links:
                st.write("**External Links**:")
                for link in external_links:
                    st.write(f"- {link}")
            st.write(f"**Last Updated**: {st.session_state.state['live_sections'][0].get('last_updated', 'Date not found')}")

        if st.button("Close Full Screen (Live)"):
            update_state('show_full_screen_live', False)

# Full-screen view for scraped content
if st.session_state.state['show_full_screen_scraped'] and st.session_state.state['scraped_sections']:
    with st.container():
        st.markdown("<h2 style='text-align: center;'>Scraped Content Details</h2>", unsafe_allow_html=True)
        for section in st.session_state.state['scraped_sections']:
            st.markdown(f"### Section {section['section']}: {section['heading']}")
            st.write(section['content'])
            st.markdown("---")
        
        if st.session_state.state['scraped_sections']:
            st.markdown("#### Page Metadata")
            st.write(f"**Origin Link**: {st.session_state.state['scraped_sections'][0]['origin_link']}")
            external_links = set()
            for section in st.session_state.state['scraped_sections']:
                external_links.update(section.get('external_links', []))
            if external_links:
                st.write("**External Links**:")
                for link in external_links:
                    st.write(f"- {link}")
            st.write(f"**Last Updated**: {st.session_state.state['scraped_sections'][0].get('last_updated', 'Date not found')}")

        if st.button("Close Full Screen (Scraped)"):
            update_state('show_full_screen_scraped', False)