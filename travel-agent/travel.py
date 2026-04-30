import anthropic
import requests
import time
import re
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()


def claude_request(prompt, max_tokens=2000):
    for attempt in range(3):
        try:
            return client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            ).content[0].text.strip()
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 2:
                wait = (attempt + 1) * 10
                print(f"API overloaded, retrying in {wait} seconds...")
                time.sleep(wait)
            else:
                raise


def clean_text(text):
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|[-:]+\|[-| :]+', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_content(text):
    text = clean_text(text)
    elements = []

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith(('- ', '* ', '+ ')):
            elements.append(('bullet', line[2:].strip()))
        elif re.match(r'^\d+[\.\)]\s+', line):
            content = re.sub(r'^\d+[\.\)]\s+', '', line)
            elements.append(('numbered', content))
        elif line.startswith('|') and line.endswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            elements.append(('table_row', cells))
        else:
            elements.append(('paragraph', line))

    return elements


def build_pdf(destination, trip_length, nationality, sections):
    filename = f"{destination.replace(' ', '_')}_travel_guide.pdf"

    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=0.85 * inch,
        leftMargin=0.85 * inch,
        topMargin=inch,
        bottomMargin=inch
    )

    dark_navy = colors.HexColor('#1a1a2e')
    mid_gray = colors.HexColor('#555555')
    light_gray = colors.HexColor('#f5f5f5')
    accent = colors.HexColor('#2e6da4')
    divider_color = colors.HexColor('#dddddd')

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title2', fontSize=32, textColor=dark_navy,
                                  fontName='Helvetica-Bold', spaceAfter=6, leading=38)
    subtitle_style = ParagraphStyle('Subtitle2', fontSize=12, textColor=mid_gray,
                                     fontName='Helvetica', spaceAfter=4)
    section_heading_style = ParagraphStyle('SectionHeading', fontSize=15,
                                            textColor=accent, fontName='Helvetica-Bold',
                                            spaceBefore=24, spaceAfter=6)
    body_style = ParagraphStyle('Body2', fontSize=10.5, textColor=colors.HexColor('#333333'),
                                 fontName='Helvetica', leading=16, spaceAfter=5)
    bullet_style = ParagraphStyle('Bullet2', fontSize=10.5, textColor=colors.HexColor('#333333'),
                                   fontName='Helvetica', leading=16, spaceAfter=4,
                                   leftIndent=16, firstLineIndent=0)
    large_bullet_style = ParagraphStyle('LargeBullet', fontSize=10.5, textColor=colors.HexColor('#333333'),
                                         fontName='Helvetica', leading=16, spaceAfter=8,
                                         leftIndent=16, spaceBefore=6)
    numbered_style = ParagraphStyle('Numbered', fontSize=10.5, textColor=colors.HexColor('#333333'),
                                     fontName='Helvetica', leading=16, spaceAfter=4,
                                     leftIndent=16)

    story = []

    # Title block
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(destination, title_style))
    story.append(Paragraph("Travel Research Report", subtitle_style))
    story.append(Paragraph(
        f"{trip_length} days &nbsp;&nbsp;|&nbsp;&nbsp; {nationality} passport &nbsp;&nbsp;|&nbsp;&nbsp; {date.today().strftime('%B %d, %Y')}",
        subtitle_style
    ))
    story.append(Spacer(1, 0.15 * inch))
    story.append(HRFlowable(width="100%", thickness=2, color=accent))
    story.append(Spacer(1, 0.2 * inch))

    section_titles = {
        'weather': 'Weather & Best Time to Visit',
        'visa': 'Visa & Entry Requirements',
        'todo': 'Top Things to Do',
        'budget': 'Budget & Cost Breakdown',
        'safety': 'Safety & Travel Advisories',
        'culture': 'Local Tips & Culture'
    }

    for section_index, (key, title) in enumerate(section_titles.items()):
        if section_index > 0:
            story.append(PageBreak())

        story.append(Paragraph(title, section_heading_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=divider_color))
        story.append(Spacer(1, 0.1 * inch))

        elements = parse_content(sections[key])

        elem_index = 0
        numbered_counter = 1
        while elem_index < len(elements):
            etype, content = elements[elem_index]

            if etype == 'table_row':
                table_rows = []
                while elem_index < len(elements) and elements[elem_index][0] == 'table_row':
                    table_rows.append(elements[elem_index][1])
                    elem_index += 1
                if len(table_rows) > 1:
                    col_count = max(len(r) for r in table_rows)
                    padded = [r + [''] * (col_count - len(r)) for r in table_rows]
                    t = Table(padded, hAlign='LEFT', colWidths=[2.5 * inch] * min(col_count, 3))
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), light_gray),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_gray]),
                        ('GRID', (0, 0), (-1, -1), 0.3, divider_color),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ]))
                    story.append(t)
                    story.append(Spacer(1, 0.1 * inch))
                continue

            elif etype == 'bullet':
                if key == 'todo':
                    story.append(Paragraph(f"&#9654;&nbsp;&nbsp;{content}", large_bullet_style))
                else:
                    story.append(Paragraph(f"&bull;&nbsp;&nbsp;{content}", bullet_style))
                numbered_counter = 1

            elif etype == 'numbered':
                story.append(Paragraph(f"{numbered_counter}.&nbsp;&nbsp;{content}", numbered_style))
                numbered_counter += 1

            elif etype == 'paragraph':
                story.append(Paragraph(content, body_style))
                numbered_counter = 1

            elem_index += 1

        story.append(Spacer(1, 0.15 * inch))

    doc.build(story)
    return filename


