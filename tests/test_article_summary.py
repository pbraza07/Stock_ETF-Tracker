import json
import pytest
import article_summary as summary


def test_requires_config_without_calling_provider(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('MARKETSCOPE_NEWS_SUMMARY_MODEL',raising=False)
    assert not summary.configured()
    with pytest.raises(summary.SummaryUnavailable):summary.summarize_article({})


def test_paywall_or_partial_article_is_not_summarized():
    for html in ['<article><p>Short preview.</p></article>',
        '<script type="application/ld+json">{"isAccessibleForFree":false}</script><article>Body</article>',
        '<article>Subscribe to continue reading</article>']:
        with pytest.raises(summary.SummaryUnavailable):summary.extract_article(html.encode())


def test_complete_body_paragraphs_are_read_including_the_end():
    paragraphs=[' '.join(f'fact{i}_{j}' for j in range(55)) for i in range(5)]
    html='<article>'+''.join('<p>'+p+'</p>' for p in paragraphs)+'<aside><p>Unrelated ad</p></aside></article>'
    body=summary.extract_article(html.encode())
    assert 'fact4_54' in body and 'Unrelated ad' not in body
    assert len(body.split())==275


def test_full_text_is_sent_and_exactly_five_original_lines_returned(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-only')
    monkeypatch.setenv('MARKETSCOPE_NEWS_SUMMARY_MODEL','test-model')
    captured={}
    lines=['Revenue grew following increased demand.','Management raised its profit outlook.',
           'Costs remained a concern for executives.','The company announced additional investment.',
           'The outlook remains subject to weaker demand.']
    class Response:
        status_code=200
        def json(self):return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'lines':lines})}]}]}
    def post(url,**kwargs):captured.update(kwargs['json']);return Response()
    monkeypatch.setattr(summary.requests,'post',post)
    text='first paragraph\n\nlast paragraph contains the ending facts'
    result=summary.summarize_text('Example',text)
    assert json.loads(captured['input'])['article_text']==text
    assert captured['store'] is False
    assert result['lines']==lines
    assert result['word_count']==len(text.split())


def test_invalid_output_is_not_saved(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-only');monkeypatch.setenv('MARKETSCOPE_NEWS_SUMMARY_MODEL','test-model')
    class Response:
        status_code=200
        def json(self):return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"lines":["Only one line"]}'}]}]}
    monkeypatch.setattr(summary.requests,'post',lambda *a,**k:Response())
    with pytest.raises(summary.SummaryUnavailable):summary.summarize_text('Title','Article')
