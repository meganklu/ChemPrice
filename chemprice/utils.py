import pandas as pd
import requests
import time
import re
from tqdm import tqdm


######################################################################
"------------------------------Molport-------------------------------"
######################################################################


# Collects prices for the given SMILES from Molport's v1 list-searches API
def molport_collect_prices(instance, smiles_list, amount=1, min_amount=None, measure="g", shipping_country="US",
                            shipping_method="consolidated", match_types=None, selection_method="lowest price",
                            poll_interval=2, poll_timeout=300):
    """
    Collects price data for molecules from Molport's v1 REST API (POST /v1/list-searches).

    Submits every SMILES in a single batched search; Molport itself selects offers
    according to selection_method across its full supplier network, so no supplier
    category is silently skipped the way the old "Screening Block Suppliers"-only
    integration was.

    :param instance: The PriceCollector instance containing API credentials.
    :param smiles_list: list containing molecule SMILES.
    :param min_amount: Minimum acceptable amount; defaults to ``amount`` (the API requires
        this field even though its own OpenAPI spec documents it as optional).
    :type instance: PriceCollector
    :type smiles_list: list
    :return: DataFrame containing collected price data.
    :rtype: pandas.DataFrame
    """
    columns = ["Source", "Input SMILES", "SMILES", "Supplier Name", "Purity", "Amount", "Measure", "Price_USD"]

    if not smiles_list:
        return pd.DataFrame([], columns=columns)

    if match_types is None:
        match_types = ["exact"]

    if min_amount is None:
        min_amount = amount

    headers = {"X-API-Key": instance.login['molport_api_key']}
    payload = {
        "search_items_type": "smiles",
        "search_items": smiles_list,
        "amount": amount,
        "min_amount": min_amount,
        "measure": measure,
        "shipping_country": shipping_country,
        "shipping_method": shipping_method,
        "match_types": match_types,
        "selection_method": selection_method,
    }

    response = requests.post('https://api.molport.com/v1/list-searches', json=payload, headers=headers)
    if response.status_code not in (200, 201):
        print(f'Error submitting Molport search: {response.status_code}')
        return pd.DataFrame([], columns=columns)

    search_key = response.json()["search_key"]

    status_url = f'https://api.molport.com/v1/list-searches/status/{search_key}'
    elapsed = 0
    while elapsed < poll_timeout:
        status = requests.get(status_url, headers=headers).json()
        if status.get("processing_completed_at"):
            break
        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        print(f'Molport search {search_key} timed out after {poll_timeout} seconds.')
        return pd.DataFrame([], columns=columns)

    results_response = requests.get(f'https://api.molport.com/v1/list-searches/{search_key}', headers=headers)
    # "results" is nested under "request" in the live response, despite the
    # published OpenAPI spec showing it as a top-level field.
    results = results_response.json().get("request", {}).get("results", [])

    # Unmatched SMILES come back as {"search_query": ..., "status": "not found"}
    # with no price fields at all, rather than being omitted from the array.
    molport_data = [
        ("Molport", item.get("search_query", ""), item.get("smiles", ""), item.get("supplier_name", ""),
         item.get("purity", ""), item.get("qty", ""), item.get("unit", ""), item.get("net_price", ""))
        for item in results if item.get("status") == "found"
    ]

    # Create a DataFrame with collected data
    df = pd.DataFrame(molport_data, columns=columns)

    #remove if no price rows
    df = df.dropna(subset=["Price_USD"], how='all')
    return df


######################################################################
"----------------------------ChemSpace-------------------------------"
######################################################################


# requires api_key
def chemspace_get_token(instance):

    chemspace_api_key = instance.login['chemspace_api_key']

    url = "https://api.chem-space.com/auth/token"
    headers = {
        "Authorization": f"Bearer {chemspace_api_key}"
    }

    response = requests.get(url, headers=headers)

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Retrieve the access token from the response
        access_token = response.json()["access_token"]

        return access_token
    else:
        # The request failed, print the status code and response content
        print("The request failed with the status code:", response.status_code)
        return None
    

######################################################################
######################################################################


