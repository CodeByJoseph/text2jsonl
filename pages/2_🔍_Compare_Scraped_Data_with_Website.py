import streamlit as st
from utils import (
    fetch_rendered_text, semantic_similarity, update_state,
    parse_live_content, find_matching_databases, display_sections,
    generate_diff_html, load_scraped_sections, validate_url, fetch_pdf_text, is_pdf_url
)
import os

st.set_page_config(page_title="🧪 Compare Scraped vs Live Content", layout="wide")
st.title("🧪 Compare Scraped Content with Live Website or PDF")

# Clear fullscreen states on every script run
if 'state' in st.session_state:
    st.session_state.state['show_full_screen_scraped'] = False
    st.session_state.state['show_full_screen_live'] = False
    st.session_state.state['show_full_screen_pdf'] = False

# Initialize session state
if 'state' not in st.session_state:
    st.session_state.state = {
        'scraped_text': None,
        'live_text': None,
        'pdf_text': None,
        'pdf_sections': [],
        'similarity': None,
        'scraped_sections': [],
        'live_sections': [],
        'show_full_screen_scraped': False,
        'show_full_screen_live': False,
        'show_full_screen_pdf': False,
        'url_input': '',
        'pdf_input': '',
        'input_type': 'web',
        'matching_dbs': [],
        'selected_db': None
    }

# Input section
st.subheader("Select Input Type")
input_type = st.radio("Compare with:", ["Web Page", "PDF"], key="input_type")
if input_type != st.session_state.state['input_type']:
    update_state('input_type', input_type, st.session_state.state)
    update_state('scraped_text', None, st.session_state.state)
    update_state('live_text', None, st.session_state.state)
    update_state('pdf_text', None, st.session_state.state)
    update_state('pdf_sections', [], st.session_state.state)
    update_state('similarity', None, st.session_state.state)
    update_state('scraped_sections', [], st.session_state.state)
    update_state('live_sections', [], st.session_state.state)
    update_state('url_input', '', st.session_state.state)
    update_state('pdf_input', '', st.session_state.state)
    update_state('matching_dbs', [], st.session_state.state)
    update_state('selected_db', None, st.session_state.state)
    update_state('show_full_screen_scraped', False, st.session_state.state)
    update_state('show_full_screen_live', False, st.session_state.state)
    update_state('show_full_screen_pdf', False, st.session_state.state)

if input_type == "Web Page":
    url_input = st.text_input("Enter URL to compare scraped content with live page:",
                              value=st.session_state.state['url_input'], key="url_input")
    if url_input != st.session_state.state['url_input']:
        update_state('url_input', url_input, st.session_state.state)
        update_state('scraped_text', None, st.session_state.state)
        update_state('live_text', None, st.session_state.state)
        update_state('pdf_text', None, st.session_state.state)
        update_state('pdf_sections', [], st.session_state.state)
        update_state('similarity', None, st.session_state.state)
        update_state('scraped_sections', [], st.session_state.state)
        update_state('live_sections', [], st.session_state.state)
        update_state('matching_dbs', [], st.session_state.state)
        update_state('selected_db', None, st.session_state.state)
        update_state('show_full_screen_scraped', False, st.session_state.state)
        update_state('show_full_screen_live', False, st.session_state.state)
        update_state('show_full_screen_pdf', False, st.session_state.state)

        if url_input:
            if not validate_url(url_input):
                st.error("Please enter a valid HTTP/HTTPS URL")
            elif is_pdf_url(url_input):
                st.error("This URL points to a PDF. Please select 'PDF' as the input type.")
            else:
                with st.spinner("🔍 Searching databases for matching URL..."):
                    matching_dbs = find_matching_databases(url_input)
                    update_state('matching_dbs', matching_dbs, st.session_state.state)
                    if len(matching_dbs) == 1:
                        update_state('selected_db', matching_dbs[0], st.session_state.state)
