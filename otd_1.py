import io
import zipfile
import fitz  # PyMuPDF
import streamlit as st

# Optional check for ODT handling via odfpy
try:
    from odf import text as odf_text, teletype
    from odf.opendocument import load as load_odt
    HAS_ODF = True
except ImportError:
    HAS_ODF = False

st.set_page_config(page_title="PDF & ODT to Typst Exact Converter", page_icon="📐", layout="centered")

st.title("📐 PDF & ODT to Typst Exact Converter")
st.markdown("Upload a **PDF** or **ODT** file to convert it into a Typst package with native adjustable page dimensions, bold headings, precise colors, and colorful images.")

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

def parse_odt_to_typst(odt_bytes):
    """Parses an ODT file and builds a flexible flowing Typst representation."""
    if not HAS_ODF:
        return "// ODT support requires 'odfpy'. Please install it using: pip install odfpy\n"
    
    f = io.BytesIO(odt_bytes)
    doc = load_odt(f)
    paragraphs = doc.getElementsByType(odf_text.P)
    
    typst_out = (
        "// Generated via ODT-to-Typst Converter\n"
        '#set page(paper: "a4", margin: 2cm)\n\n'
    )
    
    for p in paragraphs:
        text_content = teletype.extractText(p)
        if text_content.strip():
            escaped = (
                text_content.replace("\\", "\\\\")
                .replace("*", "\\*")
                .replace("_", "\\_")
                .replace("#", "\\#")
                .replace("$", "\\$")
                .replace("/", "\\u{002F}")
            )
            typst_out += f"{escaped}\n\n"
            
    return typst_out

uploaded_file = st.file_uploader("Choose a file", type=["pdf", "odt"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    file_name = uploaded_file.name.lower()
    file_ext = file_name.split(".")[-1]

    if st.button("Convert with Bold Headings & Native Layout"):
        with st.spinner(f"Processing {file_ext.upper()} file with bold headings..."):
            zip_buffer = io.BytesIO()
            
            if file_ext == "pdf":
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                try:
                    typst_content = (
                        "// Generated via Dynamic Native-Size PDF-to-Typst Converter\n"
                        '#set page(margin: 0cm)\n\n'
                    )
                    
                    images_archive = {}

                    for page_idx, page in enumerate(doc):
                        page_num = page_idx + 1
                        rect = page.rect
                        page_w, page_h = rect.width, rect.height
                        
                        typst_content += f'// --- Page {page_num} ---\n'
                        typst_content += f'#page(width: {page_w}pt, height: {page_h}pt)[\n'

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

                        # 2. Extract Text Spans with exact native coordinates, colors, and bold headings
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
                                        font_flags = s.get("flags", 0)
                                        font_name = s.get("font", "").lower()
                                        font_color_int = s.get("color", 0)
                                        
                                        # Detect if span is bold or a heading (via flags, font name, or larger font size threshold)
                                        is_bold = bool(font_flags & 2**4) or ("bold" in font_name) or (font_size > 14.0)

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
                                            .replace("/", "\\u{002F}")
                                        )
                                        
                                        if "@" in escaped_text and "." in escaped_text:
                                            escaped_text = escaped_text.replace("@", " [at] ")

                                        style_wrapper = escaped_text
                                        if is_bold:
                                            style_wrapper = f"*{style_wrapper}*"

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

                # Bundle into ZIP package
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    zip_file.writestr("exact_document.typ", typst_content)
                    for img_name, img_bytes in images_archive.items():
                        zip_file.writestr(img_name, img_bytes)

            elif file_ext == "odt":
                typst_content = parse_odt_to_typst(file_bytes)
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    zip_file.writestr("document.typ", typst_content)

            zip_buffer.seek(0)

            st.success(f"Successfully converted {file_ext.upper()} with native layout and bold headings!")
            
            st.download_button(
                label="📥 Download Typst Package (.zip)",
                data=zip_buffer,
                file_name="converted_typst_package.zip",
                mime="application/zip",
            )

            with st.expander("Preview Typst Code"):
                st.code(typst_content[:2000] + "\n...", language="typst")