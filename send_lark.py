#!/usr/bin/env python3
"""Send Lark Cards - Webhook sender utility

This module provides functions for sending Lark card payloads
to webhook URLs with proper error handling and logging.
Contains specialized notification functions for AutoOncall scenarios.

Usage:
    from send_lark import send_agent_lost_notification, send_retry_success_notification
    
    # Send notifications for Agent Lost scenarios
    send_agent_lost_notification(context, build_url)
    send_retry_success_notification(context, build_url)
"""

import logging

import requests

from lark_card_template import build_lark_card

# Lark API constants
LARK_TIMEOUT_SECONDS = 10

# Configure logging
logger = logging.getLogger(__name__)


def send_lark_card(webhook_url: str, card_payload: dict) -> bool:
    """Send the constructed card to Lark via webhook.

    Args:
        webhook_url: Lark bot webhook URL
        card_payload: JSON-compatible message card
        
    Returns:
        True if successful, False if failed
    """
    try:
        response = requests.post(webhook_url, json=card_payload, timeout=LARK_TIMEOUT_SECONDS)
        response.raise_for_status()

        # Log Lark's response
        try:
            lark_response = response.json()
            logger.info("Lark response: %s", lark_response)
        except (ValueError, KeyError):
            logger.info("Lark responded with non-JSON: %s", response.text[:200])

        return True
    except requests.exceptions.RequestException as e:
        logger.error("Failed to send Lark card: %s", e)
        return False


def send_agent_lost_notification(context: dict, build_url: str) -> None:
    """Send Lark notification for Agent Lost detection.
    
    Args:
        context: Dictionary containing build and configuration information
        build_url: URL to the failed build
    """
    webhook_url = context.get("lark_webhook_url")
    if not webhook_url:
        logger.info("No Lark webhook URL configured, skipping notification")
        return

    case_context = {
        "case_number": f"BUILD-{context.get('build_number', 'Unknown')}",
        "build_url": build_url,
        "failure_reason": "Agent Lost - Exit Status -1",
        "resolution_plan": "Automatic retry initiated",
        "resolution_basis": "Agent disconnection detected by AutoOncall Supervisor",
        "customer_notified": "System notification sent",
        "customer_clicked_at": "N/A",
        "last_retry_time": "In progress",
        "retry_count": "1"
    }

    card = build_lark_card(case_context)
    success = send_lark_card(webhook_url, card)

    if success:
        logger.info("Sent Agent Lost notification to Lark")
    else:
        logger.warning("Failed to send Agent Lost notification to Lark")


def send_retry_notification(context: dict, build_url: str, success: bool, error_message: str = None) -> None:
    """Send Lark notification for job retry result.
    
    Args:
        context: Dictionary containing job and configuration information
        build_url: URL to the build
        success: True for success, False for failure
        error_message: Error message if success=False
    """
    webhook_url = context.get("lark_webhook_url")
    if not webhook_url:
        logger.info("No Lark webhook URL configured, skipping notification")
        return

    # Shared context fields
    case_context = {
        "case_number": f"BUILD-{context.get('build_number', 'Unknown')}",
        "build_url": build_url,
        "customer_clicked_at": "N/A",
        "retry_count": "1"
    }

    # Success vs failure specific fields
    if success:
        case_context.update({
            "failure_reason": "Agent Lost - Resolved",
            "resolution_plan": "Retry completed successfully",
            "resolution_basis": "Automatic retry by AutoOncall Supervisor",
            "customer_notified": "Success notification sent",
            "last_retry_time": "Just completed"
        })
    else:
        case_context.update({
            "failure_reason": f"Agent Lost Retry Failed: {error_message}",
            "resolution_plan": "Manual intervention required",
            "resolution_basis": "Automatic retry failed - see error details",
            "customer_notified": "Failure notification sent",
            "last_retry_time": "Failed"
        })

    card = build_lark_card(case_context)
    send_retry_success = send_lark_card(webhook_url, card)

    if send_retry_success:
        logger.info("Sent retry %s notification to Lark", "success" if success else "failure")
    else:
        logger.warning("Failed to send retry %s notification to Lark", "success" if success else "failure")
