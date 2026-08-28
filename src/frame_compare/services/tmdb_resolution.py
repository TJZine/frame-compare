"""TMDB candidate resolution policy."""

from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Literal

import httpx
import structlog

from frame_compare.services import tmdb_lookup
from frame_compare.services.errors import TmdbError, TmdbRateLimitedError
from frame_compare.services.tmdb_cache import TmdbCache
from frame_compare.services.types import MetadataConfig, ParsedMetadata, TmdbMetadata

__all__ = ["TmdbResolutionOutcome", "resolve_tmdb_match"]

log = structlog.get_logger()

type MediaType = Literal["movie", "tv"]
type SearchEndpoint = Literal["movie", "tv", "multi"]
type CandidateKey = tuple[MediaType, int]


type _IndexedSearchResults = tuple[int, list[TmdbMetadata]]

MAX_SEARCH_REQUESTS = 12
MAX_CONCURRENT_SEARCH_REQUESTS = 4
MAX_ALT_TITLE_REQUESTS = 5
MAX_CANDIDATES_TO_SCORE = 8

SIMILARITY_FLOOR = 0.45
STRONG_MATCH_CUTOFF = 0.92
AMBIGUITY_MARGIN = 0.08
ALIAS_PROMOTION_THRESHOLD = 0.70

_NON_WORD_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")
_LEADING_THE_RE = re.compile(r"^the\s+", re.IGNORECASE)
_WORD_INITIAL_VV_RE = re.compile(r"\bvv", re.IGNORECASE)
_WORD_INITIAL_W_RE = re.compile(r"\bw", re.IGNORECASE)
_SUBTITLE_SPLIT_RE = re.compile(r"\s*(?::| - | – | — )\s*")
_ROMAN_TO_NUMERIC = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
}
_NUMERIC_TO_ROMAN = {value: key.upper() for key, value in _ROMAN_TO_NUMERIC.items()}
_ROMAN_TOKEN_RE = re.compile(r"\b(" + "|".join(_ROMAN_TO_NUMERIC) + r")\b", re.IGNORECASE)
_NUMERIC_TOKEN_RE = re.compile(r"\b(" + "|".join(_NUMERIC_TO_ROMAN) + r")\b")


@dataclass(frozen=True)
class TmdbResolutionOutcome:
    selected: TmdbMetadata | None
    candidates: list[TmdbMetadata]


@dataclass(frozen=True)
class _SearchRequest:
    endpoint: SearchEndpoint
    title: str
    include_year: bool


@dataclass
class _CandidateAggregate:
    metadata: TmdbMetadata
    first_request_index: int
    first_result_index: int
    aliases: list[str]


@dataclass(frozen=True)
class _ScoredCandidate:
    metadata: TmdbMetadata
    score: float
    title_similarity: float
    alias_similarity: float
    year_score: float
    category_score: float
    order_bonus: float
    first_request_index: int
    first_result_index: int
    aliases: tuple[str, ...]

    @property
    def evidence_similarity(self) -> float:
        return max(self.title_similarity, self.alias_similarity)


def _preferred_media_type(parsed: ParsedMetadata, config: MetadataConfig) -> MediaType | None:
    if parsed.season is not None or parsed.episode is not None:
        return "tv"
    return config.category_preference


def _trim_subtitle(title: str) -> str | None:
    if ":" not in title and " - " not in title and " – " not in title and " — " not in title:
        return None
    parts = _SUBTITLE_SPLIT_RE.split(title, maxsplit=1)
    if not parts:
        return None
    trimmed = parts[0].strip()
    return trimmed if trimmed and trimmed != title.strip() else None


def _swap_word_initial_vv_w(title: str) -> str | None:
    swapped = _WORD_INITIAL_VV_RE.sub("w", title)
    if swapped != title:
        return swapped
    swapped = _WORD_INITIAL_W_RE.sub("vv", title)
    if swapped != title:
        return swapped
    return None


def _roman_to_numeric_title(title: str) -> str | None:
    replaced = _ROMAN_TOKEN_RE.sub(
        lambda match: _ROMAN_TO_NUMERIC[match.group(1).casefold()], title
    )
    return replaced if replaced != title else None


def _numeric_to_roman_title(title: str) -> str | None:
    replaced = _NUMERIC_TOKEN_RE.sub(lambda match: _NUMERIC_TO_ROMAN[match.group(1)], title)
    return replaced if replaced != title else None


def _transformed_title_variants(title: str) -> list[str]:
    variants: list[str] = []
    for variant in (
        _swap_word_initial_vv_w(title),
        _roman_to_numeric_title(title),
        _numeric_to_roman_title(title),
    ):
        if variant is not None:
            variants.append(variant)
    return variants


