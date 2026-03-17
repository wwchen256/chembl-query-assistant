# tests/test_chembl_service.py
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'chembl_app'))

def test_get_molecules_by_ids_returns_fields():
    mock_mol = {
        "molecule_chembl_id": "CHEMBL25",
        "pref_name": "ASPIRIN",
        "molecule_type": "Small molecule",
        "max_phase": 4,
        "molecule_properties": {"mw_freebase": "180.16", "alogp": "1.31", "hba": "3", "hbd": "1", "psa": "63.60", "num_ro5_violations": "0"},
        "molecule_structures": {"canonical_smiles": "CC(=O)Oc1ccccc1C(=O)O"},
    }
    with patch("chembl_service.new_client") as mock_client:
        mock_client.molecule.filter.return_value = [mock_mol]
        from chembl_service import get_molecules_by_ids
        results = get_molecules_by_ids(["CHEMBL25"])
    assert len(results) == 1
    assert results[0]["molecule_chembl_id"] == "CHEMBL25"
    assert results[0]["canonical_smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
    assert results[0]["max_phase"] == 4

def test_get_molecules_by_ids_empty_list():
    from chembl_service import get_molecules_by_ids
    results = get_molecules_by_ids([])
    assert results == []
