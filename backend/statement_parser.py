"""Parse a bank credit-card statement (estado de cuenta) PDF into structured data.

Built to survive layout changes and to fail loudly instead of silently:

* Fields are found by their printed *label* ("Saldo al corte", "Total pago
  mínimo", ...), never by position, so reordered or moved sections still parse.
* Every statement is cross-checked against its own arithmetic (purchase lines
  add up to the printed total, cash payment + period interest = closing
  balance). A mismatch or a missing field becomes a warning and the statement
  is marked "needs_review" - wrong numbers are never stored as if they were
  fine.
* The extracted text is stored with the result, so after a parser fix every
  statement can be re-parsed without uploading the PDFs again.

Currently knows the BAC Credomatic (Costa Rica) layout. Add another bank by
writing a `parse_<bank>(text)` function and registering it in `PARSERS`.
"""
import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Tuple

PARSER_VERSION = 1

MONTHS = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}

AMT = r"(\d[\d,]*\.\d{2}-?)"          # 1,234.56  or  1,234.56-  (trailing minus = negative)
DATE = r"(\d{1,2}-[A-Z]{3}-\d{2})"     # 18-SET-26
TOLERANCE = Decimal("0.05")


class StatementError(ValueError):
    """The file isn't a statement we can read at all (message is safe to show)."""


@dataclass
class FinancingLine:
    """A bank installment line ("otra línea de financiamiento"), e.g. Tasa Cero."""
    merchant: str = ""
    currency: str = ""
    total_amount: Optional[Decimal] = None
    term_months: Optional[int] = None
    annual_rate: Optional[Decimal] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    installment_amount: Optional[Decimal] = None
    installment_number: Optional[int] = None
    installments_total: Optional[int] = None


@dataclass
class ParsedStatement:
    bank: str = ""
    brand: str = ""
    loyalty_plan: str = ""
    account_last4: str = ""
    card_last4s: List[str] = field(default_factory=list)   # card numbers seen in the movements
    period: str = ""                                       # "2026-09"
    cut_date: Optional[date] = None
    min_due_date: Optional[date] = None
    cash_due_date: Optional[date] = None
    limit_currency: str = ""
    credit_limit: Optional[Decimal] = None
    available: Optional[Decimal] = None
    points_assigned: Optional[Decimal] = None
    # Per currency: {"CRC": {...}, "USD": {...}} with keys previous_balance,
    # purchases_total, payments_total, interest_charged, voluntary_total,
    # other_charges_total, min_payment, cash_payment, closing_balance, apr
    amounts: Dict[str, Dict[str, Optional[Decimal]]] = field(
        default_factory=lambda: {"CRC": {}, "USD": {}})
    financing_lines: List[FinancingLine] = field(default_factory=list)
    # (currency, amount) of every purchase line on the statement (credits are negative) -
    # used to tell which transactions dated on the cut day the statement already includes.
    purchase_lines: List[Tuple[str, Decimal]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "needs_review" if self.warnings else "ok"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _num(text: str) -> Decimal:
    negative = text.endswith("-")
    value = Decimal(text.rstrip("-").replace(",", ""))
    return -value if negative else value


def _date(text: str) -> Optional[date]:
    m = re.fullmatch(r"(\d{1,2})-([A-Z]{3})-(\d{2})", text.strip())
    if not m or m.group(2) not in MONTHS:
        return None
    return date(2000 + int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))


def _pair(section: str, label: str) -> Optional[Tuple[Decimal, Decimal]]:
    """`label  <colones>  <dollars>` anywhere on a line."""
    m = re.search(label + r"\s+" + AMT + r"\s+" + AMT, section)
    return (_num(m.group(1)), _num(m.group(2))) if m else None


def extract_text(pdf_bytes: bytes) -> str:
    """Text of every page of the PDF. Raises StatementError if unreadable."""
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted and not reader.decrypt(""):
            raise StatementError("That PDF is password-protected - remove the password first.")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except StatementError:
        raise
    except Exception:
        raise StatementError("That file isn't a readable PDF.")
    if len(text.strip()) < 200:
        raise StatementError("That PDF has no selectable text (a scan?) - download the original from the bank.")
    return text


# ---------------------------------------------------------------------------
# BAC Credomatic (Costa Rica)
# ---------------------------------------------------------------------------

ACCOUNT_MARK = re.compile(r"Número de cuenta:\s*\*+(\d{4})")


