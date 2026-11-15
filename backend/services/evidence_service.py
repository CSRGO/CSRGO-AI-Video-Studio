"""Application-owned passage references; a model never has to reproduce citations."""
import re
import unicodedata

_QUOTES = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-'})
_IGNORED = {'\u200b', '\ufeff', '\u00ad'}


def canonical_text(text):
    return _canonical_map(text)[0]


def _canonical_map(text):
    result, starts, ends = [], [], []
    for index, character in enumerate(text):
        if character in _IGNORED:
            continue
        transformed = unicodedata.normalize('NFKC', character).translate(_QUOTES).casefold()
        for c in transformed:
            if c.isspace():
                if not result or result[-1] == ' ':
                    continue
                c = ' '
            result.append(c)
            starts.append(index)
            ends.append(index + 1)
    while result and result[-1] == ' ':
        result.pop(); starts.pop(); ends.pop()
    return ''.join(result), starts, ends


def original_quote(article, quote):
    normalized, starts, ends = _canonical_map(article)
    needle = canonical_text(quote)
    if len(needle) < 20:
        raise ValueError('Supporting passage is too short.')
    index = normalized.find(needle)
    if index < 0:
        raise ValueError('Quotation changes source words, numbers or meaning, or is absent from the article.')
    start, end = starts[index], ends[index + len(needle) - 1]
    return article[start:end], start, end


def build_passages(sources, topic, per_source=2):
    stop = {'the','and','for','with','what','how','why','this','that','from','about','into'}
    tokens = {w for w in re.findall(r'\w+', topic.casefold()) if len(w) > 2 and w not in stop}
    selected = []
    for source in sources:
        text = source.get('extracted_text', '')
        spans = []
        for sentence in re.finditer(r'.+?(?:[.!?](?=\s|$)|$)', text, flags=re.S):
            start, end = sentence.span()
            while start < end:
                while start < end and text[start].isspace():
                    start += 1
                finish = min(end, start + 500)
                if finish < end:
                    boundary = text.rfind(' ', start + 100, finish)
                    if boundary > start:
                        finish = boundary
                excerpt = text[start:finish].strip()
                if len(excerpt) >= 20:
                    excerpt_end = start + len(excerpt)
                    words = set(re.findall(r'\w+', excerpt.casefold()))
                    score = len(tokens & words) * 10 + min(len(excerpt), 250) / 250
                    spans.append((score, start, excerpt_end))
                start = max(finish, start + 1)
        # Prefer relevant, distinct excerpts; original offsets are retained for audit.
        unique = set()
        for _, start, end in sorted(spans, key=lambda item: (-item[0], item[1])):
            excerpt = text[start:end]
            if canonical_text(excerpt) in unique:
                continue
            unique.add(canonical_text(excerpt))
            selected.append({'passage_id': f'P{len(selected)+1:03d}', 'source_id': source['source_id'],
                             'text': excerpt, 'start_char': start, 'end_char': end})
            if len(unique) >= per_source:
                break
    return selected


def resolve_claim(raw, sources, passages=()):
    if not isinstance(raw, dict) or not isinstance(raw.get('claim_text'), str) or not raw['claim_text'].strip():
        raise ValueError('A claim must contain spoken factual text.')
    by_source = {s['source_id']: s for s in sources}
    by_passage = {p['passage_id']: p for p in passages}
    ids = raw.get('passage_ids', raw.get('supporting_passage_ids', []))
    if not ids and raw.get('passage_id'):
        ids = [raw['passage_id']]
    if isinstance(ids, str):
        ids = [ids]
    if not ids:
        ids = [e['passage_id'] for e in raw.get('evidence', []) if isinstance(e, dict) and e.get('passage_id')]
    evidence = []
    if ids:
        if not isinstance(ids, list) or any(not isinstance(i, str) or i not in by_passage for i in ids):
            raise ValueError('Unknown supporting passage ID. Select only IDs in the provided catalog.')
        for identifier in dict.fromkeys(ids):
            passage = by_passage[identifier]
            source = by_source.get(passage['source_id'])
            if not source or source['extracted_text'][passage['start_char']:passage['end_char']] != passage['text']:
                raise ValueError('Source passage integrity check failed.')
            evidence.append({'source_id': passage['source_id'], 'passage_id': identifier,
                             'quote': passage['text'], 'start_char': passage['start_char'], 'end_char': passage['end_char']})
    else:
        # Backward compatibility: accept only exact words after typography normalization.
        for item in raw.get('evidence', []):
            if not isinstance(item, dict):
                raise ValueError('Invalid evidence entry.')
            source = by_source.get(item.get('source_id'))
            if not source or not isinstance(item.get('quote'), str):
                raise ValueError('Unknown source or missing source quotation.')
            quote, start, end = original_quote(source['extracted_text'], item['quote'])
            evidence.append({'source_id': source['source_id'], 'quote': quote, 'start_char': start, 'end_char': end})
    if not evidence:
        raise ValueError('A research claim has no source quotation or passage reference.')
    return {**raw, 'evidence': evidence,
            'supporting_source_ids': list(dict.fromkeys(e['source_id'] for e in evidence)),
            'status': 'source_backed', 'confidence': 'source_backed'}