else:
    pdf_input = st.text_input("Enter PDF URL or local path:",
                              value=st.session_state.state['pdf_input'], key="pdf_input")
    if pdf_input != st.session_state.state['pdf_input']:
        update_state('pdf_input', pdf_input, st.session_state.state)
        update_state('scraped_text', None, st.session_state.state)
        update_state('live_text', None, st.session_state.state)
        update_state('pdf_text', None, st.session_state.state)
        update_state('pdf_sections', [], st.session_state.state)
        update_state('similarity', None, st.session_state.state)
        update_state('scraped_sections', [], st.session_state.state)
        update_state('live_sections', [], st.session_state.state)
        update_state('matching_dbs', [], st.session_state.state)
        update_state('selected_db', None, st.session_state.state)
        update_state('show_full_screen_scraped', False, st.session_state.state)
        update_state('show_full_screen_live', False, st.session_state.state)
        update_state('show_full_screen_pdf', False, st.session_state.state)

        is_url = pdf_input.startswith(('http://', 'https://'))
        if is_url:
            if not validate_url(pdf_input):
                st.error("Please enter a valid HTTP/HTTPS PDF URL")
            elif not is_pdf_url(pdf_input):
                st.error("This URL does not point to a PDF. Please enter a valid PDF URL or select 'Web Page' for non-PDF URLs.")
            else:
                with st.spinner("🔍 Searching databases for matching URL..."):
                    matching_dbs = find_matching_databases(pdf_input)
                    update_state('matching_dbs', matching_dbs, st.session_state.state)
                    if len(matching_dbs) == 1:
                        update_state('selected_db', matching_dbs[0], st.session_state.state)
        elif pdf_input:
            if not os.path.exists(pdf_input):
                st.error("Please enter a valid PDF URL or existing local path")
            else:
                update_state('matching_dbs', [], st.session_state.state)
                update_state('selected_db', None, st.session_state.state)

# Database selector
if (input_type == "Web Page" and st.session_state.state['url_input'] and st.session_state.state['matching_dbs']) or \
   (input_type == "PDF" and st.session_state.state['pdf_input'] and st.session_state.state['matching_dbs']):
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
            update_state('show_full_screen_scraped', False, st.session_state.state)
            update_state('show_full_screen_live', False, st.session_state.state)
            update_state('show_full_screen_pdf', False, st.session_state.state)
    elif len(st.session_state.state['matching_dbs']) == 1:
        if st.session_state.state['selected_db'] != st.session_state.state['matching_dbs'][0]:
            update_state('selected_db', st.session_state.state['matching_dbs'][0], st.session_state.state)
            update_state('scraped_text', None, st.session_state.state)
            update_state('scraped_sections', [], st.session_state.state)
            update_state('show_full_screen_scraped', False, st.session_state.state)
            update_state('show_full_screen_live', False, st.session_state.state)
            update_state('show_full_screen_pdf', False, st.session_state.state)

else:
    if input_type == "Web Page" and st.session_state.state['url_input'] and validate_url(st.session_state.state['url_input']):
        st.warning("No matching databases found for this URL")
    elif input_type == "PDF" and st.session_state.state['pdf_input'] and st.session_state.state['pdf_input'].startswith(('http://', 'https://')):
        st.warning("No matching databases found for this PDF URL")

# Load scraped data
if (input_type == "Web Page" and st.session_state.state['url_input'] and st.session_state.state['selected_db']) or \
   (input_type == "PDF" and st.session_state.state['pdf_input'] and st.session_state.state['matching_dbs'] and st.session_state.state['selected_db']):
    if st.session_state.state['scraped_text'] is None:
        with st.spinner("📚 Loading scraped content..."):
            db_path = os.path.join("database", st.session_state.state['selected_db'])
            try:
                scraped_sections, scraped_text = load_scraped_sections(
                    st.session_state.state['url_input'] if input_type == "Web Page" else st.session_state.state['pdf_input'],
                    db_path
                )
                if not scraped_sections:
                    st.warning(f"No matching entries found in {st.session_state.state['selected_db']}")
                else:
                    st.success(f"Loaded {len(scraped_sections)} sections from {st.session_state.state['selected_db']}")
                update_state('scraped_sections', scraped_sections, st.session_state.state)
                update_state('scraped_text', scraped_text, st.session_state.state)
                update_state('show_full_screen_scraped', False, st.session_state.state)
                update_state('show_full_screen_live', False, st.session_state.state)
                update_state('show_full_screen_pdf', False, st.session_state.state)
            except Exception as e:
                st.error(f"Failed to load scraped data: {str(e)}")


