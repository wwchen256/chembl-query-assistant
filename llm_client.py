import json
import logging

from openai import OpenAI

from config import (
    OPENROUTER_BASE_URL,
    MAX_TOOL_ITERATIONS,
    SYSTEM_PROMPT,
)
from tools import TOOL_DEFINITIONS, dispatch_tool

logger = logging.getLogger(__name__)


class ChEMBLAssistant:
    def __init__(self, api_key, model):
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
        )
        self.model = model

    def process_message(self, messages):
        """Run the tool-use conversation loop.

        Args:
            messages: list of {"role": ..., "content": ...} dicts (the chat history).

        Returns:
            (response_text, raw_data, tool_name) where raw_data is the parsed
            list of dicts from the last tool call (or None if no tools were used).
        """
        api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        last_tool_result = None
        last_tool_name = None

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
                return message.content or "", last_tool_result, last_tool_name

            # Append the assistant message with tool calls
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

            # Execute each tool call and collect results
            for tc in message.tool_calls:
                tool_name = tc.function.name
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                logger.info(f"Calling tool {tool_name} with {arguments}")
                result_json = dispatch_tool(tool_name, arguments)

                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_json,
                })

                # Track the last tool result for display
                try:
                    parsed = json.loads(result_json)
                    if isinstance(parsed, list):
                        last_tool_result = parsed
                        last_tool_name = tool_name
                except (json.JSONDecodeError, TypeError):
                    pass

        # If we exhausted iterations, make one final call without tools
        logger.warning("Max tool iterations reached, requesting final response")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
        )
        return response.choices[0].message.content or "", last_tool_result, last_tool_name
