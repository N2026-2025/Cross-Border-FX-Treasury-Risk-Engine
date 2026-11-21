#!/usr/bin/env python
"""Generate PDF from markdown interview Q&A."""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.platypus.flowables import Flowable
import re
import os


class MarkdownToPDF:
    """Convert markdown content to PDF using reportlab."""

    def __init__(self, output_path):
        self.doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self.story = []

    def _setup_custom_styles(self):
        """Define custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            leading=28,
            spaceAfter=12,
            textColor=HexColor('#1a3c5e'),
            fontName='Helvetica-Bold',
        ))

        # Subtitle
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Title'],
            fontSize=16,
            leading=20,
            spaceAfter=20,
            textColor=HexColor('#2c5f8a'),
            fontName='Helvetica-Bold',
        ))

        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            leading=18,
            spaceBefore=16,
            spaceAfter=8,
            textColor=HexColor('#1a3c5e'),
            fontName='Helvetica-Bold',
            borderWidth=0,
            borderPadding=0,
        ))

        # Sub-section header
        self.styles.add(ParagraphStyle(
            name='SubSectionHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            leading=16,
            spaceBefore=12,
            spaceAfter=6,
            textColor=HexColor('#2c5f8a'),
            fontName='Helvetica-BoldOblique',
        ))

        # Body text
        self.styles.add(ParagraphStyle(
            name='BodyText2',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
        ))

        # Q&A specific styles
        self.styles.add(ParagraphStyle(
            name='Question',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=15,
            spaceBefore=10,
            spaceAfter=4,
            textColor=HexColor('#1a3c5e'),
            fontName='Helvetica-Bold',
        ))

        self.styles.add(ParagraphStyle(
            name='Answer',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            spaceAfter=8,
            leftIndent=15,
            fontName='Helvetica',
        ))

        # Code/Monospace
        self.styles.add(ParagraphStyle(
            name='CodeBlock',
            parent=self.styles['Normal'],
            fontSize=9,
            leading=12,
            spaceAfter=8,
            leftIndent=20,
            rightIndent=20,
            fontName='Courier',
            backColor=HexColor('#f5f5f5'),
        ))

        # Bullet
        self.styles.add(ParagraphStyle(
            name='BulletItem',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            spaceAfter=4,
            leftIndent=30,
            bulletIndent=15,
            fontName='Helvetica',
        ))

    def parse_markdown(self, content):
        """Parse markdown and convert to flowables."""
        lines = content.split('\n')
        i = 0
        in_code_block = False
        code_lines = []

        while i < len(lines):
            line = lines[i].rstrip()

            # Skip empty lines
            if not line.strip():
                if not in_code_block:
                    self.story.append(Spacer(1, 6))
                i += 1
                continue

            # Headers
            if line.startswith('# '):
                self.story.append(Paragraph(line[2:], self.styles['CustomTitle']))
            elif line.startswith('## '):
                self.story.append(Paragraph(line[3:], self.styles['CustomSubtitle']))
            elif line.startswith('### '):
                self.story.append(Paragraph(line[4:], self.styles['SectionHeader']))
            elif line.startswith('#### '):
                self.story.append(Paragraph(line[5:], self.styles['SubSectionHeader']))

            # Horizontal rule
            elif line.startswith('---') or line.startswith('***'):
                self.story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#cccccc')))
                self.story.append(Spacer(1, 12))

            # Code blocks
            elif line.startswith('```'):
                if not in_code_block:
                    in_code_block = True
                    code_lines = []
                else:
                    in_code_block = False
                    code_text = '<br/>'.join(code_lines)
                    self.story.append(Paragraph(code_text, self.styles['CodeBlock']))
            elif in_code_block:
                code_lines.append(line)

            # Blockquotes / Pitch
            elif line.startswith('> '):
                self.story.append(Paragraph(
                    f'<i>{line[2:]}</i>',
                    ParagraphStyle('Quote', parent=self.styles['BodyText2'], leftIndent=20, textColor=HexColor('#555555'))
                ))

            # Bold inline handling
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                # Bullet points
                bullet_text = line.strip()[2:]
                bullet_text = self._process_inline(bullet_text)
                self.story.append(Paragraph(f'• {bullet_text}', self.styles['BulletItem']))

            # Q&A format
            elif line.startswith('**Q') and ':' in line:
                # Question
                question = line.replace('**Q', 'Q').replace('**', '')
                question = self._process_inline(question)
                self.story.append(Paragraph(question, self.styles['Question']))

            elif line.startswith('**A:') or line.startswith('**A :'):
                # Answer
                answer = line.replace('**A:', '').replace('**A :', '').replace('**', '')
                answer = self._process_inline(answer)
                self.story.append(Paragraph(answer, self.styles['Answer']))

            # Regular text
            else:
                processed = self._process_inline(line)
                self.story.append(Paragraph(processed, self.styles['BodyText2']))

            i += 1

        # Handle unclosed code block
        if in_code_block and code_lines:
            code_text = '<br/>'.join(code_lines)
            self.story.append(Paragraph(code_text, self.styles['CodeBlock']))

    def _process_inline(self, text):
        """Process inline markdown formatting."""
        # Bold
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # Italic
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        # Inline code
        text = re.sub(r'`([^`]+)`', r'<font face="Courier" color="#2c5f8a">\1</font>', text)
        # Escape special chars
        text = text.replace('&', '&').replace('<', '<').replace('>', '>')
        # Re-allow our tags
        text = text.replace('<b>', '<b>').replace('</b>', '</b>')
        text = text.replace('<i>', '<i>').replace('</i>', '</i>')
        text = text.replace('<font', '<font').replace('</font>', '</font>')
        return text

    def build(self):
        """Build the PDF."""
        self.doc.build(self.story)


def main():
    input_path = 'interview/interview_qa.md'
    output_path = 'interview/interview_qa.pdf'

    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    converter = MarkdownToPDF(output_path)
    converter.parse_markdown(content)
    converter.build()

    print(f"PDF generated: {output_path}")


if __name__ == '__main__':
    main()