# Compare button
if st.session_state.state['scraped_text'] or (input_type == "PDF" and st.session_state.state['pdf_input']):
    if st.button(f"🔍 Fetch and compare {'live page' if input_type == 'Web Page' else 'PDF content'}", key="compare_button"):
        with st.spinner(f"🌐 Fetching {'live page' if input_type == 'Web Page' else 'PDF'} content..."):
            update_state('show_full_screen_scraped', False, st.session_state.state)
            update_state('show_full_screen_live', False, st.session_state.state)
            update_state('show_full_screen_pdf', False, st.session_state.state)
            if input_type == "Web Page":
                live_html = fetch_rendered_text(st.session_state.state['url_input'], return_html=True)
                if not live_html:
                    st.error("Failed to fetch live page content")
                else:
                    update_state('live_text', fetch_rendered_text(st.session_state.state['url_input']), st.session_state.state)
                    update_state('live_sections', parse_live_content(live_html, st.session_state.state['url_input']), st.session_state.state)
                    update_state('pdf_text', None, st.session_state.state)
                    update_state('pdf_sections', [], st.session_state.state)
                    if st.session_state.state['scraped_text']:
                        update_state('similarity', semantic_similarity(
                            st.session_state.state['scraped_text'],
                            st.session_state.state['live_text']
                        ), st.session_state.state)
            else:
                is_url = st.session_state.state['pdf_input'].startswith(('http://', 'https://'))
                result = fetch_pdf_text(st.session_state.state['pdf_input'], is_url=is_url)
                if result is None:
                    st.error("Failed to extract text from PDF")
                    try:
                        with open("logs/fetch_errors.log", 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            if lines:
                                st.write(f"Debug: Last error: {lines[-1].strip()}")
                    except Exception as e:
                        st.write(f"Debug: Could not read error log: {str(e)}")
                else:
                    pdf_text, pdf_sections = result
                    update_state('pdf_text', pdf_text, st.session_state.state)
                    update_state('pdf_sections', pdf_sections, st.session_state.state)
                    update_state('live_text', None, st.session_state.state)
                    update_state('live_sections', [], st.session_state.state)
                    if st.session_state.state['scraped_text']:
                        update_state('similarity', semantic_similarity(
                            st.session_state.state['scraped_text'],
                            st.session_state.state['pdf_text']
                        ), st.session_state.state)
                    else:
                        st.warning("No scraped data available for comparison, displaying PDF text only")
                        update_state('similarity', None, st.session_state.state)

# Display comparison results only if not in fullscreen mode
if not any([st.session_state.state['show_full_screen_scraped'], 
            st.session_state.state['show_full_screen_live'], 
            st.session_state.state['show_full_screen_pdf']]):
    if st.session_state.state['live_text'] or st.session_state.state['pdf_text']:
        comparison_text = st.session_state.state['live_text'] if input_type == "Web Page" else st.session_state.state['pdf_text']
        comparison_sections = st.session_state.state['live_sections'] if input_type == "Web Page" else st.session_state.state['pdf_sections']
        st.success(f"{'Live' if input_type == 'Web Page' else 'PDF'} content size: {len(comparison_text)} characters")
        if comparison_sections:
            st.success(f"{'Live' if input_type == 'Web Page' else 'PDF'} sections: {len(comparison_sections)}")
        if st.session_state.state['scraped_text']:
            st.success(f"Scraped content size: {len(st.session_state.state['scraped_text'])} characters")
            st.success(f"Scraped sections: {len(st.session_state.state['scraped_sections'])}")

        if st.session_state.state['similarity'] is not None:
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

            st.markdown(generate_diff_html(comparison_text,
                                          st.session_state.state['scraped_text']),
                        unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"📄 {'Live Website' if input_type == 'Web Page' else 'PDF'} Text")
            st.text_area(f"{'Live' if input_type == 'Web Page' else 'PDF'} Text Preview",
                         comparison_text, height=300, key="preview_text_comparison")
            if st.button(f"🖥️ {'View Full Screen' if not st.session_state.state['show_full_screen_' + ('live' if input_type == 'Web Page' else 'pdf')] else 'Close Full Screen'} ({'Live' if input_type == 'Web Page' else 'PDF'})", key="fullscreen_button_comparison"):
                update_state('show_full_screen_' + ('live' if input_type == 'Web Page' else 'pdf'), not st.session_state.state['show_full_screen_' + ('live' if input_type == 'Web Page' else 'pdf')], st.session_state.state)
                update_state('show_full_screen_scraped', False, st.session_state.state)
                update_state('show_full_screen_' + ('pdf' if input_type == 'Web Page' else 'live'), False, st.session_state.state)
        with col2:
            st.subheader("📄 Scraped Text")
            st.text_area("Scraped Text Preview",
                         st.session_state.state['scraped_text'] or "No scraped text available",
                         height=300, key="preview_text_scraped")
            if st.button(f"🖥️ {'View Full Screen' if not st.session_state.state['show_full_screen_scraped'] else 'Close Full Screen'} (Scraped)", key="fullscreen_button_scraped"):
                update_state('show_full_screen_scraped', not st.session_state.state['show_full_screen_scraped'], st.session_state.state)
                update_state('show_full_screen_live', False, st.session_state.state)
                update_state('show_full_screen_pdf', False, st.session_state.state)

# Fullscreen view (exclusive)
if any([st.session_state.state['show_full_screen_scraped'], 
        st.session_state.state['show_full_screen_live'], 
        st.session_state.state['show_full_screen_pdf']]):
    if 'fullscreen_rendered' not in st.session_state:
        st.session_state.fullscreen_rendered = False
    if not st.session_state.fullscreen_rendered:
        with st.container():
            st.markdown("<h2 style='text-align: center;'>Fullscreen Content</h2>", unsafe_allow_html=True)
            if st.session_state.state['show_full_screen_scraped'] and st.session_state.state['scraped_sections']:
                display_sections(st.session_state.state['scraped_sections'],
                                "Scraped Content Details",
                                st.session_state.state['scraped_sections'][0]['origin_link'])
                if st.button("Close Full Screen (Scraped)", key="close_fullscreen_scraped"):
                    update_state('show_full_screen_scraped', False, st.session_state.state)
            elif st.session_state.state['show_full_screen_live'] and st.session_state.state['live_sections'] and input_type == "Web Page":
                display_sections(st.session_state.state['live_sections'],
                                "Live Website Content Details",
                                st.session_state.state['live_sections'][0]['origin_link'])
                if st.button("Close Full Screen (Live)", key="close_fullscreen_live"):
                    update_state('show_full_screen_live', False, st.session_state.state)
            elif st.session_state.state['show_full_screen_pdf'] and (st.session_state.state['pdf_text'] or st.session_state.state['pdf_sections']) and input_type == "PDF":
                if st.session_state.state['pdf_sections']:
                    display_sections(st.session_state.state['pdf_sections'],
                                    "PDF Content Details",
                                    st.session_state.state['pdf_sections'][0]['origin_link'])
                else:
                    st.write(st.session_state.state['pdf_text'])
                st.markdown("#### Metadata")
                st.write(f"**Source**: {st.session_state.state['pdf_input']}")
                if st.button("Close Full Screen (PDF)", key="close_fullscreen_pdf"):
                    update_state('show_full_screen_pdf', False, st.session_state.state)
            st.session_state.fullscreen_rendered = True
else:
    if 'fullscreen_rendered' in st.session_state:
        st.session_state.fullscreen_rendered = False