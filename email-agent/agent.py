import anthropic
from gmail import fetch_unread_emails

client = anthropic.Anthropic()

def classify_email(email):
    prompt = f"""You are an email triage assistant. Classify the following email into exactly one of these categories:
- URGENT: Needs immediate attention or response today
- ACTION: Needs a response or follow-up, but not urgent
- FYI: Informational only, no response needed
- IGNORE: Newsletter, spam, or not worth reading

Email details:
From: {email['sender']}
Subject: {email['subject']}
Body: {email['body']}

Respond in this exact format:
CATEGORY: <category>
REASON: <one sentence explanation>"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )

    return parse_classification(message.content[0].text)


def parse_classification(response_text):
    lines = response_text.strip().split('\n')
    result = {}
    for line in lines:
        if line.startswith('CATEGORY:'):
            result['category'] = line.replace('CATEGORY:', '').strip()
        elif line.startswith('REASON:'):
            result['reason'] = line.replace('REASON:', '').strip()
    return result

def summarize_email(email):
    prompt = f"""Summarize this email in 1-2 sentences. Be concise and focus on what matters.

From: {email['sender']}
Subject: {email['subject']}
Body: {email['body']}

Respond with just the summary, no preamble."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()


def run_triage(max_emails=10):
    print("Fetching unread emails...\n")
    emails = fetch_unread_emails(max_results=max_emails)

    results = []
    for email in emails:
        print(f"Classifying: {email['subject'][:50]}")
        classification = classify_email(email)
        results.append({**email, **classification})

    print("\n===== TRIAGE RESULTS =====\n")
    for r in sorted(results, key=lambda x: ['URGENT','ACTION','FYI','IGNORE'].index(x.get('category','IGNORE'))):
        print(f"[{r.get('category', '?')}] {r['subject']}")
        print(f"  From: {r['sender']}")
        print(f"  Reason: {r.get('reason', '')}")
        print()

    return results


if __name__ == '__main__':
    run_triage()