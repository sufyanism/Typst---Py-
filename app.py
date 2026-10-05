import io
import os
import zipfile
import fitz  # PyMuPDF
import streamlit as st

st.set_page_config(page_title="PDF to Typst Exact Layout Converter", page_icon="📐", layout="centered")

st.title("📐 PDF to Typst Exact Layout Converter")
st.markdown("Upload a PDF to convert it into a robust Typst package (`.zip`) with precise font sizing and layout positioning.")

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    temp_pdf_path = "temp_uploaded.pdf"
    with open(temp_pdf_path, "wb") as f:
        f.write(pdf_bytes)

    if st.button("Convert with Exact Layout & Images"):
        with st.spinner("Extracting assets, precise font styles, and building Typst layout..."):
            doc = fitz.open(temp_pdf_path)
            try:
                typst_content = (
                    "// Generated via Exact-Coordinate PDF-to-Typst Converter\n"
                    '#set page(paper: "a4", margin: 0cm)\n\n'
                )
                
                images_archive = {}

                for page_idx, page in enumerate(doc):
                    page_num = page_idx + 1
                    rect = page.rect
                    page_w, page_h = rect.width, rect.height
                    
                    typst_content += f'// --- Page {page_num} ---\n'
                    typst_content += f'#page(width: {page_w}pt, height: {page_h}pt)[\n'

                    # 1. Extract and save embedded images into assets folder
                    image_list = page.get_images(full=True)
                    for img_idx, img in enumerate(image_list):
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        img_filename = f"assets/img_p{page_num}_{img_idx}.{image_ext}"
                        images_archive[img_filename] = image_bytes

                        img_rects = page.get_image_rects(xref)
                        for r in img_rects:
                            typst_content += (
                                f'  #place(top + left, dx: {r.x0}pt, dy: {r.y0}pt, '
                                f'image("{img_filename}", width: {r.width}pt, height: {r.height}pt))\n'
                            )

                    # 2. Extract Text Spans for exact font size, styling, and positioning
                    text_dict = page.get_text("dict", sort=True)
                    for b in text_dict.get("blocks", []):
                        if b.get("type") == 0:  # Text block
                            for l in b.get("lines", []):
                                for s in l.get("spans", []):
                                    clean_text = s["text"].strip()
                                    if not clean_text:
                                        continue

                                    x0, y0, x1, y1 = s["bbox"]
                                    font_size = s["size"]

                                    # Sanitize text to prevent syntax crashes in Typst
                                    escaped_text = (
                                        clean_text.replace("\\", "\\\\")
                                        .replace("*", "\\*")
                                        .replace("_", "\\_")
                                        .replace("#", "\\#")
                                        .replace("$", "\\$")
                                        .replace("[", "\\[")                                         .replace("]", "\\]")
                                        .replace("<", "\\u{003C}")
                                        .replace(">", "\\u{003E}")
                                    )
                                    
                                    # Neutralize email addresses if needed
                                    if "@" in escaped_text and "." in escaped_text:
                                        escaped_text = escaped_text.replace("@", " [at] ")

                                    # Place each span with its exact font size and coordinates
                                    typst_content += (
                                        f'  #place(top + left, dx: {x0}pt, dy: {y0}pt)'
                                        f'[#text(size: {font_size}pt)[{escaped_text}]]\n'
                                    )

                    typst_content += "]\n#pagebreak()\n"

            finally:
                doc.close()

            # 3. Bundle everything into an in-memory ZIP package
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr("exact_document.typ", typst_content)
                for img_name, img_bytes in images_archive.items():
                    zip_file.writestr(img_name, img_bytes)
            
            zip_buffer.seek(0)

            st.success("Conversion completed successfully!")
            
            st.download_button(
                label="📥 Download Typst Package (.zip)",
                data=zip_buffer,
                file_name="exact_typst_package.zip",
                mime="application/zip",
            )

            with st.expander("Preview Typst Code"):
                st.code(typst_content[:2000] + "\n...", language="typst")

    if os.path.exists(temp_pdf_path):
        try:
            os.remove(temp_pdf_path)
        except PermissionError:
            pass