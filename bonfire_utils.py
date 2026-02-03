import pandas as pd
import requests
from pathlib import Path
import json
from datetime import datetime, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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


def get_open_projects(api_key: str, projects_url: str, time_delta_days=2) -> list:
    """Calls Bonfire API to get open public projects closing in > time_delta_days.

    Accepts:
        api_key (str): Bonfire API key
        projects_url (str): URL of the projects endpoint
        time_delta_days (int): Number of days ahead to filter closing projects, default is 2

    Returns:
        list: List of project dictionaries
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(
        projects_url,
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


def get_all_projects(api_key: str, projects_url: str) -> list:
    """Calls Bonfire API to get all public projects.

    Accepts:
        api_key (str): Bonfire API key
        projects_url (str): URL of the projects endpoint

    Returns:
        list: List of project dictionaries
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(
        projects_url,
        headers=headers,
        verify=False,  # no SSL verification for internal API calls
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
    df_list = []
    for project in projects:
        custom_fields = {
            cf["customField"]["name"]: cf["value"]
            for cf in project.get("customFieldValues", [])
        }

        item = {
            "bonfire_id": project.get("id"),
            "organization_id": project.get("organization")["id"],
            "department_id": project.get("department")["id"],
            "project_name": project.get("name"),
            "reference_number": project.get("referenceNumber"),
            "project_description": project.get("description"),
            "type": project.get("type"),
            "open_date": project.get("dateOpen"),
            "date_closed": project.get("dateClosed"),
            "date_evaluated": project.get("dateEvaluated"),
            "visibility": project.get("visibility"),
            "owner_name": (
                project.get("owner")["name"] if project.get("owner") else None
            ),
            "owner_email": (
                project.get("owner")["email"] if project.get("owner") else None
            ),
            "status": project.get("status"),
            "contact_name": (
                project.get("contact")["name"] if project.get("contact") else None
            ),
            "contact_email": (
                project.get("contact")["email"] if project.get("contact") else None
            ),
            "contact_phone": (
                project.get("contact")["phone"] if project.get("contact") else None
            ),
            "date_modified": project.get("dateModified"),
            **custom_fields,
        }
        df_list.append(item)

    df = pd.DataFrame(df_list)
    if columns:
        df = df[columns]

    return df


def save_to_excel(df: pd.DataFrame, output_path: Path, filename: str) -> Path:
    """Saves a pandas DataFrame to an Excel file.

    Accepts:
        df (pd.DataFrame): DataFrame to save
        output_path (Path): Path to save the Excel file
        filename (str): Name of the Excel file

    Returns:
        Path: Path to the saved Excel file
    """
    output_path = Path(output_path)  # convert if string
    output_file = output_path / filename
    df.to_excel(output_file, index=False)

    return output_file
