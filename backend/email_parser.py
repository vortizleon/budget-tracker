"""Email parser for extracting transaction data from bank emails."""
import re
from datetime import datetime
from typing import Dict, Optional
from bs4 import BeautifulSoup


class EmailParser:
    """Parser for bank receipt/payment emails."""

    def __init__(self):
        """Initialize parser with regex patterns."""
        # These patterns should be customized for your bank's email format
        # Default patterns for common formats
        self.patterns = {
            'amount': [
                # BAC format: "Monto: CRC 204.00"
                # Promerica format (2026): "Monto\nCRC: 8,150.00"
                r'(?:monto|amount)[:\s]*(?:CRC|USD|₡|\$)?[:\s]*([\d,\.]+)',
                r'(?:CRC|USD|₡|\$)[:\s]*([\d,\.]+)',
                r'([\d,\.]+)\s*(?:CRC|USD|₡|\$)',
            ],
            'currency': [
                r'\b(CRC|USD)\b',
                r'(₡|\$)',
            ],
            'commerce': [
                # BAC format: "Comercio: AFILIADO FRECUENTE"
                r'(?:comercio|commerce|merchant)[:\s]*\n?\s*([A-Z][^\n<]+?)(?:\n|</)',
                r'(?:comercio|commerce|merchant)[:\s]*([^\n<]+)',
            ],
            'card_last_four': [
                # BAC format: "***********9682" or "****9682"
                # Promerica format (2026): "****-****-****-2731"
                r'\*[\*\-]*(\d{4})\b',
                r'terminada en[:\s]*(\d{4})',
                r'card ending[:\s]*(\d{4})',
            ],
            'date': [
                # BAC format: "Nov 28, 2025, 17:36"
                # Some BAC auto-charge templates (e.g. "SEGURO ..." /
                # CARGO AUTOMATICO) omit the space after the day's comma -
                # "Sep 18,2026" - so that comma's trailing whitespace is
                # optional, not required.
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s*\d{4})',
                r'((?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[a-z]*\s+\d{1,2},\s*\d{4})',
                # Promerica format (2026): "26 sep 2026 / 16:30"
                r'(\d{1,2}\s+(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[a-z]*\s+\d{4})',
                # YYYY-MM-DD must be tried before DD-MM-YY below, since e.g.
                # "2026-08-28" otherwise gets matched as the substring
                # "26-08-28" (a valid-looking DD-MM-YY) by the looser pattern.
                r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            ]
        }

    def clean_html(self, html_content: str) -> str:
        """
        Remove HTML tags and get clean text.

        Args:
            html_content: Raw HTML email body

        Returns:
            Clean text content
        """
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        return text

    def extract_field(self, text: str, field_name: str) -> Optional[str]:
        """
        Extract a field using regex patterns.

        Args:
            text: Email text content
            field_name: Name of field to extract (must be in self.patterns)

        Returns:
            Extracted value or None
        """
        patterns = self.patterns.get(field_name, [])

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()

        return None

    def parse_amount(self, amount_str: str) -> float:
        """
        Parse amount string to float.

        Args:
            amount_str: Amount as string (e.g., "1,234.56" or "1.234,56")

        Returns:
            Amount as float
        """
        if not amount_str:
            return 0.0

        # Remove spaces
        amount_str = amount_str.replace(' ', '')

        # Handle both comma and dot as decimal separators
        # If there's both, assume the last one is decimal separator
        if ',' in amount_str and '.' in amount_str:
            if amount_str.rindex(',') > amount_str.rindex('.'):
                # Comma is decimal separator (European format)
                amount_str = amount_str.replace('.', '').replace(',', '.')
            else:
                # Dot is decimal separator (US format)
                amount_str = amount_str.replace(',', '')
        elif ',' in amount_str:
            # Check if it's likely a decimal separator
            parts = amount_str.split(',')
            if len(parts[-1]) == 2:  # Likely decimal (e.g., "1234,56")
                amount_str = amount_str.replace(',', '.')
            else:  # Likely thousands separator (e.g., "1,234")
                amount_str = amount_str.replace(',', '')

        try:
            return float(amount_str)
        except ValueError:
            return 0.0

    def normalize_currency(self, currency_str: str) -> str:
        """
        Normalize currency symbol/code to standard 3-letter code.

        Args:
            currency_str: Currency symbol or code (₡, $, CRC, USD)

        Returns:
            Normalized currency code (CRC or USD)
        """
        if not currency_str:
            return "CRC"  # Default to CRC

        currency_str = currency_str.upper().strip()

        if currency_str in ['₡', 'CRC', 'COLONES']:
            return "CRC"
        elif currency_str in ['$', 'USD', 'DOLLARS']:
            return "USD"

        return "CRC"  # Default

    # Spanish month abbreviations don't reliably match %b under the system
    # locale, so "DD mon YYYY" (Promerica's 2026 format) is parsed manually.
    SPANISH_MONTHS = {
        'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
    }

    def parse_spanish_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse Spanish-language dates in either order: "DD mon YYYY" (e.g.
        "26 sep 2026", Promerica) or "mon DD, YYYY" (e.g. "Ago 30, 2026",
        BAC). Spanish and English month abbreviations coincide for several
        months (sep/oct/nov/feb/mar/may/jun/jul), which let this go unnoticed
        until a month where they don't (ene/abr/ago/dic) showed up.

        Args:
            date_str: Date string

        Returns:
            datetime object or None
        """
        date_str = date_str.strip()

        match = re.match(r'(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})$', date_str)
        if match:
            day, month_name, year = match.groups()
        else:
            match = re.match(r'([a-zA-Z]+)\s+(\d{1,2}),\s*(\d{4})$', date_str)
            if not match:
                return None
            month_name, day, year = match.groups()

        month = self.SPANISH_MONTHS.get(month_name.lower()[:3])
        if not month:
            return None

        try:
            return datetime(int(year), month, int(day))
        except ValueError:
            return None

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string to datetime object.

        Args:
            date_str: Date string in various formats

        Returns:
            datetime object or None
        """
        if not date_str:
            return None

        spanish_date = self.parse_spanish_date(date_str)
        if spanish_date:
            return spanish_date

        # Common date formats
        date_formats = [
            '%b %d, %Y',           # Nov 28, 2025
            '%B %d, %Y',           # November 28, 2025
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%Y/%m/%d',
            '%Y-%m-%d',
            '%d/%m/%y',
            '%d-%m-%y',
        ]

        # Clean up date string (remove time if present)
        date_str = date_str.split(',')[0:2]  # Keep "Nov 28, 2025" drop ", 17:36"
        if len(date_str) == 2:
            date_str = ','.join(date_str)
        else:
            date_str = date_str[0]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def detect_transaction_type(self, text: str, subject: str = "") -> str:
        """
        Determine if transaction is a purchase or payment.

        Args:
            text: Email body text
            subject: Email subject

        Returns:
            "purchase" or "payment"
        """
        # Focus on body text primarily
        text_lower = text.lower()

        # BAC specific: Look for "Tipo de Transacción: COMPRA" or "PAGO"
        if 'tipo de transacci' in text_lower:
            # Look at what comes after "tipo de transacción:"
            match = re.search(r'tipo de transacci[oó]n[:\s]*([^\n<]+)', text_lower)
            if match:
                trans_type = match.group(1).strip()
                if 'compra' in trans_type or 'purchase' in trans_type:
                    return "purchase"
                elif 'pago' in trans_type or 'payment' in trans_type or 'abono' in trans_type:
                    return "payment"

        # Strong purchase indicators (transaction notifications)
        purchase_phrases = [
            'notificación de transacción',
            'tu transacción fue procesada',
            'compra realizada',
            'compra aprobada',
            'cargo realizado',
            'transacción aprobada',
        ]

        # Strong payment indicators (payments TO your card)
        payment_phrases = [
            'pago recibido',
            'pago aplicado',
            'abono recibido',
            'abono aplicado',
            'pago de tarjeta',
            'cancelación recibida',
        ]

        # Check purchase phrases - these indicate you SPENT money
        for phrase in purchase_phrases:
            if phrase in text_lower:
                return "purchase"

        # Check payment phrases - these indicate you PAID your card
        for phrase in payment_phrases:
            if phrase in text_lower:
                return "payment"

        # Fallback: if body mentions "compra", it's a purchase
        if 'compra' in text_lower or 'purchase' in text_lower:
            return "purchase"

        # Default: most bank notifications are purchases
        return "purchase"

    def _build_fallback_fields(self, text: str) -> Dict:
        """Shared field extraction for the account-alert email types below."""
        amount_str = self.extract_field(text, 'amount')
        currency_str = self.extract_field(text, 'currency')
        date_str = self.extract_field(text, 'date')
        transaction_date = self.parse_date(date_str) if date_str else datetime.now()
        return {
            'amount_str': amount_str,
            'currency': self.normalize_currency(currency_str) if currency_str else 'CRC',
            'date': transaction_date.date() if transaction_date else datetime.now().date(),
        }

    def parse_transfer(self, text: str, subject: str) -> Optional[Dict]:
        """BAC "Transferencia" account alerts (alerta@baccredomatic.com)."""
        fields = self._build_fallback_fields(text)
        if not fields['amount_str']:
            print(f"✗ Could not extract amount from email: {subject}")
            return None

        # "Tipo de movimiento" tells us the direction. Spanish "credito"/"debito"
        # both end differently after the accented vowel ("...dito" vs "...bito"),
        # which lets us match without worrying about header/body unicode
        # normalization differences.
        movement_match = re.search(r'tipo de movimiento\s*\n?\s*([^\n]+)', text, re.IGNORECASE)
        direction = movement_match.group(1).strip().lower() if movement_match else ''
        if 'dito' in direction and 'bito' not in direction:
            print(f"⊘ Skipped (incoming transfer not yet supported): {subject}")
            return None

        amount = self.parse_amount(fields['amount_str'])
        commerce_name = "Transferencia"
        result = {
            'date': fields['date'],
            'amount': amount,
            'currency': fields['currency'],
            'commerce_name': commerce_name,
            'card_last_four': None,
            'transaction_type': "purchase",
            'description': subject,
            'raw_text': text[:500],
        }
        # Known recurring transfer: rent, paid as a ~390,000 CRC transfer.
        if fields['currency'] == 'CRC' and abs(amount - 390000) < 1:
            result['commerce_name'] = "Transferencia (Alquiler)"
            result['suggested_category'] = 'Rent/Mortgage'
        return result

    def parse_cash_withdrawal(self, text: str, subject: str) -> Optional[Dict]:
        """BAC "Retiro sin tarjeta" (cardless ATM withdrawal) confirmations."""
        fields = self._build_fallback_fields(text)
        if not fields['amount_str']:
            print(f"✗ Could not extract amount from email: {subject}")
            return None

        location_match = re.search(r'[Ll]ugar donde se \w+ el dinero:?\s*\n?\s*([^\n]+)', text)
        location = location_match.group(1).strip() if location_match else None
        commerce_name = f"Retiro sin tarjeta - {location}" if location else "Retiro sin tarjeta"

        return {
            'date': fields['date'],
            'amount': self.parse_amount(fields['amount_str']),
            'currency': fields['currency'],
            'commerce_name': commerce_name,
            'card_last_four': None,
            'transaction_type': "purchase",
            'description': subject,
            'raw_text': text[:500],
        }

    def parse_redemption(self, text: str, subject: str) -> Optional[Dict]:
        """BAC points/miles/cashback redemption applied as a statement credit.

        The "Monto" field here holds the points amount, not money, so the
        generic amount regex would grab the wrong number. The actual credit
        value is the number right after the "=" line (e.g. "= 15172.68 CRC").
        """
        match = re.search(r'=\s*([\d,\.]+)\s*(?:CRC|USD|₡|\$)', text)
        if not match:
            print(f"✗ Could not extract redemption amount from email: {subject}")
            return None

        currency_str = self.extract_field(text, 'currency')
        card_last_four = self.extract_field(text, 'card_last_four')
        date_str = self.extract_field(text, 'date')
        transaction_date = self.parse_date(date_str) if date_str else datetime.now()

        plan_match = re.search(r'plan de lealtad:?\s*\n?\s*([^\n]+)', text, re.IGNORECASE)
        plan = plan_match.group(1).strip() if plan_match else None
        commerce_name = f"Redención de puntos ({plan})" if plan else "Redención de puntos"

        return {
            'date': transaction_date.date() if transaction_date else datetime.now().date(),
            'amount': self.parse_amount(match.group(1)),
            'currency': self.normalize_currency(currency_str) if currency_str else 'CRC',
            'commerce_name': commerce_name,
            'card_last_four': card_last_four,
            'transaction_type': "payment",  # credit applied to the card
            'description': subject,
            'raw_text': text[:500],
        }

    def parse_service_payment(self, text: str, subject: str) -> Optional[Dict]:
        """BAC "Notificación de pago" (bill/service payment via Banca Móvil)."""
        fields = self._build_fallback_fields(text)
        if not fields['amount_str']:
            print(f"✗ Could not extract amount from email: {subject}")
            return None

        card_last_four = self.extract_field(text, 'card_last_four')
        service_match = re.search(r'pago de servicio de\s*\n?\s*([^\n]+)', text, re.IGNORECASE)
        commerce_name = service_match.group(1).strip() if service_match else "Pago de servicio"

        return {
            'date': fields['date'],
            'amount': self.parse_amount(fields['amount_str']),
            'currency': fields['currency'],
            'commerce_name': commerce_name,
            'card_last_four': card_last_four,
            'transaction_type': "purchase",
            'description': subject,
            'raw_text': text[:500],
        }

    def parse_email(
        self,
        email_body: str,
        email_headers: Dict[str, str]
    ) -> Optional[Dict]:
        """
        Parse bank email and extract transaction details.

        Args:
            email_body: Raw email body (HTML or text)
            email_headers: Email headers dictionary

        Returns:
            Dictionary with extracted transaction data or None if parsing fails
        """
        # Clean HTML
        text = self.clean_html(email_body)

        # Extract subject
        subject = email_headers.get('Subject', '')
        subject_lower = subject.lower().strip()

        # BAC account-alert emails (alerta@baccredomatic.com) don't follow the
        # generic Comercio/Monto/Tarjeta purchase layout, so they're dispatched
        # to dedicated parsers based on subject.
        if 'creaci' in subject_lower and 'retiro sin tarjeta' in subject_lower:
            # Withdrawal CODE created, not yet redeemed - no money has moved
            # yet (and the matching "retirado" confirmation email, once it
            # arrives, is what actually gets recorded - parsing both would
            # double-count the same withdrawal).
            print(f"⊘ Skipped (withdrawal code created, not yet redeemed): {subject}")
            return None
        if 'retiro sin tarjeta' in subject_lower:
            return self.parse_cash_withdrawal(text, subject)
        if subject_lower == 'transferencia':
            return self.parse_transfer(text, subject)
        if 'redenci' in subject_lower:
            return self.parse_redemption(text, subject)
        if 'notificaci' in subject_lower and 'pago' in subject_lower:
            return self.parse_service_payment(text, subject)

        # Extract fields
        amount_str = self.extract_field(text, 'amount')
        currency_str = self.extract_field(text, 'currency')
        commerce = self.extract_field(text, 'commerce')
        card_last_four = self.extract_field(text, 'card_last_four')
        date_str = self.extract_field(text, 'date')

        # Validate required fields
        if not amount_str:
            print(f"✗ Could not extract amount from email: {subject}")
            return None

        # Parse values
        amount = self.parse_amount(amount_str)
        currency = self.normalize_currency(currency_str) if currency_str else "CRC"
        transaction_date = self.parse_date(date_str) if date_str else datetime.now()
        transaction_type = self.detect_transaction_type(text, subject)

        # Build result
        result = {
            'date': transaction_date.date() if transaction_date else datetime.now().date(),
            'amount': amount,
            'currency': currency,
            'commerce_name': commerce,
            'card_last_four': card_last_four,
            'transaction_type': transaction_type,
            'description': subject,
            'raw_text': text[:500],  # Store first 500 chars for debugging
        }

        return result

    def parse_email_batch(
        self,
        emails: list
    ) -> list:
        """
        Parse multiple emails.

        Args:
            emails: List of email dictionaries with 'body' and 'headers'

        Returns:
            List of parsed transaction dictionaries
        """
        results = []

        for email in emails:
            parsed = self.parse_email(
                email.get('body', ''),
                email.get('headers', {})
            )

            if parsed:
                # Add gmail message ID
                parsed['gmail_message_id'] = email.get('message_id')
                parsed['raw_email_body'] = email.get('body', '')[:1000]  # Store sample
                results.append(parsed)

        print(f"✓ Successfully parsed {len(results)} out of {len(emails)} emails")
        return results


def test_parser():
    """Test parser with sample email."""
    parser = EmailParser()

    # Sample HTML email (customize this to match your bank's format)
    sample_html = """
    <html>
    <body>
        <h2>Notificación de Compra</h2>
        <p>Se ha realizado una compra con su tarjeta</p>
        <table>
            <tr><td>Comercio:</td><td>UBER EATS SAN JOSE</td></tr>
            <tr><td>Monto:</td><td>CRC 8,500.00</td></tr>
            <tr><td>Tarjeta:</td><td>****1234</td></tr>
            <tr><td>Fecha:</td><td>08/12/2025</td></tr>
        </table>
    </body>
    </html>
    """

    sample_headers = {
        'Subject': 'Compra realizada - Tarjeta de Crédito',
        'From': 'notificaciones@banco.cr',
        'Date': 'Sun, 8 Dec 2025 10:30:00 -0600'
    }

    result = parser.parse_email(sample_html, sample_headers)

    if result:
        print("\n✓ Parser test successful!")
        print("Extracted data:")
        for key, value in result.items():
            if key not in ['raw_text', 'raw_email_body']:
                print(f"  {key}: {value}")
    else:
        print("\n✗ Parser test failed!")

    return result


if __name__ == "__main__":
    test_parser()
