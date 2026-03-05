import streamlit as st

from config import AVAILABLE_MODELS, OPENROUTER_API_KEY
from llm_client import ChEMBLAssistant
from formatters import results_to_dataframe, dataframe_to_csv

st.set_page_config(page_title="ChEMBL & OpenTargets Query Assistant", layout="wide")
st.title("ChEMBL & OpenTargets Query Assistant")

# --- Sidebar ---
with st.sidebar:
    if OPENROUTER_API_KEY:
        api_key = OPENROUTER_API_KEY
    else:
        api_key = st.text_input(
            "OpenRouter API Key",
            type="password",
            help="Set OPENROUTER_API_KEY in Streamlit secrets or env var.",
        )

    model_display = st.selectbox("Model", options=list(AVAILABLE_MODELS.keys()))
    model_id = AVAILABLE_MODELS[model_display]

    if st.button("Clear Conversation"):
        st.session_state.messages = []
        st.rerun()

    with st.expander("Example queries"):
        st.markdown(
            """
- Find approved kinase inhibitors
- What compounds bind EGFR with IC50 below 100nM?
- Show me molecules similar to aspirin
- Search for drugs approved after 2020
- Tell me about CHEMBL25
- What drugs target BRAF?
- What diseases are associated with TP53?
- Resolve the target p38 alpha
- Find targets related to serotonin in humans
"""
        )

# --- Initialize state ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Display chat history ---
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("data") is not None:
            df = results_to_dataframe(msg["data"], msg.get("tool_name"))
            st.dataframe(df, use_container_width=True)
            csv = dataframe_to_csv(df)
            st.download_button(
                "Download CSV",
                csv,
                file_name=f"chembl_results_{i}.csv",
                mime="text/csv",
                key=f"download_{i}",
            )

# --- Handle new input ---
if prompt := st.chat_input(
    "Ask about molecules, targets, drugs, disease associations...",
    disabled=not api_key,
):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Querying databases..."):
            try:
                assistant = ChEMBLAssistant(api_key=api_key, model=model_id)

                llm_messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ]

                response_text, raw_data, tool_name = assistant.process_message(
                    llm_messages
                )

                st.markdown(response_text)

                msg_data = {"role": "assistant", "content": response_text}

                if raw_data:
                    df = results_to_dataframe(raw_data, tool_name)
                    st.dataframe(df, use_container_width=True)
                    csv = dataframe_to_csv(df)
                    st.download_button(
                        "Download CSV",
                        csv,
                        file_name="chembl_results.csv",
                        mime="text/csv",
                        key=f"download_{len(st.session_state.messages)}",
                    )
                    msg_data["data"] = raw_data
                    msg_data["tool_name"] = tool_name

                st.session_state.messages.append(msg_data)

            except Exception as e:
                error_msg = f"Error: {e}"
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
