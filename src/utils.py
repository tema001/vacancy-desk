import json
import re
from contextlib import suppress

import feedparser
from httpx2 import HTTPStatusError
from langfuse import propagate_attributes
from parsel import Selector
from procrastinate.exceptions import AlreadyEnqueued
from sqlalchemy.ext.asyncio.engine import AsyncConnection

import src.db as db
from src.enums import EnglishLevel, Source, Status
from src.geo import canonicalize
from src.scoring import SIMILARITY_THRESHOLD, score_vacancy_matches
from src.seniority import seniority_from_title
from src.shared.resources import resources
from src.types import (
    DataDict,
    FullParsedPage,
    LexiconExpand,
    ParamsSchema,
    ParsedPage,
    ParseJob,
    ScoringParamsSchema,
    VacancyLLMExtract,
)

CEFR_RE = re.compile(r'\b([ABC][12])\b', re.IGNORECASE)


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
                'status': Status.new,
                'category': cat,
                'title': title,
                'url': url,
                'description': '',
                'company': '',
                'content_hash': b'',
            }
        )

    async with resources.engine.begin() as conn:
        ids = await db.insert_and_reactivate_vacancies(conn, result)

    print(ids)
    if ids:
        from src.tasks import enqueue_vacancies

        await enqueue_vacancies.defer_async(status=Status.new)


async def parse_vacancy_page(body: str) -> ParsedPage:
    sel = Selector(text=body)
    inactive = (
        sel.css('div.alert[role="alert"]')
        .xpath('.//div[contains(normalize-space(.), "Ця вакансія зараз неактивна")]')
        .get()
    )
    if inactive:
        return ParsedPage(Status.inactive)

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
        status=Status.active,
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
            page = ParsedPage(Status.inactive)
        else:
            raise err

    vacancy_id = job.vacancy_id
    defer_extract = False

    async with resources.engine.begin() as conn:
        if isinstance(page, FullParsedPage):
            if page.same_content(job.content_hash):
                await db.update_vacancy(conn, vacancy_id, data=page.last_seen())
                return

            await db.update_vacancy(conn, vacancy_id, data=page.to_db())
            await db.insert_vacancies_activity(
                conn, data={'vacancy_id': vacancy_id, 'date_started': page.timestamp}
            )
            # vacancy already parsed and has a hash
            if job.content_hash:
                print('Deleting previous vacancy extract!')
                await db.delete_vacancy_extract(conn, vacancy_id)
            defer_extract = True
        else:
            await db.update_vacancy(conn, vacancy_id, data=page.to_db())
            await db.close_vacancies_activity(conn, vacancy_id, date_ended=page.timestamp)

    if defer_extract:
        from src.tasks import extract_vacancy

        with suppress(AlreadyEnqueued):
            await extract_vacancy.configure(
                queueing_lock=f'extract:{vacancy_id}', lock=vacancy_id
            ).defer_async(vacancy_id=vacancy_id)


async def get_vacancies(params: ParamsSchema) -> DataDict:
    async with resources.engine.connect() as conn:
        total_count, rows = await db.select_vacancies(conn, params)

    result_rows = [{**r} for r in rows]

    return {
        'total_count': total_count,
        'has_next': len(result_rows) > params.limit,
        'rows': result_rows[: params.limit],
    }


async def get_scored_vacancies(params: ScoringParamsSchema) -> DataDict:
    async with resources.engine.connect() as conn:
        rows = await db.select_vacancy_skill_matches(
            conn,
            params,
            similarity_threshold=SIMILARITY_THRESHOLD,
        )

    print(len(rows))
    scored_rows = score_vacancy_matches(rows)
    total_count = len(scored_rows)
    page_rows = scored_rows[params.offset : params.offset + params.limit]

    return {
        'total_count': total_count,
        'has_next': params.offset + params.limit < total_count,
        'rows': page_rows,
    }


async def _add_vacancy_skill_and_lexicon(
    conn: AsyncConnection, vacancy_id: str, data: VacancyLLMExtract
) -> None:
    for skill in data.skills:
        name = skill.canonical
        skill.canonical = name[:1].upper() + name[1:]

    missing_names = set(
        await db.select_new_skill_lexicon(
            conn, data=[skill.canonical for skill in data.skills]
        )
    )
    matched: dict[str, str] = {}
    if missing_names:
        new_skills = [s for s in data.skills if s.canonical in missing_names]
        rows = await db.select_skill_lexicon_matches(
            conn, data=[skill.normalized for skill in new_skills]
        )
        print('Matched lexicon', rows)

        matched = {row['s_norm']: row['skill_name'] for row in rows}
        lexicon_data = [
            {'skill_name': skill.canonical, 'kind': skill.kind}
            for skill in new_skills
            if skill.normalized not in matched
        ]
        if lexicon_data:
            await db.insert_skill_lexicon(conn, lexicon_data)

    unique_skills: dict[str, DataDict] = {}
    for skill in data.skills:
        name = matched.get(skill.normalized) or skill.canonical
        existing = unique_skills.get(name)
        if existing is None:
            unique_skills[name] = {
                'vacancy_id': vacancy_id,
                'skill_name': name,
                'depth': skill.depth,
                'importance': skill.importance,
            }
            continue

        existing['depth'] = max(existing['depth'], skill.depth)
        existing['importance'] = max(existing['importance'], skill.importance)

    await db.insert_vacancy_skills(conn, data=list(unique_skills.values()))
    await conn.commit()


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
            else:
                raw_resp = await db.select_vacancy_extract_response(conn, vacancy_id)
                data = VacancyLLMExtract.model_validate(json.loads(raw_resp))

                await _add_vacancy_skill_and_lexicon(conn, vacancy_id, data)

                return

        row = await db.select_vacancy_by_id(conn, vacancy_id)

    if not row:
        print(f'No vacancy! vacancy_id: {vacancy_id}')
        return

    compiled_prompt = prompt.compile(
        seniority_field='',
        title=row['title'],
        experience=row['experience'],
        description=row['description'],
    )

    with propagate_attributes(prompt=prompt):
        resp = await resources.llm.chat.completions.create(
            name=prompt.name,
            model=prompt.config['model'],
            messages=compiled_prompt,
            temperature=0,
            response_format={'type': 'json_object'},
            reasoning_effort='none',
            metadata={'vacancy_id': vacancy_id, 'category': row['category']},
        )

    raw_resp = resp.choices[0].message.content
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

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, data)


async def process_lexicon_expanding() -> None:
    prompt = resources.get_prompt('lexicon-expand')
    limit = 10

    async with resources.engine.connect() as conn:
        rows = await db.select_skill_lexicon_for_expand(conn, limit=limit)

    if not rows:
        return

    compiled_prompt = prompt.compile(skill_names=rows[:limit])
    with propagate_attributes(prompt=prompt):
        resp = await resources.llm.chat.completions.create(
            name=prompt.name,
            model=prompt.config['model'],
            messages=compiled_prompt,
            temperature=0,
            response_format={'type': 'json_object'},
            reasoning_effort='none',
        )

    raw_resp = resp.choices[0].message.content
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
            await lexicon_embed.configure(schedule_in={'minutes': 1}).defer_async()
    else:
        with suppress(AlreadyEnqueued):
            await lexicon_embed.defer_async()


async def process_lexicon_embedding() -> None:
    model = resources.config['llm']['embedding_model']
    limit = 64

    async with resources.engine.connect() as conn:
        rows = await db.select_skill_lexicon_for_embed(conn, limit=limit)

    if not rows:
        return

    batch = rows[:limit]
    resp = await resources.llm.embeddings.create(
        name='lexicon-embed',
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
