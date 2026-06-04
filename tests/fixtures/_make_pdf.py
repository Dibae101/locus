"""Generate a minimal text-layer PDF fixture (no external deps).

Produces a single-page PDF containing a few lines of text so the PdfParser can be
tested without a heavy PDF-authoring library. Run:  python tests/fixtures/_make_pdf.py
"""

from __future__ import annotations

from pathlib import Path


def _make_pdf(lines: list[str]) -> bytes:
    # Build the content stream (simple text positioning).
    text_ops = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
    for i, line in enumerate(lines):
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        if i == 0:
            text_ops.append(f"({escaped}) Tj")
        else:
            text_ops.append(f"T* ({escaped}) Tj")
    text_ops.append("ET")
    content = "\n".join(text_ops).encode("latin-1")

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
    )
    objects.append(
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode()
        + b"\n%%EOF"
    )
    return bytes(pdf)


if __name__ == "__main__":
    out = Path(__file__).parent / "sample.pdf"
    out.write_bytes(
        _make_pdf(
            [
                "Invoice INV-2001",
                "Vendor: Acme Corp",
                "Total: 512.75 USD",
            ]
        )
    )
    print(f"wrote {out}")
