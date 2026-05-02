#!/usr/bin/env python3
"""
stylometry_profiler.py

Stylometric feature extractor for Chinese academic texts.
Detects ghostwriting / team-writing signals by comparing low-level
language fingerprints across documents.

New in v2.0:
  - word_frequency_heatmap: z-score deviations from scholar baseline per
    feature, enabling visual identification of outlier documents.
  - Heatmap is included in every run; no separate invocation needed.

Semi-automatic principle: human selects and labels the comparison corpus;
script computes feature vectors, similarity matrices, and PCA projections.

Usage:
    python stylometry_profiler.py --manifest ./manifest.json --output ./style_report.json

Manifest JSON schema:
[
  {
    "path": "./pdfs/paper1.pdf",
    "label": "scholar",
    "title": "主权资产负债表研究",
    "year": 2012,
    "note": "学者独立一作"
  },
  {
    "path": "./pdfs/target1.pdf",
    "label": "target",
    "title": "现代化经济体系研究",
    "year": 2019
  },
  {
    "path": "./texts/student_thesis.txt",
    "label": "student",
    "title": "学生毕业论文"
  }
]

Labels:
  - "scholar" : baseline corpus of the investigated scholar
  - "target"  : document(s) under suspicion
  - "student" : suspected ghostwriter / assistant
  (Any custom label is accepted.)
"""

import json
import re
import sys
import math
import argparse
from pathlib import Path
from collections import defaultdict


def extract_text(file_path: str) -> str:
    """Extract text from PDF or read plain text / Markdown file."""
    p = Path(file_path)
    if p.suffix.lower() in {".txt", ".md"}:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    # PDF extraction (reuse logic from text_profiler.py)
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] pdfplumber failed for {file_path}: {e}", file=sys.stderr)

    try:
        import fitz
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        doc.close()
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] PyMuPDF failed for {file_path}: {e}", file=sys.stderr)

    try:
        import PyPDF2
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] PyPDF2 failed for {file_path}: {e}", file=sys.stderr)

    if not text.strip():
        raise RuntimeError(
            f"Failed to extract text from {file_path}. "
            "Supported formats: .pdf, .md, .txt. "
            "For PDFs, please install one of: pdfplumber, PyMuPDF (fitz), or PyPDF2."
        )
    return text


def split_sentences(text: str) -> list:
    """Split Chinese text into sentences by 。！？"""
    # Normalize whitespace
    text = re.sub(r"\s+", "", text)
    # Split while keeping the delimiter would be complex; simple split is enough
    sentences = re.split(r"[。！？]+", text)
    return [s.strip() for s in sentences if s.strip()]


def compute_features(text: str) -> dict:
    """Compute stylometric feature vector for a Chinese text."""
    sentences = split_sentences(text)
    sentence_count = len(sentences)

    # Total characters (Chinese + alphanumeric)
    total_chars = len(text.replace(" ", "").replace("\n", ""))
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))

    # Clause complexity: sentences with >2 commas or a semicolon
    complex_sentences = 0
    for s in sentences:
        comma_count = s.count("，")
        if comma_count > 2 or "；" in s:
            complex_sentences += 1

    clause_complexity = round(complex_sentences / sentence_count, 4) if sentence_count else 0
    avg_sentence_length = round(total_chars / sentence_count, 2) if sentence_count else 0

    # Helper for density per N chars
    def density(term_list, base=100):
        total = sum(text.count(t) for t in term_list)
        return round(total / (total_chars / base), 4) if total_chars else 0

    def density_per_1000(term_list):
        return density(term_list, 1000)

    # 1. 的 density
    de_density = density(["的"])

    # 2. Aspect particles
    aspect_density = density(["了", "着", "过"])

    # 3. Contrast connectors
    contrast_density = density(["而", "但", "然而", "不过", "可是"])

    # 4. Formulaic phrases (per 1000)
    formulaic = {
        "综上所述": text.count("综上所述"),
        "一言以蔽之": text.count("一言以蔽之"),
        "毋庸讳言": text.count("毋庸讳言"),
        "值得注意的是": text.count("值得注意的是"),
        "本文认为": text.count("本文认为"),
        "笔者认为": text.count("笔者认为"),
    }
    formulaic_density = {k: round(v / (total_chars / 1000), 4) if total_chars else 0 for k, v in formulaic.items()}

    # 5. Enumeration preference
    flow_markers = sum(text.count(t) for t in ["首先", "其次", "最后", "再次"])
    num_markers = sum(text.count(t) for t in ["第一", "第二", "第三", "第四", "第五", "其一", "其二", "其三"])
    total_enum = flow_markers + num_markers
    enum_preference = round(flow_markers / total_enum, 4) if total_enum else None

    # 6. Punctuation ratios (per 1000 chars)
    semicolons = text.count("；")
    colons = text.count("：")
    dashes = len(re.findall(r"——|—", text))
    quotes = len(re.findall(r'["""''「」『』]', text))
    punct_density = {
        "semicolon": round(semicolons / (total_chars / 1000), 4),
        "colon": round(colons / (total_chars / 1000), 4),
        "dash": round(dashes / (total_chars / 1000), 4),
        "quote": round(quotes / (total_chars / 1000), 4),
    }

    # 7. Self-reference density (per 1000)
    self_refs = density_per_1000(["笔者", "本文", "我们"])

    # 8. Verb density (per 1000)
    verb_density = density_per_1000(["认为", "发现", "指出", "表明"])

    return {
        "total_chars": total_chars,
        "chinese_chars": chinese_chars,
        "sentence_count": sentence_count,
        "avg_sentence_length": avg_sentence_length,
        "clause_complexity": clause_complexity,
        "de_density": de_density,
        "aspect_density": aspect_density,
        "contrast_density": contrast_density,
        "formulaic_density": formulaic_density,
        "enumeration_preference": enum_preference,
        "punctuation_density": punct_density,
        "self_reference_density": self_refs,
        "verb_density": verb_density,
    }


