import unittest
import pandas as pd
import os
import sys

# Add path
sys.path.insert(0, os.path.abspath('..'))
from chemprice import utils
from chemprice import chemprice as cp

MOLPORT_API_KEY = os.environ.get('MOLPORT_API_KEY')
MCULE_API_KEY = os.environ.get('MCULE_API_KEY')

# Création d'instances
instance = cp.PriceCollector()
instance.login['molport_api_key'] = MOLPORT_API_KEY
instance.login['mcule_api_key'] = MCULE_API_KEY




class TestMolportCollectPrices(unittest.TestCase):




    def test_empty_smiles_list(self):
        """
        Test with no smiles
        """
        # Input data
        smiles_list = []

        # Function application
        result = utils.molport_collect_prices(instance, smiles_list)

        # Check the result
        self.assertTrue(result.empty)




    @unittest.skipUnless(MOLPORT_API_KEY, "MOLPORT_API_KEY is not set")
    def test_imaginary_smiles(self):
        """
        Test with imaginary SMILES is recognized
        """
        # Input data
        smiles_list = ["SMILOU"]

        # Function application
        result = utils.molport_collect_prices(instance, smiles_list)

        # Check the result
        self.assertTrue(result.empty)




    @unittest.skipUnless(MOLPORT_API_KEY, "MOLPORT_API_KEY is not set")
    def test_single_smiles(self):
        """
        Test with a single SMILES
        """
        # Input data
        smiles_list = ["O=C(C)Oc1ccccc1C(=O)O"] # aspirin

        # Function application
        result = utils.molport_collect_prices(instance, smiles_list)

        # Check the result
        self.assertFalse(result.empty)
        self.assertListEqual(list(result.columns),
            ["Source", "Input SMILES", "SMILES", "Supplier Name", "Purity", "Amount", "Measure", "Price_USD"])
        self.assertTrue((result['Input SMILES'] == smiles_list[0]).all())




    @unittest.skipUnless(MOLPORT_API_KEY, "MOLPORT_API_KEY is not set")
    def test_multiple_smiles(self):
        """
        Test with multiple SMILES
        """
        # Input data
        smiles_list = ["CC(=O)NC1=CC=C(C=C1)O", "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O", "O=C(C)Oc1ccccc1C(=O)O"]

        # Function application
        result = utils.molport_collect_prices(instance, smiles_list)

        # Check the result
        self.assertFalse(result.empty)
        self.assertTrue(set(result['Input SMILES'].unique()).issubset(set(smiles_list)))




class TestMculeCollectPrices(unittest.TestCase):




    def test_empty_ids(self):
        """
        Test with no molecule IDs
        """
        # Input data
        molecule_ids = pd.DataFrame({'ID': [], 'Input SMILES': []})

        # Function application
        result = utils.mcule_collect_prices(instance, molecule_ids)

        # Check the result
        self.assertTrue(result.empty)




    @unittest.skipUnless(MCULE_API_KEY, "MCULE_API_KEY is not set")
    def test_single_smiles(self):
        """
        Test with a single SMILES
        """
        # Input data
        smiles_list = ["O=C(C)Oc1ccccc1C(=O)O"] # aspirin

        # Function application
        molecule_ids = utils.mcule_get_ids(instance, smiles_list)
        result = utils.mcule_collect_prices(instance, molecule_ids)

        # Check the result
        self.assertFalse(result.empty)
        self.assertListEqual(list(result.columns),
            ["Source", "ID", "Supplier Name", "SMILES", "Purity", "Price_USD", "Amount", "Measure"])
        self.assertTrue((result['Source'] == 'MCule').all())
        self.assertTrue((result['ID'] == molecule_ids['ID'].iloc[0]).all())




    @unittest.skipUnless(MCULE_API_KEY, "MCULE_API_KEY is not set")
    def test_multiple_smiles(self):
        """
        Test with multiple SMILES
        """
        # Input data
        smiles_list = ["CC(=O)NC1=CC=C(C=C1)O", "O=C(C)Oc1ccccc1C(=O)O"]

        # Function application
        molecule_ids = utils.mcule_get_ids(instance, smiles_list)
        result = utils.mcule_collect_prices(instance, molecule_ids)

        # Check the result
        self.assertFalse(result.empty)
        self.assertTrue(set(result['ID'].unique()).issubset(set(molecule_ids['ID'].unique())))




class TestCollectVendors(unittest.TestCase):




    def test_empty_smiles_list(self):
        """
        Test with no smiles
        """
        smiles_list = []

        data_result = utils.collect_vendors(instance, smiles_list, Molport=True, ChemSpace=False, MCule=False)

        # Assert that the parsed data is an empty list
        self.assertTrue(data_result.empty)




    @unittest.skipUnless(MOLPORT_API_KEY, "MOLPORT_API_KEY is not set")
    def test_wrong_smiles_list(self):
        """
        Test with a wrong smiles
        """
        smiles_list = ["wrong"]

        data_result = utils.collect_vendors(instance, smiles_list, Molport=True, ChemSpace=False, MCule=False)

        # Assert that the parsed data is an empty list
        self.assertTrue(data_result.empty)




if __name__ == '__main__':
    unittest.main()
