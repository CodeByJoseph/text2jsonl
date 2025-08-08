import streamlit as st
from datetime import datetime

# Fixed prompt text
PROMPT_TEXT = """Follow these instructions:
1. Convert to JSONL with chunks of 250-300 tokens and 10-20% overlap
2. Preserve EXACT original formatting: Markdown headers (##/###), bullet styles, whitespace
3. Chunking rules:
   - Split only at section/subsection boundaries
   - Never break mid-sentence or mid-list
   - If section >300 tokens, split at sub-header boundaries
4. Overlap must include:
   - Last complete sentence of current chunk
   - Next section header
   - First complete sentence of next section
5. Tags: Generate 5-8 Swedish topic tags per chunk
6. Validation:
   a) Calculate token counts using GPT-4 tokenizer
   b) Verify 250 ≤ tokens ≤ 300 for all chunks
   c) Confirm 10% ≤ overlap ≤ 20% between chunks
   d) Abort and re-process if validation fails
7. Structure:
{"document": "Title", "text": "Original formatted text", "tags": ["svenska","taggar"], "origin_link": "URL", "external_link": [], "last_updated": "YYYY-MM-DD"}
8. Return JSONL with each line as a separate chunk
9. Answer these questions:
   a) How many tokens does each chunk have?
   b) How much overlapping are there between chunks?"""

def main():
    st.title("Text Processor")
    st.subheader("Prepare text with metadata")
    
    # Document name input
    document_name = st.text_input(
        "Document Name:", 
        placeholder="e.g., N1COS Datavetenskapligt program"
    )
    
    # Input fields
    col1, col2 = st.columns(2)
    with col1:
        origin_link = st.text_input("Origin Link:", placeholder="https://example.com")
    with col2:
        # Get date and format as YYYY-MM-DD
        date_value = st.date_input("Last Updated:", value=datetime.today())
        formatted_date = date_value.strftime("%Y-%m-%d")
    
    # Text input area
    text_content = st.text_area(
        "Text Content:", 
        height=300,
        placeholder="Paste your text here and edit as needed"
    )
    
    # Generate copy payload
    if st.button("Generate Copy Payload"):
        if not document_name or not origin_link or not text_content:
            st.warning("Please fill in Document Name, Origin Link, and Text Content")
        else:
            copy_payload = (
                f"{text_content}\n\n"
                f"document_name: \"{document_name}\"\n"
                f"origin_link: \"{origin_link}\"\n"
                f"last_updated: \"{formatted_date}\"\n"
                f"prompt: \"{PROMPT_TEXT}\""
            )
            st.session_state.copy_payload = copy_payload
            st.success("Payload generated! Scroll down to copy")
    
    # Display copyable data if generated
    if 'copy_payload' in st.session_state:
        st.divider()
        st.subheader("Copy Payload")
        st.code(st.session_state.copy_payload, language="text")
        
        # Add copy button using HTML hack
        st.markdown(f"""
        <button onclick="navigator.clipboard.writeText(`{st.session_state.copy_payload.replace('`', '\\`').replace('"', '&quot;')}`)">Copy to Clipboard</button>
        <span style="color:green; margin-left:10px" id="copy-confirm"></span>
        <script>
            document.querySelector("button").addEventListener("click", function() {{
                document.getElementById("copy-confirm").innerText = "Copied!";
                setTimeout(function(){{ 
                    document.getElementById("copy-confirm").innerText = ""; 
                }}, 2000);
            }});
        </script>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()