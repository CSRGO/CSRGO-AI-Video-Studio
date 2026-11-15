import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from backend.services.research_service import ResearchService


class SearchRecoveryTests(unittest.TestCase):
    def client_for(self, handler):
        return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    def test_duckduckgo_challenge_falls_back_to_bing_article_urls(self):
        def handler(request):
            if request.url.host == 'html.duckduckgo.com':
                return httpx.Response(202, text='<form id="challenge-form">verification</form>')
            self.assertEqual(request.url.params['format'], 'rss')
            return httpx.Response(200, text='''<rss><channel><item><title>Outlook incident report</title>
                <link>https://example.com/report</link><description>Reported disruption.</description></item></channel></rss>''')
        diagnostics = []
        client = self.client_for(handler)
        with patch('backend.services.research_service.httpx.Client', return_value=client):
            sources = ResearchService().search_web('Microsoft Outlook outage', diagnostics=diagnostics)
        self.assertEqual(sources[0]['url'], 'https://example.com/report')
        self.assertEqual(sources[0]['discovered_via'], 'Bing RSS')
        self.assertEqual([a['status'] for a in diagnostics], ['failed', 'ok'])
        self.assertIn('verification challenge', diagnostics[0]['reason'])

    def test_article_word_anomaly_does_not_trigger_false_challenge(self):
        def handler(request):
            self.assertEqual(request.url.host, 'html.duckduckgo.com')
            return httpx.Response(200, text='<a href="https://example.com/anomaly" class="result__a">A network anomaly</a>')
        client = self.client_for(handler)
        with patch('backend.services.research_service.httpx.Client', return_value=client):
            self.assertEqual(len(ResearchService().search_web('network anomaly')), 1)

    def test_all_search_failures_keep_actionable_reasons_and_save_diagnostics(self):
        def handler(request):
            return httpx.Response(202, text='challenge') if request.url.host == 'html.duckduckgo.com' else httpx.Response(403)
        client = self.client_for(handler)
        with tempfile.TemporaryDirectory() as folder, \
             patch('backend.services.research_service.httpx.Client', return_value=client), \
             patch('backend.services.research_service.ai_service.generate') as generate, \
             patch.object(ResearchService, 'plan_search', return_value={'queries': ['Outlook incident']}):
            with self.assertRaises(RuntimeError) as failure:
                ResearchService().research_topic('Outlook outage', out_dir=folder)
            self.assertIn('verification challenge', str(failure.exception))
            self.assertIn('Bing RSS: HTTP 403', str(failure.exception))
            self.assertNotIn('Search unavailable: RuntimeError', str(failure.exception))
            diagnostics = json.loads((Path(folder) / 'research_diagnostics.json').read_text())
            self.assertEqual(len(diagnostics['search_attempts']), 2)
            self.assertEqual(diagnostics['readable_sources'], 0)
            self.assertEqual(generate.call_count, 0)  # Search never needs model-generated JSON.

    def test_proxy_denial_is_distinct_from_challenge(self):
        def handler(request):
            raise httpx.ProxyError('private proxy diagnostic intentionally not exposed')
        client = self.client_for(handler)
        with patch('backend.services.research_service.httpx.Client', return_value=client):
            with self.assertRaises(RuntimeError) as failure:
                ResearchService().search_web('Outlook')
        self.assertIn('proxy or network policy denied', str(failure.exception))
        self.assertNotIn('private proxy diagnostic', str(failure.exception))

    def test_direct_articles_work_without_any_search_provider(self):
        article = 'Outlook is an email application. ' * 8
        responses = [
            {'claims': [{'claim_text': 'Outlook is an email application.', 'evidence': [
                {'source_id': 'SRC-01', 'quote': 'Outlook is an email application.'}]}]},
            {'supported_claim_ids': ['CLM-01'], 'issues': []},
        ]
        service = ResearchService()
        with patch('backend.services.research_service.ai_service.generate', side_effect=[json.dumps(r) for r in responses]), \
             patch.object(service, 'search_web') as search, patch.object(service, 'fetch_page_article', return_value=article):
            result = service.research_topic('Outlook', source_urls=['https://example.com/official-report'])
        search.assert_not_called()
        self.assertEqual(len(result['claims']), 1)
        self.assertEqual(result['sources'][0]['credibility'], 'user_supplied')

    def test_search_planning_never_calls_model_or_invents_incident_dates(self):
        with patch('backend.services.research_service.ai_service.generate', return_value='{"queries": []}') as generate:
            plan = ResearchService().plan_search('Microsoft Outlook outage January 2023')
        generate.assert_not_called()
        self.assertEqual(plan['queries'][0], 'Microsoft Outlook outage January 2023')
        self.assertTrue(all('2023' in query and '2026' not in query for query in plan['queries']))

    def test_recovery_url_validation(self):
        from backend.api.routes import ResearchInputsRequest
        self.assertEqual(ResearchInputsRequest(source_urls=['https://example.com/report']).source_urls,
                         ['https://example.com/report'])
        with self.assertRaises(ValueError):
            ResearchInputsRequest(source_urls=['file:///private.txt'])
