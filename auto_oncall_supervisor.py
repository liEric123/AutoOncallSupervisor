#!/usr/bin/env python3
"""AutoOncallSupervisor - Automated Buildkite Agent Lost Detection and Retry

This script monitors Buildkite pipelines for builds that failed due to "Agent Lost" scenarios
and automatically retries the affected jobs. Agent Lost occurs when a Buildkite agent 
disconnects mid-job execution, resulting in exit_status == -1.

The script performs the following workflow:
1. Fetches recent failed builds from a specified pipeline and branch
2. Examines the last job in each failed build  
3. Detects jobs with exit_status == -1 (indicating agent disconnection)
4. Automatically retries those jobs using the Buildkite REST API
5. Sends a message via Lark Bot Webhook via POST

This helps reduce manual intervention for transient infrastructure issues that cause
agent disconnections during CI/CD pipeline execution.

Configuration:
    Requires a config.json file with Buildkite API credentials and pipeline settings.
    
Dependencies:
    - requests: For HTTP API calls to Buildkite
    
Usage:
    python auto_oncall_supervisor.py
"""

__version__ = "1.0.0"
import json
import logging
import os

import requests

from send_lark import send_agent_lost_notification, send_retry_notification

# Buildkite API constants
BUILDKITE_DEFAULT_PAGE_SIZE = 30
API_TIMEOUT_SECONDS = 10

# Configure logging to show timestamps and clean messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_context_fields(context: dict, required_fields: list, function_name: str) -> bool:
    """Validate that required fields are present in context.
    
    Args:
        context: Dictionary containing configuration and runtime data
        required_fields: List of field names that must be present in context
        function_name: Name of calling function for error message context
        
    Returns:
        True if all required fields are present, False otherwise
    """
    missing_fields = [field for field in required_fields if not context.get(field)]
    if missing_fields:
        logger.error("Missing required config fields for %s: %s", function_name, ", ".join(missing_fields))
        return False
    return True


def fetch_recent_builds(context: dict) -> list:
    """Fetch the most recent builds from the target pipeline and branch.
    
    Uses Buildkite's default page size of 30 builds per page and includes job data
    in the response to avoid additional API calls.
    
    Args:
        context: Dictionary containing API configuration including base_url, headers,
                org_slug, pipeline_slug, and target_branch
                
    Returns:
        List of recent builds or empty list on error
    """
    required_fields = ["base_url", "headers", "org_slug", "pipeline_slug", "target_branch"]
    if not validate_context_fields(context, required_fields, "fetch_recent_builds"):
        logger.warning("Cannot fetch builds due to missing configuration")
        return []

    logger.info("Fetching %d recent builds from %s on %s",
                BUILDKITE_DEFAULT_PAGE_SIZE, context["pipeline_slug"], context["target_branch"])
    builds_url = f"{context['base_url']}/organizations/{context['org_slug']}/pipelines/{context['pipeline_slug']}/builds"
    params = {
        "branch": context["target_branch"],
        "include": "jobs",
        "per_page": BUILDKITE_DEFAULT_PAGE_SIZE,
    }

    try:
        response = requests.get(builds_url, headers=context["headers"], params=params, timeout=API_TIMEOUT_SECONDS)
        response.raise_for_status()
        recent_builds = response.json()

        logger.info("API returned %d build objects (each build = one CI/CD run)", len(recent_builds))
        return recent_builds
    except requests.exceptions.RequestException as e:
        logger.error("Error fetching builds: %s", e)
        return []


def retry_job(context: dict) -> None:
    """Retry a specific job using Buildkite's retry API.
    
    Args:
        context: Dictionary containing API configuration and job details including
                base_url, headers, org_slug, pipeline_slug, build_number, job_id, and lark_webhook_url
    """
    required_fields = ["base_url", "headers", "org_slug", "pipeline_slug", "build_number", "job_id"]
    if not validate_context_fields(context, required_fields, "retry_job"):
        logger.warning("Cannot retry job due to missing configuration")
        return

    logger.info("Attempting to retry job %s in build #%s...", context["job_id"], context["build_number"])
    retry_url = (f"{context['base_url']}/organizations/{context['org_slug']}/pipelines/"
                  f"{context['pipeline_slug']}/builds/{context['build_number']}/jobs/{context['job_id']}/retry")

    build_url = f"https://buildkite.com/{context['org_slug']}/{context['pipeline_slug']}/builds/{context['build_number']}"

    try:
        retry_response = requests.put(retry_url, headers=context["headers"], timeout=API_TIMEOUT_SECONDS)
        retry_response.raise_for_status()
        logger.info("Successfully retried job %s in build #%s (%s)",
                    context["job_id"], context["build_number"], build_url)

        # Send success notification to Lark
        send_retry_notification(context, build_url, success=True)

    except requests.exceptions.RequestException as e:
        logger.error("Failed to retry job %s: %s", context["job_id"], e)

        # Send failure notification to Lark
        send_retry_notification(context, build_url, success=False, error_message=str(e))


