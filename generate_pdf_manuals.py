"""
PDF Manual Generator for Metal Spinning CNC Controller
=======================================================
Converts Markdown manuals to PDF documents with images.

INSTALL:
    pip install fpdf2

USAGE:
    python generate_pdf_manuals.py
"""

import os
import re
from pathlib import Path
from fpdf import FPDF

# Configuration
MANUAL_DIR = Path(__file__).parent
MANUALS = [
    ("Manual_Technical.md", "Manual_Technical.pdf", "Technical Manual"),
    ("Manual_Developer.md", "Manual_Developer.pdf", "Developer Manual"),
    ("Manual_Operator.md", "Manual_Operator.pdf", "Operator Manual"),
]

# Unicode to ASCII replacements
UNICODE_REPLACEMENTS = {
    '•': '*',
    '→': '->',
    '←': '<-',
    '▶': '>',
    '◀': '<',
    '▼': 'v',
    '▲': '^',
    '✅': '[OK]',
    '✓': '[x]',
    '✗': '[!]',
    '☑': '[x]',
    '☐': '[ ]',
    '⚠️': '[!]',
    '⛔': '[X]',
    '─': '-',
    '│': '|',
    '┌': '+',
    '┐': '+',
    '└': '+',
    '┘': '+',
    '├': '+',
    '┤': '+',
    '┬': '+',
    '┴': '+',
    '┼': '+',
    '█': '#',
    '░': '.',
    '═': '=',
    '║': '|',
    '╔': '+',
    '╗': '+',
    '╚': '+',
    '╝': '+',
    '╠': '+',
    '╣': '+',
    '╦': '+',
    '╩': '+',
    '╬': '+',
    '└─>': '-->',
    '├─>': '-->',
    '◄': '<',
    '►': '>',
}


def clean_unicode(text: str) -> str:
    """Replace unicode characters with ASCII equivalents."""
    for unicode_char, ascii_char in UNICODE_REPLACEMENTS.items():
        text = text.replace(unicode_char, ascii_char)
    # Remove any remaining non-ASCII characters
    return ''.join(c if ord(c) < 256 else '?' for c in text)


class PDFManual(FPDF):
    """Custom PDF class for manuals."""
    
    def __init__(self, title):
        super().__init__()
        self.title_text = title
        self.set_auto_page_break(auto=True, margin=20)
        
    def header(self):
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'Metal Spinning CNC Controller', align='C')
        self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')
    
    def chapter_title(self, title, level=1):
        title = clean_unicode(title)
        
        if level == 1:
            self.set_font('Helvetica', 'B', 18)
            self.set_text_color(26, 82, 118)
        elif level == 2:
            self.set_font('Helvetica', 'B', 14)
            self.set_text_color(40, 116, 166)
        else:
            self.set_font('Helvetica', 'B', 12)
            self.set_text_color(52, 152, 219)
        
        self.ln(5)
        self.multi_cell(0, 8, title)
        
        if level <= 2:
            self.set_draw_color(40, 116, 166)
            self.line(10, self.get_y(), 200, self.get_y())
        
        self.ln(3)
        self.set_text_color(0, 0, 0)
        
    def body_text(self, text):
        text = clean_unicode(text)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, text)
        self.ln(2)
    
    def code_block(self, code):
        code = clean_unicode(code)
        self.set_font('Courier', '', 9)
        self.set_fill_color(240, 240, 240)
        self.multi_cell(0, 5, code, fill=True)
        self.ln(3)
        
    def add_table(self, headers, rows):
        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(26, 82, 118)
        self.set_text_color(255, 255, 255)
        
        col_width = 190 / len(headers)
        
        for header in headers:
            header = clean_unicode(header)[:20]
            self.cell(col_width, 8, header, border=1, fill=True, align='C')
        self.ln()
        
        self.set_font('Helvetica', '', 9)
        self.set_text_color(0, 0, 0)
        
        fill = False
        for row in rows:
            if fill:
                self.set_fill_color(245, 245, 245)
            else:
                self.set_fill_color(255, 255, 255)
            
            for cell in row:
                cell_text = clean_unicode(str(cell))[:25]
                self.cell(col_width, 7, cell_text, border=1, fill=True)
            self.ln()
            fill = not fill
        
        self.ln(3)
    
    def add_image_safe(self, img_path, base_path):
        """Add image if it exists."""
        full_path = base_path / img_path
        if full_path.exists():
            try:
                page_width = 190
                self.image(str(full_path), x=10, w=page_width)
                self.ln(5)
            except Exception as e:
                self.body_text(f"[Image: {img_path}]")
        else:
            self.body_text(f"[Image not found: {img_path}]")


