import json
import logging

import chembl_service
import ot_service

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_molecules",
            "description": (
                "Search for molecules/compounds in ChEMBL by name, molecular properties, "
                "or clinical phase. Use this for questions about finding compounds, drugs by "
                "name, or filtering by properties like molecular weight or logP."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Molecule name to search (case-insensitive). E.g. 'aspirin', 'ibuprofen', 'erlotinib'",
                    },
                    "max_molecular_weight": {
                        "type": "number",
                        "description": "Maximum molecular weight in Daltons.",
                    },
                    "min_molecular_weight": {
                        "type": "number",
                        "description": "Minimum molecular weight in Daltons.",
                    },
                    "max_logp": {
                        "type": "number",
                        "description": "Maximum ALogP value for lipophilicity filtering.",
                    },
                    "max_phase": {
                        "type": "integer",
                        "description": "Clinical phase (0-4). 4 = approved drug.",
                    },
                    "ro5_violations": {
                        "type": "integer",
                        "description": "Number of Lipinski Rule-of-Five violations. 0 = fully compliant.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return. Default 20, max 100.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_molecule_by_id",
            "description": "Get detailed information about a single molecule by its ChEMBL ID (e.g. CHEMBL25 for aspirin).",
            "parameters": {
                "type": "object",
                "properties": {
                    "chembl_id": {
                        "type": "string",
                        "description": "ChEMBL ID, e.g. 'CHEMBL25'.",
                    }
                },
                "required": ["chembl_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_targets",
            "description": (
                "Search for protein targets in ChEMBL by name, gene name, organism, or type. "
                "Use this for questions about drug targets, receptors, enzymes, kinases, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Target name (case-insensitive contains). E.g. 'EGFR', 'kinase', 'serotonin receptor'",
                    },
                    "gene_name": {
                        "type": "string",
                        "description": "Gene name to search. E.g. 'EGFR', 'BRD4', 'ACE2'",
                    },
                    "organism": {
                        "type": "string",
                        "description": "Organism filter. E.g. 'Homo sapiens', 'Rattus norvegicus'",
                    },
                    "target_type": {
                        "type": "string",
                        "description": "Target type: 'SINGLE PROTEIN', 'PROTEIN COMPLEX', 'PROTEIN FAMILY', 'ORGANISM', 'CELL-LINE'",
                    },
                    "uniprot_id": {
                        "type": "string",
                        "description": "UniProt accession to filter by. E.g. 'P00533'. More precise than name search.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results. Default 20, max 100.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_activities",
            "description": (
                "Get bioactivity data (IC50, Ki, EC50, etc.) for a specific target or molecule. "
                "Use this when users ask about potency, binding affinity, what compounds bind a target, "
                "or bioactivity measurements. At least one of target_chembl_id or molecule_chembl_id is required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_chembl_id": {
                        "type": "string",
                        "description": "ChEMBL ID of the target, e.g. 'CHEMBL203' for EGFR.",
                    },
                    "molecule_chembl_id": {
                        "type": "string",
                        "description": "ChEMBL ID of the molecule, e.g. 'CHEMBL25' for aspirin.",
                    },
                    "target_uniprot_id": {
                        "type": "string",
                        "description": "UniProt accession of the target. Alternative to target_chembl_id for more precise queries.",
                    },
                    "standard_type": {
                        "type": "string",
                        "description": "Activity type: 'IC50', 'Ki', 'EC50', 'Kd', 'GI50'",
                    },
                    "pchembl_value_min": {
                        "type": "number",
                        "description": (
                            "Minimum pChEMBL value (-log10 molar). Higher = more potent. "
                            "5 = 10uM, 6 = 1uM, 7 = 100nM, 8 = 10nM."
                        ),
                    },
                    "assay_type": {
                        "type": "string",
                        "description": "Assay type: 'B' (binding), 'F' (functional), 'A' (ADMET), 'T' (toxicity)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results. Default 20, max 100.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_approved_drugs",
            "description": (
                "Get approved drugs from ChEMBL, optionally filtered by USAN stem, approval year, "
                "or disease indication. Use this for questions about approved medications."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "usan_stem": {
                        "type": "string",
                        "description": (
                            "USAN stem filter. E.g. '-mab' (monoclonal antibodies), '-nib' (kinase inhibitors), "
                            "'-pril' (ACE inhibitors), '-statin' (HMG-CoA reductase inhibitors)"
                        ),
                    },
                    "min_approval_year": {
                        "type": "integer",
                        "description": "Minimum first approval year, e.g. 2020.",
                    },
                    "max_approval_year": {
                        "type": "integer",
                        "description": "Maximum first approval year.",
                    },
                    "indication": {
                        "type": "string",
                        "description": "Disease indication (case-insensitive). E.g. 'lung cancer', 'diabetes'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results. Default 20, max 100.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "similarity_search",
            "description": (
                "Find molecules similar to a given molecule using Tanimoto similarity. "
                "Provide either a SMILES string or a ChEMBL ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "smiles": {
                        "type": "string",
                        "description": "SMILES of the query molecule. E.g. 'CC(=O)Oc1ccccc1C(=O)O' (aspirin)",
                    },
                    "chembl_id": {
                        "type": "string",
                        "description": "ChEMBL ID of the query molecule. E.g. 'CHEMBL25'",
                    },
                    "similarity_threshold": {
                        "type": "integer",
                        "description": "Tanimoto similarity cutoff 0-100. Default 70. Higher = more similar.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results. Default 20, max 100.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "substructure_search",
            "description": (
                "Find molecules containing a specific substructure. "
                "Provide either a SMILES string or a ChEMBL ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "smiles": {
                        "type": "string",
                        "description": "SMILES of the substructure. E.g. 'c1ccncc1' (pyridine ring)",
                    },
                    "chembl_id": {
                        "type": "string",
                        "description": "ChEMBL ID of the molecule whose structure to use.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results. Default 20, max 100.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_molecules_by_ids",
            "description": (
                "Batch fetch molecule details (structure, MW, logP, max_phase) for a list of "
                "ChEMBL IDs. Use this after get_activities to enrich activity results with "
                "molecular properties. Results stored as 'get_molecules_by_ids'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chembl_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ChEMBL IDs, e.g. ['CHEMBL25', 'CHEMBL941']",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results. Default = length of ids list, max 100.",
                    },
                },
                "required": ["chembl_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "join_tables",
            "description": (
                "Join two stored tables on a shared column key. Use after fetching data from "
                "multiple tools to combine results into one table. "
                "Tables are referenced by their tool name (e.g. 'get_activities', 'get_molecules_by_ids'). "
                "Result is stored under 'joined'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "left": {
                        "type": "string",
                        "description": "Name of the left table in the store (e.g. 'get_activities').",
                    },
                    "right": {
                        "type": "string",
                        "description": "Name of the right table in the store (e.g. 'get_molecules_by_ids').",
                    },
                    "on": {
                        "type": "string",
                        "description": "Column name shared by both tables to join on (e.g. 'molecule_chembl_id').",
                    },
                    "how": {
                        "type": "string",
                        "description": "Join type: 'inner' (default), 'left', 'outer'.",
                    },
                },
                "required": ["left", "right", "on"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "filter_table",
            "description": (
                "Filter rows in a stored table by a column condition. "
                "Result replaces the table under the same name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Name of the table to filter (e.g. 'get_activities', 'joined').",
                    },
                    "column": {
                        "type": "string",
                        "description": "Column to filter on.",
                    },
                    "operator": {
                        "type": "string",
                        "description": "One of: 'eq', 'gt', 'gte', 'lt', 'lte', 'contains'.",
                    },
                    "value": {
                        "description": "Value to compare against.",
                    },
                },
                "required": ["table", "column", "operator", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sort_table",
            "description": (
                "Sort a stored table by a column. "
                "Result replaces the table under the same name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Name of the table to sort.",
                    },
                    "column": {
                        "type": "string",
                        "description": "Column to sort by (e.g. 'pchembl_value', 'molecular_weight').",
                    },
                    "ascending": {
                        "type": "boolean",
                        "description": "True for ascending (default), False for descending.",
                    },
                },
                "required": ["table", "column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_target",
            "description": (
                "Resolve ANY target identifier (gene symbol, protein name, UniProt ID, "
                "ChEMBL ID, or casual name like 'p38 alpha') to a standardized record with "
                "gene symbol, Ensembl ID, UniProt ID, and ChEMBL target IDs. "
                "ALWAYS call this first when a user mentions a target before using other tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Target identifier to resolve. Can be a gene symbol (EGFR, BRAF), "
                            "casual name (p38 alpha), UniProt accession (P00533), or "
                            "ChEMBL ID (CHEMBL203)."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_drugs_for_target",
            "description": (
                "Get drugs that target a specific protein, including mechanism of action, "
                "clinical phase, and disease indications. Requires an Ensembl gene ID "
                "(from resolve_target). Uses OpenTargets data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ensembl_id": {
                        "type": "string",
                        "description": "Ensembl gene ID, e.g. 'ENSG00000146648'. Get this from resolve_target.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results. Default 20, max 100.",
                    },
                },
                "required": ["ensembl_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_disease_associations",
            "description": (
                "Get diseases associated with a target protein, ranked by association score. "
                "Requires an Ensembl gene ID (from resolve_target). Uses OpenTargets data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ensembl_id": {
                        "type": "string",
                        "description": "Ensembl gene ID, e.g. 'ENSG00000146648'. Get this from resolve_target.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results. Default 20, max 100.",
                    },
                },
                "required": ["ensembl_id"],
            },
        },
    },
]

_DISPATCH = {
    "search_molecules": chembl_service.search_molecules,
    "get_molecule_by_id": chembl_service.get_molecule_by_id,
    "search_targets": chembl_service.search_targets,
    "get_activities": chembl_service.get_activities,
    "get_approved_drugs": chembl_service.get_approved_drugs,
    "similarity_search": chembl_service.similarity_search,
    "substructure_search": chembl_service.substructure_search,
    "get_molecules_by_ids": chembl_service.get_molecules_by_ids,
    "resolve_target": ot_service.resolve_target,
    "get_drugs_for_target": ot_service.get_drugs_for_target,
    "get_disease_associations": ot_service.get_disease_associations,
}

# Tools that operate on the data store rather than external APIs
_STORE_OPS = {"join_tables", "filter_table", "sort_table"}


def dispatch_tool(tool_name, arguments, data_store=None):
    if tool_name in _STORE_OPS:
        if data_store is None:
            return json.dumps({"error": "No data store available for table operations."})
        try:
            if tool_name == "join_tables":
                result = data_store.join(
                    arguments["left"],
                    arguments["right"],
                    arguments["on"],
                    arguments.get("how", "inner"),
                )
                data_store.store("joined", result)
            elif tool_name == "filter_table":
                result = data_store.filter(
                    arguments["table"],
                    arguments["column"],
                    arguments["operator"],
                    arguments["value"],
                )
                data_store.store(arguments["table"], result)
            elif tool_name == "sort_table":
                result = data_store.sort(
                    arguments["table"],
                    arguments["column"],
                    arguments.get("ascending", True),
                )
                data_store.store(arguments["table"], result)
            return json.dumps({"status": "ok", "rows": len(result)}, default=str)
        except Exception as e:
            logger.error(f"Store op {tool_name} failed: {e}")
            return json.dumps({"error": str(e)})

    func = _DISPATCH.get(tool_name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        result = func(**arguments)
        if data_store is not None and isinstance(result, list):
            data_store.store(tool_name, result)
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return json.dumps({"error": str(e)})
