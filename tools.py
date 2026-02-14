import json
import logging

import chembl_service

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
]

_DISPATCH = {
    "search_molecules": chembl_service.search_molecules,
    "get_molecule_by_id": chembl_service.get_molecule_by_id,
    "search_targets": chembl_service.search_targets,
    "get_activities": chembl_service.get_activities,
    "get_approved_drugs": chembl_service.get_approved_drugs,
    "similarity_search": chembl_service.similarity_search,
    "substructure_search": chembl_service.substructure_search,
}


def dispatch_tool(tool_name, arguments):
    func = _DISPATCH.get(tool_name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        result = func(**arguments)
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return json.dumps({"error": str(e)})
