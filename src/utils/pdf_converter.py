import subprocess
import sys
from pathlib import Path
from typing import Optional

from ..utils.logger import log


def convert_docx_to_pdf(
    docx_path: str, output_path: Optional[str] = None
) -> Optional[str]:
    docx_path = Path(docx_path)

    if not docx_path.exists():
        log.error(f"Docx file not found: {docx_path}")
        return None

    if output_path is None:
        output_path = docx_path.with_suffix(".pdf")
    else:
        output_path = Path(output_path)

    try:
        import docx2pdf

        docx2pdf.convert(str(docx_path), str(output_path))
        log.info(f"PDF created: {output_path}")
        return str(output_path)
    except ImportError:
        log.warning("docx2pdf not installed, trying alternative method...")
        return _convert_with_libreoffice(docx_path, output_path)
    except Exception as e:
        log.error(f"PDF conversion failed: {e}")
        return _convert_with_libreoffice(docx_path, output_path)


def _convert_with_libreoffice(docx_path: Path, output_path: Path) -> Optional[str]:
    try:
        import platform

        system = platform.system()

        if system == "Windows":
            soffice = "soffice"
        elif system == "Darwin":
            soffice = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        else:
            soffice = "soffice"

        cmd = [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_path.parent),
            str(docx_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            expected_pdf = docx_path.with_suffix(".pdf")
            if expected_pdf.exists():
                if expected_pdf != output_path:
                    expected_pdf.rename(output_path)
                log.info(f"PDF created via LibreOffice: {output_path}")
                return str(output_path)

        log.error(f"LibreOffice conversion failed: {result.stderr}")
        return None

    except FileNotFoundError:
        log.error("LibreOffice not found. Install it or use pip install docx2pdf")
        return None
    except Exception as e:
        log.error(f"LibreOffice conversion error: {e}")
        return None


def ensure_pdf(resume_path: str, output_path: Optional[str] = None) -> Optional[str]:
    path = Path(resume_path)

    if path.suffix.lower() == ".pdf":
        return str(path)

    return convert_docx_to_pdf(resume_path, output_path)
