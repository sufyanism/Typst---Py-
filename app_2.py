import io
import zipfile
import fitz  # PyMuPDF
import streamlit as st

st.set_page_config(page_title="PDF to 6x9 Typst Converter", page_icon="📐", layout="centered")

st.title("📐 PDF to 6x9 Typst Exact Match Converter")
st.markdown("Upload a PDF to instantly convert it into a 6×9 inch Typst package preserving exact layouts, precise text colors, and colorful images.")

def int_to_hex_color(color_int):
    """Converts PyMuPDF sRGB integer color to a Typst rgb hex string."""
    if color_int is None or color_int == 0:
        return None
    r = (color_int >> 16) & 255
    g = (color_int >> 8) & 255
    b = color_int & 255
    if r == 0 and g == 0 and b == 0:
        return None
    return f"rgb(\"{r:02x}{g:02x}{b:02x}\")"

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()

    if st.button("Convert to 6x9 Typst Layout"):
        with st.spinner("Extracting assets, colors, and building 6x9 layout..."):
            # Load PDF directly from memory for lightning-fast processing
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                typst_content = (
                    "// Generated via Fast 6x9 PDF-to-Typst Converter\n"
                    '#set page(width: 6in, height: 9in, margin: 0cm)\n\n'
                )
                
                images_archive = {}

                for page_idx, page in enumerate(doc):
                    page_num = page_idx + 1
                    
                    typst_content += f'// --- Page {page_num} ---\n'
                    typst_content += f'#page[\n'

                    # 1. Extract and save colorful images into assets folder
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

                    # 2. Extract Text Spans with exact coordinates, sizes, and colors
                    text_dict = page.get_text("dict", sort=True)
                    
                    for b in text_dict.get("blocks", []):
                        if b.get("type") == 0:  # Text block
                            for l in b.get("lines", []):
                                for s in l.get("spans", []):
                                    clean_text = s["text"]
                                    if not clean_text:
                                        continue

                                    x0, y0, x1, y1 = s["bbox"]
                                    font_size = s["size"]
                                    font_color_int = s.get("color", 0)
                                    
                                    # Sanitize special characters without altering words
                                    escaped_text = (
                                        clean_text.replace("\\", "\\\\")
                                        .replace("*", "\\*")
                                        .replace("_", "\\_")
                                        .replace("#", "\\#")
                                        .replace("$", "\\$")
                                        .replace("[", "\\[")
                                        .replace("]", "\\]")
                                        .replace("<", "\\u{003C}")
                                        .replace(">", "\\u{003E}")
                                    )
                                    
                                    if "@" in escaped_text and "." in escaped_text:
                                        escaped_text = escaped_text.replace("@", " [at] ")

                                    style_wrapper = escaped_text
                                    hex_color = int_to_hex_color(font_color_int)
                                    if hex_color:
                                        style_wrapper = f"#text(fill: {hex_color})[{style_wrapper}]"

                                    typst_content += (
                                        f'  #place(top + left, dx: {x0}pt, dy: {y0}pt)'
                                        f'[#text(size: {font_size}pt)[{style_wrapper}]]\n'
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

            st.success("Conversion completed successfully in seconds!")
            
            st.download_button(
                label="📥 Download 6x9 Typst Package (.zip)",
                data=zip_buffer,
                file_name="exact_6x9_typst_package.zip",
                mime="application/zip",
            )

            with st.expander("Preview Typst Code"):
                st.code(typst_content[:2000] + "\n...", language="typst")