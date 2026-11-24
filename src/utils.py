import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from contextlib import suppress
from datetime import date
from typing import Any, cast

import feedparser
from httpx2 import HTTPStatusError
from langfuse import propagate_attributes
from openai.types.responses import ResponseInputParam, ResponseTextConfigParam
from openai.types.shared_params.reasoning import Reasoning
from parsel import Selector
from procrastinate.exceptions import AlreadyEnqueued
from sqlalchemy.ext.asyncio.engine import AsyncConnection

import src.db as db
from src.enums import (
    EnglishLevel,
    ProfileStatus,
    SkillAliasStatus,
    SkillLexiconStatus,
    Source,
    VacancyStatus,
)
from src.geo import canonicalize
from src.seniority import seniority_from_title
from src.shared.resources import resources
from src.shared.utils import dt_now, normalize_skill_name
from src.splitters import split_vacancy_text
from src.types import (
    ExperiencePeriod,
    FullParsedPage,
    InactivePage,
    JudgeItem,
    JudgeVerdict,
    LexiconExpand,
    LexiconJudge,
    ParsedPage,
    ParseJob,
    ProfileLLMExtract,
    SkillExtract,
    VacancyLLMExtract,
    VacancySkillExtract,
)

CEFR_RE = re.compile(r'\b([ABC][12])\b', re.IGNORECASE)

JSON_TEXT: ResponseTextConfigParam = {'format': {'type': 'json_object'}}
LOW_REASONING: Reasoning = {'effort': 'low'}


def openai_input(compiled: object) -> str | ResponseInputParam:
    if isinstance(compiled, str):
        return compiled
    if isinstance(compiled, list):
        return cast(ResponseInputParam, compiled)
    raise TypeError(f'unexpected compiled prompt: {type(compiled).__name__}')


async def process_feed(category: str) -> None:
    resp = await resources.client.get(
        f'https://djinni.co/jobs/rss/?primary_keyword={category}',
    )
    resp.raise_for_status()
    content = resp.content

    # local_file = Path(__file__).with_name('djinni_result.xml')
    # local_file.write_bytes(resp.content)
    # content = local_file.read_bytes()

    feed = feedparser.parse(content)
    duplicates = set()

    result = []
    for entry in feed.entries:
        guid = entry.guid
        split_guid = guid.rstrip('/').split('/')
        external_id = split_guid[-1].split('-')[0]

        if external_id in duplicates:
            continue

        duplicates.add(external_id)

        title = entry.title
        url = entry.link
        cat = entry.category

        result.append(
            {
                'source': Source.djinni,
                'external_id': external_id,
                'status': VacancyStatus.pending,
                'category': cat,
                'title': title,
                'url': url,
                'description': '',
                'company': '',
            }
        )

    async with resources.engine.begin() as conn:
        ids = await db.insert_and_reactivate_vacancies(conn, result)

    print(ids)
    if ids:
        from src.tasks import enqueue_vacancies

        await enqueue_vacancies.defer_async(status=VacancyStatus.pending)


