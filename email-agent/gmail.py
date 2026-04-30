import base64
from googleapiclient.discovery import build
from auth import authenticate

def fetch_unread_emails(max_results=20):
    creds = authenticate()
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().messages().list(
        userId='me',
        q='category:primary',
        maxResults=max_results
    ).execute()

    messages = results.get('messages', [])
    emails = []

    for msg in messages:
        full_msg = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='full'
        ).execute()
        emails.append(parse_email(full_msg))

    return emails


def parse_email(msg):
    headers = {h['name']: h['value'] for h in msg['payload']['headers']}

    body = ''
    parts = msg['payload'].get('parts', [])

    if parts:
        for part in parts:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                body = base64.urlsafe_b64decode(data).decode('utf-8')
                break
    else:
        data = msg['payload']['body'].get('data', '')
        body = base64.urlsafe_b64decode(data).decode('utf-8')

    return {
        'id': msg['id'],
        'thread_id': msg['threadId'],
        'subject': headers.get('Subject', '(no subject)'),
        'sender': headers.get('From', ''),
        'date': headers.get('Date', ''),
        'snippet': msg.get('snippet', ''),
        'body': body[:3000]
    }


def mark_as_read(service, msg_id):
    service.users().messages().modify(
        userId='me',
        id=msg_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()


# Quick test — run this file directly to check everything works
if __name__ == '__main__':
    emails = fetch_unread_emails(max_results=3)
    for e in emails:
        print(f"From: {e['sender']}")
        print(f"Subject: {e['subject']}")
        print(f"Snippet: {e['snippet']}")
        print('---')