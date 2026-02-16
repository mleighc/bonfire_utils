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


def parse_api_datetime(date_string: str) -> str:
    """Parses a datetime string from the API and converts to Eastern time.

    Accepts:
        date_string (str): ISO format datetime string from API

    Returns:
        str: Human-readable datetime string in Eastern time (12-hour format)
    """
    if not date_string:
        return None  # type: ignore

    try:
        # Handle 'Z' suffix (UTC)
        if date_string.endswith("Z"):
            date_string = date_string[:-1] + "+00:00"
        dt = datetime.fromisoformat(date_string)
        # Convert to Eastern
        if dt.tzinfo is not None:
            dt_eastern = dt.astimezone(EASTERN)
        else:
            # If naive, assume UTC
            dt_eastern = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(EASTERN)
        # Format as human-readable 12-hour format
        return dt_eastern.strftime("%b %d, %Y %I:%M %p %Z")
    except ValueError:
        return date_string  # Return original if parsing fails


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

        date_closed = project.get("dateClosed")
        if date_closed:
            if date_closed.endswith("Z"):
                date_closed = date_closed[:-1] + "+00:00"
            close_date = datetime.fromisoformat(date_closed)
            if close_date.tzinfo:
                close_date = close_date.astimezone(EASTERN)
            if close_date > cutoff:
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
            "open_date": parse_api_datetime(project.get("dateOpen")),
            "date_closed": parse_api_datetime(project.get("dateClosed")),
            "date_evaluated": parse_api_datetime(project.get("dateEvaluated")),
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
            "date_modified": parse_api_datetime(project.get("dateModified")),
            **custom_fields,
        }
        df_list.append(item)

    df = pd.DataFrame(df_list)
    if columns:
        df = df[columns]

    return df


def get_commodities(api_key: str, base_url: str, project_id: str) -> list:
    """
    Calls Bonfire API to get commodities for a specific project.

    Accepts:
        api_key (str): Bonfire API key
        base_url (str): Base URL of the Bonfire API
        project_id (str): ID of the project to get commodities for
    Returns:
        list: List of commodity dictionaries
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{base_url}/v1/projects/{project_id}/commodityCodes"
    response = requests.get(url, headers=headers, verify=False)
    response.raise_for_status()
    return response.json()


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
