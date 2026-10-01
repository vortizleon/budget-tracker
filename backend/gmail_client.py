"""Gmail API client for fetching bank receipt emails."""
import os
import base64
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gmail API scopes - we only need read access
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent


class GmailClient:
    """Client for interacting with Gmail API."""

    def __init__(
        self,
        credentials_file: str = "credentials.json",
        token_file: str = "token.json"
    ):
        """
        Initialize Gmail client.

        Args:
            credentials_file: Path to OAuth credentials JSON
            token_file: Path to store/load access token
        """
        self.credentials_path = BASE_DIR / credentials_file
        self.token_path = BASE_DIR / token_file
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth 2.0."""
        creds = None

        # Load existing token if available
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing expired token...")
                creds.refresh(Request())
            else:
                print("Starting OAuth flow...")
                print("A browser window will open for authentication.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token for future use
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
            print(f"✓ Token saved to {self.token_path}")

        # Build Gmail service
        self.service = build('gmail', 'v1', credentials=creds)
        print("✓ Gmail API authenticated successfully")

    def search_messages(
        self,
        query: str,
        max_results: int = 100,
        after_date: Optional[datetime] = None,
        before_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Search for messages matching a query.

        Args:
            query: Gmail search query (e.g., "from:bank@example.com subject:compra")
            max_results: Maximum number of messages to return
            after_date: Only fetch messages after this date
            before_date: Only fetch messages before this date (exclusive on
                Gmail's side, so callers wanting a day included should pass
                the day after it)

        Returns:
            List of message objects with basic info
        """
        try:
            # Add date filters to query if specified
            if after_date:
                query = f"{query} after:{after_date.strftime('%Y/%m/%d')}"
            if before_date:
                query = f"{query} before:{before_date.strftime('%Y/%m/%d')}"

            print(f"Searching Gmail with query: {query}")

            # Search for messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            print(f"✓ Found {len(messages)} messages")

            return messages

        except HttpError as error:
            print(f"✗ Gmail API error: {error}")
            return []

    def get_message(self, message_id: str) -> Optional[Dict]:
        """
        Fetch full message content by ID.

        Args:
            message_id: Gmail message ID

        Returns:
            Full message object with headers and body
        """
        max_retries = 5
        for attempt in range(max_retries):
            try:
                message = self.service.users().messages().get(
                    userId='me',
                    id=message_id,
                    format='full'
                ).execute()

                return message

            except HttpError as error:
                is_rate_limit = error.resp.status in (403, 429) and 'rateLimitExceeded' in str(error)
                if is_rate_limit and attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1, 2, 4, 8s
                    print(f"  ⏳ Rate limited, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"✗ Error fetching message {message_id}: {error}")
                return None

    def get_message_body(self, message: Dict) -> str:
        """
        Extract email body from message object.

        Args:
            message: Full message object from Gmail API

        Returns:
            Email body as text (HTML or plain text)
        """
        payload = message.get('payload', {})
        body = ""

        # Try to get body from parts (multipart email)
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/html':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
                elif part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')

        # Try to get body directly (simple email)
        elif 'body' in payload:
            data = payload['body'].get('data', '')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')

        return body

    def get_message_headers(self, message: Dict) -> Dict[str, str]:
        """
        Extract headers from message as a dictionary.

        Args:
            message: Full message object from Gmail API

        Returns:
            Dictionary of header names to values
        """
        headers = {}
        for header in message.get('payload', {}).get('headers', []):
            headers[header['name']] = header['value']
        return headers

    def fetch_bank_emails(
        self,
        bank_email: str,
        keywords: List[str] = None,  # Kept for backwards compatibility, not used
        days_back: int = 30,
        max_results: int = 100,
        after_date: Optional[datetime] = None,
        before_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fetch bank receipt/payment emails.

        Args:
            bank_email: Email address of the bank (e.g., "notificaciones@banco.cr")
            keywords: Deprecated - not used, kept for backwards compatibility
            days_back: How many days back to search (ignored if after_date is given)
            max_results: Maximum number of emails to fetch
            after_date: Explicit lower bound, overrides days_back - use this
                plus before_date to backfill a specific range (e.g. a gap
                before the usual rolling sync window) without re-fetching
                everything that's already been synced
            before_date: Explicit upper bound (exclusive)

        Returns:
            List of dictionaries with message_id, headers, and body
        """
        # Build search query - search ALL emails from this sender
        # We don't filter by keywords anymore - the parser will determine
        # if an email contains valid transaction data
        query = f"from:{bank_email}"

        if after_date is None:
            after_date = datetime.now() - timedelta(days=days_back)

        # Search for messages
        messages = self.search_messages(query, max_results, after_date, before_date)

        # Fetch full content for each message
        results = []
        for i, msg in enumerate(messages):
            if i > 0:
                time.sleep(0.3)  # stay under the per-minute quota on big batches
            msg_id = msg['id']
            full_message = self.get_message(msg_id)

            if full_message:
                results.append({
                    'message_id': msg_id,
                    'headers': self.get_message_headers(full_message),
                    'body': self.get_message_body(full_message),
                    'internal_date': full_message.get('internalDate')
                })

        print(f"✓ Fetched {len(results)} full email messages")
        return results


def test_connection():
    """Test Gmail API connection."""
    print("Testing Gmail API connection...")
    client = GmailClient()

    # Search for recent emails (any email from last 7 days)
    messages = client.search_messages("is:inbox", max_results=5)
    print(f"✓ Successfully connected! Found {len(messages)} recent messages in inbox.")

    return client


if __name__ == "__main__":
    # Test the connection
    test_connection()
