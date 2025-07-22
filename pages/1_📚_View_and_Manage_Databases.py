import streamlit as st
import os
import json
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="📚 Manage Databases", layout="wide")
st.title("📚 Manage JSONL Databases")

# Initialize session state for error details
if 'error_details' not in st.session_state:
    st.session_state.error_details = None

# Database directory setup
database_dir = "database"
Path(database_dir).mkdir(exist_ok=True)

# List all .jsonl files
jsonl_files = [f for f in os.listdir(database_dir) if f.endswith(".jsonl")]

if not jsonl_files:
    st.info("No .jsonl files found in the database folder.")
else:
    st.subheader("📂 Select a JSONL file to view:")
    selected_file = st.selectbox("", jsonl_files)
    file_path = os.path.join(database_dir, selected_file)

    # Error handling options
    error_options = st.expander("🔍 Error Handling Options", expanded=False)
    with error_options:
        show_raw = st.checkbox("Show raw file content for debugging")
        show_validation = st.checkbox("Show file validation details")
        show_repair = st.checkbox("🔧 Show repair options")

    if st.button("📖 Load and display"):
        try:
            with st.spinner("Loading file..."):
                data = []
                errors = []
                
                # Process file line by line
                with open(file_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        if not line.strip():
                            continue  # Skip empty lines
                        
                        try:
                            data.append(json.loads(line))
                        except json.JSONDecodeError as je:
                            errors.append({
                                "line": line_num,
                                "char_pos": je.pos,
                                "error_type": "JSONDecodeError",
                                "message": str(je),
                                "line_preview": line[:100] + "..." if len(line) > 100 else line
                            })
                        except Exception as e:
                            errors.append({
                                "line": line_num,
                                "error_type": type(e).__name__,
                                "message": str(e),
                                "line_preview": line[:100] + "..." if len(line) > 100 else line
                            })
                
                # Store error details in session state
                st.session_state.error_details = {
                    "file": selected_file,
                    "errors": errors,
                    "valid_entries": data
                }
                
                # Display results
                if errors:
                    st.warning(f"Loaded file with {len(errors)} errors. Only valid entries are shown.")
                    st.markdown("### ❌ Error Details")
                    
                    # Error summary table
                    error_df = pd.DataFrame(errors)
                    st.dataframe(error_df, use_container_width=True)
                    
                    # Detailed error display
                    for error in errors:
                        st.markdown(f"""
                        **Error on line {error['line']}**  
                        Type: `{error['error_type']}`  
                        Message: `{error['message']}`  
                        Line preview: `{error['line_preview']}`
                        """)
                    
                    # Repair option
                    if show_repair:
                        st.markdown("### 🔧 Repair Options")
                        if st.button("Create Clean File"):
                            repaired_path = os.path.join(database_dir, f"{selected_file}.repaired")
                            with open(repaired_path, "w", encoding="utf-8") as f:
                                for item in data:
                                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                            st.success(f"✅ Clean file created at: {repaired_path}")
                            st.info("You can now load the repaired version")
                else:
                    df = pd.DataFrame(data)
                    st.success(f"✅ Successfully loaded {len(df)} valid entries from {selected_file}")
                    st.dataframe(df, use_container_width=True)

                    # Download button
                    if st.download_button("⬇️ Download as JSONL", 
                                       data=open(file_path, "rb"), 
                                       file_name=selected_file):
                        st.toast("Download started!")
                    
        except Exception as e:
            st.error(f"🚨 Unexpected error loading file: {e}")
            st.exception(e)  # Show full traceback in development

    # Show raw content if requested
    if show_raw and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            st.markdown("### 🔍 Raw File Content")
            st.code(f.read(2000) + "...", language="json")
    
    # File validation details
    if show_validation and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            file_size = os.path.getsize(file_path) / 1024  # in KB
            line_count = sum(1 for _ in f)
            f.seek(0)
            first_lines = ''.join(next(f) for x in range(3))
            
        st.info(f"""
        **File Validation Details**  
        - File: {selected_file}  
        - Size: {file_size:.2f} KB  
        - Total lines: {line_count}  
        - First 3 lines preview:  
        ```json
        {first_lines}...
        ```
        """)

# Deletion section
st.markdown("---")
st.subheader("🗑️ Delete one or more databases")
to_delete = st.multiselect("Select database(s) to delete:", jsonl_files)

if to_delete:
    if st.button("🗑️ Delete selected database(s)"):
        for db in to_delete:
            try:
                os.remove(os.path.join(database_dir, db))
                st.success(f"✅ Deleted: {db}")
            except Exception as e:
                st.error(f"❌ Failed to delete {db}: {e}")
        st.experimental_rerun()  # Refresh the page to update the file list

# Debug section
if st.session_state.error_details and st.session_state.error_details.get("errors"):
    if st.checkbox("Show error summary in sidebar"):
        with st.sidebar:
            st.markdown("### ❌ Last Error Summary")
            for error in st.session_state.error_details["errors"]:
                st.markdown(f"Line {error['line']}: {error['message'][:50]}...")