import json
from typing import Literal, NotRequired

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt
from pydantic import BaseModel, Field

import src.db as db
import src.queries as queries
from src.ai_agent import prompts
from src.enums import ProfileStatus
from src.shared.resources import resources
from src.shared.utils import dt_now
from src.types import DataDict


class State(MessagesState):
    action_info: NotRequired[DataDict]
    decision: NotRequired[str]


class ProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=5, max_length=100)
    is_selected: bool | None = None


class ApprovalAnswer(BaseModel):
    answer: Literal['approve', 'reject', 'revise']


@tool
async def get_profile(profile_id: str) -> DataDict:
    """Get detailed profile information including skills and experience."""
    profile = await queries.get_profile(profile_id)
    return profile or {'error': 'Profile not found'}


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
        'action_type': 'update_profile',
        'item_id': profile_id,
        'patch': changes,
    }


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


def capture_action(state: State) -> DataDict:
    last_msg = state['messages'][-1]
    assert isinstance(last_msg, ToolMessage)
    assert isinstance(last_msg.content, str)

    payload = json.loads(last_msg.content)
    payload['date_created'] = dt_now()
    db_example.append(payload)

    return {
        'messages': [AIMessage('Are you sure you want to apply changes?')],
        'action_info': {
            'action_type': payload['action_type'],
            'item_id': payload['item_id'],
        },
    }


def human_approval(state: State) -> DataDict:
    last_msg = state['messages'][-1]
    user_resp = interrupt(last_msg.content)

    return {'messages': [HumanMessage(user_resp)]}


async def interpret_approval(state: State) -> DataDict:
    model = ChatOpenAI(
        model='gpt-5.4-nano',
        temperature=0,
        reasoning_effort='none',
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


async def apply_action(state: State) -> DataDict:
    profile_id = state['action_info']['item_id']
    aaa = db_example[-1]

    async with resources.engine.begin() as conn:
        await db.update_profile(conn, profile_id, data=aaa['patch'])

    return {'action_info': None, 'decision': None}


async def final_response(state: State) -> DataDict:
    model = ChatOpenAI(
        model='gpt-6-luna',
        reasoning_effort='none',
        use_responses_api=True,
        async_client=resources.llm.responses,
        root_async_client=resources.llm,
    )
    response = await model.ainvoke([SystemMessage(prompts.APPROVAL), *state['messages']])
    return {'messages': [response]}


db_example = []
tools = [list_profiles, get_profile, prepare_update_profile]

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
