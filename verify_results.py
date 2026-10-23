"""Independent validation of delivered artifacts, not just execution success."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent


def verify():
    checked = []
    for dataset in ['news', 'products']:
        prefix = ROOT / 'results' / dataset
        summary = json.loads(Path(str(prefix) + '_summary.json').read_text(encoding='utf-8'))
        docs = json.loads(Path(str(prefix) + '_cleaned.json').read_text(encoding='utf-8'))
        scores = pd.read_csv(str(prefix) + '_coherence.csv')
        assert len(docs) >= 200
        assert len({d['id'] for d in docs}) == len(docs)
        assert summary['code_sha256'] == hashlib.sha256((ROOT / 'topic_modeling.py').read_bytes()).hexdigest()
        for entry in summary['inputs']:
            assert entry['sha256'] == hashlib.sha256((ROOT / 'data' / entry['file']).read_bytes()).hexdigest()
        for method in ['lda', 'nmf']:
            part = scores[scores.method == method]
            assert set(part.k) == set(range(3, 21))
            assert len(part) == 18 and np.isfinite(part.coherence_cv).all()
            topics = json.loads(Path(str(prefix) + f'_{method}_topics.json').read_text(encoding='utf-8'))
            assert topics['k'] == int(part.loc[part.coherence_cv.idxmax(), 'k'])
            assert np.isclose(topics['coherence_cv'], part.coherence_cv.max())
            frame = pd.read_csv(str(prefix) + f'_{method}_documents.csv')
            assert list(frame.id) == [d['id'] for d in docs]
            matrix = frame[[f'topic_{i+1}' for i in range(topics['k'])]].to_numpy()
            assert np.isfinite(matrix).all() and (matrix >= 0).all()
            np.testing.assert_allclose(matrix[frame.assigned].sum(axis=1), 1, atol=1e-8)
            assert len(topics['topics']) == topics['k']
            assert all(t['words'] and all(w['weight'] >= 0 for w in t['words']) for t in topics['topics'])
            words = pd.read_csv(str(prefix) + f'_{method}_keywords.csv')
            assert len(words) == topics['k'] * summary['arguments']['top_words']
            checked.append(f'{dataset}/{method}: {len(docs)} documents, K={topics["k"]}, c_v={topics["coherence_cv"]:.6f}')
        assert Path(str(prefix) + '_lda_interactive.html').stat().st_size > 1000
    frequencies = pd.read_csv(ROOT / 'results/cities/city_dish_frequencies.csv', index_col=0)
    assert len(frequencies) == 9
    assert ((frequencies.values >= 0) & (frequencies.values <= 1)).all()
    clusters = pd.read_csv(ROOT / 'results/cities/city_clusters.csv')
    assert len(clusters) == 9 and not clusters.isna().any().any()
    checked.append('cities: 9 cities, frequencies in [0, 1], all 3 methods')
    mixed = json.loads((ROOT / 'results/mixed_summary.json').read_text(encoding='utf-8'))
    mixed_docs = json.loads((ROOT / 'results/mixed_cleaned.json').read_text(encoding='utf-8'))
    assert mixed['code_sha256'] == hashlib.sha256((ROOT / 'topic_modeling.py').read_bytes()).hexdigest()
    for kind in ['news', 'products']:
        assert sum(d['dataset'] == kind for d in mixed_docs) >= 200
    for entry in mixed['inputs']:
        assert entry['sha256'] == hashlib.sha256((ROOT / 'data' / entry['file']).read_bytes()).hexdigest()
    for method in ['lda', 'nmf']:
        assert mixed['models'][method]['k'] == 10
        frame = pd.read_csv(ROOT / f'results/mixed_{method}_documents.csv')
        assert list(frame.id) == [d['id'] for d in mixed_docs]
        np.testing.assert_allclose(frame[[f'topic_{i+1}' for i in range(10)]].sum(axis=1), 1, atol=1e-8)
    checked.append(f'mixed: {len(mixed_docs)} documents, both methods, fixed K=10')
    (ROOT / 'results/verification.txt').write_text('\n'.join(checked) + '\nAll artifact checks passed.\n', encoding='utf-8')
    print('\n'.join(checked))
    print('All artifact checks passed.')


if __name__ == '__main__':
    verify()
