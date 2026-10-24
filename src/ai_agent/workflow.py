import json
from typing import Literal, NotRequired

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt
from pydantic import BaseModel, Field

import src.db as db
import src.queries as queries
from src.ai_agent import db as agent_db
from src.ai_agent import prompts
from src.enums import ChatActionType, ProfileStatus
from src.shared.resources import resources
from src.shared.utils import enum_name
from src.types import AgentHybridSearch, DataDict


class State(MessagesState):
    action_info: NotRequired[DataDict]
    decision: NotRequired[str]


class ProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=5, max_length=100)
    is_selected: bool | None = None


class ApprovalAnswer(BaseModel):
    answer: Literal['approve', 'reject', 'revise']


@tool
def get_feature_instructions(
    feature: Literal['profiles', 'vacancy_search'],
) -> str:
    """
    Load the operating prompt for one product feature and follow it.

    Call this only when need an additional context to make answer or decision.
    profiles: general description, how to list, read, and propose a profile update.
    vacancy_search: general description, how to fill args and how to read its rows.
    """
    match feature:
        case 'profiles':
            return resources.get_prompt('profiles-sys-prompt').prompt
        case 'vacancy_search':
            return resources.get_prompt('vacancy-search-sys-prompt').prompt
        case _:
            return 'Unknown feature'


@tool
async def get_profile(profile_id: str) -> DataDict:
    """Get detailed profile information including skills and experience."""
    profile = await queries.get_profile(profile_id)
    if not profile:
        return {'error': 'profile_not_found'}

    profile['english_level'] = enum_name(profile['english_level'])

    return profile


@tool
async def list_profiles() -> DataDict:
    """List available profiles with their IDs and names."""
    return await queries.get_all_profiles()


@tool
async def prepare_update_profile(profile_id: str, patch: ProfilePatch) -> DataDict:
    """
    Prepare a profile update without changing the database.
    It validates the profile state and input parameters.
    profile_id must be a UUID returned by list_profiles.
    """
    async with resources.engine.connect() as conn:
        profile = await db.select_profile_status(conn, profile_id)

    if not profile:
        return {'error': 'profile_not_found'}

    if profile['status'] != ProfileStatus.ready:
        return {'error': 'invalid_profile_status', 'status': profile['status'].name}

    changes = patch.model_dump(exclude_none=True)
    if not changes:
        return {'error': 'empty_patch'}

    return {
        'action_type': ChatActionType.update_profile.name,
        'item_id': profile_id,
        'patch': changes,
    }


@tool
async def search_vacancies(params: AgentHybridSearch) -> DataDict:
    """
    Search active vacancies by meaning, keywords and optional filters.
    Rows are ordered by relevance. An empty rows list means nothing matched.
    """
    resp = await queries.get_search_response(params)
    for row in resp['rows']:
        row['source'] = enum_name(row['source'])
        row['english_level'] = enum_name(row['english_level'])
        row['status'] = enum_name(row['status'])

    return resp


async def agent(state: MessagesState) -> DataDict:
    model = ChatOpenAI(
        model='gpt-6-luna',
        reasoning_effort='low',
        use_responses_api=True,
        async_client=resources.llm.chat.completions,
        root_async_client=resources.llm,
    ).bind_tools(tools)

    resp = await model.ainvoke([SystemMessage(prompts.MAIN_AGENT), *state['messages']])
    return {'messages': [resp]}


def route_after_tools(state: State) -> Literal['agent', 'capture_action']:
    last_msg = state['messages'][-1]
    if isinstance(last_msg, ToolMessage):
        if not isinstance(last_msg.content, str):
            return 'agent'

        try:
            payload = json.loads(last_msg.content)
        except json.JSONDecodeError:
            return 'agent'

        if payload.get('action_type') == 'update_profile':
            return 'capture_action'

    return 'agent'


async def capture_action(state: State, config: RunnableConfig) -> DataDict:
    last_msg = state['messages'][-1]
    assert isinstance(last_msg, ToolMessage)
    assert isinstance(last_msg.content, str)
    data = json.loads(last_msg.content)

    chat_id = config['configurable']['thread_id']

    async with resources.engine.begin() as conn:
        action_id = await agent_db.insert_chat_action(
            conn,
            data={
                'chat_id': chat_id,
                'action_type': ChatActionType[data['action_type']],
                'item_id': data['item_id'],
                'payload': data['patch'],
            },
        )

    return {
        'messages': [AIMessage('Are you sure you want to apply changes?')],
        'action_info': {'id': action_id},
    }


def human_approval(state: State) -> DataDict:
    last_msg = state['messages'][-1]
    user_resp = interrupt(last_msg.content)

    return {'messages': [HumanMessage(user_resp)]}


async def interpret_approval(state: State) -> DataDict:
    model = ChatOpenAI(
        model='gpt-6-luna',
        reasoning_effort='none',
        use_responses_api=True,
        async_client=resources.llm.chat.completions,
        root_async_client=resources.llm,
    ).with_structured_output(ApprovalAnswer)

    resp = await model.ainvoke([SystemMessage(prompts.INTERPRET), *state['messages']])
    return {'decision': resp.answer}


def route_approval_answer(
    state: State,
) -> Literal['apply_action', 'revise_action', 'cancel_action']:
    answer = state['decision']

    if answer == 'approve':
        return 'apply_action'
    if answer == 'revise':
        return 'revise_action'

    return 'cancel_action'


async def apply_action(state: State, config: RunnableConfig) -> DataDict:
    action_id = state['action_info']['id']
    chat_id = config['configurable']['thread_id']

    async with resources.engine.begin() as conn:
        row = await agent_db.select_chat_action(conn, action_id)
        assert row
        assert row['chat_id'] == chat_id

        await db.update_profile(conn, row['item_id'], data=row['payload'])

    return {
        'action_info': {
            'action_type': row['action_type'].name,
            'payload': json.dumps(row['payload'], ensure_ascii=False),
        },
        'decision': None,
    }


async def final_response(state: State) -> DataDict:
    model = ChatOpenAI(
        model='gpt-6-luna',
        reasoning_effort='none',
        use_responses_api=True,
        async_client=resources.llm.chat.completions,
        root_async_client=resources.llm,
    )
    messages = ChatPromptTemplate.from_messages(
        [('system', prompts.APPROVAL), MessagesPlaceholder('history')]
    )
    chain = messages | model

    response = await chain.ainvoke(
        {
            **state['action_info'],
            'history': state['messages'],
        }
    )
    return {'messages': [response], 'action_info': None}


tools = [
    get_feature_instructions,
    list_profiles,
    get_profile,
    prepare_update_profile,
    search_vacancies,
]

builder = StateGraph(State)
builder.add_node('agent', agent)
builder.add_node('tools', ToolNode(tools))
builder.add_node('capture_action', capture_action)
builder.add_node('human_approval', human_approval)
builder.add_node('interpret_approval', interpret_approval)
builder.add_node('apply_action', apply_action)
builder.add_node('final_response', final_response)

builder.add_edge(START, 'agent')

builder.add_conditional_edges('agent', tools_condition)
builder.add_conditional_edges(
    'tools',
    route_after_tools,
    {
        'agent': 'agent',
        'capture_action': 'capture_action',
    },
)

builder.add_edge('capture_action', 'human_approval')
builder.add_edge('human_approval', 'interpret_approval')
builder.add_conditional_edges(
    'interpret_approval',
    route_approval_answer,
    {
        'apply_action': 'apply_action',
        'cancel_action': 'agent',
        'revise_action': 'agent',
    },
)
builder.add_edge('apply_action', 'final_response')
builder.add_edge('final_response', END)
