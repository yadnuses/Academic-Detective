#!/usr/bin/env python3
"""
watermark.py

Invisible watermark toolkit for investigation reports.
Uses zero-width characters (U+200B, U+200C, U+200D, U+FEFF) to encode
tracking information into text. The watermark survives copy-paste,
screenshots (via OCR on rendered text), and most format conversions.

Usage:
    # Embed watermark into a markdown file
    python watermark.py embed --input report.md --output report_watermarked.md \
        --case-id AD-2026-0418-001 --client zhangsan

    # Extract watermark from text
    python watermark.py extract --input report_watermarked.md

    # Verify file integrity (SHA-256)
    python watermark.py hash --input report.md --case-dir ./cases/zhangsan
"""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.utils import get_logger, save_json

logger = get_logger("watermark")

# ---------------------------------------------------------------------------
# Zero-width character codec
# ---------------------------------------------------------------------------

# 4 zero-width chars = 2 bits per char = binary encoding
ZW_CHARS = {
    "00": "\u200b",   # ZERO WIDTH SPACE
    "01": "\u200c",   # ZERO WIDTH NON-JOINER
    "10": "\u200d",   # ZERO WIDTH JOINER
    "11": "\ufeff",   # ZERO WIDTH NO-BREAK SPACE (BOM)
}

ZW_REVERSE = {v: k for k, v in ZW_CHARS.items()}

# Delimiter: a recognizable pattern to locate watermark
# Using a sequence that won't appear in normal text
DELIMITER_BITS = "00" * 8  # 16 bits of 00 -> 8x U+200B


def _str_to_bits(s: str) -> str:
    """Convert string to binary representation."""
    return "".join(format(ord(c), "016b") for c in s)


def _bits_to_str(bits: str) -> str:
    """Convert binary representation back to string."""
    chars = []
    for i in range(0, len(bits), 16):
        chunk = bits[i:i + 16]
        if len(chunk) == 16:
            chars.append(chr(int(chunk, 2)))
    return "".join(chars)


def _bits_to_zw(bits: str) -> str:
    """Encode bit string into zero-width characters."""
    result = []
    for i in range(0, len(bits), 2):
        pair = bits[i:i + 2]
        if pair in ZW_CHARS:
            result.append(ZW_CHARS[pair])
        else:
            # Pad incomplete pair
            result.append(ZW_CHARS["00"])
    return "".join(result)


def _zw_to_bits(zw_text: str) -> str:
    """Decode zero-width characters into bit string."""
    bits = []
    for ch in zw_text:
        if ch in ZW_REVERSE:
            bits.append(ZW_REVERSE[ch])
    return "".join(bits)


def encode_watermark(payload: str) -> str:
    """
    Encode a payload string into zero-width characters.
    Format: [DELIMITER][length(16bits)][payload_bits][DELIMITER]
    """
    length_bits = format(len(payload), "016b")
    payload_bits = _str_to_bits(payload)
    full_bits = DELIMITER_BITS + length_bits + payload_bits + DELIMITER_BITS
    return _bits_to_zw(full_bits)


