import streamlit as st
import os
import json
import re
from urllib.parse import urlparse
from utils import (
    find_matching_databases,
    load_scraped_sections,
    normalize_url,
    validate_url,
    is_pdf_url
)

st.set_page_config(page_title="🔍 JSONL Entry Viewer", layout="wide")
st.title("🔍 JSONL Entry Viewer")
st.markdown("View all JSONL entries for a URL in fullscreen")

# Initialize session state for this page
if 'viewer_state' not in st.session_state:
    st.session_state.viewer_state = {
        'url_input': '',
        'matching_dbs': [],
        'selected_db': None,
        'scraped_sections': [],
        'show_entries': False
    }

# Input section
url_input = st.text_input("Enter URL to view scraped entries:",
                          value=st.session_state.viewer_state['url_input'])

if url_input != st.session_state.viewer_state['url_input']:
    st.session_state.viewer_state['url_input'] = url_input
    st.session_state.viewer_state['matching_dbs'] = []
    st.session_state.viewer_state['selected_db'] = None
    st.session_state.viewer_state['scraped_sections'] = []
    st.session_state.viewer_state['show_entries'] = False
    
    if url_input:
        if not validate_url(url_input):
            st.error("Please enter a valid HTTP/HTTPS URL")
        else:
            with st.spinner("🔍 Searching databases for matching URL..."):
                matching_dbs = find_matching_databases(url_input)
                st.session_state.viewer_state['matching_dbs'] = matching_dbs
                if len(matching_dbs) == 1:
                    st.session_state.viewer_state['selected_db'] = matching_dbs[0]

# Database selector
if st.session_state.viewer_state['url_input'] and st.session_state.viewer_state['matching_dbs']:
    if len(st.session_state.viewer_state['matching_dbs']) > 1:
        st.info(f"Found {len(st.session_state.viewer_state['matching_dbs'])} databases with this URL")
        selected_db = st.selectbox(
            "Select database to view:",
            options=[""] + st.session_state.viewer_state['matching_dbs'],
            format_func=lambda x: x or "Select a database",
            key="db_selector"
        )
        if selected_db != st.session_state.viewer_state['selected_db']:
            st.session_state.viewer_state['selected_db'] = selected_db
            st.session_state.viewer_state['scraped_sections'] = []
            st.session_state.viewer_state['show_entries'] = False
    elif len(st.session_state.viewer_state['matching_dbs']) == 1:
        if st.session_state.viewer_state['selected_db'] != st.session_state.viewer_state['matching_dbs'][0]:
            st.session_state.viewer_state['selected_db'] = st.session_state.viewer_state['matching_dbs'][0]
            st.session_state.viewer_state['scraped_sections'] = []
            st.session_state.viewer_state['show_entries'] = False
else:
    if st.session_state.viewer_state['url_input'] and validate_url(st.session_state.viewer_state['url_input']):
        st.warning("No matching databases found for this URL")

# Load button
if st.session_state.viewer_state['url_input'] and st.session_state.viewer_state['selected_db']:
    if st.button("📂 Load All Entries", key="load_button"):
        with st.spinner("📚 Loading all entries from database..."):
            db_path = os.path.join("database", st.session_state.viewer_state['selected_db'])
            try:
                scraped_sections, _ = load_scraped_sections(
                    st.session_state.viewer_state['url_input'],
                    db_path
                )
                if not scraped_sections:
                    st.warning(f"No matching entries found in {st.session_state.viewer_state['selected_db']}")
                else:
                    st.success(f"Loaded {len(scraped_sections)} entries from {st.session_state.viewer_state['selected_db']}")
                st.session_state.viewer_state['scraped_sections'] = scraped_sections
                st.session_state.viewer_state['show_entries'] = True
            except Exception as e:
                st.error(f"Failed to load data: {str(e)}")