def build_feature_vector(features: dict) -> list:
    """Flatten feature dict into a numeric vector for similarity/PCA."""
    fd = features["formulaic_density"]
    pd = features["punctuation_density"]
    return [
        features["avg_sentence_length"],
        features["clause_complexity"],
        features["de_density"],
        features["aspect_density"],
        features["contrast_density"],
        fd.get("综上所述", 0),
        fd.get("一言以蔽之", 0),
        fd.get("毋庸讳言", 0),
        fd.get("值得注意的是", 0),
        fd.get("本文认为", 0),
        fd.get("笔者认为", 0),
        features["enumeration_preference"] if features["enumeration_preference"] is not None else 0.5,
        pd.get("semicolon", 0),
        pd.get("colon", 0),
        pd.get("dash", 0),
        pd.get("quote", 0),
        features["self_reference_density"],
        features["verb_density"],
    ]


def cosine_similarity(v1: list, v2: list) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return round(dot / (norm1 * norm2), 4)


def compute_similarity_matrix(docs: list, vectors: list) -> dict:
    n = len(docs)
    matrix = {}
    for i in range(n):
        row = {}
        for j in range(n):
            row[docs[j]["id"]] = cosine_similarity(vectors[i], vectors[j])
        matrix[docs[i]["id"]] = row
    return matrix


def compute_pca(vectors: list, n_components: int = 2) -> list:
    """Simple PCA using numpy SVD. Falls back to None if numpy unavailable."""
    try:
        import numpy as np
    except ImportError:
        return None

    X = np.array(vectors, dtype=float)
    # Center
    mean = np.mean(X, axis=0)
    Xc = X - mean
    # SVD
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    # Projection
    components = Vt[:n_components]
    projected = np.dot(Xc, components.T)
    return projected.tolist()