def parse_bac(text: str) -> List[ParsedStatement]:
    """One ParsedStatement per card account in the PDF (a PDF can hold several)."""
    marks = list(ACCOUNT_MARK.finditer(text))
    if not marks:
        return []
    # A section starts at the "Banco:" header just above its account number
    # (brand, dates and limit are printed around it).
    starts = []
    for mark in marks:
        header = text.rfind("Banco:", 0, mark.start())
        starts.append(header if header != -1 else mark.start())
    results = []
    for i, mark in enumerate(marks):
        end = starts[i + 1] if i + 1 < len(marks) else len(text)
        results.append(_parse_bac_section(text[starts[i]:end], mark.group(1)))
    return results


def _parse_bac_section(sec: str, account_last4: str) -> ParsedStatement:
    st = ParsedStatement(bank="BAC", account_last4=account_last4)
    warn = st.warnings.append

    def line_value(label: str) -> str:
        m = re.search(label + r"\s*:?\s*(.+)", sec)
        return m.group(1).strip() if m else ""

    st.brand = line_value(r"Marca de tarjeta")
    st.loyalty_plan = line_value(r"Plan de lealtad")

    # --- dates -------------------------------------------------------------
    st.cut_date = _date(line_value(r"Fecha de corte"))
    st.min_due_date = _date(line_value(r"Fecha límite pago mínimo"))
    st.cash_due_date = _date(line_value(r"Fecha límite pago de contado"))
    m = re.search(r"Mes y año del estado de cuenta:\s*([A-Z]{3})-(\d{4})", sec)
    if m and m.group(1) in MONTHS:
        st.period = f"{m.group(2)}-{MONTHS[m.group(1)]:02d}"
    elif st.cut_date:
        st.period = st.cut_date.strftime("%Y-%m")
    for name, value in (("cut date", st.cut_date), ("payment due date", st.cash_due_date),
                        ("statement month", st.period)):
        if not value:
            warn(f"Couldn't find the {name}.")

    # --- limit / available -------------------------------------------------
    m = re.search(r"Límite de crédito:\s*(USD|CRC)\s*" + AMT, sec)
    if m:
        st.limit_currency, st.credit_limit = m.group(1), _num(m.group(2))
    m = re.search(r"Saldo disponible:\s*(?:USD|CRC)\s*" + AMT, sec)
    if m:
        st.available = _num(m.group(1))

    # --- per-currency totals ------------------------------------------------
    def put(key: str, pair: Optional[Tuple[Decimal, Decimal]]):
        if pair:
            st.amounts["CRC"][key], st.amounts["USD"][key] = pair

    put("previous_balance", _pair(sec, r"Saldo anterior"))
    put("min_payment", _pair(sec, r"Total pago mínimo"))
    put("cash_payment", _pair(sec, r"Total pago de contado"))
    put("closing_balance", _pair(sec, r"(?m)^Saldo al corte"))
    put("voluntary_total", _pair(sec, r"Total por concepto de productos y servicios de elección voluntaria"))
    put("other_charges_total", _pair(sec, r"Total por concepto otros cargos"))
    period_interest = _pair(sec, r"Pago interés del periodo")

    m = re.search(r"Total de compras del periodo[^\n]*?" + AMT + r"\s+" + AMT + r"\s*\n", sec)
    if m:
        st.amounts["CRC"]["purchases_total"], st.amounts["USD"]["purchases_total"] = _num(m.group(1)), _num(m.group(2))

    # "Total de pagos recibidos" prints colones, colones-interest, dollars, dollars-interest.
    m = re.search(r"Total de pagos recibidos\s+" + AMT + r"\s+" + AMT + r"\s+" + AMT + r"\s+" + AMT, sec)
    if m:
        st.amounts["CRC"]["payments_total"], st.amounts["USD"]["payments_total"] = _num(m.group(1)), _num(m.group(3))

    # Interest charged this cycle: every positive "Monto por intereses ..." line
    # (reversals are credits for an earlier cycle and don't count).
    interest = [Decimal(0), Decimal(0)]
    for m in re.finditer(r"(?m)^Monto por intereses[^\d\n]*?\s+" + AMT + r"\s+" + AMT + r"\s*$", sec):
        interest[0] += _num(m.group(1))
        interest[1] += _num(m.group(2))
    st.amounts["CRC"]["interest_charged"], st.amounts["USD"]["interest_charged"] = interest

    m = re.search(r"Tasa Nominal Anual\s+([\d.]+)%\s+([\d.]+)%", sec)
    if m:
        st.amounts["CRC"]["apr"], st.amounts["USD"]["apr"] = Decimal(m.group(1)), Decimal(m.group(2))
    m = re.search(r"Asignados:\s*([\d,]+(?:\.\d+)?)", sec)
    if m:
        st.points_assigned = Decimal(m.group(1).replace(",", ""))

    for key, label in (("closing_balance", "closing balance"), ("min_payment", "minimum payment"),
                       ("cash_payment", "pay-in-full amount")):
        if "CRC" not in st.amounts or key not in st.amounts["CRC"]:
            warn(f"Couldn't find the {label}.")

    # --- purchase lines (for the cross-check) -------------------------------
    start = sec.find("B) Detalle de compras")
    stop = sec.find("Total de compras del periodo")
    if start != -1 and stop != -1:
        region = sec[start:stop]
        st.card_last4s = sorted(set(re.findall(r"\*{8,}(\d{4})", region)))
        sums = {"CRC": Decimal(0), "USD": Decimal(0)}
        for m in re.finditer(r"(?m)^\d{9,}\s+" + DATE + r"\s+.*?\s+(CRC|USD)\s+" + AMT + r"\s*$", region):
            sums[m.group(2)] += _num(m.group(3))
            st.purchase_lines.append((m.group(2), _num(m.group(3))))
        for cur in ("CRC", "USD"):
            printed = st.amounts[cur].get("purchases_total")
            if printed is not None and abs(sums[cur] - printed) > TOLERANCE:
                warn(f"{cur} purchase lines add up to {sums[cur]:,.2f} but the statement total is "
                     f"{printed:,.2f} - a line may be missing or unreadable.")
    else:
        warn("Couldn't find the purchases section.")

    # --- arithmetic cross-check ---------------------------------------------
    if period_interest:
        for i, cur in enumerate(("CRC", "USD")):
            cash = st.amounts[cur].get("cash_payment")
            closing = st.amounts[cur].get("closing_balance")
            if cash is not None and closing is not None and abs(cash + period_interest[i] - closing) > TOLERANCE:
                warn(f"{cur}: pay-in-full amount + period interest doesn't equal the closing balance - "
                     "the layout may have changed.")

    st.financing_lines = _parse_financing_lines(sec)
    return st


