"""Re-clean and re-score cached analyzed JSON after FinBERT label fix."""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def rescore_all(device: str = "cuda") -> None:
    from src.chunker import TextChunker
    from src.exhibit_cleaner import clean_exhibit_text
    from src.sentiment_analyzer import FinBERTAnalyzer
    from src.temporal_analyzer import TemporalAnalyzer
    from src.uncertainty_analyzer import UncertaintyAnalyzer

    analyzer = FinBERTAnalyzer(device=device)
    chunker = TextChunker()
    ua = UncertaintyAnalyzer()
    ta = TemporalAnalyzer()

    files = sorted(glob.glob(os.path.join("data", "analyzed", "*_analyzed.json")))
    files = [f for f in files if not f.endswith("_temporal_analysis.json")]
    print(f"Rescoring {len(files)} files on {analyzer.device}...")

    for i, path in enumerate(files, 1):
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        pr = doc.get("prepared_remarks") or {}
        raw = pr.get("text") or ""
        cleaned = clean_exhibit_text(raw) or raw
        if cleaned and len(cleaned.split()) >= 40:
            pr["text"] = cleaned
            pr["word_count"] = len(cleaned.split())
        chunks = chunker.chunk_by_sentences(pr.get("text") or "")
        chunks = [c for c in chunks if chunker._keep_chunk(c)] or chunks
        pr["chunks"] = chunks
        pr["chunk_count"] = len(chunks)

        prepared_results = analyzer.analyze_chunks(chunks, show_progress=False)
        prepared_aggregated = analyzer.aggregate_sentiment(prepared_results)
        prepared_score = analyzer.calculate_sentiment_score(prepared_aggregated)
        pr["sentiment"] = prepared_aggregated
        pr["sentiment_score"] = prepared_score
        pr["sentiment_by_chunk"] = prepared_results
        pr["uncertainty"] = ua.analyze_uncertainty(pr.get("text") or "")
        doc["prepared_remarks"] = pr

        qa = doc.get("qa_session") or {}
        qa_chunks = qa.get("chunks") or []
        if qa_chunks:
            qa_results = analyzer.analyze_chunks(qa_chunks, show_progress=False)
            qa_agg = analyzer.aggregate_sentiment(qa_results)
            qa_score = analyzer.calculate_sentiment_score(qa_agg)
            qa["sentiment"] = qa_agg
            qa["sentiment_score"] = qa_score
            qa["sentiment_by_chunk"] = qa_results
        else:
            qa_score = 0.0
        doc["qa_session"] = qa
        doc["sentiment_analysis"] = {
            "prepared_remarks_score": prepared_score,
            "qa_session_score": qa_score,
            "sentiment_gap": prepared_score - qa_score,
            "gap_interpretation": analyzer._interpret_gap(prepared_score - qa_score),
        }
        doc["executive_confidence"] = ta.analyze_document_confidence(doc)
        doc["sentiment_model"] = {
            "name": analyzer.model_name,
            "labels": analyzer.labels,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)

        meta = doc.get("metadata") or {}
        print(
            f"  [{i}/{len(files)}] {os.path.basename(path)} "
            f"chunks={len(chunks)} score={prepared_score:.3f} {prepared_aggregated.get('label')}"
        )

    for temporal in glob.glob(os.path.join("data", "analyzed", "*_temporal_analysis.json")):
        try:
            os.remove(temporal)
        except OSError:
            pass
    print("Done. Deleted stale temporal_analysis JSON so load rebuilds signals.")


if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "cuda"
    rescore_all(device=device)
