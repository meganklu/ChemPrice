import requests
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import utils


class PriceCollector:
    """
    A class for collecting and checking API credentials, as well as data collection and filtering.
    """
    
    instances = []
    
    def __init__(self):
        self.login = {
            'molport_api_key': None,
            'chemspace_api_key': None,
            'mcule_api_key': None,
        }
        self.add_to_the_dictionnary(self)

        self.molport_api_key_valid = False
        self.chemspace_api_key_valid = False
        self.mcule_api_key_valid = False

#------------------------------------------------------


    def add_to_the_dictionnary(self, instance):
        PriceCollector.instances.append(instance)


#------------------------------------------------------


    def setMolportApiKey(self, api_key):
        """
        Sets the Molport api key.

        :param api_key: The Molport api key to set.
        """
        self.login['molport_api_key'] = api_key


#------------------------------------------------------


    def setChemSpaceApiKey(self, api_key):
        """
        Sets the ChemSpace api key.

        :param api_key: The ChemSpace api key to set.
        """
        self.login['chemspace_api_key'] = api_key


#------------------------------------------------------


    def setMCuleApiKey(self, api_key):
        """
        Sets the MCule api key.

        :param api_key: The MCule api key to set.
        """
        self.login['mcule_api_key'] = api_key


#------------------------------------------------------

    def status(self):
        """
        Displays the set status of various API keys.
        """
        # Display the set status of various API keys
        if self.login['molport_api_key']:
            print("Status: Molport : creditential is set.")
        else:
            print("Status: Molport : no credential is set.")

        if self.login['chemspace_api_key']:
            print("Status: Chemspace : creditential is set.")
        else:
            print("Status: Chemspace : no credential is set.")
            
        if self.login['mcule_api_key']:
            print("Status: MCule : creditential is set.")
        else:
            print("Status: MCule : no credential is set.")
        print("")


#------------------------------------------------------


    def check(self, Molport=True, ChemSpace=True, MCule=True):
        """
        Checks the validity of API credentials.

        :param Molport: Whether to check Molport credentials.
        :param ChemSpace: Whether to check ChemSpace credentials.
        :param MCule: Whether to check MCule credentials.
        :return: A value indicating whether the checks were successful.
        """
        smiles = "CC(=O)NC1=CC=C(C=C1)O"
        value_return = 1
        integrator_correct = 0
        
        if Molport:
            if self.login['molport_api_key']:
                # Lightweight credential check via availability-searches (no pricing needed here)
                headers = {"X-API-Key": self.login['molport_api_key']}
                payload = {
                    "search_items_type": "smiles",
                    "search_items": [smiles],
                    "match_types": ["exact"],
                }
                r = requests.post('https://api.molport.com/v1/availability-searches', json=payload, headers=headers)
                if r.status_code in (200, 201):
                    self.molport_api_key_valid = True
                    print("Check: Molport api key is correct.")
                    integrator_correct = 1
                else:
                    print("Check: Molport api key is incorrect.")
                    value_return = 0


        if ChemSpace:
            if self.login['chemspace_api_key']:    
                # Requires api_key
                url = "https://api.chem-space.com/auth/token"
                headers = {
                    "Authorization": f"Bearer {self.login['chemspace_api_key']}"
                }
                response = requests.get(url, headers=headers)
                # Check if the request was successful (status code 200)
                if response.status_code == 200:
                    self.chemspace_api_key_valid = True
                    print("Check: Chemspace api key is correct.")
                    integrator_correct= 1
                else:
                    print("Check: Chemspace api key is incorrect.")
                    value_return = 0


        if MCule:
            if self.login['mcule_api_key']:   
                headers = {
                    'Authorization': 'Token ' + self.login['mcule_api_key'],
                }
                data = {
                    'queries': [smiles]
                }
                # Send a POST request to MCule API for exact search
                response = requests.post('https://mcule.com/api/v1/search/exact/', headers=headers, json=data)
                if response.status_code == 200:
                    self.mcule_api_key_valid = True
                    print("Check: MCule api key is correct.")
                    integrator_correct = 1
                else:
                    print("Check: MCule api key is incorrect.")
                    value_return = 0
        print("")
        
        if integrator_correct:
            return value_return
        return 0


#------------------------------------------------------


    def collect(self, smiles_list, progress_output=None, molport_amount=1, molport_measure="g",
                molport_shipping_country="US", molport_shipping_method="consolidated",
                molport_match_types=None, molport_selection_method="lowest price"):
        """
        Collects data using API credentials.

        :param smiles_list: List of SMILES representations.
        :param progress_output: Progress output (optional).
        :param molport_amount: Desired quantity per compound for Molport's quote (default 1).
        :param molport_measure: Unit for molport_amount, "mg" or "g" (default "g").
        :param molport_shipping_country: Destination country code for Molport's quote (default "US").
        :param molport_shipping_method: "consolidated" or "direct" (default "consolidated").
        :param molport_match_types: List of Molport match types, e.g. ["exact"] (default).
        :param molport_selection_method: How Molport selects among matching offers
            ("lowest price", "minimum count of shipments", or "best offer"; default "lowest price").
        :return: A DataFrame containing collected data.
        """
        # Determine if Chemspace and/or Molport APIs are valid
        Chemspace = self.chemspace_api_key_valid
        Molport = self.molport_api_key_valid
        MCule = self.mcule_api_key_valid
        # Call collect_vendors function with the determined API statuses
        df = utils.collect_vendors(self, smiles_list, progress_output, Chemspace, Molport, MCule,
                                    molport_amount, molport_measure, molport_shipping_country,
                                    molport_shipping_method, molport_match_types, molport_selection_method)

        return df


#------------------------------------------------------


    def selectBest(self, dataframe):
        """
        Filters and selects the best data from a DataFrame.

        :param dataframe: The input DataFrame.
        :return: The filtered DataFrame.
        """
        if dataframe.empty:
            return dataframe
        
        # Add standardized columns to the dataframe
        dataframe = utils.add_standardized_columns(dataframe)

        # Filter the dataframe by minimum price
        df = utils.filter_csv_by_min_price(dataframe)

        return df
