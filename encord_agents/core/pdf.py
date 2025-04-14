from pathlib import Path

import pymupdf


def extract_page(
    pdf_path: Path,
    page_number: int,
) -> Path:
    target_file_path = pdf_path.with_name(f"{pdf_path.name}_{page_number}").with_suffix(".png")
    # Open the PDF
    doc = pymupdf.open(pdf_path)

    # Get the specified page
    page = doc[page_number]  # 0-based index
    # Render page to an image (pixmap)
    pix = page.get_pixmap()
    # Save the image
    pix.save(target_file_path)

    # Close the document
    doc.close()
    return target_file_path
