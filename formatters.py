import base64
import io

import pandas as pd

_RDKIT_AVAILABLE = False
_RDKIT_ERROR = None
try:
    from rdkit import Chem
    from rdkit.Chem import Draw
    _RDKIT_AVAILABLE = True
except Exception as e:
    _RDKIT_ERROR = str(e)


def smiles_to_image_uri(smiles, size=(400, 300)):
    """Convert a SMILES string to a base64 PNG data URI. Returns None on failure."""
    if not _RDKIT_AVAILABLE or not smiles or smiles == "N/A":
        return None
    try:
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            return None
        img = Draw.MolToImage(mol, size=size)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


_CHEMBL_IMAGE_URL = "https://www.ebi.ac.uk/chembl/api/data/image/{}"


def add_structure_column(df, size=(400, 300)):
    """Insert a 'Structure' column of image data URIs.

    Only adds structures when a 'SMILES' column is present (i.e. molecular data
    tables). Tables like get_activities have no SMILES and get no structure column.

    Priority:
    1. RDKit rendering from 'SMILES' column (best quality, white background)
    2. ChEMBL image API URL from 'ChEMBL ID' column (fallback for invalid SMILES)
    """
    if "SMILES" not in df.columns:
        return df
    df = df.copy()
    if _RDKIT_AVAILABLE:
        df.insert(0, "Structure", df["SMILES"].apply(lambda s: smiles_to_image_uri(s, size=size)))
    else:
        df.insert(0, "Structure", None)
    # Fill any None entries with ChEMBL image API URL (covers rdkit failures and
    # the rdkit-unavailable case when a ChEMBL ID is available)
    if "ChEMBL ID" in df.columns:
        mask = df["Structure"].isna()
        if mask.any():
            df.loc[mask, "Structure"] = df.loc[mask, "ChEMBL ID"].apply(
                lambda cid: _CHEMBL_IMAGE_URL.format(cid) if cid and cid != "N/A" else None
            )
    return df

# Columns to display for each tool type (ordered by importance)
_DISPLAY_COLUMNS = {
    "search_molecules": [
        "molecule_chembl_id", "pref_name", "max_phase",
        "molecular_weight", "alogp", "ro5_violations", "canonical_smiles",
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
    "resolve_target": [
        "gene_symbol", "approved_name", "ensembl_id", "uniprot_id",
        "chembl_target_ids", "common_names",
    ],
    "get_drugs_for_target": [
        "drug_chembl_id", "drug_name", "drug_type",
        "mechanism_of_action", "phase", "status", "disease",
    ],
    "get_disease_associations": [
        "disease_id", "disease_name", "association_score",
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
    "gene_symbol": "Gene Symbol",
    "approved_name": "Approved Name",
    "ensembl_id": "Ensembl ID",
    "uniprot_id": "UniProt ID",
    "chembl_target_ids": "ChEMBL Target IDs",
    "common_names": "Aliases",
    "drug_chembl_id": "Drug ChEMBL ID",
    "drug_name": "Drug Name",
    "drug_type": "Drug Type",
    "mechanism_of_action": "Mechanism",
    "phase": "Phase",
    "status": "Status",
    "disease": "Disease",
    "disease_id": "Disease ID",
    "disease_name": "Disease",
    "association_score": "Score",
    "source": "Source",
    "query": "Query",
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