def _parse_financing_lines(sec: str) -> List[FinancingLine]:
    blocks = re.split(r"Otras líneas de financiamiento \(Línea # \d+\)", sec)[1:]
    lines = []
    for block in blocks:
        fl = FinancingLine()

        def grab(pattern, conv=lambda s: s):
            m = re.search(pattern, block)
            return conv(m.group(1)) if m else None

        fl.total_amount = grab(r"Monto de crédito\s+" + AMT, _num)
        fl.term_months = grab(r"Plazo del crédito en meses\s+(\d+)", int)
        fl.currency = grab(r"Moneda\s+(USD|CRC)") or ""
        fl.annual_rate = grab(r"Tasa nominal anual\s+([\d.]+)", Decimal)
        fl.merchant = (grab(r"Origen del crédito \(establecimiento\)\s+(.*?)\s+Tasa de interés total") or "").strip()
        fl.start_date = grab(r"Fecha del inicio del crédito\s+" + DATE, _date)
        fl.end_date = grab(r"Fecha finalización del crédito\s+" + DATE, _date)
        fl.installment_amount = grab(r"Monto de la cuota otra línea de financiamiento\s+" + AMT, _num)
        m = re.search(r"Cuota No\.\s*(\d+) de (\d+)", block)
        if m:
            fl.installment_number, fl.installments_total = int(m.group(1)), int(m.group(2))
        if fl.total_amount is not None or fl.installment_amount is not None:
            lines.append(fl)
    return lines


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

PARSERS: Dict[str, Callable[[str], List[ParsedStatement]]] = {"BAC": parse_bac}


def detect_bank(text: str) -> Optional[str]:
    if "BAC" in text and "Número de cuenta:" in text:
        return "BAC"
    return None


def parse_text(text: str) -> List[ParsedStatement]:
    bank = detect_bank(text)
    if not bank:
        raise StatementError("That doesn't look like a statement from a supported bank (BAC).")
    statements = PARSERS[bank](text)
    if not statements:
        raise StatementError("Recognised the bank, but found no card accounts in it - "
                             "the statement layout may have changed.")
    return statements


def parse_pdf(pdf_bytes: bytes) -> Tuple[str, List[ParsedStatement]]:
    text = extract_text(pdf_bytes)
    return text, parse_text(text)
