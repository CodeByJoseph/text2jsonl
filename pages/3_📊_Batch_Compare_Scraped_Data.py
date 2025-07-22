import streamlit as st
import json
import os
import pandas as pd
from utils import load_all_urls, load_scraped_text, fetch_rendered_text, semantic_similarity, get_status
from batch_processing import get_database_files, load_cached_results, save_cached_results

DATA_DIR = "database"

st.title("🔍 Batch Compare: Scraped vs Live Content")
st.markdown("Compare scraped content with live web content to detect drift or changes")


st.header("⚙️ Settings")
    
db_files = get_database_files(DATA_DIR)
db_options = ["All Databases"] + db_files
    
selected_db = st.selectbox("Select database to process", db_options)
    
# Toggle button: run or stop
if "batch_running" not in st.session_state:
    st.session_state.batch_running = False
if "stop_batch" not in st.session_state:
    st.session_state.stop_batch = False
    
col1, col2 = st.columns(2)
with col1:
    if st.button("▶️ Run", use_container_width=True):
        st.session_state.batch_running = True
        st.session_state.stop_batch = False
            
with col2:
    if st.button("🛑 Stop", use_container_width=True):
        st.session_state.stop_batch = True

# Main content area
if st.session_state.batch_running:
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    to_process = db_files if selected_db == "All Databases" else [selected_db]
    overall_results = {}
    
    total_dbs = len(to_process)
    for db_idx, db in enumerate(to_process):
        if st.session_state.stop_batch:
            st.warning(f"Batch stopped by user before processing database: {db}")
            break

        db_path = os.path.join(DATA_DIR, f"{db}.jsonl")  # Only append .jsonl once
        st.write(f"Processing: {db} → {db_path}")
        
        with st.expander(f"📦 Processing: {db}", expanded=True):
            st.write(f"Database {db_idx+1} of {total_dbs}")
            cached = load_cached_results(db)
            
            if cached is not None:
                st.info(f"Cached results loaded for {db} ({len(cached)} entries)")
                overall_results[db] = cached
                continue
            
            results = {}
            db_path = f"{DATA_DIR}/{db}.jsonl"
            
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    total_lines = sum(1 for _ in f)  # Count total lines
                    f.seek(0)  # Reset file pointer
                    
                    for line_idx, line in enumerate(f):
                        if st.session_state.stop_batch:
                            st.warning("Batch stopped by user during processing.")
                            break
                        
                        try:
                            obj = json.loads(line)
                            url = obj.get("origin_link", "")
                            scraped_content = obj.get("content", "")
                            
                            if not url:
                                continue
                            
                            if url not in results:
                                live_content = fetch_rendered_text(url)
                                
                                # Calculate progress
                                progress = (line_idx + 1) / total_lines
                                progress_bar.progress(min(progress, 1.0))
                                status_text.text(f"Processing {url} ({line_idx+1}/{total_lines})")
                                
                                if not live_content or len(live_content.strip()) < 100:
                                    results[url] = {
                                        "similarity": None,
                                        "scraped_length": len(scraped_content),
                                        "live_length": len(live_content) if live_content else 0,
                                        "status": "⚠️ Empty"
                                    }
                                else:
                                    similarity_score = semantic_similarity(scraped_content, live_content)
                                    results[url] = {
                                        "similarity": similarity_score,
                                        "scraped_length": len(scraped_content),
                                        "live_length": len(live_content),
                                        "status": get_status(similarity_score)
                                    }
                        except Exception as e:
                            st.error(f"Error processing line: {e}")
                            continue
            except Exception as e:
                st.error(f"⚠️ Error reading database file '{db_path}': {str(e)}")
                continue  # Skip this file and move to the next
            
            if not st.session_state.stop_batch:
                save_cached_results(db, results)
                st.success(f"Saved results for {db} ({len(results)} entries)")
            
            overall_results[db] = results
    
    st.session_state.batch_running = False
    st.session_state.stop_batch = False
    status_text.empty()
    
    st.success("✅ Batch processing complete!")
    
    # Display Results
    table_data = []
    for db, res in overall_results.items():
        with st.expander(f"📊 Results for {db}", expanded=True):
            for url, data in res.items():
                similarity = data.get("similarity")
                status = data.get("status")
                
                table_data.append({
                    "URL": url,
                    "Score": f"{similarity:.3f}" if similarity is not None else "N/A",
                    "Status": status,
                    "Scraped Length": data.get("scraped_length"),
                    "Live Length": data.get("live_length")
                })
    
    if table_data:
        df = pd.DataFrame(table_data)
        
        # Add color formatting
        def color_status(val):
            if val == "⚠️ Empty":
                return 'background-color: #fff3cd'
            elif "Low" in str(val):
                return 'background-color: #f8d7da'
            elif "Medium" in str(val):
                return 'background-color: #fff3cd'
            elif "High" in str(val):
                return 'background-color: #d4edda'
            return ''
        
        styled_df = df.style.applymap(color_status, subset=['Status'])
        
        st.markdown("### 📋 Comparison Results")
        st.dataframe(styled_df, use_container_width=True)
        
    else:
        st.info("No results to display")