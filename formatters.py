import pandas as pd

# Columns to display for each tool type (ordered by importance)
_DISPLAY_COLUMNS = {
    "search_molecules": [
        "molecule_chembl_id", "pref_name", "max_phase",
        "molecular_weight", "alogp", "ro5_violations",
    ],
    "get_molecule_by_id": [
        "molecule_chembl_id", "pref_name", "molecule_type", "max_phase",
        "molecular_weight", "alogp", "hba", "hbd", "psa", "ro5_violations",
        "canonical_smiles",
    ],
    "search_targets": [
        "target_chembl_id", "pref_name", "target_type", "organism", "accessions",
    ],
    "get_activities": [
        "molecule_chembl_id", "molecule_pref_name", "target_pref_name",
        "standard_type", "standard_value", "standard_units", "pchembl_value",
    ],
    "get_approved_drugs": [
        "molecule_chembl_id", "pref_name", "first_approval", "usan_stem",
    ],
    "similarity_search": [
        "molecule_chembl_id", "pref_name", "similarity", "molecular_weight",
    ],
    "substructure_search": [
        "molecule_chembl_id", "pref_name", "molecular_weight",
    ],
}

_COLUMN_LABELS = {
    "molecule_chembl_id": "ChEMBL ID",
    "target_chembl_id": "Target ID",
    "pref_name": "Name",
    "molecule_pref_name": "Molecule",
    "target_pref_name": "Target",
    "molecule_type": "Type",
    "max_phase": "Phase",
    "molecular_weight": "MW",
    "alogp": "ALogP",
    "hba": "HBA",
    "hbd": "HBD",
    "psa": "PSA",
    "ro5_violations": "RO5 Violations",
    "canonical_smiles": "SMILES",
    "target_type": "Target Type",
    "organism": "Organism",
    "accessions": "UniProt",
    "standard_type": "Type",
    "standard_value": "Value",
    "standard_units": "Units",
    "pchembl_value": "pChEMBL",
    "first_approval": "Approved",
    "usan_stem": "USAN Stem",
    "similarity": "Similarity",
    "max_phase_for_ind": "Max Phase",
    "indication": "Indication",
    "assay_chembl_id": "Assay ID",
    "assay_type": "Assay Type",
}


def results_to_dataframe(data, tool_name=None):
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    # Select display columns if we know the tool
    if tool_name and tool_name in _DISPLAY_COLUMNS:
        cols = [c for c in _DISPLAY_COLUMNS[tool_name] if c in df.columns]
        if cols:
            df = df[cols]

    # Rename columns to human-readable labels
    rename = {c: _COLUMN_LABELS.get(c, c) for c in df.columns}
    df = df.rename(columns=rename)

    return df


def dataframe_to_csv(df):
    return df.to_csv(index=False)
