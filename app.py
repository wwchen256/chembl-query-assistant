import streamlit as st

from config import AVAILABLE_MODELS, OPENROUTER_API_KEY
from data_store import DataStore
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
        st.session_state.data_store = DataStore()
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
- Find p38 inhibitors, show their structures and whether they're approved
"""
        )

# --- Initialize state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "data_store" not in st.session_state:
    st.session_state.data_store = DataStore()

# --- Display chat history ---
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for j, (tname, tdata) in enumerate(msg.get("tables", {}).items()):
            with st.expander(f"Table: {tname} ({len(tdata)} rows)"):
                df = results_to_dataframe(tdata, tname)
                st.dataframe(df, use_container_width=True)
                csv = dataframe_to_csv(df)
                st.download_button(
                    f"Download {tname}.csv",
                    csv,
                    file_name=f"{tname}_{i}.csv",
                    mime="text/csv",
                    key=f"dl_{i}_{j}",
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

                response_text, new_tables = assistant.process_message(
                    llm_messages,
                    data_store=st.session_state.data_store,
                )

                st.markdown(response_text)

                for j, (tname, tdata) in enumerate(new_tables.items()):
                    if tdata:
                        with st.expander(f"Table: {tname} ({len(tdata)} rows)"):
                            df = results_to_dataframe(tdata, tname)
                            st.dataframe(df, use_container_width=True)
                            csv = dataframe_to_csv(df)
                            st.download_button(
                                f"Download {tname}.csv",
                                csv,
                                file_name=f"{tname}.csv",
                                mime="text/csv",
                                key=f"dl_new_{j}",
                            )

                msg_data = {
                    "role": "assistant",
                    "content": response_text,
                    "tables": new_tables,
                }
                st.session_state.messages.append(msg_data)

            except Exception as e:
                error_msg = f"Error: {e}"
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg, "tables": {}}
                )
