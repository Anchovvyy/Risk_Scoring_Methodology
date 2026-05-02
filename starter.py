"""
Starter script for full local pipeline execution with logs:
1) generate synthetic resumes
2) calculate base/stage3/stage4/stage5 risk values
3) save per-resume results + global shared values
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from base_score_calculator import (
    load_global_calculation_values,
    process_resume_files,
    save_global_calculation_values,
)
from graphs import build_stats, load_resumes, save_plots, save_stats_json
from resume_generator import OUT_DIR, run_test_stand_and_save

DEFAULT_COUNT = 100
DEFAULT_SEED = 42

BASE_DIR = Path(__file__).parent.absolute()
LOG_DIR = Path(os.path.join(BASE_DIR, "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
GLOBAL_CONFIG_PATH = Path(os.path.join(BASE_DIR, "global_calculation_values.json"))


def run_pipeline(n_resumes: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"pipeline_log_{timestamp}.txt"

    os.makedirs(LOG_DIR, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as log:
        def write(message: str) -> None:
            line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
            print(line)
            log.write(line + "\n")

        write(f"Pipeline start. n_resumes={n_resumes}, seed={seed}")
        cached_global = load_global_calculation_values(str(GLOBAL_CONFIG_PATH))
        existing_resumes = list(Path(OUT_DIR).glob("*.json"))
        if cached_global is not None and existing_resumes:
            write(f"Detected existing global config at: {GLOBAL_CONFIG_PATH}")
            write("Step 1 skipped. Reusing previously generated resumes and global config.")
        else:
            files = run_test_stand_and_save(
                n_resumes=n_resumes,
                seed=seed,
                out_dir=OUT_DIR,
                overwrite=True,
            )
            write(f"Step 1 done. Generated resumes: {len(files)}")

        results, global_values = process_resume_files(
            resume_dir=OUT_DIR,
            random_seed=seed,
            generate_random_osint=(cached_global is None),
            global_values=cached_global,
        )
        write(f"Step 2-5 done. Processed resumes: {len(results)}")
        write("Global values:")
        write(str(global_values))

        if cached_global is None:
            global_json_path = save_global_calculation_values(global_values)
            write(f"Saved global values JSON: {global_json_path}")
        else:
            write("Global values JSON preserved (reused existing configuration).")

        resumes = load_resumes(OUT_DIR)
        stats = build_stats(resumes)
        stats_path = save_stats_json(stats)
        write(f"Saved analytics summary JSON: {stats_path}")
        plot_paths = save_plots(stats)
        if plot_paths:
            write(f"Saved analytics plots: {len(plot_paths)} files")
        else:
            write("Analytics plots skipped (matplotlib unavailable).")
        write("Pipeline completed successfully.")

    return str(log_path)


if __name__ == "__main__":
    log_file = run_pipeline()
    print(f"Log saved to: {log_file}")
