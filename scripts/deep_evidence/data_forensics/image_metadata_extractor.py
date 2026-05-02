#!/usr/bin/env python3
"""
image_metadata_extractor.py

Extract image metadata from PDFs to detect anomalies.
Scans embedded images for resolution, software metadata, and duplicates.

Supported sources:
    Embedded images inside PDF files (local filesystem)

Anomalies flagged:
    - duplicate_image_across_papers: same image hash in multiple papers
    - suspicious_resolution: very low resolution for scientific figures
    - mismatched_software: image editing software in scientific figure metadata
    - missing_metadata: no creation metadata at all

Usage:
    python image_metadata_extractor.py --pdfs ./data/pdfs/ --output ./data/image_audit.json
    python image_metadata_extractor.py --pdf-list ./data/pdf_list.json --output ./data/image_audit.json --hash-threshold 5
"""

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("image_metadata_extractor")

# Optional dependencies — imported lazily
_HAS_PIKEPDF = False
_HAS_PYMUPDF = False

try:
    import pikepdf
    _HAS_PIKEPDF = True
except Exception:
    pass

try:
    import fitz  # PyMuPDF
    _HAS_PYMUPDF = True
except Exception:
    pass

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ImageRecord:
    pdf_path: str
    image_index: int
    format: str
    width: int
    height: int
    dpi: Optional[float]
    software: Optional[str]
    created: Optional[str]
    md5_hash: str
    perceptual_hash: Optional[str]
    flags: list[str]


# ---------------------------------------------------------------------------
# Image extraction backends
# ---------------------------------------------------------------------------


def _average_hash(img) -> Optional[str]:
    """Compute a simple 8x8 average hash string."""
    if not _HAS_PIL:
        return None
    try:
        small = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
        pixels = list(small.getdata())
        avg = sum(pixels) / len(pixels)
        bits = "".join("1" if p >= avg else "0" for p in pixels)
        return hex(int(bits, 2))[2:].zfill(16)
    except Exception:
        return None


def _extract_with_pikepdf(pdf_path: Path) -> list[ImageRecord]:
    records: list[ImageRecord] = []
    try:
        pdf = pikepdf.open(str(pdf_path))
    except Exception as exc:
        logger.warning("pikepdf cannot open %s: %s", pdf_path, exc)
        return records

    img_idx = 0
    for page in pdf.pages:
        if "/Resources" not in page or "/XObject" not in page.Resources:
            continue
        xobjects = page.Resources.XObject
        for name, xobj in xobjects.items():
            try:
                obj = pikepdf.PdfImage(xobj)
            except Exception:
                continue
            try:
                raw = obj.as_pil_image()
            except Exception:
                continue
            img_idx += 1
            md5 = hashlib.md5(raw.tobytes()).hexdigest()
            phash = _average_hash(raw)
            width, height = raw.size
            dpi = obj.dpi[0] if hasattr(obj, "dpi") and obj.dpi else None
            software = None
            created = None
            flags = []
            if _HAS_PIL and hasattr(raw, "info"):
                info = raw.info
                software = info.get("Software")
                created = info.get("DateTime")
            records.append(ImageRecord(
                pdf_path=str(pdf_path),
                image_index=img_idx,
                format=raw.format or "UNKNOWN",
                width=width,
                height=height,
                dpi=dpi,
                software=software,
                created=created,
                md5_hash=md5,
                perceptual_hash=phash,
                flags=flags,
            ))
    pdf.close()
    return records


def _extract_with_pymupdf(pdf_path: Path) -> list[ImageRecord]:
    records: list[ImageRecord] = []
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        logger.warning("PyMuPDF cannot open %s: %s", pdf_path, exc)
        return records

    img_idx = 0
    for page in doc:
        images = page.get_images(full=True)
        for img in images:
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                ext = base_image["ext"].upper()
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
            except Exception:
                continue
            img_idx += 1
            md5 = hashlib.md5(image_bytes).hexdigest()
            phash = None
            software = None
            created = None
            dpi = None
            if _HAS_PIL:
                try:
                    pil_img = Image.open(__import__("io").BytesIO(image_bytes))
                    phash = _average_hash(pil_img)
                    width, height = pil_img.size
                    dpi = pil_img.info.get("dpi", (None, None))[0]
                    software = pil_img.info.get("Software")
                    created = pil_img.info.get("DateTime")
                except Exception:
                    pass
            records.append(ImageRecord(
                pdf_path=str(pdf_path),
                image_index=img_idx,
                format=ext,
                width=width,
                height=height,
                dpi=dpi,
                software=software,
                created=created,
                md5_hash=md5,
                perceptual_hash=phash,
                flags=[],
            ))
    doc.close()
    return records