def process_and_retry_builds(failed_builds: list, context: dict) -> None:
    """Process failed builds and retry jobs that failed due to Agent Lost.
    
    Iterates through failed builds, examines the last job in each build for
    exit_status == -1 (indicating agent disconnection), and retries those jobs.
    
    Args:
        failed_builds: List of build objects that have state == "failed"
        context: Dictionary containing API configuration for job retry operations
    """
    required_fields = ["org_slug", "pipeline_slug"]
    if not validate_context_fields(context, required_fields, "process_and_retry_builds"):
        logger.warning("Cannot process builds due to missing configuration")
        return

    agent_lost_found = False

    for build in failed_builds:
        build_number = build.get("number")
        build_url = f"https://buildkite.com/{context['org_slug']}/{context['pipeline_slug']}/builds/{build_number}"
        logger.info("Checking build #%s (%s)", build_number, build_url)

        jobs = build.get("jobs", [])

        if len(jobs) == 0:
            continue

        # Check if the last job failed due to Agent Lost (exit_status == -1)
        last_job = jobs[-1]
        if last_job.get("exit_status") == -1:
            agent_lost_found = True
            job_id = last_job.get("id")
            logger.warning("Agent Lost detected in build #%s, job %s (%s)",
                          build_number, job_id, build_url)

            # Create context for retry with job-specific info
            retry_context = context.copy()
            retry_context.update({
                "build_number": build_number,
                "job_id": job_id
            })

            # Send Agent Lost notification to Lark
            send_agent_lost_notification(retry_context, build_url)

            # Retry the job
            retry_job(retry_context)

    # Log completion status
    if not agent_lost_found:
        logger.info("No Agent Lost scenarios detected - no Lark notifications needed")


def load_config() -> dict | None:
    """Load configuration from config.json file.

    Returns:
        Dictionary of config values, or None if file cannot be read or parsed
    """
    logger.info("Loading configuration from config.json...")
    config_file = "config.json"

    if not os.path.exists(config_file):
        logger.error("Config file 'config.json' not found. Please create it with format:")
        logger.error('{"buildkite_token": "your_token", "org_slug": "your_org", "pipeline_slug": "your_pipeline", "target_branch": "prod"}')
        return None

    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            config = json.load(file)
        if "target_branch" not in config:
            config["target_branch"] = "prod"
        return config
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in config.json: %s", e)
        return None
    except (OSError, IOError) as e:
        logger.error("Error reading config.json: %s", e)
        return None


def filter_failed_builds(recent_builds: list, context: dict) -> list:
    """Filter recent builds to find only those with failed state.
    
    Args:
        recent_builds: List of build objects from Buildkite API
        context: Dictionary containing configuration including target_branch for logging
        
    Returns:
        List of build objects that have state == "failed"
    """
    required_fields = ["target_branch"]
    if not validate_context_fields(context, required_fields, "filter_failed_builds"):
        logger.warning("Cannot filter builds due to missing configuration")
        return []

    failed_builds = [build for build in recent_builds if build.get("state") == "failed"]
    logger.info(
        "Found %d failed builds out of %d total builds on %s.",
        len(failed_builds),
        len(recent_builds),
        context["target_branch"]
    )
    return failed_builds


def main() -> None:
    """Main function that orchestrates the Agent Lost detection and retry process.

    Workflow:
        1. Load configuration from config.json
        2. Fetch recent builds from target pipeline/branch (30 builds max)
        3. Filter for failed builds
        4. Check each failed build's last job for Agent Lost (exit_status == -1)
        5. Retry any jobs that failed due to Agent Lost
    """
    logger.info("Starting AutoOncallSupervisor v%s", __version__)

    config = load_config()
    if not config:
        return
    logger.info("Configuration loaded successfully.")

    # Create context dictionary with all necessary information
    context = {
        "base_url": "https://api.buildkite.com/v2",
        "headers": {
            "Authorization": f"Bearer {config.get('buildkite_token', '')}",
            "Content-Type": "application/json",
            "User-Agent": "AutoOncallSupervisor/1.0"
        },
        "org_slug": config.get("org_slug", ""),
        "pipeline_slug": config.get("pipeline_slug", ""),
        "target_branch": config.get("target_branch", "prod"),
        "lark_webhook_url": config.get("lark_webhook_url", "")
    }

    # Fetch the most recent builds from the target pipeline and branch
    recent_builds = fetch_recent_builds(context)
    if not recent_builds:
        logger.info("No recent builds found. Nothing to do.")
        return

    # Filter for failed builds
    failed_builds = filter_failed_builds(recent_builds, context)
    if not failed_builds:
        logger.info("No failed builds found in the most recent page. Nothing to do.")
        return

    # Check each failed build for Agent Lost scenarios
    process_and_retry_builds(failed_builds, context)


if __name__ == "__main__":
    main()