def parse_markdown_to_pdf(md_content: str, pdf: PDFManual, base_path: Path):
    """Parse markdown and add to PDF."""
    
    lines = md_content.split('\n')
    in_code_block = False
    code_buffer = []
    in_table = False
    table_headers = []
    table_rows = []
    
    for line in lines:
        # Handle code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                pdf.code_block('\n'.join(code_buffer))
                code_buffer = []
            in_code_block = not in_code_block
            continue
        
        if in_code_block:
            code_buffer.append(line)
            continue
        
        # Handle tables
        if '|' in line and line.strip().startswith('|'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            
            if all(c.replace('-', '').replace(':', '') == '' for c in cells):
                continue
            
            if not in_table:
                in_table = True
                table_headers = cells
            else:
                table_rows.append(cells)
            continue
        else:
            if in_table:
                if table_headers and table_rows:
                    pdf.add_table(table_headers, table_rows)
                table_headers = []
                table_rows = []
                in_table = False
        
        # Handle headers
        if line.startswith('# '):
            if pdf.page_no() > 0:
                pdf.add_page()
            pdf.chapter_title(line[2:].strip(), 1)
        elif line.startswith('## '):
            pdf.chapter_title(line[3:].strip(), 2)
        elif line.startswith('### '):
            pdf.chapter_title(line[4:].strip(), 3)
        
        # Handle images
        elif '![' in line:
            match = re.search(r'!\[.*?\]\((.+?)\)', line)
            if match:
                img_path = match.group(1)
                pdf.add_image_safe(img_path, base_path)
        
        # Handle horizontal rules
        elif line.strip() == '---':
            pdf.ln(5)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
        
        # Handle regular text
        elif line.strip():
            text = line.strip()
            # Remove markdown formatting
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            text = re.sub(r'`(.+?)`', r'\1', text)
            text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
            
            if text.startswith('- [ ]') or text.startswith('- [x]'):
                checked = '[x]' if '[x]' in text else '[ ]'
                text = checked + ' ' + text[6:].strip()
            elif text.startswith('- '):
                text = '* ' + text[2:]
            
            pdf.body_text(text)
    
    # Handle remaining table
    if in_table and table_headers and table_rows:
        pdf.add_table(table_headers, table_rows)


def generate_pdf(md_file: Path, pdf_file: Path, title: str):
    """Generate PDF from markdown file."""
    
    print(f"Converting: {md_file.name} -> {pdf_file.name}")
    
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    pdf = PDFManual(title)
    pdf.add_page()
    
    # Title page
    pdf.set_font('Helvetica', 'B', 24)
    pdf.set_text_color(26, 82, 118)
    pdf.ln(40)
    pdf.cell(0, 20, title, align='C')
    pdf.ln(20)
    pdf.set_font('Helvetica', '', 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, 'Metal Spinning CNC Controller', align='C')
    pdf.ln(10)
    pdf.cell(0, 10, 'Documentation', align='C')
    
    pdf.add_page()
    parse_markdown_to_pdf(md_content, pdf, md_file.parent)
    
    pdf.output(str(pdf_file))
    print(f"  [OK] Created: {pdf_file.name}")


def main():
    print("=" * 60)
    print("PDF Manual Generator")
    print("=" * 60)
    
    success_count = 0
    
    for md_name, pdf_name, title in MANUALS:
        md_path = MANUAL_DIR / md_name
        pdf_path = MANUAL_DIR / pdf_name
        
        if not md_path.exists():
            print(f"  [!] Not found: {md_name}")
            continue
        
        try:
            generate_pdf(md_path, pdf_path, title)
            success_count += 1
        except Exception as e:
            print(f"  [!] Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("=" * 60)
    print(f"Complete: {success_count}/{len(MANUALS)} PDFs generated")
    print("=" * 60)


if __name__ == "__main__":
    main()