async def parse_vacancy_page(body: str) -> ParsedPage:
    sel = Selector(text=body)
    inactive = (
        sel.css('div.alert[role="alert"]')
        .xpath('.//div[contains(normalize-space(.), "Ця вакансія зараз неактивна")]')
        .get()
    )
    if inactive:
        return InactivePage()

    ld_raw = sel.css('script[type="application/ld+json"]::text').get()
    if ld_raw is None:
        print(ld_raw)
        raise ValueError('JSON-LD not found')
    ld_json = json.loads(ld_raw)

    location_tokens = []
    for job_loc in (
        ld_json.get('jobLocation'),
        ld_json.get('applicantLocationRequirements'),
    ):
        if not job_loc:
            continue

        if isinstance(job_loc, dict):
            job_loc = [job_loc]

        for x in job_loc:
            addr = x['address']
            if (addr_reg := addr.get('addressRegion')) and isinstance(addr_reg, str):
                location_tokens.append(addr_reg)

            if (addr_cnt := addr.get('addressCountry')) and isinstance(addr_cnt, str):
                location_tokens.append(addr_cnt)

            if addr_loc := addr.get('addressLocality'):
                if isinstance(addr_loc, list):
                    location_tokens.extend(addr_loc)
                elif isinstance(addr_loc, str):
                    location_tokens.append(addr_loc)

        break

    geo = canonicalize(location_tokens)

    # salary
    salary_min = None
    salary_max = None
    salary_level = None
    if base_salary := ld_json.get('baseSalary', {}).get('value'):
        salary_min = base_salary.get('minValue')
        salary_max = base_salary.get('maxValue')

    elif est_salary := ld_json.get('estimatedSalary'):
        salary_min = est_salary.get('minValue')
        salary_max = est_salary.get('maxValue')

    else:
        text = 'Рівень зарплати відносно інших'
        salary_level = sel.css(
            f'span[title*="{text}"]::text, span[data-bs-original-title*="{text}"]::text'
        ).get()
    ###

    experience = None
    exp_years = None
    if exp := ld_json.get('experienceRequirements', {}).get('monthsOfExperience'):
        experience = float(exp)
        exp_years = experience // 12

    english_raw = None
    for line in sel.css('div.detail-rows__line'):
        name = line.css('span.detail-rows__name::text').get(default='').strip()
        if 'Англійська' in name:
            english_raw = (
                line.css('span.detail-rows__value::text').get(default='').strip()
            )
            break

    english_level = None
    if english_raw and (m := CEFR_RE.search(english_raw)):
        english_level = EnglishLevel[m.group(1)]

    title = ld_json['title']
    seniority = seniority_from_title(title, years=exp_years)

    page = FullParsedPage(
        status=VacancyStatus.active,
        company=ld_json['hiringOrganization']['name'],
        title=title,
        description=ld_json['description'],  # already not a html page
        location_str=geo.location_str,
        location=geo.location,
        experience=experience,
        salary_min=int(salary_min) if salary_min else None,
        salary_max=int(salary_max) if salary_max else None,
        salary_level=salary_level,
        english_level=english_level,
        seniority=seniority,
    )

    return page


async def fetch_vacancy_body(url: str) -> str:
    async with resources.client.stream('GET', url) as resp:
        resp.raise_for_status()

        await resp.aread()
        return resp.text


async def process_vacancy_page(job: ParseJob) -> None:
    if not job.url:
        print(f'url is empty for vacancy id {job.vacancy_id}')
        return

    try:
        # TODO: handle 301
        body = await fetch_vacancy_body(job.url)
        page = await parse_vacancy_page(body)
    except HTTPStatusError as err:
        if err.response.status_code == 404:
            page = InactivePage()
        else:
            raise err

    vacancy_id = job.vacancy_id
    defer_extract = False

    async with resources.engine.begin() as conn:
        if isinstance(page, FullParsedPage):
            params_same = page.same_params(job.params_hash)
            desc_same = page.same_description(job.desc_hash)

            if params_same and desc_same:
                await db.update_vacancy(conn, vacancy_id, data=page.last_seen())
                return

            await db.update_vacancy(conn, vacancy_id, data=page.to_db())
            if job.params_hash is None:
                await db.insert_vacancies_activity(
                    conn, data={'vacancy_id': vacancy_id, 'date_started': page.timestamp}
                )
            if not desc_same:
                if job.desc_hash:
                    print('Deleting previous vacancy extract!')
                    await db.delete_vacancy_extract(conn, vacancy_id)
                defer_extract = True

        elif isinstance(page, InactivePage):
            await db.update_vacancy(conn, vacancy_id, data=page.to_db())
            await db.close_vacancies_activity(conn, vacancy_id, date_ended=page.timestamp)
        else:
            raise ValueError

    if defer_extract:
        from src.tasks import chunk_vacancy, extract_vacancy

        with suppress(AlreadyEnqueued):
            await extract_vacancy.configure(
                queueing_lock=f'extract:{vacancy_id}', lock=vacancy_id
            ).defer_async(vacancy_id=vacancy_id)

        await chunk_vacancy.configure(
            queueing_lock=f'chunk:{vacancy_id}', lock=vacancy_id
        ).defer_async(vacancy_id=vacancy_id)


