"""
ROA OCR — Benchmark Framework
================================
Reproducible accuracy measurement for OCR quality.
Compares ROA OCR output against ground-truth text files.

Usage:
    python benchmarks/benchmark.py --input samples/ --ground-truth ground_truth/

The benchmark measures:
  - Character Error Rate (CER)
  - Word Error Rate (WER)
  - Processing throughput (pages/second)
  - Correction effectiveness
"""

import sys
import time
import json
import logging
import difflib
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

log = logging.getLogger("roa.benchmark")


@dataclass
class BenchmarkResult:
    """Result of a single file benchmark."""
    filename: str
    cer: float = 0.0        # Character Error Rate (0.0 = perfect)
    wer: float = 0.0        # Word Error Rate (0.0 = perfect)
    accuracy: float = 0.0   # 1 - CER as percentage
    pages: int = 0
    processing_time_s: float = 0.0
    engine_used: str = ""
    corrections_applied: int = 0
    chars_extracted: int = 0
    chars_expected: int = 0
    error: str = ""


@dataclass
class BenchmarkReport:
    """Aggregated benchmark report."""
    timestamp: str = ""
    total_files: int = 0
    avg_cer: float = 0.0
    avg_wer: float = 0.0
    avg_accuracy: float = 0.0
    total_pages: int = 0
    total_time_s: float = 0.0
    pages_per_second: float = 0.0
    engine_used: str = ""
    results: List[Dict] = field(default_factory=list)


def character_error_rate(reference: str, hypothesis: str) -> float:
    """
    Calculate Character Error Rate (CER).
    CER = (insertions + deletions + substitutions) / len(reference)
    Uses difflib for efficient edit distance approximation.
    """
    if not reference:
        return 0.0 if not hypothesis else 1.0

    # Normalize whitespace
    ref = " ".join(reference.split())
    hyp = " ".join(hypothesis.split())

    matcher = difflib.SequenceMatcher(None, ref, hyp)
    edits = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            edits += max(i2 - i1, j2 - j1)

    return min(edits / max(len(ref), 1), 1.0)


def word_error_rate(reference: str, hypothesis: str) -> float:
    """
    Calculate Word Error Rate (WER).
    WER = (word insertions + deletions + substitutions) / len(reference_words)
    """
    ref_words = reference.split()
    hyp_words = hypothesis.split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    matcher = difflib.SequenceMatcher(None, ref_words, hyp_words)
    edits = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            edits += max(i2 - i1, j2 - j1)

    return min(edits / max(len(ref_words), 1), 1.0)


def run_benchmark(
    input_dir: str,
    ground_truth_dir: Optional[str] = None,
    output_report: Optional[str] = None,
    language: str = "spa+eng",
    engine: str = "auto",
) -> BenchmarkReport:
    """
    Run the benchmark suite.

    Args:
        input_dir: Directory containing PDF/image files to OCR
        ground_truth_dir: Directory containing .txt files with expected text
                         (matched by filename stem)
        output_report: Path to save JSON report
        language: OCR language setting
        engine: Engine preference

    Returns:
        BenchmarkReport with all results
    """
    from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig
    from datetime import datetime

    input_path = Path(input_dir)
    gt_path = Path(ground_truth_dir) if ground_truth_dir else None

    # Find input files
    input_files = []
    for ext in ["*.pdf", "*.png", "*.jpg", "*.bmp", "*.tiff"]:
        input_files.extend(input_path.glob(ext))
    input_files = sorted(input_files)

    if not input_files:
        print(f"No input files found in {input_dir}")
        return BenchmarkReport()

    # Initialize pipeline
    config = PipelineConfig(
        lang=language, dpi=300,
        run_correction=True, run_optimization=False,
        ocr_engine=engine,
    )
    pipeline = PDFPipeline(config=config)
    active_engine = pipeline.initialize()

    report = BenchmarkReport(
        timestamp=datetime.now().isoformat(),
        total_files=len(input_files),
        engine_used=active_engine,
    )

    print(f"\n{'='*60}")
    print(f"  ROA OCR Benchmark — {len(input_files)} files")
    print(f"  Engine: {active_engine.upper()}")
    print(f"{'='*60}\n")

    for i, src in enumerate(input_files, 1):
        br = BenchmarkResult(filename=src.name)

        try:
            t0 = time.time()
            md_result = pipeline.process_to_markdown(src)
            t1 = time.time()

            extracted_text = md_result.get("full_markdown", "")
            br.chars_extracted = len(extracted_text)
            br.pages = md_result.get("pages", 0)
            br.processing_time_s = round(t1 - t0, 3)
            br.engine_used = md_result.get("engine_used", "")

            # Compare with ground truth if available
            if gt_path:
                gt_file = gt_path / f"{src.stem}.txt"
                if gt_file.exists():
                    expected = gt_file.read_text(encoding="utf-8", errors="replace")
                    br.chars_expected = len(expected)
                    br.cer = round(character_error_rate(expected, extracted_text), 4)
                    br.wer = round(word_error_rate(expected, extracted_text), 4)
                    br.accuracy = round((1 - br.cer) * 100, 2)
                else:
                    br.accuracy = -1  # No ground truth available

            report.total_pages += br.pages
            report.total_time_s += br.processing_time_s

            status = f"CER={br.cer:.2%} WER={br.wer:.2%}" if br.accuracy >= 0 else "no ground truth"
            print(f"  [{i}/{len(input_files)}] {src.name}: {status} | {br.processing_time_s:.1f}s | {br.pages}p")

        except Exception as e:
            br.error = str(e)
            print(f"  [{i}/{len(input_files)}] {src.name}: ERROR — {e}")

        report.results.append(asdict(br))

    # Aggregate
    valid = [r for r in report.results if r.get("accuracy", -1) >= 0]
    if valid:
        report.avg_cer = round(sum(r["cer"] for r in valid) / len(valid), 4)
        report.avg_wer = round(sum(r["wer"] for r in valid) / len(valid), 4)
        report.avg_accuracy = round((1 - report.avg_cer) * 100, 2)

    report.pages_per_second = round(
        report.total_pages / max(report.total_time_s, 0.001), 2
    )

    # Summary
    print(f"\n{'='*60}")
    print(f"  BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f"  Files:            {report.total_files}")
    print(f"  Pages:            {report.total_pages}")
    print(f"  Avg CER:          {report.avg_cer:.2%}")
    print(f"  Avg WER:          {report.avg_wer:.2%}")
    print(f"  Avg Accuracy:     {report.avg_accuracy:.1f}%")
    print(f"  Total Time:       {report.total_time_s:.1f}s")
    print(f"  Throughput:       {report.pages_per_second:.1f} pages/s")
    print(f"  Engine:           {report.engine_used}")
    print(f"{'='*60}")

    # Save report
    if output_report:
        out_path = Path(output_report)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False)
        print(f"\n  Report saved to: {out_path}")

    pipeline.shutdown()
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ROA OCR Benchmark Framework")
    parser.add_argument("--input", "-i", required=True, help="Directory with PDF/image files")
    parser.add_argument("--ground-truth", "-g", help="Directory with .txt ground truth files")
    parser.add_argument("--output", "-o", default="benchmarks/report.json", help="Output report path")
    parser.add_argument("--lang", default="spa+eng", help="OCR language")
    parser.add_argument("--engine", default="auto", help="Engine preference")

    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    run_benchmark(
        input_dir=args.input,
        ground_truth_dir=args.ground_truth,
        output_report=args.output,
        language=args.lang,
        engine=args.engine,
    )
