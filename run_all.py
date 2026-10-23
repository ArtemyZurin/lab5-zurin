"""Reproduce all submitted analyses from local data, without network."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    jobs = [
        ['topic_modeling.py', '--dataset', 'news', '--method', 'both', '--topics', 'auto', '--compare', '--pyldavis'],
        ['topic_modeling.py', '--dataset', 'products', '--method', 'both', '--topics', 'auto', '--compare', '--pyldavis'],
        ['topic_modeling.py', '--dataset', 'mixed', '--method', 'both', '--topics', '10', '--compare'],
        ['city_clustering.py'],
        ['verify_results.py'],
        ['build_report.py'],
    ]
    for index, command in enumerate(jobs, 1):
        print(f'[{index}/{len(jobs)}] {" ".join(command)}', flush=True)
        result = subprocess.run([sys.executable, *command], cwd=ROOT)
        if result.returncode:
            print(f'Failed: {command[0]}; exit={result.returncode}', file=sys.stderr)
            return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
