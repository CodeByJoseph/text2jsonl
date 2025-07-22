import streamlit as st
import os
from utils import (fetch_rendered_text, semantic_similarity, update_state, 
                   parse_live_content, find_matching_databases, display_sections, 
                   generate_diff_html, load_scraped_sections)

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

# URL input section
url_input = st.text_input("Enter URL to compare scraped content with live page:", 
                          value=st.session_state.state['url_input'])
if url_input != st.session_state.state['url_input']:
    update_state('url_input', url_input, st.session_state.state)
    update_state('scraped_text', None, st.session_state.state)
    update_state('live_text', None, st.session_state.state)
    update_state('similarity', None, st.session_state.state)
    update_state('scraped_sections', [], st.session_state.state)
    update_state('live_sections', [], st.session_state.state)
    update_state('matching_dbs', [], st.session_state.state)
    update_state('selected_db', None, st.session_state.state)
    
    if url_input:
        with st.spinner("🔍 Searching databases for matching URL..."):
            matching_dbs = find_matching_databases(url_input)
            update_state('matching_dbs', matching_dbs, st.session_state.state)
            if len(matching_dbs) == 1:
                update_state('selected_db', matching_dbs[0], st.session_state.state)

# Database selector
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
            update_state('selected_db', selected_db, st.session_state.state)
            update_state('scraped_text', None, st.session_state.state)
            update_state('scraped_sections', [], st.session_state.state)
    elif len(st.session_state.state['matching_dbs']) == 1:
        if st.session_state.state['selected_db'] != st.session_state.state['matching_dbs'][0]:
            update_state('selected_db', st.session_state.state['matching_dbs'][0], st.session_state.state)
            update_state('scraped_text', None, st.session_state.state)
            update_state('scraped_sections', [], st.session_state.state)
else:
    st.warning("No matching databases found for this URL")

# Load scraped data
if url_input and st.session_state.state['selected_db'] and st.session_state.state['scraped_text'] is None:
    with st.spinner("📚 Loading scraped content..."):
        db_path = os.path.join("database", st.session_state.state['selected_db'])
        scraped_sections, scraped_text = load_scraped_sections(url_input, db_path)
        if not scraped_sections:
            st.warning(f"No matching entries found for {url_input} in {st.session_state.state['selected_db']}")
        else:
            st.success(f"Loaded {len(scraped_sections)} sections from {st.session_state.state['selected_db']}")
        update_state('scraped_sections', scraped_sections, st.session_state.state)
        update_state('scraped_text', scraped_text, st.session_state.state)

# Compare button
if st.session_state.state['scraped_text']:
    if st.button("🔍 Fetch and compare live page"):
        with st.spinner("🌐 Fetching live page content..."):
            live_html = fetch_rendered_text(url_input, return_html=True)
            update_state('live_text', fetch_rendered_text(url_input), st.session_state.state)
            update_state('live_sections', parse_live_content(live_html, url_input), st.session_state.state)
            update_state('similarity', semantic_similarity(
                st.session_state.state['scraped_text'],
                st.session_state.state['live_text']
            ), st.session_state.state)

# Display comparison results
if st.session_state.state['live_text']:
    st.success(f"Live content size: {len(st.session_state.state['live_text'])} characters")
    st.success(f"Scraped content size: {len(st.session_state.state['scraped_text'])} characters")
    
    if st.session_state.state['similarity']:
        st.metric(label="Semantic Similarity Score (0 to 1)", 
                  value=f"{st.session_state.state['similarity']:.3f}")

        sim_score = st.session_state.state['similarity']
        if sim_score > 0.95:
            st.success("✅ Excellent match")
        elif sim_score > 0.85:
            st.info("🟡 Minor differences")
        elif sim_score > 0.70:
            st.warning("🟠 Partial match")
        else:
            st.error("🔴 Poor match — consider reviewing scraped data")

        st.markdown(generate_diff_html(st.session_state.state['live_text'], 
                                      st.session_state.state['scraped_text']), 
                    unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📄 Live Website Text")
            st.text_area("Live Text Preview", st.session_state.state['live_text'], height=300)
            if st.button("🖥️ View Live Text Full Screen"):
                update_state('show_full_screen_live', True, st.session_state.state)
        with col2:
            st.subheader("📄 Scraped Text")
            st.text_area("Scraped Text Preview", st.session_state.state['scraped_text'], height=300)
            if st.button("🖥️ View Scraped Text Full Screen"):
                update_state('show_full_screen_scraped', True, st.session_state.state)

# Full-screen views
if st.session_state.state['show_full_screen_live'] and st.session_state.state['live_sections']:
    display_sections(st.session_state.state['live_sections'], 
                     "Live Website Content Details", 
                     st.session_state.state['live_sections'][0]['origin_link'])
    if st.button("Close Full Screen (Live)"):
        update_state('show_full_screen_live', False, st.session_state.state)

if st.session_state.state['show_full_screen_scraped'] and st.session_state.state['scraped_sections']:
    display_sections(st.session_state.state['scraped_sections'], 
                     "Scraped Content Details", 
                     st.session_state.state['scraped_sections'][0]['origin_link'])
    if st.button("Close Full Screen (Scraped)"):
        update_state('show_full_screen_scraped', False, st.session_state.state)