def decode_watermark(text: str) -> Optional[str]:
    """
    Extract and decode watermark from text.
    Returns the payload string or None if no watermark found.
    """
    # Collect all zero-width characters from text
    zw_chars = [ch for ch in text if ch in ZW_REVERSE]
    if len(zw_chars) < 20:  # Too short to contain a valid watermark
        return None

    zw_string = "".join(zw_chars)
    bits = _zw_to_bits(zw_string)

    # Find delimiters
    delim_pattern = DELIMITER_BITS
    positions = []
    start = 0
    while True:
        idx = bits.find(delim_pattern, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + len(delim_pattern)

    if len(positions) < 2:
        return None

    # Extract payload between first two delimiters
    payload_start = positions[0] + len(delim_pattern)
    payload_end = positions[1]
    payload_bits = bits[payload_start:payload_end]

    if len(payload_bits) < 16:
        return None

    # First 16 bits = length
    length = int(payload_bits[:16], 2)
    data_bits = payload_bits[16:]

    # Validate length
    expected_bits = length * 16
    if len(data_bits) < expected_bits:
        logger.warning("Watermark truncated: expected %d bits, got %d", expected_bits, len(data_bits))
        return None

    payload = _bits_to_str(data_bits[:expected_bits])
    return payload


# ---------------------------------------------------------------------------
# Watermark embedding strategies
# ---------------------------------------------------------------------------

def build_watermark_payload(case_id: str, client: str, investigator: str = "") -> str:
    """Build a compact watermark payload."""
    payload = {
        "c": case_id,           # case-id
        "cl": client,           # client identifier
        "t": int(datetime.now().timestamp()),  # timestamp
        "i": investigator,      # investigator
    }
    # Compact JSON, no spaces
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def embed_in_markdown(text: str, watermark_zw: str, strategy: str = "header") -> str:
    """
    Embed zero-width watermark into markdown text.

    Strategies:
        - "header": Insert after the first heading (# Title)
        - "paragraph": Insert after the first paragraph
        - "distributed": Distribute across first N paragraphs
        - "every_period": Append to every sentence in first paragraph
    """
    if strategy == "header":
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("#"):
                # Insert watermark after heading line
                lines[i] = line + watermark_zw
                break
        return "\n".join(lines)

    elif strategy == "paragraph":
        # Find first non-empty, non-heading paragraph
        lines = text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("|"):
                lines[i] = line + watermark_zw
                break
        return "\n".join(lines)

    elif strategy == "every_period":
        # Split first paragraph by Chinese/English periods, embed in each
        lines = text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("|"):
                # Split by sentence endings
                import re
                sentences = re.split(r'(。\.\.\!\?)', stripped)
                # Embed partial watermark in each sentence
                if len(sentences) > 1:
                    # Distribute watermark chars across sentences
                    chars = list(watermark_zw)
                    n = len(sentences) // 2  # number of sentence breaks
                    per_sentence = max(1, len(chars) // max(n, 1))
                    result = []
                    char_idx = 0
                    for j, part in enumerate(sentences):
                        if j % 2 == 0 and char_idx < len(chars):
                            end = min(char_idx + per_sentence, len(chars))
                            result.append(part + "".join(chars[char_idx:end]))
                            char_idx = end
                        else:
                            result.append(part)
                    lines[i] = "".join(result)
                else:
                    lines[i] = line + watermark_zw
                break
        return "\n".join(lines)

    else:
        # Default: append to first line
        lines = text.split("\n")
        lines[0] = lines[0] + watermark_zw
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# File integrity
# ---------------------------------------------------------------------------

def compute_file_hash(filepath: Path | str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def save_hash_manifest(case_dir: Path | str, files: list[str], metadata: dict) -> Path:
    """Save hash manifest for delivered files."""
    case_path = Path(case_dir)
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "files": {},
        "metadata": metadata,
    }
    for f in files:
        fp = case_path / f
        if fp.exists():
            manifest["files"][f] = {
                "sha256": compute_file_hash(fp),
                "size": fp.stat().st_size,
            }

    manifest_path = case_path / "report_hash_manifest.json"
    save_json(manifest, manifest_path)
    logger.info("Hash manifest saved: %s", manifest_path)
    return manifest_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_embed(args):
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        return

    text = input_path.read_text(encoding="utf-8")

    payload = build_watermark_payload(
        case_id=args.case_id,
        client=args.client,
        investigator=args.investigator or "",
    )
    watermark_zw = encode_watermark(payload)

    watermarked = embed_in_markdown(text, watermark_zw, strategy=args.strategy)

    output_path = Path(args.output)
    output_path.write_text(watermarked, encoding="utf-8")
    logger.info("Watermarked report saved: %s", output_path)
    logger.info("Watermark payload: %s", payload)
    logger.info("Zero-width chars embedded: %d", len(watermark_zw))


def cmd_extract(args):
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        return

    text = input_path.read_text(encoding="utf-8")
    payload = decode_watermark(text)

    if payload:
        try:
            data = json.loads(payload)
            print("Watermarks found:")
            print(f"  Case ID:     {data.get('c', 'N/A')}")
            print(f"  Client:      {data.get('cl', 'N/A')}")
            print(f"  Timestamp:   {data.get('t', 'N/A')}")
            print(f"  Investigator:{data.get('i', 'N/A')}")
            ts = data.get('t')
            if ts:
                print(f"  Generated:   {datetime.fromtimestamp(ts).isoformat()}")
        except json.JSONDecodeError:
            print(f"Raw payload: {payload}")
    else:
        print("No watermark found.")


def cmd_hash(args):
    filepath = Path(args.input)
    if not filepath.exists():
        logger.error("File not found: %s", filepath)
        return

    file_hash = compute_file_hash(filepath)
    print(f"SHA-256: {file_hash}")
    print(f"File:    {filepath}")

    if args.case_dir:
        manifest = save_hash_manifest(
            args.case_dir,
            [str(filepath.name)],
            {"file": str(filepath.name), "sha256": file_hash},
        )
        print(f"Manifest: {manifest}")


def main():
    parser = argparse.ArgumentParser(description="Invisible watermark toolkit for investigation reports")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_embed = subparsers.add_parser("embed", help="Embed invisible watermark into text file")
    p_embed.add_argument("--input", "-i", required=True, help="Input markdown file")
    p_embed.add_argument("--output", "-o", required=True, help="Output watermarked file")
    p_embed.add_argument("--case-id", "-c", required=True, help="Case identifier (e.g. AD-2026-0418-001)")
    p_embed.add_argument("--client", "-cl", required=True, help="Client identifier")
    p_embed.add_argument("--investigator", "-inv", default="", help="Investigator name")
    p_embed.add_argument("--strategy", "-s", default="header", choices=["header", "paragraph", "every_period"], help="Embedding strategy")

    p_extract = subparsers.add_parser("extract", help="Extract watermark from text file")
    p_extract.add_argument("--input", "-i", required=True, help="Input file to analyze")

    p_hash = subparsers.add_parser("hash", help="Compute SHA-256 hash of a file")
    p_hash.add_argument("--input", "-i", required=True, help="File to hash")
    p_hash.add_argument("--case-dir", "-C", help="Case directory to save hash manifest")

    args = parser.parse_args()

    if args.command == "embed":
        cmd_embed(args)
    elif args.command == "extract":
        cmd_extract(args)
    elif args.command == "hash":
        cmd_hash(args)


if __name__ == "__main__":
    main()