def generate_word_frequency_heatmap(docs: list, vectors: list, n_top_features: int = 15) -> dict:
    """
    Generate a word-frequency-difference heatmap comparing each document
    against the scholar baseline mean.

    Returns structured data for HTML/JSON visualization:
      - features: list of feature names
      - documents: list of doc ids with their deviation-from-baseline per feature
    """
    # Build feature labels matching build_feature_vector order
    feature_labels = [
        "avg_sentence_length",
        "clause_complexity",
        "de_density",
        "aspect_density",
        "contrast_density",
        "formulaic_综上所述",
        "formulaic_一言以蔽之",
        "formulaic_毋庸讳言",
        "formulaic_值得注意的是",
        "formulaic_本文认为",
        "formulaic_笔者认为",
        "enumeration_preference",
        "punct_semicolon",
        "punct_colon",
        "punct_dash",
        "punct_quote",
        "self_reference_density",
        "verb_density",
    ]

    # Identify scholar baseline indices
    labels = [d.get("label", "unknown") for d in docs]
    scholar_indices = [i for i, lbl in enumerate(labels) if lbl == "scholar"]

    if len(scholar_indices) < 2:
        return {
            "status": "insufficient_baseline",
            "note": "Need at least 2 scholar documents to compute deviation heatmap.",
            "feature_labels": feature_labels,
            "heatmap_data": None,
        }

    # Compute scholar baseline mean vector
    scholar_vecs = [vectors[i] for i in scholar_indices]
    baseline_mean = [sum(col) / len(col) for col in zip(*scholar_vecs)]

    # Compute z-score normalization (std across scholar baseline)
    baseline_std = []
    for col_idx in range(len(baseline_mean)):
        col_vals = [v[col_idx] for v in scholar_vecs]
        mean = baseline_mean[col_idx]
        variance = sum((x - mean) ** 2 for x in col_vals) / len(col_vals)
        std = math.sqrt(variance) if variance > 0 else 1.0
        baseline_std.append(std)

    # Compute deviation for each document
    heatmap_entries = []
    max_abs_deviation = 0
    for doc_idx, doc in enumerate(docs):
        vec = vectors[doc_idx]
        feature_deviations = []
        for feat_idx in range(len(vec)):
            if baseline_std[feat_idx] > 0:
                z = (vec[feat_idx] - baseline_mean[feat_idx]) / baseline_std[feat_idx]
            else:
                z = 0.0
            feature_deviations.append(round(z, 3))
            max_abs_deviation = max(max_abs_deviation, abs(z))

        heatmap_entries.append({
            "id": doc["id"],
            "title": doc["title"],
            "label": doc["label"],
            "deviations": feature_deviations,
        })

    return {
        "status": "success",
        "feature_labels": feature_labels,
        "scaling": "z-score vs scholar baseline mean",
        "max_abs_deviation": round(max_abs_deviation, 2),
        "n_scholar_baseline_docs": len(scholar_indices),
        "entries": heatmap_entries,
    }


def generate_red_flags(docs: list, vectors: list, labels: list) -> list:
    """Generate red flags based on stylometric distances."""
    flags = []

    # Group by label
    label_indices = defaultdict(list)
    for idx, lbl in enumerate(labels):
        label_indices[lbl].append(idx)

    scholar_indices = label_indices.get("scholar", [])
    target_indices = label_indices.get("target", [])
    student_indices = label_indices.get("student", [])

    if len(scholar_indices) < 2:
        flags.append({
            "signal": "Insufficient baseline corpus",
            "detail": "Need at least 2 documents labeled 'scholar' to compute baseline consistency.",
            "severity": "low"
        })
        return flags

    # Scholar internal consistency
    scholar_sims = []
    for i in scholar_indices:
        for j in scholar_indices:
            if i < j:
                scholar_sims.append(cosine_similarity(vectors[i], vectors[j]))
    scholar_mean = sum(scholar_sims) / len(scholar_sims) if scholar_sims else 0
    scholar_std = math.sqrt(sum((s - scholar_mean) ** 2 for s in scholar_sims) / len(scholar_sims)) if scholar_sims else 0

    if scholar_mean < 0.4:
        flags.append({
            "signal": "Low scholar internal consistency",
            "detail": f"Mean similarity among scholar baseline docs: {scholar_mean:.2f}. Suggests scholar style is highly variable or texts are from different authors.",
            "severity": "high" if scholar_mean < 0.3 else "medium-high"
        })

    for t_idx in target_indices:
        target_vec = vectors[t_idx]
        target_doc = docs[t_idx]

        # Target vs scholar baseline
        target_scholar_sims = [cosine_similarity(target_vec, vectors[s]) for s in scholar_indices]
        ts_mean = sum(target_scholar_sims) / len(target_scholar_sims) if target_scholar_sims else 0

        if ts_mean < 0.3:
            flags.append({
                "signal": "Significant style break (target vs scholar)",
                "detail": f"Document '{target_doc['title']}' mean similarity to scholar baseline: {ts_mean:.2f}",
                "severity": "high"
            })
        elif ts_mean < scholar_mean - 2 * scholar_std:
            flags.append({
                "signal": "Target document deviates from scholar baseline",
                "detail": f"Document '{target_doc['title']}' similarity {ts_mean:.2f} is >2 std below scholar baseline mean {scholar_mean:.2f}.",
                "severity": "high"
            })

        # Target vs student
        for st_idx in student_indices:
            st_sim = cosine_similarity(target_vec, vectors[st_idx])
            st_doc = docs[st_idx]
            if st_sim > scholar_mean:
                flags.append({
                    "signal": "Target document resembles student style more than scholar baseline",
                    "detail": f"'{target_doc['title']}' vs '{st_doc['title']}': {st_sim:.2f}, which exceeds scholar baseline mean {scholar_mean:.2f}.",
                    "severity": "high"
                })
            elif st_sim > ts_mean:
                flags.append({
                    "signal": "Target document closer to student than to scholar",
                    "detail": f"'{target_doc['title']}' vs student '{st_doc['title']}': {st_sim:.2f}, vs scholar baseline: {ts_mean:.2f}.",
                    "severity": "medium-high"
                })

    # Check for dual personality within scholar corpus
    if len(scholar_indices) >= 4:
        # Simple k=2 split via median of first principal component
        try:
            import numpy as np
            scholar_vecs = np.array([vectors[i] for i in scholar_indices])
            mean = np.mean(scholar_vecs, axis=0)
            Xc = scholar_vecs - mean
            _, _, Vt = np.linalg.svd(Xc, full_matrices=False)
            pc1 = np.dot(Xc, Vt[0])
            median = np.median(pc1)
            group_a = [scholar_indices[i] for i, v in enumerate(pc1) if v <= median]
            group_b = [scholar_indices[i] for i, v in enumerate(pc1) if v > median]
            if group_a and group_b:
                cross_sims = [cosine_similarity(vectors[i], vectors[j]) for i in group_a for j in group_b]
                cross_mean = sum(cross_sims) / len(cross_sims)
                if cross_mean < scholar_mean - scholar_std:
                    flags.append({
                        "signal": "Dual personality detected in scholar baseline",
                        "detail": f"Scholar documents split into two clusters with cross-cluster similarity {cross_mean:.2f} (baseline mean {scholar_mean:.2f}).",
                        "severity": "medium-high"
                    })
        except ImportError:
            pass

    if not flags:
        flags.append({
            "signal": "None detected",
            "detail": "No stylometric red flags triggered.",
            "severity": "low"
        })

    return flags