# Collects prices for the given SMILES and coverts them into dataframe
def chemspace_collect_prices(instance, smiles_list):
    """
    Collects price data for molecules from ChemSpace API.

    :param instance: The PriceCollector instance containing API credentials.
    :param smiles_list: list containing molecule SMILES.
    :type instance: PriceCollector
    :type smiles_list: list
    :return: DataFrame containing collected price data.
    :rtype: pandas.DataFrame
    """

    access_token = chemspace_get_token(instance)
    url = "https://api.chem-space.com/v3/search/exact"
    headers = {
        "Accept": "application/json; version=3.1",
        "Authorization": "Bearer " + access_token,
    }
    params = {
        "count": 3,
        "page": 1,
        "categories": "CSCS,CSMB"
    }

    response_data = []

    for index, smiles in tqdm(enumerate(smiles_list),total=len(smiles_list)):
        data = {
            "SMILES": smiles
        }

        response = requests.post(url, headers=headers, data=data, params=params)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Process the response here
            molecule_data = response.json()

            # original smiles added
            for item in molecule_data['items']:
                item['input smiles'] = smiles

            response_data.append(molecule_data)
        else:
            # The request failed, print the status code and response content
            print("Request failed with status code:", response.status_code)
            print("Response content:", response.text)

        # Pause for 1.5 seconds between each request
        if index < len(smiles_list) - 1:
            time.sleep(1.5)

    chemspace_data = []
    
    # Iterate through the elements of the JSON file
    for data in response_data:
        for item in data['items']:
            for offer in item['offers']:
                for price in offer['prices']:
                    
                    source = "ChemSpace"
                    input_smiles = item['input smiles']
                    smiles = item["smiles"]
                    cas = item["cas"]
                    supplier_name = offer['vendorName']
                    purity = offer['purity']
                    amount = price['pack']
                    measure = price['uom']
                    price_usd = price['priceUsd']

                    chemspace_data.append((source, input_smiles, smiles, cas, supplier_name, purity, amount, measure, price_usd))
                    
    df = pd.DataFrame(chemspace_data, columns=["Source", "Input SMILES", "SMILES", "CAS", "Supplier Name", "Purity", "Amount", "Measure", "Price_USD"])
    df = df.dropna(subset=["Price_USD"], how='all')

    return df


######################################################################
"-------------------------------MCule--------------------------------"
######################################################################


# Function to collect MCule IDs with respect to limits
def mcule_get_ids(instance, smiles_list):
    
    mcule_token = instance.login['mcule_api_key']
    
    id_smiles_list = []

    headers = {
        'Authorization': 'Token ' + mcule_token,
    }

    # Iterate through smiles_list while respecting the limits
    for i in range(0, len(smiles_list), 500):  # Process 500 SMILES at a time
        batch_smiles = smiles_list[i:i+500]  # Extract a batch of SMILES

        data = {
            'queries': batch_smiles
        }

        # Send a POST request to MCule API for exact search
        response = requests.post('https://mcule.com/api/v1/search/exact/', headers=headers, json=data)

        if response.status_code == 200:
            results = response.json()["results"]

            # Extract MCule IDs and corresponding SMILES
            for result in results:
                molecule_id = result["mcule_id"]
                query = result["query"]
                id_smiles_list.append((molecule_id, query))

    # Create a DataFrame with collected data
    df = pd.DataFrame(id_smiles_list, columns=["ID", "Input SMILES"])
    return df