def _append_search_variant(
    variants: list[_SearchRequest],
    seen: set[tuple[str, bool]],
    title: str | None,
    *,
    include_year: bool,
) -> None:
    if title is None:
        return
    normalized_title = title.strip()
    if not normalized_title:
        return
    key = (normalized_title, include_year)
    if key in seen:
        return
    seen.add(key)
    variants.append(
        _SearchRequest(endpoint="multi", title=normalized_title, include_year=include_year)
    )


def _build_search_variants(parsed: ParsedMetadata) -> list[_SearchRequest]:
    variants: list[_SearchRequest] = []
    seen: set[tuple[str, bool]] = set()
    trimmed = _trim_subtitle(parsed.title)
    include_year = parsed.year is not None

    _append_search_variant(variants, seen, parsed.title, include_year=include_year)
    _append_search_variant(variants, seen, trimmed, include_year=include_year)
    if include_year:
        _append_search_variant(variants, seen, parsed.title, include_year=False)
        _append_search_variant(variants, seen, trimmed, include_year=False)

    bases = [parsed.title]
    if trimmed is not None:
        bases.append(trimmed)
    for base in bases:
        for variant in _transformed_title_variants(base):
            _append_search_variant(variants, seen, variant, include_year=False)

    return variants


def _request_with_endpoint(template: _SearchRequest, endpoint: SearchEndpoint) -> _SearchRequest:
    return _SearchRequest(
        endpoint=endpoint, title=template.title, include_year=template.include_year
    )


def _build_search_plan(parsed: ParsedMetadata, config: MetadataConfig) -> list[_SearchRequest]:
    variants = _build_search_variants(parsed)
    preferred_media_type = _preferred_media_type(parsed, config)
    plan: list[_SearchRequest] = []
    seen: set[tuple[SearchEndpoint, str, bool]] = set()

    def add_request(request: _SearchRequest) -> None:
        if len(plan) >= MAX_SEARCH_REQUESTS:
            return
        key = (request.endpoint, request.title, request.include_year)
        if key in seen:
            return
        seen.add(key)
        plan.append(request)

    if preferred_media_type is None:
        for variant in variants:
            for endpoint in ("multi", "movie", "tv"):
                add_request(_request_with_endpoint(variant, endpoint))
    else:
        for variant in variants:
            add_request(_request_with_endpoint(variant, preferred_media_type))
        for variant in variants[:2]:
            add_request(_request_with_endpoint(variant, "multi"))

    return plan


def _parsed_for_request(parsed: ParsedMetadata, request: _SearchRequest) -> ParsedMetadata:
    return replace(
        parsed,
        title=request.title,
        year=parsed.year if request.include_year else None,
    )


async def _search_request(
    request: _SearchRequest,
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    cache: TmdbCache | None,
) -> list[TmdbMetadata]:
    request_parsed = _parsed_for_request(parsed, request)

    if request.endpoint == "movie":
        if cache is None:
            return await tmdb_lookup.search_tmdb_movie(request_parsed, config, client)
        return await tmdb_lookup.search_tmdb_movie(request_parsed, config, client, cache=cache)

    if request.endpoint == "tv":
        if cache is None:
            return await tmdb_lookup.search_tmdb_tv(request_parsed, config, client)
        return await tmdb_lookup.search_tmdb_tv(request_parsed, config, client, cache=cache)

    if cache is None:
        return await tmdb_lookup.search_tmdb(request_parsed, config, client)
    return await tmdb_lookup.search_tmdb(request_parsed, config, client, cache=cache)


async def _indexed_search_request(
    request_index: int,
    request: _SearchRequest,
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    cache: TmdbCache | None,
) -> _IndexedSearchResults:
    async with semaphore:
        return request_index, await _search_request(request, parsed, config, client, cache)


async def _collect_candidates(
    plan: list[_SearchRequest],
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    cache: TmdbCache | None,
) -> dict[CandidateKey, _CandidateAggregate]:
    candidates: dict[CandidateKey, _CandidateAggregate] = {}

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCH_REQUESTS)
    search_results = await asyncio.gather(
        *(
            _indexed_search_request(
                request_index,
                request,
                parsed,
                config,
                client,
                semaphore,
                cache,
            )
            for request_index, request in enumerate(plan)
        )
    )

    for request_index, results in search_results:
        for result_index, candidate in enumerate(results):
            key: CandidateKey = (candidate.media_type, candidate.tmdb_id)
            aggregate = candidates.get(key)
            if aggregate is None:
                candidates[key] = _CandidateAggregate(
                    metadata=candidate,
                    first_request_index=request_index,
                    first_result_index=result_index,
                    aliases=[],
                )

    return candidates