async def _sync_skills_into_lexicon[T: SkillExtract](
    conn: AsyncConnection, skills: list[T]
) -> list[T]:
    extracted_skills: dict[str, T] = {}  # normalized name -> skill
    for skill in skills:
        norm = skill.normalized
        if norm:
            existing = extracted_skills.get(norm)
            extracted_skills[norm] = existing.prefer(skill) if existing else skill

    if not extracted_skills:
        return []

    # waits while the judge changes skill_lexicon
    await db.lock_skill_lexicon_shared(conn)
    known = await db.select_skill_resolutions(conn, data=list(extracted_skills))
    unknown = [norm for norm in extracted_skills if norm not in known]

    similar = await db.select_skill_lexicon_matches(conn, data=unknown)
    new = {
        norm: extracted_skills[norm].canonical for norm in unknown if norm not in similar
    }

    await db.increase_skill_alias_seen_count(
        conn, data=[norm for norm, name in known.items() if name is None]
    )
    await db.insert_skill_alias(
        conn,
        data=[
            {
                'alias_name': extracted_skills[norm].canonical,
                'skill_name': name,
                'status': SkillAliasStatus.alias,
            }
            for norm, name in similar.items()
        ],
    )
    await db.insert_skill_lexicon(
        conn,
        data=[
            {
                'skill_name': name,
                'kind': extracted_skills[norm].kind,
                'status': SkillLexiconStatus.pending,
            }
            for norm, name in new.items()
        ],
    )
    # another worker could save the same skill first under another spelling
    # take the names from DB
    saved = await db.select_skill_resolutions(conn, data=list(new))

    resolved_skills: dict[str, T] = {}  # skill_lexicon name -> skill
    for norm, name in (known | similar | saved).items():
        if name is None:  # rejected earlier
            continue

        skill = extracted_skills[norm]
        skill.canonical = name

        existing = resolved_skills.get(name)
        resolved_skills[name] = existing.prefer(skill) if existing else skill

    return list(resolved_skills.values())


async def _add_vacancy_skill_and_lexicon(
    conn: AsyncConnection, vacancy_id: str, skills: list[VacancySkillExtract]
) -> None:
    skills_ = await _sync_skills_into_lexicon(conn, skills)
    if not skills_:
        return

    await db.insert_vacancy_skills(
        conn,
        data=[
            {
                'vacancy_id': vacancy_id,
                'skill_name': skill.canonical,
                'depth': skill.depth,
                'importance': skill.importance,
            }
            for skill in skills_
        ],
    )


async def _add_profile_skill_and_lexicon(
    conn: AsyncConnection, profile_id: str, skills: list[SkillExtract]
) -> None:
    skills_ = await _sync_skills_into_lexicon(conn, skills)
    if not skills_:
        return

    await db.insert_profile_skills(
        conn,
        data=[
            {
                'profile_id': profile_id,
                'skill_name': skill.canonical,
                'depth': skill.depth,
            }
            for skill in skills_
        ],
    )