# Collects prices for the given MCule IDs from the Compound List Details API
def mcule_collect_prices(instance, molecule_ids_df, price_amounts=(1, 10, 100, 500, 1000)):
    """
    Collects price data for molecules from MCule's Compound List Details API
    (POST /api/v1/compounds/).

    price_amounts is technically optional at the API level, but omitting it
    means the response has no best_prices at all (just structural/property
    data) -- since this function's job is prices, it's always sent.

    Batches requests at 50 IDs each (the limit once price_amounts is requested)
    and self-throttles to stay under the endpoint's 5 requests/minute burst limit.
    Sustained usage is capped at 200 requests/day by MCule; this is not tracked
    across separate runs, so very large batches spread across many collect()
    calls in one day could still exceed it.

    :param instance: The PriceCollector instance containing API credentials.
    :param molecule_ids_df: DataFrame containing MCule IDs and SMILES (see mcule_get_ids).
    :param price_amounts: Amounts in mg to request prices for (max 5 values, each <= 1000).
    :type instance: PriceCollector
    :type molecule_ids_df: pandas.DataFrame
    :return: DataFrame containing collected price data.
    :rtype: pandas.DataFrame
    """
    columns = ["Source", "ID", "Supplier Name", "SMILES", "Purity", "Price_USD", "Amount", "Measure"]

    if molecule_ids_df.empty:
        return pd.DataFrame([], columns=columns)

    token = instance.login['mcule_api_key']
    headers = {
        'Authorization': 'Token ' + token,
        'Content-Type': 'application/json',
    }

    ids = molecule_ids_df["ID"].tolist()
    data = []
    request_times = []

    for i in tqdm(range(0, len(ids), 50)):
        batch = ids[i:i + 50]

        # Stay under the 5 requests/minute burst limit: drop timestamps
        # older than 60s, and if 5 remain, wait for the oldest to age out.
        now = time.time()
        request_times = [t for t in request_times if now - t < 60]
        if len(request_times) >= 5:
            time.sleep(60 - (now - request_times[0]))
        request_times.append(time.time())

        payload = {
            "mcule_ids": batch,
            "price_amounts": list(price_amounts),
        }
        response = requests.post('https://mcule.com/api/v1/compounds/', headers=headers, json=payload)

        if response.status_code != 200:
            print(f'Error in the request for MCule batch starting at {i}: {response.status_code}')
            continue

        for compound in response.json().get("results", []):
            mcule_id = compound.get("mcule_id")
            smiles = compound.get("smiles")
            for price in compound.get("best_prices", []):
                data.append(("MCule", mcule_id, "", smiles, price.get("purity", ""),
                             price.get("price", ""), price.get("amount", ""), price.get("unit", "")))

    df = pd.DataFrame(data, columns=columns)
    return df

# Merges two dataframes
def add_input_smiles_columns(df1, df2):

    # Common columns to use for merging
    common_columns = ['ID']

    # Convert columns to compatible data types
    df1 = df1.astype(str)
    df2 = df2.astype(str)

    # Merge the two dataframes using the common columns
    merged_df = pd.merge(df1, df2, on=common_columns, how='outer')

    # Sort dataframe
    merged_df = merged_df.sort_values(by=['Input SMILES'])
    merged_df.drop("ID", axis=1, inplace=True)
    merged_df = merged_df.dropna(subset=['SMILES'])
    merged_df = merged_df.drop_duplicates()

    return merged_df


######################################################################
"--------------------------Data operation----------------------------"
######################################################################


def merge_dataframes(df_list):
    # Common columns to use for merging
    common_columns = ['Source', 'Input SMILES', 'SMILES', 'Supplier Name', 'Purity', 'Amount', 'Measure', 'Price_USD']

    # Initialize an empty dataframe to store the merged results
    merged_df = pd.DataFrame(columns=common_columns)

    # Convert columns to compatible data types for all dataframes in the list
    for i in range(len(df_list)):
        df_list[i] = df_list[i].astype(str)

    # Merge all dataframes in the list using the common columns
    for df in df_list:
        merged_df = pd.merge(merged_df, df, on=common_columns, how='outer')

    # Sort dataframe
    merged_df = merged_df.sort_values(by=['Input SMILES'])

    # Save the merged dataframe to a new CSV file
    # merged_df.to_csv("merged_prices.csv", index=False)

    return merged_df


######################################################################
######################################################################


# Define conversion factors for different measures
conversion_factors = {
    # Conversion to g
    'kg': 1000,
    'g': 1,
    'mg': 1 / 1000,
    'microg': 1 / 1000000,
    'ug': 1 / 1000000,

    # Conversion to mol
    'kmol': 1000,
    'mol': 1,
    'mmol': 1 / 1000,
    'micromol': 1 / 1000000,
    'umol': 1 / 1000000,

    # Conversion to l
    'kl': 1000,
    'l': 1,
    'ml': 1 / 1000,
    'mL': 1 / 1000,
    'microl': 1 / 1000000,
    'ul': 1 / 1000000,
}


