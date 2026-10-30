"""A small correctness check for the public synthetic benchmark entry point."""

from spaceanalyzer.benchmark import run_benchmark


def test_benchmark_counts_real_synthetic_files() -> None:
    report = run_benchmark("wide", 12)
    assert report.file_count == 12
    assert report.total_bytes == 12
    assert report.directory_count == 1
    assert report.status == "completed"
    assert report.database_bytes > 0
    assert report.peak_process_bytes > 0