# Display all entries
if st.session_state.viewer_state['show_entries'] and st.session_state.viewer_state['scraped_sections']:
    entries = st.session_state.viewer_state['scraped_sections']
    st.subheader(f"All Entries for {st.session_state.viewer_state['url_input']}")
    st.markdown(f"**Database:** {st.session_state.viewer_state['selected_db']} | **Total Entries:** {len(entries)}")
    
    # Back button
    if st.button("← Back to Search", key="back_button"):
        st.session_state.viewer_state['show_entries'] = False
        st.experimental_rerun()
    
    # Display all entries
    for i, entry in enumerate(entries):
        st.markdown("---")
        st.subheader(f"Entry {i+1} of {len(entries)}")
        
        # Handle different entry types
        if isinstance(entry, dict):
            # Create columns for better organization
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Display metadata fields
                metadata_fields = ['origin_link', 'last_updated', 'document', 'section', 'heading', 'tags']
                for field in metadata_fields:
                    if field in entry:
                        st.markdown(f"**{field.replace('_', ' ').title()}**")
                        if field == 'origin_link' and isinstance(entry[field], str):
                            st.markdown(f"[{entry[field]}]({entry[field]})")
                        elif field == 'tags' and isinstance(entry[field], list):
                            st.write(", ".join(entry[field]))
                        else:
                            st.write(entry[field])
                
                # Display external links
                for link_field in ['external_links', 'external_link']:
                    if link_field in entry:
                        st.markdown("**External Links**")
                        links = entry[link_field]
                        if isinstance(links, list):
                            for link in links:
                                if isinstance(link, str):
                                    st.markdown(f"- [{link}]({link})")
                        elif isinstance(links, str):
                            st.markdown(f"- [{links}]({links})")
            
            with col2:
                # Display content fields
                content_fields = ['text', 'content', 'programinnehåll', 'description']
                for field in content_fields:
                    if field in entry:
                        st.markdown(f"**{field.replace('_', ' ').title()}**")
                        content = entry[field]
                        if isinstance(content, str) and len(content) > 100:
                            st.text_area(label="", value=content, height=300, key=f"{field}_{i}_text_area")
                        else:
                            st.write(content)
                
                # Display any other fields not shown yet
                displayed_fields = set(metadata_fields + content_fields + ['external_links', 'external_link'])
                other_fields = [f for f in entry.keys() if f not in displayed_fields]
                
                if other_fields:
                    st.markdown("**Additional Fields**")
                    for field in other_fields:
                        st.markdown(f"**{field.replace('_', ' ').title()}**")
                        value = entry[field]
                        if isinstance(value, list):
                            st.write(", ".join(str(item) for item in value))
                        elif isinstance(value, dict):
                            st.json(value)
                        else:
                            st.write(value)
            
            # Raw JSON view - ALWAYS DISPLAYED with same style as before
            st.markdown("**Raw JSON Data**")
            st.json(entry)  # Using st.json() for the same interactive viewer
            
        elif isinstance(entry, str):
            # Handle simple string entries
            st.markdown("**Content**")
            st.text_area(label="", value=entry, height=300, key=f"content_{i}")
            
        else:
            st.warning("Unsupported entry format")
            st.write(entry)
    
    # Add navigation to top button at the bottom
    st.markdown("[Back to top ↑](#)")

# Instructions when no data is loaded
elif not st.session_state.viewer_state['url_input']:
    st.info("""
    **How to use this viewer:**
    1. Enter a URL you want to view entries for
    2. Select a database that contains this URL
    3. Click "Load All Entries" to retrieve all entries from the database
    4. View all entries in fullscreen
    """)
    
    st.markdown("### Supported JSONL Formats")
    st.markdown("This viewer works with any JSONL format. Here are examples:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Document-style Entry**")
        st.json({
            "document": "Program Overview",
            "text": "This is a sample program overview text...",
            "tags": ["education", "program", "computer-science"],
            "origin_link": "https://example.com/program",
            "external_link": ["https://external1.com", "https://external2.com"],
            "last_updated": "2023-01-01"
        })
    
    with col2:
        st.markdown("**Section-style Entry**")
        st.json({
            "section": 11,
            "heading": "Other regulations",
            "content": "The course is collected with Chalmers...",
            "origin_link": "https://example.com/course",
            "external_links": [],
            "last_updated": "2025-08-02",
            "tags": ["Introduction", "Regulations", "Education"]
        })

# Status message when URL is entered but no entries loaded
elif st.session_state.viewer_state['url_input']:
    st.info("Click 'Load All Entries' to view all scraped data for this URL")