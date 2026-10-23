import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import topic_modeling as tm
from city_clustering import build_matrix, extract_dishes
from collect_data import session


def test_encoding_html_and_urls():
    text = tm.clean_text('FranÃ§ais <b>NEWS</b><script>steal secret</script>&amp; https://example.com/a')
    assert text == 'français news &'


def test_english_lemmatization_and_stopwords():
    tokens = tm.Preprocessor('en')('the children were running with cats')
    assert 'child' in tokens and 'run' in tokens and 'cat' in tokens
    assert 'the' not in tokens and 'with' not in tokens


def test_russian_lemmatization():
    tokens = tm.Preprocessor('ru')('кошки гуляли по улицам')
    assert 'кошка' in tokens and 'улица' in tokens
    assert 'по' not in tokens


def product(id='1', url='https://example.org/1'):
    return {'id': id, 'url': url, 'title': 'Photo editor',
            'description': 'Powerful software for editing photographs and creating colorful pictures.',
            'reviews': [{'text': 'Excellent editor with useful drawing tools and layers.'}]}


def test_dedup_content_independent_of_url_title():
    a, b = product(), product('2', 'https://example.org/2')
    b['title'] = 'Different title'
    docs, audit = tm.prepare([a, b], 'products', 'en')
    assert len(docs) == 1
    assert audit['reasons'] == {'duplicate_content': 1}


def test_duplicate_url_is_reported():
    a, b = product(), product('2')
    b['description'] = 'Distinct video editing application with sound tracks and media files.'
    _, audit = tm.prepare([a, b], 'products', 'en')
    assert audit['reasons'] == {'duplicate_url': 1}


def test_missing_reviews_and_title_only_news_rejected():
    row = product()
    row['reviews'] = []
    assert tm.document_text(row, 'products')[1] == 'missing_description_or_reviews'
    assert tm.document_text({'title': 'Just a headline', 'summary': ''}, 'news')[1] == 'missing_or_short_article'


def test_bom_csv_and_json_validation(tmp_path):
    p = tmp_path / 'input.csv'
    p.write_text('id,title\n1,Example\n', encoding='utf-8-sig')
    assert tm.read_rows(p)[0]['id'] == '1'
    p = tmp_path / 'input.json'
    p.write_text('{"not": "a list"}', encoding='utf-8')
    with pytest.raises(ValueError, match='массив'):
        tm.read_rows(p)


@pytest.mark.parametrize('args', [['--topics', 'zero'], ['--topics', '0'], ['--passes', '0'],
                                  ['--max-features', '-1'], ['--top-words', '1']])
def test_invalid_cli(args):
    with pytest.raises(SystemExit) as exc:
        tm.parse_args(args)
    assert exc.value.code == 2


def test_small_dataset_fails_and_saves_audit(tmp_path):
    p = tmp_path / 'small.json'
    p.write_text(json.dumps([product()]), encoding='utf-8')
    prefix = tmp_path / 'nested' / 'result'
    assert tm.main(['--dataset', 'products', '--input', str(p), '--output', str(prefix), '--topics', '3']) == 1
    assert (tmp_path / 'nested/result_audit.json').exists()
    assert not (tmp_path / 'nested/result_summary.json').exists()


def test_synonyms_and_word_boundaries():
    dishes = extract_dishes('Посекунчики, шанежки, учпочмак, чак чак, бешбармак. Щипцы, машина.')
    assert {'посику́нчики', 'шаньги', 'эчпочмак', 'чак-чак', 'бешбармак'} <= set(dishes)
    assert 'щи' not in dishes


def test_frequency_counts_domains_not_pages():
    rows = [dict(city='A', status='ok', domain='one', text_sha256='1', dishes=['пельмени']),
            dict(city='A', status='ok', domain='one', text_sha256='2', dishes=['пельмени']),
            dict(city='A', status='ok', domain='two', text_sha256='3', dishes=['шаньги'])]
    cities, names, X, counts = build_matrix(rows)
    assert counts == {'A': 2}
    np.testing.assert_allclose(X, [[.5, .5]])


def test_insufficient_city_sources_fail():
    with pytest.raises(ValueError, match='2 независимых'):
        build_matrix([dict(city='A', status='error')])


def test_http_retry_503_429_then_success():
    class Handler(BaseHTTPRequestHandler):
        attempts = 0
        def do_GET(self):
            Handler.attempts += 1
            self.send_response([503, 429, 200][min(Handler.attempts-1, 2)])
            self.send_header('Retry-After', '0')
            self.end_headers()
            self.wfile.write(b'ok')
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with session() as client:
            client.trust_env = False
            response = client.get(f'http://127.0.0.1:{server.server_port}/', timeout=5)
        assert response.status_code == 200
        assert Handler.attempts == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_cli_help_without_network():
    result = subprocess.run([sys.executable, str(tm.ROOT / 'topic_modeling.py'), '--help'], capture_output=True)
    assert result.returncode == 0 and b'--compare' in result.stdout