def main():
    parser = argparse.ArgumentParser(description="Stylometric feature extractor")
    parser.add_argument("--manifest", "-m", required=True, help="Path to manifest JSON")
    parser.add_argument("--output", "-o", required=True, help="Path to output JSON report")
    args = parser.parse_args()

    print(f"[INFO] Loading manifest: {args.manifest}")
    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    docs = []
    vectors = []
    labels = []

    for idx, item in enumerate(manifest):
        path = item["path"]
        label = item.get("label", "unknown")
        title = item.get("title", Path(path).name)
        print(f"[INFO] Processing [{label}] {title} ...")
        try:
            text = extract_text(path)
        except Exception as e:
            print(f"[ERROR] Skipping {path}: {e}", file=sys.stderr)
            continue

        features = compute_features(text)
        vec = build_feature_vector(features)
        doc_id = f"doc_{idx}"

        docs.append({
            "id": doc_id,
            "title": title,
            "path": path,
            "label": label,
            "year": item.get("year"),
            "note": item.get("note", ""),
            "features": features
        })
        vectors.append(vec)
        labels.append(label)

    if len(docs) < 2:
        print("[ERROR] Need at least 2 successfully processed documents.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Processed {len(docs)} documents. Computing similarities...")
    sim_matrix = compute_similarity_matrix(docs, vectors)

    print("[INFO] Computing PCA projection...")
    pca = compute_pca(vectors, n_components=2)
    pca_result = None
    if pca:
        pca_result = {
            "components": 2,
            "coordinates": [
                {"id": d["id"], "x": pca[i][0], "y": pca[i][1], "label": d["label"]}
                for i, d in enumerate(docs)
            ]
        }
    else:
        print("[WARN] numpy not available; PCA projection skipped.")

    print("[INFO] Generating red flags...")
    red_flags = generate_red_flags(docs, vectors, labels)

    print("[INFO] Generating word frequency deviation heatmap...")
    heatmap = generate_word_frequency_heatmap(docs, vectors)

    report = {
        "analysis_timestamp": __import__("datetime").datetime.now().isoformat(),
        "document_count": len(docs),
        "documents": docs,
        "similarity_matrix": sim_matrix,
        "pca_projection": pca_result,
        "word_frequency_heatmap": heatmap,
        "red_flags": red_flags
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Report saved to: {args.output}")
    print(f"[SUMMARY] Documents: {len(docs)}, Red flags: {len(red_flags)}")


if __name__ == "__main__":
    main()