def _extract_images(pdf_path: Path) -> list[ImageRecord]:
    if _HAS_PIKEPDF:
        return _extract_with_pikepdf(pdf_path)
    if _HAS_PYMUPDF:
        return _extract_with_pymupdf(pdf_path)
    logger.error("No PDF image extraction backend available (install pikepdf or PyMuPDF)")
    return []


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

SUSPICIOUS_SOFTWARE = {"Photoshop", "GIMP", "Adobe", "Paint", "Canva"}
MIN_DPI = 150


def _hamming_distance(a: str, b: str) -> int:
    """Hamming distance between two hex strings."""
    if not a or not b or len(a) != len(b):
        return 999
    try:
        x = int(a, 16)
        y = int(b, 16)
        return bin(x ^ y).count("1")
    except ValueError:
        return 999


def flag_anomalies(all_records: list[ImageRecord], hash_threshold: int) -> list[ImageRecord]:
    # Group by hash for duplicate detection
    md5_groups: dict[str, list[ImageRecord]] = {}
    for rec in all_records:
        md5_groups.setdefault(rec.md5_hash, []).append(rec)

    phash_groups: dict[str, list[ImageRecord]] = {}
    for rec in all_records:
        if rec.perceptual_hash:
            phash_groups.setdefault(rec.perceptual_hash, []).append(rec)

    flagged: list[ImageRecord] = []
    for rec in all_records:
        flags: list[str] = []
        # Resolution check
        if rec.dpi and rec.dpi < MIN_DPI:
            flags.append("suspicious_resolution")
        # Software check
        if rec.software:
            sw_lower = rec.software.lower()
            for suspect in SUSPICIOUS_SOFTWARE:
                if suspect.lower() in sw_lower:
                    flags.append("mismatched_software")
                    break
        # Missing metadata
        if not rec.software and not rec.created:
            flags.append("missing_metadata")
        # Duplicate across papers (different PDF paths)
        siblings = md5_groups.get(rec.md5_hash, [])
        pdf_paths = {r.pdf_path for r in siblings}
        if len(pdf_paths) > 1:
            flags.append("duplicate_image_across_papers")
        else:
            # Also check perceptual hash neighbors
            if rec.perceptual_hash:
                for other_hash, other_recs in phash_groups.items():
                    if other_hash == rec.perceptual_hash:
                        continue
                    if _hamming_distance(rec.perceptual_hash, other_hash) <= hash_threshold:
                        other_paths = {r.pdf_path for r in other_recs}
                        if len(other_paths | {rec.pdf_path}) > 1:
                            flags.append("duplicate_image_across_papers")
                            break
        rec.flags = flags
        flagged.append(rec)
    return flagged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Extract image metadata from PDFs for anomaly detection")
    p.add_argument("--pdfs", type=Path, help="Directory containing PDF files")
    p.add_argument("--pdf-list", type=Path, help="JSON array of PDF file paths")
    p.add_argument("--output", type=Path, default=Path("./data/image_audit.json"), help="Output JSON path")
    p.add_argument("--hash-threshold", type=int, default=5, help="Perceptual hash Hamming threshold for duplicates")
    p.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel(10)

    pdf_paths: list[Path] = []
    if args.pdfs:
        if not args.pdfs.exists():
            logger.error("PDF directory not found: %s", args.pdfs)
            sys.exit(1)
        pdf_paths = sorted(args.pdfs.glob("*.pdf"))
    elif args.pdf_list:
        if not args.pdf_list.exists():
            logger.error("PDF list file not found: %s", args.pdf_list)
            sys.exit(1)
        with open(args.pdf_list, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        for p in raw:
            pdf_paths.append(Path(p))
    else:
        logger.error("Either --pdfs or --pdf-list must be provided")
        sys.exit(1)

    logger.info("Found %d PDF files to scan", len(pdf_paths))

    if not _HAS_PIKEPDF and not _HAS_PYMUPDF:
        logger.error("No PDF backend available. Install pikepdf (`pip install pikepdf`) or PyMuPDF (`pip install PyMuPDF`).")
        # Still produce empty output so pipeline does not break
        result = {
            "meta": {
                "queried_at": datetime.now().isoformat(),
                "pdfs_scanned": len(pdf_paths),
                "images_found": 0,
                "anomaly_count": 0,
                "backends": {"pikepdf": _HAS_PIKEPDF, "pymupdf": _HAS_PYMUPDF, "pil": _HAS_PIL},
            },
            "images": [],
            "alerts": [],
        }
        save_json(result, args.output)
        sys.exit(0)

    all_records: list[ImageRecord] = []
    for pdf_path in pdf_paths:
        if not pdf_path.exists():
            logger.warning("PDF not found, skipping: %s", pdf_path)
            continue
        records = _extract_images(pdf_path)
        logger.info("%s: extracted %d images", pdf_path.name, len(records))
        all_records.extend(records)

    all_records = flag_anomalies(all_records, args.hash_threshold)

    anomalies = [r for r in all_records if r.flags]
    alerts = []
    for rec in anomalies:
        for flag in rec.flags:
            alerts.append({
                "pdf_path": rec.pdf_path,
                "image_index": rec.image_index,
                "flag": flag,
                "md5_hash": rec.md5_hash,
                "perceptual_hash": rec.perceptual_hash,
                "format": rec.format,
                "width": rec.width,
                "height": rec.height,
                "dpi": rec.dpi,
                "software": rec.software,
            })

    signals = []
    conf_map = {
        "duplicate_image_across_papers": 0.8,
        "mismatched_software": 0.75,
        "suspicious_resolution": 0.6,
        "missing_metadata": 0.5,
    }
    for alert in alerts:
        flag = alert["flag"]
        signals.append({
            "type": flag,
            "description": f"Image {alert['image_index']} in {alert['pdf_path']}: {flag}",
            "confidence": float(conf_map.get(flag, 0.5)),
            "paper_id": alert["pdf_path"],
            "source": "image_metadata_extractor",
            "evidence": {
                "md5_hash": alert["md5_hash"],
                "perceptual_hash": alert["perceptual_hash"],
                "format": alert["format"],
                "width": alert["width"],
                "height": alert["height"],
                "dpi": alert["dpi"],
                "software": alert["software"],
            },
        })

    result = {
        "meta": {
            "script": "image_metadata_extractor",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.pdfs or args.pdf_list),
            "pdfs_scanned": len(pdf_paths),
            "images_found": len(all_records),
            "anomaly_count": len(alerts),
            "backends": {"pikepdf": _HAS_PIKEPDF, "pymupdf": _HAS_PYMUPDF, "pil": _HAS_PIL},
        },
        "signals": signals,
        "details": {
            "images": [asdict(r) for r in all_records],
            "alerts": alerts,
        },
    }

    save_json(result, args.output)
    logger.info("Saved image audit to %s", args.output)

    print(f"\n{'='*60}")
    print(f"Image Metadata Extractor Summary")
    print(f"{'='*60}")
    print(f"PDFs scanned:    {len(pdf_paths)}")
    print(f"Images found:    {len(all_records)}")
    print(f"Anomalies:       {len(alerts)}")
    if alerts:
        by_flag: dict[str, int] = {}
        for a in alerts:
            by_flag[a["flag"]] = by_flag.get(a["flag"], 0) + 1
        print(f"\nBy flag:")
        for f, c in sorted(by_flag.items(), key=lambda x: -x[1]):
            print(f"  {f}: {c}")
    print(f"\nOutput:         {args.output}")


if __name__ == "__main__":
    main()
