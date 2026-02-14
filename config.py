import os

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

DEFAULT_MODEL = "qwen/qwen3-coder-next"

AVAILABLE_MODELS = {
    "Qwen3 Coder Next": "qwen/qwen3-coder-next",
    "Gemini 2.5 Flash": "google/gemini-2.5-flash",
    "Gemini 2.5 Pro": "google/gemini-2.5-pro",
    "Claude Sonnet 4": "anthropic/claude-sonnet-4",
    "GPT-4o Mini": "openai/gpt-4o-mini",
    "DeepSeek V3": "deepseek/deepseek-chat",
}

CHEMBL_TIMEOUT = 30
MAX_RESULTS = 100
DEFAULT_RESULTS_LIMIT = 20
MAX_TOOL_ITERATIONS = 3

SYSTEM_PROMPT = """You are a helpful ChEMBL database assistant. You help scientists and researchers \
query the ChEMBL database for information about molecules, drug targets, bioactivity data, \
approved drugs, and chemical similarity/substructure searches.

When users ask questions that can be answered with ChEMBL data, use the available tools to \
query the database. When users ask conversational questions, general chemistry questions, \
or need clarification, respond directly without using tools.

After receiving tool results, summarize the findings in a clear, scientifically accurate way. \
Mention key data points, highlight notable results, and offer to provide more details or \
refine the search.

Always mention the ChEMBL IDs of molecules and targets so users can look them up.

If a query returns no results, suggest alternative search strategies (different spelling, \
broader filters, trying a different tool)."""
