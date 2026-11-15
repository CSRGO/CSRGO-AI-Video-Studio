"""Citation repairs must preserve real evidence and never bypass semantic review."""
import json
import tempfile
import unittest
import httpx
from pathlib import Path
from unittest.mock import patch

from backend.services.evidence_service import build_passages, original_quote, resolve_claim
from backend.services.research_service import ResearchService, NoSupportedClaimsError
from backend.services.youtube_story_service import analyze_hooks, hook_tool

TEXT = ('Microsoft reported that Outlook synchronization was interrupted for 20 minutes. '
        'The company said it had not confirmed the cause of the interruption. '
        'Users could still read previously downloaded messages during the interruption.')
SOURCE = {'source_id': 'SRC-01', 'title': 'Outlook incident', 'url': 'https://example.com/report', 'extracted_text': TEXT}


class EvidenceRepairTests(unittest.TestCase):
    def setUp(self):
        self.service = ResearchService()
        self.passages = build_passages([SOURCE], 'Outlook interruption')

    def test_passage_ids_attach_original_source_without_model_quotation(self):
        result = resolve_claim({'claim_text': 'Outlook synchronization was interrupted.', 'passage_ids': ['P001']}, [SOURCE], self.passages)
        self.assertEqual(result['evidence'][0]['quote'], self.passages[0]['text'])
        with self.assertRaises(ValueError):
            resolve_claim({'claim_text': 'Fact', 'passage_ids': ['P999']}, [SOURCE], self.passages)
        corrupted = [{**self.passages[0], 'text': 'fabricated quotation'}]
        with self.assertRaises(ValueError):
            resolve_claim({'claim_text': 'Fact', 'passage_ids': ['P001']}, [SOURCE], corrupted)

    def test_typography_repair_retains_original_offsets_and_rejects_changed_meaning(self):
        article = 'The company’s report — published today — says 20\u00a0minutes, not 30.'
        quote, start, end = original_quote(article, "The company's report - published today - says 20 minutes, not 30.")
        self.assertEqual(quote, article)
        self.assertEqual(article[start:end], quote)
        for altered in [article.replace('20', '30'), article.replace('not ', ''), article.replace('today', 'yesterday')]:
            with self.assertRaises(ValueError):
                original_quote(article, altered)

    def test_invalid_model_quote_is_repaired_with_passage_id(self):
        responses = [
            {'claims': [{'claim_text': 'Outlook was interrupted.', 'evidence': [{'source_id':'SRC-01','quote':'A quote the model invented that is not in the source.'}]}]},
            {'claims': [{'claim_text': 'Outlook synchronization was interrupted.', 'passage_ids':['P001']}]},
            {'supported_claim_ids':['CLM-01'], 'issues':[]},
        ]
        with tempfile.TemporaryDirectory() as folder, patch.object(self.service, 'fetch_page_article', return_value=TEXT), \
             patch('backend.services.research_service.ai_service.generate', side_effect=map(json.dumps, responses)) as model:
            brief = self.service.research_topic('Outlook interruption', folder, source_urls=[SOURCE['url']])
            diagnostics = json.loads((Path(folder)/'research_diagnostics.json').read_text())
            self.assertEqual(len(diagnostics['citation_attempts']), 2)
            self.assertEqual(model.call_count, 3)
            self.assertEqual(brief['claims'][0]['evidence'][0]['quote'], self.passages[0]['text'])
            self.assertTrue((Path(folder)/'passages.json').exists())
            # A retry reuses fetched evidence but reruns claim generation and review.
            with patch.object(self.service, 'fetch_page_article') as fetch, patch.object(self.service, 'search_web') as search, \
                 patch('backend.services.research_service.ai_service.generate', side_effect=map(json.dumps, responses[1:])):
                self.service.research_topic('Outlook interruption', folder, source_urls=[SOURCE['url']])
            fetch.assert_not_called()
            search.assert_not_called()
            self.assertFalse(self.service.cached_sources('different topic', [SOURCE['url']], folder))
            self.assertFalse(self.service.cached_sources('Outlook interruption', ['https://example.com/new'], folder))

    def test_partial_valid_claim_survives_and_bad_claim_is_not_accepted(self):
        diagnostics = {}
        first = {'claims':[{'claim_text':'Supported fact', 'passage_ids':['P001']}, {'claim_text':'Bad fact', 'passage_ids':['P999']}]}
        second = {'claims':[{'claim_text':'Another supported fact', 'passage_ids':['P002']}]}
        with patch('backend.services.research_service.ai_service.generate', side_effect=map(json.dumps,[first,second])):
            claims, _ = self.service.extract_claims('Outlook', [SOURCE], self.passages, diagnostics, lambda:None, lambda *a:None)
        self.assertEqual([c['claim_text'] for c in claims], ['Supported fact','Another supported fact'])
        self.assertEqual([c['claim_id'] for c in claims], ['CLM-01','CLM-02'])

    def test_malformed_extraction_uses_excerpts_only_after_semantic_approval(self):
        responses = ['bad json']*3 + [json.dumps({'supported_claim_ids':['CLM-01'],'issues':[]})]
        with patch.object(self.service,'fetch_page_article',return_value=TEXT), \
             patch('backend.services.research_service.ai_service.generate',side_effect=responses):
            result = self.service.research_topic('Outlook',source_urls=[SOURCE['url']])
        self.assertEqual(result['claims'][0]['claim_text'], result['claims'][0]['evidence'][0]['quote'])
        with patch.object(self.service,'fetch_page_article',return_value=TEXT), \
             patch('backend.services.research_service.ai_service.generate',side_effect=['bad json']*3+[json.dumps({'supported_claim_ids':[],'issues':['unrelated']})]):
            with self.assertRaises(NoSupportedClaimsError):
                self.service.research_topic('Outlook',source_urls=[SOURCE['url']])

    def test_review_format_repair_and_semantic_rejection_remain_distinct(self):
        claims = self.service.validate_claims([{'claim_text':'Fact','passage_ids':['P001']}],[SOURCE],self.passages)
        with patch('backend.services.research_service.ai_service.generate',side_effect=['{}',json.dumps({'supported_claim_ids':['CLM-01'],'issues':[]})]):
            approved, _ = self.service.review_claims('Outlook', claims, {}, lambda:None)
        self.assertEqual(approved,claims)

    def test_windows_encoded_article_retains_quotation_characters(self):
        article = '<meta charset="windows-1252"><p>The company’s report — published today — says 20 minutes.</p>'
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, content=article.encode('cp1252'), headers={'content-type':'text/html'})))
        with patch('backend.services.research_service.public_url'), \
             patch('backend.services.research_service.httpx.Client',return_value=client):
            text = self.service.fetch_page_article('https://example.com/report')
        self.assertIn('company’s report — published today',text)

    def test_hook_scorer_runs_upstream_tool_without_replacing_spoken_narration(self):
        opening = 'Outlook is an email app. Here is what stopped working.'
        board = {'scenes':[{'narration':opening}], 'hook_options':[{'text':'Why did Outlook stop synchronizing?'}]}
        result = analyze_hooks(board)
        self.assertTrue(result['scored'])
        self.assertEqual(result['selected_hook'],opening)
        self.assertEqual(board['scenes'][0]['narration'],opening)
        for candidate in result['candidates']:
            self.assertEqual(candidate['verdict'],hook_tool().score(candidate['hook'])[1])
        self.assertFalse(analyze_hooks(board,'hi')['scored'])
