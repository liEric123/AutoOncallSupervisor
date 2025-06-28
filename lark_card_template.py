#!/usr/bin/env python3
"""Lark Card Template - Bilingual interactive card builder

This module provides a template function for building bilingual (English + Chinese)
interactive Lark cards for case notifications.

Usage:
    from lark_card_template import build_lark_card
    
    case_context = {
        "case_number": "307896",
        "build_url": "https://buildkite.com/...",
        "failure_reason": "Agent Lost - Exit Status -1",
        "resolution_plan": "Auto retry task",
        "resolution_basis": "Agent disconnection detected",
        "customer_notified": "Yes",
        "customer_clicked_at": "2025-01-15 17:37:28",
        "last_retry_time": "Never",
        "retry_count": "0"
    }
    
    card = build_lark_card(case_context)
"""

def build_lark_card(case_context: dict) -> dict:
    """
    Build a bilingual (English + Chinese) interactive Lark card.

    Args:
        case_context: dict with keys:
            - case_number, build_url, failure_reason, resolution_plan
            - resolution_basis, customer_notified, customer_clicked_at
            - last_retry_time, retry_count

    Returns:
        dict: JSON payload for Lark webhook
    """
    return {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": (
                        f"**❌ Failure Reason | 失败原因:**\n"
                        f"<font color='blue'>{case_context['failure_reason']}</font>\n\n"
                        f"**🔧 Resolution Plan | 处理方案:**\n"
                        f"{case_context['resolution_plan']}\n\n"
                        f"**📄 Based On | 处理依据:**\n"
                        f"{case_context['resolution_basis']}\n\n"
                        f"**📢 Customer Notified | 已通知客户:** {case_context['customer_notified']}\n"
                        f"**🕒 Customer Clicked At | 点击时间:** {case_context['customer_clicked_at']}\n"
                        f"**🔁 Last Auto Retry | 最近自动重试:** {case_context['last_retry_time']}\n"
                        f"**🔁 Retry Count | 重试次数:** {case_context['retry_count']}"
                    )
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "🔍 View Build Details | 查看Build详情"
                            },
                            "type": "primary",
                            "multi_url": {
                                "url": case_context["build_url"],
                                "pc_url": "",
                                "android_url": "",
                                "ios_url": ""
                            }
                        }
                    ]
                }
            ],
            "header": {
                "template": "blue",
                "title": {
                    "content": f"Case {case_context['case_number']}",
                    "tag": "plain_text"
                }
            }
        }
    }
