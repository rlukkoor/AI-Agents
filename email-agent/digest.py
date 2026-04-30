from datetime import date
from agent import classify_email, summarize_email
from gmail import fetch_unread_emails
from memory import init_db, is_processed, mark_processed

CATEGORY_ORDER = ['URGENT', 'ACTION', 'FYI', 'IGNORE']

def build_digest(max_emails=10):
    init_db()  # Create DB if it doesn't exist yet

    print("Fetching emails...\n")
    emails = fetch_unread_emails(max_results=max_emails)

    # Skip already processed emails
    new_emails = [e for e in emails if not is_processed(e['id'])]
    print(f"{len(new_emails)} new emails to process (skipping {len(emails) - len(new_emails)} already seen)\n")

    if not new_emails:
        print("Nothing new to process.")
        return

    # Classify and summarize each email
    processed = []
    for email in new_emails:
        print(f"Processing: {email['subject'][:50]}")
        classification = classify_email(email)
        summary = summarize_email(email)
        result = {**email, **classification, 'summary': summary}
        mark_processed(result)  # Save to memory
        processed.append(result)

    # Sort by priority
    processed.sort(key=lambda x: CATEGORY_ORDER.index(x.get('category', 'IGNORE')))

    # Build digest text
    today = date.today().strftime('%B %d, %Y')
    lines = [f"EMAIL DIGEST — {today}", "=" * 40, ""]

    current_category = None
    for email in processed:
        category = email.get('category', 'IGNORE')
        if category != current_category:
            current_category = category
            lines.append(f"\n── {category} ──────────────────────\n")
        lines.append(f"  {email['subject']}")
        lines.append(f"  From: {email['sender']}")
        lines.append(f"  {email['summary']}")
        lines.append("")

    digest = '\n'.join(lines)
    print("\n" + digest)

    filename = f"digest_{date.today().strftime('%Y%m%d')}.txt"
    with open(filename, 'w') as f:
        f.write(digest)
    print(f"Digest saved to {filename}")

    return digest


if __name__ == '__main__':
    build_digest()