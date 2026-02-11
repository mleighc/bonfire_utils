import pandas as pd
import requests
from pathlib import Path
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Timezone constant
EASTERN = ZoneInfo("America/New_York")


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


def update_config(new_config: dict) -> None:
    """Updates the local JSON configuration file with new data.

    Accepts:
        new_config (dict): New configuration data to write

    Returns:
        None
    """
    config_path = Path(__file__).parent / "config.json"
    config = load_config()
    config.update(new_config)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)


def parse_api_datetime(date_string: str) -> datetime:
    """Parses a datetime string from the API and converts to Eastern time.

    Accepts:
        date_string (str): ISO format datetime string from API

    Returns:
        datetime: Timezone-aware datetime in Eastern time
    """
    if not date_string:
        return None  # type: ignore

    # Try parsing with timezone info (e.g., 2025-02-15T17:00:00Z or 2025-02-15T17:00:00+00:00)
    try:
        # Handle 'Z' suffix (UTC)
        if date_string.endswith("Z"):
            date_string = date_string[:-1] + "+00:00"
        dt = datetime.fromisoformat(date_string)
        # If it has timezone info, convert to Eastern
        if dt.tzinfo is not None:
            return dt.astimezone(EASTERN)
        # If naive, assume it's already Eastern (adjust if Bonfire sends UTC)
        return dt.replace(tzinfo=EASTERN)
    except ValueError:
        return None  # type: ignore


def get_open_projects(api_key: str, projects_url: str, time_delta_days=2) -> list:
    """Calls Bonfire API to get open public projects closing in > time_delta_days.

    Accepts:
        api_key (str): Bonfire API key
        projects_url (str): URL of the projects endpoint
        time_delta_days (int): Number of days ahead to filter closing projects, default is 2

    Returns:
        list: List of project dictionaries
    """
    all_projects = []
    page = 1
    limit = 100
    headers = {"Authorization": f"Bearer {api_key}"}

    while True:
        url = f"{projects_url}?limit={limit}&page={page}"
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        data = response.json()

        if not data:
            break

        all_projects.extend(data)

        if len(data) < limit:
            break

        page += 1

    # Calculate cutoff in Eastern time
    cutoff = datetime.now(EASTERN) + timedelta(days=time_delta_days)

    # Only open, public, closing in >time_delta_days
    open_projects = []
    for project in all_projects:
        if project["status"].lower() != "open":
            continue
        if project["visibility"].lower() != "public":
            continue

        close_date = parse_api_datetime(project["dateClosed"])
        if close_date and close_date > cutoff:
            open_projects.append(project)

    return open_projects


def get_all_projects(api_key: str, projects_url: str) -> list:
    """Calls Bonfire API to get all public projects with automatic pagination.

    Accepts:
        api_key (str): Bonfire API key
        projects_url (str): URL of the projects endpoint

    Returns:
        list: List of project dictionaries
    """
    all_projects = []
    page = 1
    limit = 100
    headers = {"Authorization": f"Bearer {api_key}"}

    while True:
        url = f"{projects_url}?limit={limit}&page={page}"
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        data = response.json()

        if not data:
            break

        all_projects.extend(data)

        if len(data) < limit:
            break

        page += 1

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