def _normalize_seed(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("&", " and ")
    normalized = _NON_WORD_RE.sub(" ", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    return normalized.strip()


@lru_cache(maxsize=512)
def _normalized_title_forms(text: str) -> tuple[str, ...]:
    seed = _normalize_seed(text)
    if not seed:
        return ("",)

    pending = [seed]
    seen: set[str] = set()

    while pending and len(seen) < 8:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)

        without_the = _LEADING_THE_RE.sub("", current, count=1).strip()
        if without_the and without_the != current:
            pending.append(without_the)

        swapped = _swap_word_initial_vv_w(current)
        if swapped is not None:
            pending.append(_normalize_seed(swapped))

        roman_numeric = _roman_to_numeric_title(current)
        if roman_numeric is not None:
            pending.append(_normalize_seed(roman_numeric))

        numeric_roman = _numeric_to_roman_title(current)
        if numeric_roman is not None:
            pending.append(_normalize_seed(numeric_roman))

    return tuple(sorted(seen))


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0

    score = SequenceMatcher(a=left, b=right).ratio()
    left_tokens = left.split()
    right_tokens = right.split()
    if left_tokens and right_tokens:
        left_set = set(left_tokens)
        right_set = set(right_tokens)
        if left_set.issubset(right_set) and len(right_tokens) > len(left_tokens):
            score = max(score, 0.9)
        if right_set.issubset(left_set) and len(left_tokens) > len(right_tokens):
            score = max(score, 0.9)
    if right.startswith(left) and len(left) >= 4:
        score = max(score, 0.9)
    if left.startswith(right) and len(right) >= 4:
        score = max(score, 0.9)
    return score


def _best_similarity(query: str, candidate_texts: tuple[str, ...]) -> float:
    query_forms = _normalized_title_forms(query)
    candidate_forms: list[str] = []
    for text in candidate_texts:
        candidate_forms.extend(_normalized_title_forms(text))

    best = 0.0
    for query_form in query_forms:
        for candidate_form in candidate_forms:
            best = max(best, _similarity(query_form, candidate_form))
    return best


def _year_score(parsed: ParsedMetadata, config: MetadataConfig, candidate: TmdbMetadata) -> float:
    if parsed.year is None:
        return 1.0
    if candidate.year <= 0:
        return 0.5

    delta = abs(parsed.year - candidate.year)
    if delta == 0:
        return 1.0
    if delta <= max(config.year_tolerance, 0):
        return max(0.7, 1.0 - (0.15 * delta))
    return max(0.0, 0.35 - (0.15 * (delta - config.year_tolerance - 1)))


def _category_score(expected_media_type: MediaType | None, candidate: TmdbMetadata) -> float:
    if expected_media_type is None:
        return 0.5
    return 1.0 if candidate.media_type == expected_media_type else 0.0


def _order_bonus(first_request_index: int, first_result_index: int) -> float:
    return max(
        0.0,
        0.01 - (0.0015 * first_request_index) - (0.00075 * first_result_index),
    )


def _promoted_similarity(title_similarity: float, alias_similarity: float) -> float:
    if alias_similarity < ALIAS_PROMOTION_THRESHOLD:
        return max(title_similarity, alias_similarity)
    return max(title_similarity, min(1.0, alias_similarity + 0.08))


def _informative_aliases(candidate: TmdbMetadata, aliases: tuple[str, ...]) -> tuple[str, ...]:
    existing_forms = set(_normalized_title_forms(candidate.title))
    existing_forms.update(_normalized_title_forms(candidate.original_title))
    informative: list[str] = []
    for alias in aliases:
        alias_forms = set(_normalized_title_forms(alias))
        if alias_forms and alias_forms.issubset(existing_forms):
            continue
        informative.append(alias)
    return tuple(informative)


def _score_candidate(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    aggregate: _CandidateAggregate,
    *,
    aliases: tuple[str, ...],
) -> _ScoredCandidate:
    candidate = aggregate.metadata
    expected_media_type = _preferred_media_type(parsed, config)
    title_similarity = _best_similarity(parsed.title, (candidate.title, candidate.original_title))
    informative_aliases = _informative_aliases(candidate, aliases)
    alias_similarity = (
        _best_similarity(parsed.title, informative_aliases) if informative_aliases else 0.0
    )
    effective_similarity = _promoted_similarity(title_similarity, alias_similarity)
    year_score = _year_score(parsed, config, candidate)
    category_score = _category_score(expected_media_type, candidate)
    order_bonus = _order_bonus(aggregate.first_request_index, aggregate.first_result_index)
    score = (
        (effective_similarity * 0.78) + (year_score * 0.17) + (category_score * 0.04) + order_bonus
    )
    if alias_similarity >= ALIAS_PROMOTION_THRESHOLD:
        score = max(score + max(0.1, alias_similarity * 0.25), alias_similarity + 0.05)
    return _ScoredCandidate(
        metadata=candidate,
        score=score,
        title_similarity=title_similarity,
        alias_similarity=alias_similarity,
        year_score=year_score,
        category_score=category_score,
        order_bonus=order_bonus,
        first_request_index=aggregate.first_request_index,
        first_result_index=aggregate.first_result_index,
        aliases=aliases,
    )


def _rank_candidates(
    scored_candidates: list[_ScoredCandidate],
) -> list[_ScoredCandidate]:
    return sorted(
        scored_candidates,
        key=lambda candidate: (
            candidate.score,
            candidate.alias_similarity,
            candidate.title_similarity,
            -candidate.first_request_index,
            -candidate.first_result_index,
        ),
        reverse=True,
    )


def _variant_risk(parsed: ParsedMetadata) -> bool:
    return len(_build_search_variants(parsed)) > 2


def _select_scoring_pool(
    parsed: ParsedMetadata,
    ranked_base: list[_ScoredCandidate],
) -> list[_ScoredCandidate]:
    by_score = ranked_base[: min(5, len(ranked_base))]
    selected_keys: set[CandidateKey] = {
        (candidate.metadata.media_type, candidate.metadata.tmdb_id) for candidate in by_score
    }
    pool = list(by_score)

    if len(pool) >= MAX_CANDIDATES_TO_SCORE:
        return pool[:MAX_CANDIDATES_TO_SCORE]

    if _variant_risk(parsed):
        by_discovery = sorted(
            ranked_base,
            key=lambda candidate: (candidate.first_request_index, candidate.first_result_index),
        )
        for candidate in by_discovery:
            key = (candidate.metadata.media_type, candidate.metadata.tmdb_id)
            if key in selected_keys:
                continue
            selected_keys.add(key)
            pool.append(candidate)
            if len(pool) >= MAX_CANDIDATES_TO_SCORE:
                break
    else:
        for candidate in ranked_base[len(pool) : MAX_CANDIDATES_TO_SCORE]:
            key = (candidate.metadata.media_type, candidate.metadata.tmdb_id)
            if key in selected_keys:
                continue
            selected_keys.add(key)
            pool.append(candidate)

    return pool


def _select_alt_title_pool(ranked_candidates: list[_ScoredCandidate]) -> list[_ScoredCandidate]:
    if not ranked_candidates:
        return []

    top_score = ranked_candidates[0].score
    pool: list[_ScoredCandidate] = []
    seen: set[CandidateKey] = set()

    for candidate in ranked_candidates:
        key = (candidate.metadata.media_type, candidate.metadata.tmdb_id)
        if key in seen:
            continue
        if len(pool) < 2:
            seen.add(key)
            pool.append(candidate)
            continue
        should_fetch_aliases = (
            candidate.score >= top_score - max(AMBIGUITY_MARGIN, 0.12)
            or candidate.title_similarity < ALIAS_PROMOTION_THRESHOLD
            or candidate.metadata.original_title != candidate.metadata.title
        )
        if should_fetch_aliases:
            seen.add(key)
            pool.append(candidate)
        if len(pool) >= MAX_ALT_TITLE_REQUESTS:
            break

    return pool[:MAX_ALT_TITLE_REQUESTS]


async def _fetch_candidate_aliases(
    candidate: _ScoredCandidate,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    cache: TmdbCache | None,
) -> tuple[CandidateKey, tuple[str, ...]]:
    key: CandidateKey = (candidate.metadata.media_type, candidate.metadata.tmdb_id)

    try:
        if cache is None:
            aliases = await tmdb_lookup.fetch_tmdb_alternative_titles(
                candidate.metadata.tmdb_id,
                candidate.metadata.media_type,
                config,
                client,
            )
        else:
            aliases = await tmdb_lookup.fetch_tmdb_alternative_titles(
                candidate.metadata.tmdb_id,
                candidate.metadata.media_type,
                config,
                client,
                cache=cache,
            )
    except (TmdbError, TmdbRateLimitedError) as exc:
        log.warning(
            "tmdb_alternative_titles_unavailable",
            tmdb_id=candidate.metadata.tmdb_id,
            media_type=candidate.metadata.media_type,
            error_type=type(exc).__name__,
        )
        return key, ()

    deduped: list[str] = []
    seen_titles: set[str] = set()
    for alias in aliases:
        normalized = alias.strip()
        if not normalized or normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        deduped.append(normalized)

    return key, tuple(deduped)


async def _enrich_candidates_with_aliases(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    aggregates: dict[CandidateKey, _CandidateAggregate],
    ranked_candidates: list[_ScoredCandidate],
    cache: TmdbCache | None,
) -> list[_ScoredCandidate]:
    pool = _select_alt_title_pool(ranked_candidates)
    if not pool:
        return ranked_candidates

    alias_results = await asyncio.gather(
        *[_fetch_candidate_aliases(candidate, config, client, cache) for candidate in pool]
    )
    alias_map = dict(alias_results)

    rescored: list[_ScoredCandidate] = []
    for candidate in ranked_candidates:
        key: CandidateKey = (candidate.metadata.media_type, candidate.metadata.tmdb_id)
        aggregate = aggregates[key]
        aliases = alias_map.get(key, candidate.aliases)
        aggregate.aliases = list(aliases)
        rescored.append(_score_candidate(parsed, config, aggregate, aliases=aliases))

    return _rank_candidates(rescored)


def _select_candidate(
    expected_media_type: MediaType | None,
    ranked_candidates: list[_ScoredCandidate],
) -> TmdbMetadata | None:
    if not ranked_candidates:
        return None

    top = ranked_candidates[0]
    if expected_media_type is not None and top.metadata.media_type != expected_media_type:
        return None
    if top.evidence_similarity < SIMILARITY_FLOOR:
        return None
    if top.score < STRONG_MATCH_CUTOFF:
        return None

    second_score = ranked_candidates[1].score if len(ranked_candidates) > 1 else 0.0
    if top.score - second_score < AMBIGUITY_MARGIN:
        return None

    return top.metadata


def _filter_ranked_candidates(ranked_candidates: list[_ScoredCandidate]) -> list[_ScoredCandidate]:
    filtered = [
        candidate
        for candidate in ranked_candidates
        if candidate.evidence_similarity >= SIMILARITY_FLOOR
    ]
    return filtered[:MAX_CANDIDATES_TO_SCORE]


async def resolve_tmdb_match(
    parsed: ParsedMetadata,
    config: MetadataConfig,
    client: httpx.AsyncClient,
    *,
    cache: TmdbCache | None = None,
) -> TmdbResolutionOutcome:
    title = parsed.title.strip()
    if not title or config.api_key is None:
        return TmdbResolutionOutcome(selected=None, candidates=[])

    plan = _build_search_plan(parsed, config)
    log.debug(
        "tmdb_resolution_query_plan",
        title=parsed.title,
        year=parsed.year,
        season=parsed.season,
        episode=parsed.episode,
        category_preference=config.category_preference,
        requests=[
            {
                "endpoint": request.endpoint,
                "title": request.title,
                "include_year": request.include_year,
            }
            for request in plan
        ],
    )

    aggregates = await _collect_candidates(plan, parsed, config, client, cache)
    if not aggregates:
        log.debug("tmdb_resolution_no_candidates", title=parsed.title, year=parsed.year)
        return TmdbResolutionOutcome(selected=None, candidates=[])

    base_scored = _rank_candidates(
        [
            _score_candidate(parsed, config, aggregate, aliases=())
            for aggregate in aggregates.values()
        ]
    )
    scoring_pool = _select_scoring_pool(parsed, base_scored)
    ranked_candidates = await _enrich_candidates_with_aliases(
        parsed,
        config,
        client,
        aggregates,
        scoring_pool,
        cache,
    )
    ranked_candidates = _filter_ranked_candidates(ranked_candidates)
    selected = _select_candidate(_preferred_media_type(parsed, config), ranked_candidates)

    log.debug(
        "tmdb_resolution_complete",
        title=parsed.title,
        year=parsed.year,
        candidate_count=len(ranked_candidates),
        selected_tmdb_id=None if selected is None else selected.tmdb_id,
        top_candidates=[
            {
                "tmdb_id": candidate.metadata.tmdb_id,
                "media_type": candidate.metadata.media_type,
                "title": candidate.metadata.title,
                "score": round(candidate.score, 4),
                "title_similarity": round(candidate.title_similarity, 4),
                "alias_similarity": round(candidate.alias_similarity, 4),
                "year_score": round(candidate.year_score, 4),
            }
            for candidate in ranked_candidates[:3]
        ],
    )

    return TmdbResolutionOutcome(
        selected=selected,
        candidates=[candidate.metadata for candidate in ranked_candidates],
    )
