"""Local extraction only; decrypted text is never persisted in the database."""
import io
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from app.services.documents import read_encrypted_file

MAX_PAGES = 10
MAX_TEXT = 100000


def command(args, timeout=20):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout).stdout.decode("utf-8", errors="replace")


def extract_content(content, mime_type):
    if mime_type == "text/plain":
        return content.decode("utf-8", errors="replace")[:MAX_TEXT], "Texte (100 000 caractères maximum)"
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > 5_000_000:
                raise ValueError("Document XML trop volumineux")
            root = ElementTree.fromstring(archive.read(info))
            return " ".join(root.itertext())[:MAX_TEXT], "DOCX (100 000 caractères maximum)"
    if mime_type not in {"application/pdf", "image/png", "image/jpeg"}:
        return "", "Format non pris en charge pour l’extraction"
    with tempfile.TemporaryDirectory(prefix="infobridge-ocr-") as directory:
        source = Path(directory) / "source"
        source.write_bytes(content)
        if mime_type == "application/pdf":
            # Per-page OCR also covers mixed PDFs containing both text and scans.
            info = command(["pdfinfo", str(source)])
            pages = next(int(line.split(":", 1)[1].strip()) for line in info.splitlines() if line.startswith("Pages:"))
            texts = []
            for page in range(1, min(pages, MAX_PAGES) + 1):
                value = command(["pdftotext", "-f", str(page), "-l", str(page), str(source), "-"])
                if len(value.strip()) < 30:
                    prefix = str(Path(directory) / f"page-{page}")
                    command(["pdftoppm", "-f", str(page), "-l", str(page), "-singlefile", "-scale-to", "1800", "-png", str(source), prefix])
                    value = command(["tesseract", prefix + ".png", "stdout", "-l", "fra+eng"])
                texts.append(f"[Page {page}]\n{value}")
            return "\n".join(texts)[:MAX_TEXT], f"PDF/OCR : {min(pages, MAX_PAGES)} page(s) sur {pages}, 100 000 caractères maximum"
        return command(["tesseract", str(source), "stdout", "-l", "fra+eng"])[:MAX_TEXT], "OCR image : résultat à vérifier"


def attachment_text(attachment):
    if attachment.size_bytes > 20_000_000:
        return "", "Extraction limitée aux fichiers de 20 Mo maximum"
    try:
        content = read_encrypted_file(attachment.file_path, storage_backend=attachment.storage_backend,
            encryption_key_ref=attachment.encryption_key_ref, encryption_algorithm=attachment.encryption_algorithm,
            encrypted_data_key=attachment.encrypted_data_key, encryption_nonce=attachment.encryption_nonce)
        return extract_content(content, attachment.mime_type)
    except (FileNotFoundError, subprocess.SubprocessError):
        return "", "Extraction indisponible : moteur OCR absent, délai dépassé ou document illisible"
    except Exception:
        return "", "Extraction impossible pour cette pièce"


def summarize_text(content, subject, limit=1500):
    """Select relevant source sentences, preserving their order and wording."""
    import re
    keywords = {word.casefold() for word in re.findall(r"\w+", subject) if len(word) > 3}
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", content) if part.strip()]
    ranked = sorted(enumerate(sentences), key=lambda item: (
        -len(keywords & {word.casefold() for word in re.findall(r"\w+", item[1])}), item[0]))
    selected = sorted(ranked[:4])
    return "\n[…]\n".join(sentence for _, sentence in selected)[:limit]
