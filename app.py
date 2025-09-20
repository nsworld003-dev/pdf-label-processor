import streamlit as st
import fitz  # PyMuPDF
from collections import defaultdict
import io
import zipfile

# --- YOUR CLASSIFICATION RULES ---
# You can edit these rules directly in this file
categories = {
    "Black": {
        "include": ["black", "maverix"],
        "exclude": ["neck", "neckband", "cable", "uv", "holder", "case", "cover", "sticker", "watch"]
    },
    "Case Black": { "include": ["case", "black"], "all_required": True },
    "Case White": { "include": ["case", "white"], "all_required": True },
    "Cable": { "include": ["cable"] },
    "W STICKER": { "include": ["uv", "sticker"], "and_also": ["white"] },
    "BSTICKER": { "include": ["uv", "sticker"], "and_also": ["black"] },
    "White": {
        "include": ["white"],
        "exclude": ["neck", "neckband", "cable", "uv", "holder", "case", "cover", "sticker", "watch"]
    },
    "Neckband": { "include": ["neck"] },
    "Holder": { "include": ["hold"] },
    "Grey Wired": { "include": ["grey", "wired"] },
    "Black and grey": { "include": ["black", "grey"], "all_required": True },
    "t800 watch": { "include": ["watch"] },
    "MAP buds": { "include": ["map"] },
    "CABLEWHITE": { "include": ["white", "cable"], "all_required": True },
    "WIREBLACK": { "include": ["black", "wire"], "all_required": True },
    "GREY AND WHITE COMBO": {
        "include": ["white", "grey", "combo"],
        "all_required": True,
        "exclude": ["whiteandgreycombo"],
    },
    "GREY AND Black COMBO": { "include": ["whiteandgreycombo"] },
    "KAPDA BLACK": { "include": ["blackvdltch3nd"] },
}

# --- STREAMLIT WEB INTERFACE ---
st.set_page_config(layout="centered", page_title="PDF Label Processor")

st.title("📄 Smart Label Processor")
st.write("Upload your PDF manifests to automatically sort and format shipping labels for your 3x5 thermal printer.")

# Updated to allow multiple file uploads
uploaded_pdfs = st.file_uploader("Upload your PDF files", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    total_files = len(uploaded_pdfs)
    st.success(f"{total_files} file(s) uploaded successfully.")
    
    if st.button(f"Process All {total_files} Files", type="primary"):
        
        master_output_pages = defaultdict(list)

        with st.spinner("Analyzing pages from all files..."):
            # 1. Loop through each uploaded file to classify pages
            for uploaded_file in uploaded_pdfs:
                pdf_bytes = uploaded_file.getvalue()
                source_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                for page_num in range(len(source_doc)):
                    page = source_doc.load_page(page_num)
                    text = page.get_text().lower()
                    assigned = False
                    for cat, rules in categories.items():
                        include = rules.get("include", [])
                        exclude = rules.get("exclude", [])
                        all_required = rules.get("all_required", False)
                        and_also = rules.get("and_also", [])

                        match = False
                        if all_required:
                            if all(w in text for w in include) and not any(w in text for w in exclude):
                                match = True
                        elif and_also:
                            if any(w in text for w in include) and all(a in text for a in and_also):
                                match = True
                        else:
                            if any(w in text for w in include) and not any(w in text for w in exclude):
                                match = True

                        if match:
                            # Store the source file bytes and page number
                            master_output_pages[cat].append((pdf_bytes, page_num))
                            assigned = True
                            break
                    if not assigned:
                        master_output_pages["Mix"].append((pdf_bytes, page_num))

        with st.spinner("Formatting labels and creating final PDFs..."):
            # 2. Create the final PDFs from the master list of pages
            final_pdfs = {}

            # Define final output dimensions
            final_width = 3 * 72
            final_height = 5 * 72
            capture_height = 5.5 * 72
            capture_width = 3.4 * 72

            for cat, pages_info in master_output_pages.items():
                if not pages_info:
                    continue

                final_doc = fitz.open()

                for pdf_bytes, page_num in pages_info:
                    source_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    source_page = source_doc.load_page(page_num)

                    page_width = source_page.rect.width
                    x_offset = (page_width - capture_width) / 2
                    source_rect = fitz.Rect(x_offset, 0, x_offset + capture_width, capture_height)

                    new_page = final_doc.new_page(width=final_width, height=final_height)

                    source_aspect = source_rect.width / source_rect.height
                    target_aspect = final_width / final_height
                    
                    if source_aspect > target_aspect:
                        dest_width, dest_height = final_width, final_width / source_aspect
                    else:
                        dest_width, dest_height = final_height * source_aspect, final_height

                    dest_x_offset = (final_width - dest_width) / 2
                    dest_y_offset = (final_height - dest_height) / 2
                    dest_rect = fitz.Rect(dest_x_offset, dest_y_offset, dest_x_offset + dest_width, dest_y_offset + dest_height)

                    new_page.show_pdf_page(dest_rect, source_doc, page_num, clip=source_rect, rotate=0)

                final_pdfs[f"{cat}.pdf"] = final_doc.write()
                final_doc.close()

        st.balloons()
        st.header("✅ Processing Complete!")

        # 3. Zip all processed PDFs together for a single download
        if final_pdfs:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for filename, data in final_pdfs.items():
                    zf.writestr(filename, data)
            
            st.download_button(
                label="📥 Download All Labels (.zip)",
                data=zip_buffer.getvalue(),
                file_name="processed_labels.zip",
                mime="application/zip",
            )
        else:
            st.warning("No labels were categorized across all uploaded files.")

