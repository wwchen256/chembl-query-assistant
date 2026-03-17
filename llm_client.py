import json
import logging
import re

from openai import OpenAI

from config import (
    OPENROUTER_BASE_URL,
    MAX_TOOL_ITERATIONS,
    SYSTEM_PROMPT,
)
from data_store import DataStore
from tools import TOOL_DEFINITIONS, dispatch_tool

_CHEMBL_ID_RE = re.compile(r'\bCHEMBL\d+\b', re.IGNORECASE)

logger = logging.getLogger(__name__)


class ChEMBLAssistant:
    def __init__(self, api_key, model):
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
        )
        self.model = model

    def process_message(self, messages, data_store=None):
        """Run the tool-use conversation loop.

        Args:
            messages: list of {"role": ..., "content": ...} dicts (the chat history).
            data_store: DataStore instance for persisting and joining tool results.

        Returns:
            (response_text, new_tables) where new_tables is a dict of
            {table_name: [records]} for all tables created/updated in this call.
        """
        if data_store is None:
            data_store = DataStore()

        api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        snapshot_before = data_store.snapshot()

        # Pre-fetch any ChEMBL IDs in the last user message so structure images always
        # appear in the UI, even if the LLM answers from training knowledge.
        last_user_content = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            ""
        )
        for cid in _CHEMBL_ID_RE.findall(last_user_content)[:5]:
            dispatch_tool("get_molecule_by_id", {"chembl_id": cid.upper()}, data_store)

        for iteration in range(MAX_TOOL_ITERATIONS):
            logger.info(f"LLM call iteration {iteration + 1}, model={self.model}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )

            choice = response.choices[0]
            message = choice.message

            if not message.tool_calls:
                new_tables = data_store.diff_since(snapshot_before)
                return message.content or "", new_tables

            api_messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            })

            for tc in message.tool_calls:
                tool_name = tc.function.name
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                logger.info(f"Calling tool {tool_name} with {arguments}")
                result_json = dispatch_tool(tool_name, arguments, data_store)

                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_json,
                })

        logger.warning("Max tool iterations reached, requesting final response")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
        )
        new_tables = data_store.diff_since(snapshot_before)
        return response.choices[0].message.content or "", new_tables