async def process_vacancy_extract(vacancy_id: str) -> None:
    prompt = resources.get_prompt('vacancy-extract')
    prompt_version = f'{prompt.name} v{prompt.version}'

    async with resources.engine.connect() as conn:
        extract_row = await db.select_vacancy_extract_info(conn, vacancy_id)

        if extract_row:
            skill_count = extract_row['skill_count']
            # if vacancy extract exists and skills are defined - skip
            if skill_count > 0:  # row['prompt_version'] == prompt_version
                return

            raw_resp = await db.select_vacancy_extract_response(conn, vacancy_id)
            assert raw_resp

            data = VacancyLLMExtract.model_validate_json(raw_resp)
            if data.skills:
                await _add_vacancy_skill_and_lexicon(conn, vacancy_id, data.skills)
            await conn.commit()

            return

        row = await db.select_vacancy_for_extract(conn, vacancy_id)

    if not row:
        print(f'No vacancy! vacancy_id: {vacancy_id}')
        return

    compiled_prompt = prompt.compile(
        title=row['title'],
        experience=row['experience'],
        description=row['description'],
    )

    with propagate_attributes(prompt=prompt, trace_name=prompt.name):
        resp = await resources.llm.responses.create(
            model=prompt.config['model'],
            input=openai_input(compiled_prompt),
            text=JSON_TEXT,
            reasoning=LOW_REASONING,
            metadata={
                'vacancy_id': vacancy_id,
                'category': str(row['category']),
            },
        )

    raw_resp = resp.output_text
    if not raw_resp:
        raise RuntimeError('Vacancy extract. LLM response is empty!')

    data = VacancyLLMExtract.model_validate_json(raw_resp)
    if not data.skills:
        print('Vacancy extract. Skills list is empty!')
        return

    async with resources.engine.connect() as conn:
        await db.insert_vacancy_extract(
            conn,
            data={
                'vacancy_id': vacancy_id,
                'prompt_version': prompt_version,
                'job_family': data.job_family,
                'industry': data.industry,
                'raw_response': raw_resp,
            },
        )
        await conn.commit()

        if data.skills:
            await _add_vacancy_skill_and_lexicon(conn, vacancy_id, data.skills)
            await conn.commit()

    # from src.tasks import lexicon_expand
    #
    # with suppress(AlreadyEnqueued):
    #     await lexicon_expand.configure(schedule_in={'minutes': 1}).defer_async()


async def process_lexicon_expanding() -> None:
    prompt = resources.get_prompt('lexicon-expand')
    limit = 10

    async with resources.engine.connect() as conn:
        rows = await db.select_skill_lexicon_for_expand(conn, limit=limit)

    if not rows:
        return

    compiled_prompt = prompt.compile(skill_names=rows[:limit])
    with propagate_attributes(prompt=prompt, trace_name=prompt.name):
        resp = await resources.llm.responses.create(
            model=prompt.config['model'],
            input=openai_input(compiled_prompt),
            text=JSON_TEXT,
            reasoning=LOW_REASONING,
        )

    raw_resp = resp.output_text
    if not raw_resp:
        raise RuntimeError('Lexicon expanding. LLM response is empty!')

    data = LexiconExpand.model_validate_json(raw_resp)
    if not data.items:
        raise RuntimeError('Lexicon expanding. Items is empty!')

    requested = set(rows[:limit])
    for item in data.items:
        if item.skill_name not in requested:
            print('Lexicon expanding. Unwanted skill in response!', item.skill_name)

    update_items = [i.model_dump() for i in data.items]
    async with resources.engine.begin() as conn:
        await db.update_skill_lexicon_expand(conn, data=update_items)

    from src.tasks import lexicon_embed, lexicon_expand

    if len(rows) > limit:
        await lexicon_expand.defer_async()

        with suppress(AlreadyEnqueued):
            await lexicon_embed.configure(schedule_in={'minutes': 2}).defer_async()
    else:
        with suppress(AlreadyEnqueued):
            await lexicon_embed.defer_async()


def validate_judge_items(
    items: Iterable[JudgeItem], sent: Iterable[str]
) -> list[JudgeItem]:
    valid: dict[str, JudgeItem] = {}
    sent = set(sent)

    for item in items:
        if item.skill_name not in sent:
            print('Lexicon judging. Unwanted skill in response!', item.skill_name)
            continue
        if item.skill_name in valid:
            print('Lexicon judging. Duplicate skill in response!', item.skill_name)
            continue

        if item.verdict not in set(JudgeVerdict):
            print('Lexicon judging. Unknown verdict!', item.skill_name, item.verdict)
            continue
        if item.verdict != JudgeVerdict.rejected and not item.canonical:
            print('Lexicon judging. No canonical!', item.skill_name, item.verdict)
            continue

        valid[item.skill_name] = item

    return list(valid.values())


async def _reject_pending_skill(conn: AsyncConnection, original_name: str) -> None:
    await db.delete_pending_skill_lexicon(conn, original_name)
    await db.insert_skill_alias(
        conn,
        data={
            'alias_name': original_name,
            'skill_name': None,
            'status': SkillAliasStatus.rejected,
        },
    )