######################################################################
######################################################################


# parses the units like 5x100g
def extract_unit_bulk(unit_string):
    # Extract the numeric part and unit from the unit string
    parts = re.search(r'(\d+)x(\d+)(\D+)', unit_string)
    if parts:
        bulk = int(parts.group(1)) * int(parts.group(2))
        unit = parts.group(3).lower()
        return bulk, unit
    else:
        bulk = re.search(r'\d+', unit_string)
        if bulk:
            bulk = int(bulk.group())
        else:
            return None, None

        unit = re.search(r'[a-zA-Z]+', unit_string)
        if unit:
            unit = unit.group().lower()
        else:
            return None, None

#Convert all prices into USD/g or USD/mol or USD/l
def standardize_prices(row):
    measure = row['Measure']
    amount = float(row['Amount'])
    price = float(row['Price_USD'])

    if measure in conversion_factors:
        return price / (conversion_factors[measure] * amount)
    else:
        bulk, unit = extract_unit_bulk(measure)
        if amount and unit:
            if unit in conversion_factors:
                return price / (conversion_factors[unit] * (amount * bulk))
        print("Unknown measure units for:",measure)
        return None
    
def add_standardized_columns(df):

    if df.empty:
        # Empty dataframe, add empty columns and save
        df['USD/g'] = ''
        df['USD/mol'] = ''
        df['USD/l'] = ''
        return df

    df['Measure'] = df['Measure'].astype(str)

    # Apply the function to create new columns
    df['USD/g'] = df.apply(lambda row: standardize_prices(row) if row['Measure'] in ['g', 'mg', 'kg', 'microg', 'ug' ] or re.match(r'\d+x\d+g', row['Measure']) else None, axis=1)
    df['USD/mol'] = df.apply(lambda row: standardize_prices(row) if row['Measure'] in ['mol', 'micromol', 'mmol', 'kmol', 'umol'] else None, axis=1)
    df['USD/l'] = df.apply(lambda row: standardize_prices(row) if (row['Measure'] in ['ml', 'microl', 'l', 'mL', 'kl', 'ul']) or re.match(r'\d+x\d+mL', row['Measure']) else None, axis=1)

    # Sort and Save the dataframe with the additional columns to a new CSV file
    df = df.sort_values(by=['Input SMILES', 'USD/g', 'USD/mol', 'USD/l'])
    # df.to_csv("standardized_merged_prices.csv", index=False)
    return df


######################################################################
######################################################################


def filter_csv_by_min_price(df):

    # Remove rows where neither of the two values (USD/g and USD/mol) is present
    df = df.dropna(subset=["USD/g", "USD/mol", "USD/l"], how='all')

    # Filter the rows from the initial dataframe, keeping only those corresponding to the smallest value of "Price_USD"
    filtered_df_g = df[df.groupby("Input SMILES")["USD/g"].transform(min) == df["USD/g"]]
    filtered_df_mol = df[df.groupby("Input SMILES")["USD/mol"].transform(min) == df["USD/mol"]]
    filtered_df_l = df[df.groupby("Input SMILES")["USD/l"].transform(min) == df["USD/l"]]

    # If multiple rows have the same price, keep the first one
    filtered_df_g = filtered_df_g.sample(frac=1).groupby("Input SMILES", as_index=False).first()
    filtered_df_mol = filtered_df_mol.sample(frac=1).groupby("Input SMILES", as_index=False).first()
    filtered_df_l = filtered_df_l.sample(frac=1).groupby("Input SMILES", as_index=False).first()

    # Combine the results using concatenation
    filtered_df = pd.concat([filtered_df_g, filtered_df_mol, filtered_df_l])

    filtered_df = filtered_df.sort_values(by=['Input SMILES', 'USD/g', 'USD/mol', 'USD/l'])
    
    return filtered_df


######################################################################
######################################################################


