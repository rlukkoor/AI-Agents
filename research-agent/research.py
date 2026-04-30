import anthropic
import requests
import time
import re
import os
from datetime import date
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

load_dotenv()

client = anthropic.Anthropic()
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")


def brave_search(query, count=10):
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY
    }
    params = {
        "q": query,
        "count": count,
        "text_decorations": False
    }
    try:
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params
        )
        data = response.json()
        results = data.get("web", {}).get("results", [])
        snippets = []
        for r in results:
            title = r.get("title", "")
            snippet = r.get("description", "")
            url = r.get("url", "")
            if snippet:
                snippets.append(f"- {title}: {snippet} ({url})")
        return "\n".join(snippets)
    except Exception as e:
        print(f"Search failed: {e}")
        return ""


def claude_request(prompt, max_tokens=3000):
    for attempt in range(3):
        try:
            return client.messages.create(
                model="claude-sonnet-4-20250514",
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


def make_context(search_results):
    return f"""Today's date is {date.today().strftime('%B %d, %Y')}.
You are researching current events. The search results below are from real, live web searches conducted today.
Treat all information in the search results as factual and current, even if the events occurred recently.
Do not question whether events are real. Summarize and analyze what the search results say.

Search results:
{search_results}"""


def research_topic(topic):
    print(f"\nResearching: {topic}\n")
    sections = {}

    print("Searching the web...")
    search_general = brave_search(f"{topic} overview")
    search_general2 = brave_search(f"{topic} analysis in depth")
    search_timeline = brave_search(f"{topic} timeline history events")
    search_timeline2 = brave_search(f"{topic} chronology milestones")
    search_people = brave_search(f"{topic} key figures people organizations")
    search_people2 = brave_search(f"{topic} leaders roles impact")
    search_debate = brave_search(f"{topic} perspectives debate controversy")
    search_debate2 = brave_search(f"{topic} criticism arguments different views")

    print("Writing summary...")
    sections['summary'] = claude_request(f"""{make_context(search_general + chr(10) + search_general2)}

Topic: {topic}

Write a thorough executive summary covering the most important things to know about this topic.
Write 5-6 substantial paragraphs. Include specific facts, figures, dates, and names from the search results.
Cover the background context, what happened, why it matters, and its broader significance.
Write in plain text only. No markdown, no asterisks, no hashtags.""", max_tokens=3000)

    print("Analyzing perspectives...")
    sections['perspectives'] = claude_request(f"""{make_context(search_debate + chr(10) + search_debate2)}

Topic: {topic}

Write a deep analysis of the key perspectives, debates, and disagreements surrounding this topic.
Cover at least 4 distinct viewpoints or schools of thought.
For each perspective: explain who holds it, why they hold it, what evidence they cite, and what critics say about it.
Be specific - name real people, organizations, and arguments.
Write in plain text only. No markdown, no asterisks, no hashtags. Use a dash (-) to start each perspective.""", max_tokens=3000)

    print("Building timeline...")
    sections['timeline'] = claude_request(f"""{make_context(search_timeline + chr(10) + search_timeline2)}

Topic: {topic}

List at least 12 of the most important events, developments, or milestones related to this topic in chronological order.
For each entry include specific details - names, numbers, locations, outcomes.
Format each entry exactly like this:
DATE: [year or specific date]
EVENT: [detailed description of what happened and why it mattered]

Do not use any other format. Write in plain text only. No markdown, no asterisks, no hashtags.""", max_tokens=3000)

    print("Identifying key figures...")
    sections['people'] = claude_request(f"""{make_context(search_people + chr(10) + search_people2)}

Topic: {topic}

Identify at least 8 of the most important people and organizations related to this topic.
For each: explain their background, their specific role, key actions they took, and their lasting impact.
Be detailed and specific - go beyond surface-level descriptions.
Write in plain text only. No markdown, no asterisks, no hashtags. Use a dash (-) to start each entry.""", max_tokens=3000)

    return sections


def clean_text(text):
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_content(text):
    text = clean_text(text)
    elements = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('DATE:'):
            date_val = line[5:].strip()
            event_val = ''
            if i + 1 < len(lines) and lines[i + 1].strip().startswith('EVENT:'):
                event_val = lines[i + 1].strip()[6:].strip()
                i += 1
            elements.append(('timeline', (date_val, event_val)))
        elif line.startswith(('- ', '* ', '+ ')):
            elements.append(('bullet', line[2:].strip()))
        else:
            elements.append(('paragraph', line))
        i += 1
    return elements


def build_pdf(topic, sections):
    filename = f"{topic.replace(' ', '_').replace('/', '_')}_research_brief.pdf"

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
    light_gray = colors.HexColor('#f0f0f0')
    accent = colors.HexColor('#2e6da4')
    divider_color = colors.HexColor('#dddddd')
    timeline_color = colors.HexColor('#2e6da4')

    title_style = ParagraphStyle('Title2', fontSize=28, textColor=dark_navy,
                                  fontName='Helvetica-Bold', spaceAfter=6, leading=34)
    subtitle_style = ParagraphStyle('Subtitle2', fontSize=12, textColor=mid_gray,
                                     fontName='Helvetica', spaceAfter=4)
    section_heading_style = ParagraphStyle('SectionHeading', fontSize=15,
                                            textColor=accent, fontName='Helvetica-Bold',
                                            spaceBefore=24, spaceAfter=6)
    body_style = ParagraphStyle('Body2', fontSize=10.5, textColor=colors.HexColor('#333333'),
                                 fontName='Helvetica', leading=17, spaceAfter=6)
    bullet_style = ParagraphStyle('Bullet2', fontSize=10.5, textColor=colors.HexColor('#333333'),
                                   fontName='Helvetica', leading=16, spaceAfter=6,
                                   leftIndent=16)
    timeline_year_style = ParagraphStyle('TimelineYear', fontSize=10.5,
                                          textColor=timeline_color,
                                          fontName='Helvetica-Bold', leading=16,
                                          spaceAfter=2, leftIndent=16)
    timeline_body_style = ParagraphStyle('TimelineBody', fontSize=10.5,
                                          textColor=colors.HexColor('#333333'),
                                          fontName='Helvetica', leading=16,
                                          spaceAfter=8, leftIndent=32)

    story = []

    # Title block
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(topic, title_style))
    story.append(Paragraph("Research Brief", subtitle_style))
    story.append(Paragraph(f"Generated {date.today().strftime('%B %d, %Y')}", subtitle_style))
    story.append(Spacer(1, 0.15 * inch))
    story.append(HRFlowable(width="100%", thickness=2, color=accent))
    story.append(Spacer(1, 0.2 * inch))

    section_titles = {
        'summary': 'Executive Summary',
        'perspectives': 'Key Perspectives & Debates',
        'timeline': 'Timeline of Events',
        'people': 'Key People & Organizations'
    }

    for section_index, (key, title) in enumerate(section_titles.items()):
        if section_index > 0:
            story.append(PageBreak())

        story.append(Paragraph(title, section_heading_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=divider_color))
        story.append(Spacer(1, 0.1 * inch))

        elements = parse_content(sections[key])

        for etype, content in elements:
            if etype == 'bullet':
                story.append(Paragraph(f"&bull;&nbsp;&nbsp;{content}", bullet_style))
            elif etype == 'timeline':
                date_val, event_val = content
                story.append(Paragraph(date_val, timeline_year_style))
                story.append(Paragraph(event_val, timeline_body_style))
            else:
                story.append(Paragraph(content, body_style))

        story.append(Spacer(1, 0.15 * inch))

    doc.build(story)
    return filename


def run(topic):
    sections = research_topic(topic)
    print("\nGenerating PDF...\n")
    filename = build_pdf(topic, sections)
    print(f"Research brief saved to: {filename}")


if __name__ == '__main__':
    topic = input("What would you like to research? ")
    run(topic)