async def _alias_pending_skill(
    conn: AsyncConnection, original_name: str, canonical: str
) -> None:
    await db.rename_vacancy_skill(conn, from_name=original_name, to_name=canonical)
    await db.rename_profile_skill(conn, from_name=original_name, to_name=canonical)
    await db.delete_pending_skill_lexicon(conn, original_name)
    await db.insert_skill_alias(
        conn,
        data={
            'alias_name': original_name,
            'skill_name': canonical,
            'status': SkillAliasStatus.alias,
        },
    )


async def _accept_pending_skill(
    conn: AsyncConnection, original_name: str, canonical: str
) -> bool:
    row = await db.select_skill_by_norm(conn, normalize_skill_name(canonical))
    # canonical name is not exists, rename original name to canonical
    # and create new alias for original skill name
    if row is None:
        await db.accept_pending_skill_lexicon(conn, original_name, new_name=canonical)
        await db.insert_skill_alias(
            conn,
            data={
                'alias_name': original_name,
                'skill_name': canonical,
                'status': SkillAliasStatus.alias,
            },
        )
        return True

    if row.is_rejected:
        await _reject_pending_skill(conn, original_name)
        return True

    # already confirmed skill exists with canonical name
    if row.is_canonical:
        await _alias_pending_skill(conn, original_name, row.skill_name)
        return True

    # the same processed skill
    if row.skill_name == original_name:
        await db.accept_pending_skill_lexicon(conn, original_name, new_name=canonical)
        return True

    print(
        'Lexicon judging. Canonical name found, but is pending too! Skip',
        original_name,
        canonical,
    )
    return False


async def apply_judge_verdicts(conn: AsyncConnection, pending: list[JudgeItem]) -> int:
    applied = 0

    # new skills go first: an alias can point to a skill accepted in this batch
    new_items = (i for i in pending if i.verdict == JudgeVerdict.new)
    for item in new_items:
        assert item.canonical
        is_processed = await _accept_pending_skill(
            conn, original_name=item.skill_name, canonical=item.canonical
        )
        if is_processed:
            applied += 1

    alias_items = (i for i in pending if i.verdict == JudgeVerdict.alias)
    for item in alias_items:
        assert item.canonical

        row = await db.select_skill_by_norm(conn, normalize_skill_name(item.canonical))
        if row and row.is_rejected:
            await _reject_pending_skill(conn, item.skill_name)
        elif row and row.is_canonical:
            await _alias_pending_skill(conn, item.skill_name, row.skill_name)
        else:
            print(
                'Lexicon judging. Canonical not found or pending! Skip',
                item.skill_name,
                item.canonical,
            )
            continue

        applied += 1

    rej_items = (i for i in pending if i.verdict == JudgeVerdict.rejected)
    for item in rej_items:
        await _reject_pending_skill(conn, item.skill_name)
        applied += 1

    return applied


async def process_lexicon_judging() -> None:
    prompt = resources.get_prompt('lexicon-judge')
    limit = 10

    async with resources.engine.connect() as conn:
        rows = await db.select_pending_skill_names(conn, limit=limit)
        if not rows:
            return

        batch = rows[:limit]
        titles = await db.select_vacancy_titles_for_skills(conn, skill_names=batch)
        canonical_skills = await db.select_canonical_skill_names(conn)

    compiled_prompt = prompt.compile(
        candidates=[
            {'skill_name': name, 'titles': titles.get(name, [])} for name in batch
        ],
        canonical_skills=canonical_skills,
    )
    with propagate_attributes(prompt=prompt, trace_name=prompt.name):
        resp = await resources.llm.responses.create(
            model=prompt.config['model'],
            input=openai_input(compiled_prompt),
            text=JSON_TEXT,
            reasoning=LOW_REASONING,
        )

    raw_resp = resp.output_text
    if not raw_resp:
        raise RuntimeError('Lexicon judging. LLM response is empty!')

    data = LexiconJudge.model_validate_json(raw_resp)
    if not data.items:
        raise RuntimeError('Lexicon judging. Items is empty!')

    pending = validate_judge_items(data.items, sent=batch)

    async with resources.engine.begin() as conn:
        await db.lock_skill_lexicon(conn)
        applied = await apply_judge_verdicts(conn, pending)

    from src.tasks import lexicon_judge

    if len(rows) > limit and applied:
        with suppress(AlreadyEnqueued):
            await lexicon_judge.defer_async()