def research_destination(destination, trip_length, nationality):
    print(f"\nResearching {destination}...\n")
    sections = {}

    print("Researching weather...")
    sections['weather'] = claude_request(f"""You are a travel expert writing a professional travel guide. For {destination}, cover:
- Best months to visit and why
- Seasonal weather breakdown
- Any weather hazards to be aware of
Write in clear plain text. Do not use markdown formatting, asterisks, or hashtags. Use short paragraphs and simple bullet points starting with a dash (-).""", max_tokens=2000)

    print("Researching visa requirements...")
    sections['visa'] = claude_request(f"""You are a travel expert writing a professional travel guide. For someone from {nationality} visiting {destination}, cover:
- Visa requirements and length of stay
- Required documents
- Key entry restrictions
Write in clear plain text. Do not use markdown formatting, asterisks, or hashtags. Use short paragraphs and simple bullet points starting with a dash (-).""", max_tokens=2000)

    print("Researching things to do...")
    sections['todo'] = claude_request(f"""You are a travel expert writing a professional travel guide. List the top 10 things to do in {destination}.
For each include the name, why it is worth doing, and practical tips.
Write in clear plain text. Do not use markdown formatting, asterisks, or hashtags. Start each item with a dash (-).""", max_tokens=2000)

    print("Researching costs...")
    sections['budget'] = claude_request(f"""You are a travel expert writing a professional travel guide. For {destination} over {trip_length} days, cover:
- Accommodation costs (budget, mid-range, luxury per night)
- Daily food costs (budget, mid-range, fine dining)
- Transportation costs
- Total estimated trip cost for each traveler type
Write in clear plain text. Do not use markdown formatting, asterisks, or hashtags. Use simple bullet points starting with a dash (-).""", max_tokens=2000)

    print("Researching safety...")
    sections['safety'] = claude_request(f"""You are a travel expert writing a professional travel guide. For {destination}, cover:
- Overall safety level
- Areas or situations to avoid
- Common scams targeting tourists
- Emergency numbers
- Health precautions
Write in clear plain text. Do not use markdown formatting, asterisks, or hashtags. Use simple bullet points starting with a dash (-).""", max_tokens=2000)

    print("Researching local culture...")
    sections['culture'] = claude_request(f"""You are a travel expert writing a professional travel guide. For {destination}, cover:
- Key cultural customs and etiquette
- Dress code expectations
- Tipping culture
- Language tips and key phrases
- Food and dining customs
Write in clear plain text. Do not use markdown formatting, asterisks, or hashtags. Use simple bullet points starting with a dash (-).""", max_tokens=2000)

    return sections


def run(destination, trip_length, nationality):
    sections = research_destination(destination, trip_length, nationality)
    print("\nGenerating PDF...\n")
    filename = build_pdf(destination, trip_length, nationality, sections)
    print(f"Report saved to: {filename}")


if __name__ == '__main__':
    destination = input("Where are you travelling to? ")
    trip_length = input("How many days is your trip? ")
    nationality = input("What country are you from? ")
    run(destination, trip_length, nationality)