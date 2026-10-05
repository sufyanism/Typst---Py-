import io
import os
import zipfile
import fitz  # PyMuPDF
import streamlit as st

st.set_page_config(page_title="PDF to Typst Exact Layout & Style Converter", page_icon="📐", layout="centered")

st.title("📐 PDF to Typst Exact Layout & Style Converter")
st.markdown("Upload a PDF to convert it into a styled Typst package (`.zip`) preserving headings, subheadings, bullet lists, colors, and precise positions.")

def int_to_hex_color(color_int):
    """Converts PyMuPDF sRGB integer color to a Typst rgb hex string."""
    if color_int is None or color_int == 0:
        return None
    # Extract RGB components
    r = (color_int >> 16) & 255
    g = (color_int >> 8) & 255
    b = color_int & 255
    # If it's pure black or default text color, skip explicit coloring to keep clean markup
    if r == 0 and g == 0 and b == 0:
        return None
    return f"rgb(\"{r:02x}{g:02x}{b:02x}\")"

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    temp_pdf_path = "temp_uploaded.pdf"
    with open(temp_pdf_path, "wb") as f:
        f.write(pdf_bytes)

    if st.button("Convert with Exact Styles, Lists & Images"):
        with st.spinner("Analyzing layout, headings, bullets, colors, and rendering Typst package..."):
            doc = fitz.open(temp_pdf_path)
            try:
                typst_content = (
                    "// Generated via Advanced Exact-Match PDF-to-Typst Converter\n"
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

                    # 2. Extract Text Spans with deep style mapping (Headings, Bullets, Colors, Fonts)
                    text_dict = page.get_text("dict", sort=True)
                    
                    for b in text_dict.get("blocks", []):
                        if b.get("type") == 0:  # Text block
                            for l in b.get("lines", []):
                                line_text_accum = ""
                                line_styles = []
                                
                                for s in l.get("spans", []):
                                    clean_text = s["text"]
                                    if not clean_text:
                                        continue

                                    x0, y0, x1, y1 = s["bbox"]
                                    font_size = s["size"]
                                    font_flags = s["flags"] # bit 0: super, bit 1: italic, bit 4: bold
                                    font_color_int = s.get("color", 0)
                                    
                                    is_bold = bool(font_flags & 2**4)
                                    is_italic = bool(font_flags & 2**1)
                                    
                                    # Sanitize characters to protect Typst parser
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
                                    
                                    if "@" in escaped_text and "." in escaped_text:
                                        escaped_text = escaped_text.replace("@", " [at] ")

                                    # Build stylistic formatting wrapper
                                    styled_snippet = escaped_text
                                    if is_bold:
                                        styled_snippet = f"*{styled_snippet}*"
                                    if is_italic:
                                        styled_snippet = f"_{styled_snippet}_"
                                        
                                    hex_color = int_to_hex_color(font_color_int)
                                    if hex_color:
                                        styled_snippet = f"#text(fill: {hex_color})[{styled_snippet}]"

                                    # Detect Heading Level based on standard font scaling heuristics
                                    if font_size > 18:  # Large Main Heading
                                        typst_content += f'  #place(top + left, dx: {x0}pt, dy: {y0}pt)[= {styled_snippet}]\n'
                                    elif font_size > 14:  # Subheading
                                        typst_content += f'  #place(top + left, dx: {x0}pt, dy: {y0}pt)[== {styled_snippet}]\n'
                                    elif font_size > 12 and is_bold:  # Minor Section Title
                                        typst_content += f'  #place(top + left, dx: {x0}pt, dy: {y0}pt)[=== {styled_snippet}]\n'
                                    else:
                                        # Check if line acts as a bullet point item
                                        stripped_check = escaped_text.strip()
                                        if stripped_check.startswith(("•", "-", "*", "▪", "➢")) and len(stripped_check) > 1:
                                            bullet_content = stripped_check[1:].strip()
                                            typst_content += f'  #place(top + left, dx: {x0}pt, dy: {y0}pt)[#text(size: {font_size}pt)[- {bullet_content}]]\n'
                                        else:
                                            # Standard precise text mapping block
                                            typst_content += f'  #place(top + left, dx: {x0}pt, dy: {y0}pt)[#text(size: {font_size}pt)[{styled_snippet}]]\n'

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
                st.code(typst_content[:2500] + "\n...", language="typst")

    if os.path.exists(temp_pdf_path):
        try:
            os.remove(temp_pdf_path)
        except PermissionError:
            pass