def collect_vendors(instance, smiles_list, progress_output=None, ChemSpace=True, Molport=True, MCule=True,
                     molport_amount=1, molport_measure="g", molport_shipping_country="US",
                     molport_shipping_method="consolidated", molport_match_types=None,
                     molport_selection_method="lowest price"):

    time_start  = time.perf_counter()

    nb_integrator = sum([ChemSpace, Molport, MCule])
    progress = 0

    # List of selected suppliers
    selected_providers = []

    if Molport:
        # Get the prices and print count from MolPort
        print(f"Collecting Prices for given {len(smiles_list)} SMILES from MolPort...")
        molport_prices = molport_collect_prices(instance, smiles_list, amount=molport_amount,
                                                  measure=molport_measure, shipping_country=molport_shipping_country,
                                                  shipping_method=molport_shipping_method,
                                                  match_types=molport_match_types,
                                                  selection_method=molport_selection_method)
        smiles_with_price = molport_prices.loc[molport_prices['Price_USD'].notnull(), 'Input SMILES'].nunique()
        print(f"Total: {len(molport_prices)} prices for {smiles_with_price} molecules are found in MolPort.\n")
        progress += 1/nb_integrator
        if progress_output is not None:
            progress_output.append(progress)
        selected_providers.append(("Molport", molport_prices))

    if ChemSpace:
        # Get the prices and print count from ChemSpace
        print(f"Collecting Prices for given {len(smiles_list)} SMILES from ChemSpace...")
        chemspace_prices=chemspace_collect_prices(instance, smiles_list)
        unique_smiles_count = chemspace_prices['Input SMILES'].nunique()
        smiles_with_price_cs = len(chemspace_prices[chemspace_prices['Price_USD'].notnull()])
        print(f"Total: {smiles_with_price_cs} prices for {unique_smiles_count} molecules are found in ChemSpace.\n")
        progress += 1/nb_integrator
        if progress_output is not None:
            progress_output.append(progress) 
        selected_providers.append(("ChemSpace", chemspace_prices))
        
    if MCule:
        # Get the molecule IDs and print count MolPort
        print(f"Collecting ID's for given {len(smiles_list)} SMILES from MCule...")
        df_molecule_ids = mcule_get_ids(instance, smiles_list)
        smiles_exists = df_molecule_ids['Input SMILES'].nunique()
        print(f"Total: {smiles_exists} molecules and {len(df_molecule_ids)} conformers are found in MCule.\n")
        progress += 1/(2*nb_integrator)
        if progress_output is not None:
            progress_output.append(progress)

        # Get the prices and print count from MCule
        print(f"Collecting Prices for given {len(smiles_list)} IDs from MCule...")
        mcule_prices = mcule_collect_prices(instance, df_molecule_ids)
        mcule_prices = add_input_smiles_columns(df_molecule_ids, mcule_prices)
        smiles_with_price = mcule_prices.loc[mcule_prices['Price_USD'].notnull(), 'Input SMILES'].nunique()
        print(f"Total: {len(mcule_prices)} prices for {smiles_with_price} molecules are found in MCule.\n")
        progress += 1/(2*nb_integrator)
        if progress_output is not None:
            progress_output.append(progress)  
        selected_providers.append(("MCule", mcule_prices))

    if selected_providers:
        name_providers = [row[0] for row in selected_providers]
        if len(name_providers) >= 2:
            all_providers = ", ".join(name_providers[:-1]) + " and " + name_providers[-1]
        else:
            all_providers = name_providers[0]
        print(f"Merging Results from {all_providers}...")
        merged_df = merge_dataframes([row[1] for row in selected_providers])
        unique_smiles_count_merged = merged_df['Input SMILES'].nunique()
        smiles_with_price_merged = len(merged_df.loc[merged_df['Price_USD'].notnull(), 'Input SMILES'])
        print(f"Total: {smiles_with_price_merged} prices for {unique_smiles_count_merged} molecules exist in the Merged file.\n")
    else:
        print(f"The credentials are missing or incorrect. You need to set credential for at least one integrator.")
        return pd.DataFrame([])

    time_end = time.perf_counter()
    print(f"Total time: {time_end - time_start:0.4f} seconds")
    print(f"Vendor price collection is successfully done!")
    
    if progress_output is not None:
        progress_output.append(1.0)  # Ensure completion
    
    return merged_df
