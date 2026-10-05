"""Synthetic BAC-style statement text/PDF for tests (fake names and numbers)."""

SECTION = """TARJETA DE CREDITO
Banco:
BAC San José, S.A. Cédula Jurídica 3-101012009
Marca de tarjeta: AMERICAN EXPRESS
Número de cuenta: ************{acct}
Dueño de la cuenta:
JANE DOE
Fecha de corte: 18-SET-26
Fecha límite pago mínimo: 3-OCT-26
Fecha límite pago de contado: 3-OCT-26
Límite de crédito: USD 5,000.00
Saldo disponible: USD 4,000.00
Plan de lealtad: TEST PLAN
Pago mínimo amortización 800.00 5.00 Saldo anterior 10,000.00 50.00
Pago interés del periodo 200.00 1.00 Saldo del principal adeudado (compras) 3,300.00 40.00
Total pago mínimo 1,000.00 6.00 Total pago de contado 3,300.00 40.00
Saldo al corte {closing_crc} 41.00
Mes y año del estado de cuenta: SET-2026
Movimientos de la tarjeta de crédito
Total de pagos recibidos 500.00- 10.00- 0.00 0.00
B) Detalle de compras del periodo
************{card} JANE /DOE
081999300901 18-AGO-26 SUPERMERCADO UNO SAN JOSE CRC 1,000.00
082599300901 21-AGO-26 TIENDA DOS SAN JOSE CRC 2,500.00
082599300902 22-AGO-26 DEVOLUCION TIENDA DOS CRC 200.00-
082599300903 22-AGO-26 STREAMING SERVICE USD 40.00
Total de compras del periodo (del 19-AGO-26 al 18-SET-26) {purchases_crc} 40.00
C) Detalle de intereses
Monto por intereses corrientes 0.00 0.00
Monto por intereses corrientes del periodo actual 200.00 1.00
Reversión de intereses corrientes del periodo anterior 50.00- 0.00
Total por concepto de intereses 150.00 1.00
Total por concepto de productos y servicios de elección voluntaria 120.00 0.00
Tasa Nominal Anual 35.8800000% 29.6400000%
Puntos: TEST PLAN
Asignados: 1,234.50
Otras líneas de financiamiento (Línea # 1)
Monto de crédito 300.00 Plazo del crédito en meses 6
Moneda USD Tasa nominal anual 0.00
Origen del crédito (establecimiento) SHOP ONE 123 Tasa de interés total anualizada 0.00
Fecha del inicio del crédito 25-JUN-26 Tasa de interés moratoria anual 0.00
Fecha finalización del crédito 25-DIC-26 Tasa anual máxima de interés (TAMI) 30.39
Monto de la cuota otra línea de financiamiento 50.00 Porcentaje cargo por comisión de desembolso 0.00
3-OCT-26 Cuota No.3 de 6 50.00 0.00 50.00 0.00
"""


def statement_text(acct="1111", card="1112", closing_crc="3,500.00", purchases_crc="3,300.00", sections=1):
    """Defaults add up: purchases 1000+2500-200=3300; closing = cash 3300 + interest 200 = 3500."""
    one = SECTION.format(acct=acct, card=card, closing_crc=closing_crc, purchases_crc=purchases_crc)
    if sections == 2:
        one += "\n" + SECTION.format(acct="2221", card="2222", closing_crc=closing_crc, purchases_crc=purchases_crc)
    return "BAC Credomatic estado de cuenta\n" + one


def make_pdf(text: str) -> bytes:
    """A minimal one-page PDF whose extractable text is `text` (no extra deps)."""
    lines = text.splitlines()
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1", "replace").decode("latin-1")
    content = "BT /F1 6 Tf 6 TL 20 780 Td\n" + "\n".join(f"({esc(l)}) '" for l in lines) + "\nET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 800] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content.encode('latin-1', 'replace'))} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1", "replace")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out