async def _write_vacancy_chunks(conn: AsyncConnection, row: Mapping[Any, Any]) -> bool:
    vacancy_id = row['id']
    # do not quit early for empty list, need to delete stored chunks
    chunks = split_vacancy_text(row['title'], row['description'])
    print(f'Vacancy chunking. Chunks: {[len(ch) for ch in chunks]}')
    # sorted by fragment
    existing = await db.select_vacancy_chunk_state(conn, vacancy_id)

    len_ch = len(chunks)
    len_ex = len(existing)

    hashes = [hashlib.sha256(content.encode()).digest() for content in chunks]
    assert len_ch == len(hashes)

    need_embed = False
    update_c = skip_c = delete_c = new_c = 0  # c - count

    for i, ch in enumerate(chunks[:len_ex]):
        item = existing[i]
        if item['content_hash'] != hashes[i]:
            await db.update_vacancy_chunk(
                conn,
                chunk_id=item['id'],
                data={
                    'id': item['id'],
                    'content_hash': hashes[i],
                    'content': ch,
                    'embedding': None,
                    'embedding_model': None,
                },
            )
            need_embed = True
            update_c += 1
        else:
            need_embed = need_embed or item['needs_embed']
            skip_c += 1

    if len_ex > len_ch:
        await db.delete_vacancy_chunks_from(conn, vacancy_id, from_=len_ch)
        delete_c = len_ex - len_ch
    elif len_ex < len_ch:
        insert_items = [
            {
                'vacancy_id': vacancy_id,
                'content_hash': hashes[i],
                'content': chunks[i],
                'fragment': i,
            }
            for i in range(len_ex, len_ch)
        ]
        await db.insert_vacancy_chunks(conn, insert_items)
        need_embed = True
        new_c = len_ch - len_ex

    print(
        f'Vacancy chunking. Chunks processed. '
        f'Updated: {update_c}, skipped: {skip_c}, deleted: {delete_c}, created: {new_c}'
    )

    return need_embed


async def process_vacancy_chunking(vacancy_id: str) -> None:
    async with resources.engine.begin() as conn:
        row = await db.select_vacancy_for_chunk(conn, vacancy_id, lock=True)
        if not row:
            print('Vacancy chunking. Vacancy not found!')
            return

        needs_embed = await _write_vacancy_chunks(conn, row)

    if needs_embed:
        from src.tasks import chunk_embed

        with suppress(AlreadyEnqueued):
            await chunk_embed.configure(schedule_in={'minutes': 2}).defer_async()


async def process_chunk_embedding() -> None:
    model = resources.config['llm']['embedding_model']
    limit = 64

    async with resources.engine.connect() as conn:
        rows = await db.select_vacancy_chunks_for_embed(conn, limit=limit)

    if not rows:
        return

    batch = rows[:limit]
    with propagate_attributes(trace_name='chunk-embed'):
        resp = await resources.llm.embeddings.create(
            model=model,
            input=[row['content'] for row in batch],
            dimensions=1536,
        )
    by_index = {item.index: item.embedding for item in resp.data}
    if len(by_index) != len(batch):
        raise RuntimeError('Chunk embedding. Unexpected embedding count!')

    update_items = [
        {
            'id': row['id'],
            'content_hash': row['content_hash'],
            'embedding': by_index[i],
            'embedding_model': model,
        }
        for i, row in enumerate(batch)
    ]
    async with resources.engine.begin() as conn:
        saved = await db.update_vacancy_chunk_embed(conn, update_items)

    if len(rows) > limit or saved < len(batch):
        from src.tasks import chunk_embed

        await chunk_embed.defer_async()


