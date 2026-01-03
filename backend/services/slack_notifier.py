"""
Slack Notifier Service

Sends alerts to Slack for monitoring events.
"""
import aiohttp
from datetime import datetime
from typing import Dict, Optional
import os


class SlackNotifier:
    """Send alerts to Slack"""
    
    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)
        
    async def send_alert(
        self,
        severity: str,
        title: str,
        message: str,
        details: Optional[Dict] = None
    ):
        """Send alert to Slack"""
        if not self.enabled:
            print(f"[SLACK DISABLED] {severity}: {title} - {message}")
            return
            
        # Color coding
        colors = {
            "CRITICAL": "#FF0000",
            "WARNING": "#FFA500",
            "INFO": "#0000FF"
        }
        
        # Build payload
        payload = {
            "attachments": [{
                "color": colors.get(severity, "#808080"),
                "title": f"[{severity}] {title}",
                "text": message,
                "fields": [],
                "footer": "BeatVegas Monitoring",
                "ts": int(datetime.now().timestamp())
            }]
        }
        
        # Add details as fields
        if details:
            for key, value in details.items():
                payload["attachments"][0]["fields"].append({
                    "title": key,
                    "value": str(value),
                    "short": True
                })
        
        # Send to Slack
        try:
            if not self.webhook_url:
                print("Slack webhook URL not configured")
                return
                
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as resp:
                    if resp.status != 200:
                        print(f"Slack notification failed: {resp.status}")
        except Exception as e:
            print(f"Slack notification error: {e}")
