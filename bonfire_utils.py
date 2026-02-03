import pandas as pd
import requests
from pathlib import Path
import json
from datetime import datetime, timedelta


# Load config
def load_config() -> dict:
    """Loads configuration data to a dictionary from a local JSON file.

    Accepts:
        None

    Returns:
        dict: Configuration dictionary
    """
    config_path = Path(__file__).parent / "config.json"
    with open(config_path) as f:
        return json.load(f)


# Bonfire API pull all currently open public projects
def get_open_projects(api_key: str, time_delta_days=2) -> list:
    """Calls Bonfire API to get open public projects closing in > time_delta_days.

    Accepts:
        api_key (str): Bonfire API key
        time_delta_days (int): Number of days ahead to filter closing projects, default is 2

    Returns:
        list: List of project dictionaries
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(
        "https://us-production-api-public.bonfirehub.com/v1/projects/all",
        headers=headers,
        verify=False,
    )
    response.raise_for_status()
    all_projects = response.json()

    # Only open, public, closing in >2 days
    open_projects = [
        project
        for project in all_projects
        if project["status"].lower() == "open"
        and project["dateClosed"]
        > (datetime.now() + timedelta(days=time_delta_days)).isoformat()
        and project["visibility"].lower() == "public"
    ]

    return open_projects


# Bonfire API pull ALL public projects
def get_all_projects(api_key: str) -> list:
    """Calls Bonfire API to get all public projects.

    Accepts:
        api_key (str): Bonfire API key

    Returns:
        list: List of project dictionaries
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(
        "https://us-production-api-public.bonfirehub.com/v1/projects/all",
        headers=headers,
        verify=False,
    )
    response.raise_for_status()
    all_projects = response.json()

    return all_projects


def convert_to_df(projects: list, columns=None) -> pd.DataFrame:
    """Converts a list of project dictionaries to a pandas DataFrame.

    Accepts:
        projects (list): List of project dictionaries
        columns (list): List of columns to include in the DataFrame

    Returns:
        pd.DataFrame: DataFrame containing project data
    """
    df = pd.DataFrame(projects)
    if columns:
        df = df[columns]

    return df


def save_to_excel(df: pd.DataFrame, output_path: Path, filename: str) -> Path:
    """Saves a pandas DataFrame to an Excel file.

    Accepts:
        df (pd.DataFrame): DataFrame to save
        output_path (Path): Path to save the Excel file

    Returns:
        Path: Path to the saved Excel file
    """
    output_file = output_path / filename
    df.to_excel(output_file, index=False)
    return output_file