async def process_lexicon_embedding() -> None:
    model = resources.config['llm']['embedding_model']
    limit = 64

    async with resources.engine.connect() as conn:
        rows = await db.select_skill_lexicon_for_embed(conn, limit=limit)

    if not rows:
        return

    batch = rows[:limit]
    with propagate_attributes(trace_name='lexicon-embed'):
        resp = await resources.llm.embeddings.create(
            model=model,
            input=[row['expanded'] for row in batch],
            dimensions=1536,
        )
    by_index = {item.index: item.embedding for item in resp.data}
    if len(by_index) != len(batch):
        raise RuntimeError('Lexicon embedding. Unexpected embedding count!')

    update_items = [
        {
            'skill_name': row['skill_name'],
            'expanded_vector': by_index[i],
            'embedding_model': model,
        }
        for i, row in enumerate(batch)
    ]
    async with resources.engine.begin() as conn:
        await db.update_skill_lexicon_embed(conn, data=update_items)

    if len(rows) > limit:
        from src.tasks import lexicon_embed

        await lexicon_embed.defer_async()


def months_from_periods(periods: list[ExperiencePeriod]) -> float | None:
    def _month(s: str) -> date:
        return date.fromisoformat(f'{s}-01')

    dates = []
    today = dt_now().date()

    for period in periods:
        try:
            start_date = _month(period.start)
            end_date = _month(period.end) if period.end else today
        except ValueError:
            print('Profile extract. Invalid experience period!')
            continue

        if start_date <= end_date:
            dates.append((start_date, end_date))

    if not dates:
        return None

    dates.sort()
    merged = [dates[0]]
    for start_date, end_date in dates[1:]:
        first, last = merged[-1]
        if start_date <= last:
            merged[-1] = (first, max(last, end_date))
        else:
            merged.append((start_date, end_date))

    return float(
        sum(
            (end.year - start.year) * 12 + (end.month - start.month)
            for start, end in merged
        )
    )


async def process_new_profile(profile_id: str) -> None:
    prompt = resources.get_prompt('profile-extract')
    prompt_version = f'{prompt.name} v{prompt.version}'

    async with resources.engine.connect() as conn:
        row = await db.select_profile_extract_info(conn, profile_id)
        if not row:
            print(f'No profile! profile_id {profile_id}')
            return

        if row['status'] != ProfileStatus.pending:
            return

        raw_resp = row['raw_response']
        skill_count = row['skill_count']

        if raw_resp:
            if skill_count == 0:
                data = ProfileLLMExtract.model_validate_json(raw_resp)
                if data.skills:
                    await _add_profile_skill_and_lexicon(conn, profile_id, data.skills)

            await db.update_profile(
                conn, profile_id, data={'status': ProfileStatus.ready}
            )
            await conn.commit()

            return

    compiled_prompt = prompt.compile(text=row['text'])

    with propagate_attributes(prompt=prompt, trace_name=prompt.name):
        resp = await resources.llm.responses.create(
            model=prompt.config['model'],
            input=openai_input(compiled_prompt),
            text=JSON_TEXT,
            reasoning=LOW_REASONING,
            metadata={'profile_id': profile_id},
        )

    raw_resp = resp.output_text
    if not raw_resp:
        print('Profile extract. LLM response is empty!')
        async with resources.engine.begin() as conn:
            await db.update_profile(
                conn, profile_id=profile_id, data={'status': ProfileStatus.failed}
            )
        return

    data = ProfileLLMExtract.model_validate_json(raw_resp)
    if not data.skills:
        print('Profile extract. Skills list is empty!')

    async with resources.engine.connect() as conn:
        await db.update_profile(
            conn,
            profile_id,
            data={
                'prompt_version': prompt_version,
                'raw_response': raw_resp,
                'job_families': data.job_families,
                'experience': (
                    data.experience
                    if data.experience is not None
                    else months_from_periods(data.experience_periods)
                ),
                'english_level': data.eng_lvl,
                'seniority': data.seniority,
            },
        )
        await conn.commit()

        if data.skills:
            await _add_profile_skill_and_lexicon(conn, profile_id, data.skills)

        await db.update_profile(conn, profile_id, data={'status': ProfileStatus.ready})
        await conn.commit()
