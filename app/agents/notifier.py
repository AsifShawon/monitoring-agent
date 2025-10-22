"""Email notification agent for monitoring alerts."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List

from dotenv import load_dotenv

load_dotenv()

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USERNAME)


def send_email_notification(
    to_email: str,
    url: str,
    target_type: str,
    severity: str,
    summary: str,
    key_changes: List[str]
) -> bool:
    """Send email notification about detected changes.
    
    Args:
        to_email: Recipient email address
        url: Monitored URL
        target_type: Type of target (profile/company/website)
        severity: Change severity (high/medium/low)
        summary: AI-generated summary
        key_changes: List of specific changes
    
    Returns:
        True if email sent successfully, False otherwise
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("⚠️ Email credentials not configured. Set SMTP_USERNAME and SMTP_PASSWORD in .env")
        return False
    
    try:
        # Create email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔔 {severity.upper()} Change Detected: {url}"
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        
        html_body = _create_email_html(url, target_type, severity, summary, key_changes)
        
        # fallback
        text_body = _create_email_text(url, target_type, severity, summary, key_changes)
        
        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"✓ Email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def _create_email_html(url: str, target_type: str, severity: str, summary: str, key_changes: List[str]) -> str:
    """Create HTML email body."""
    
    severity_colors = {
        "high": "#DC2626",  # red
        "medium": "#F59E0B",  # orange
        "low": "#3B82F6"  # blue
    }
    color = severity_colors.get(severity, "#6B7280")
    
    severity_icons = {
        "high": "🚨",
        "medium": "⚠️",
        "low": "ℹ️"
    }
    icon = severity_icons.get(severity, "🔔")
    
    changes_html = ""
    if key_changes:
        changes_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
        for change in key_changes:
            changes_html += f"<li style='margin: 5px 0;'>{change}</li>"
        changes_html += "</ul>"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">
                {icon} Change Detection Alert
            </h1>
        </div>
        
        <div style="background: white; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
            
            <div style="background: {color}15; border-left: 4px solid {color}; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
                <p style="margin: 0; color: {color}; font-weight: bold; font-size: 14px; text-transform: uppercase;">
                    {severity} Severity
                </p>
            </div>
            
            <h2 style="color: #1f2937; font-size: 20px; margin-top: 0;">Summary</h2>
            <p style="font-size: 16px; color: #4b5563; margin: 10px 0;">
                {summary}
            </p>
            
            {f'<h3 style="color: #1f2937; font-size: 18px; margin-top: 25px;">Key Changes</h3>{changes_html}' if changes_html else ''}
            
            <div style="background: #f9fafb; padding: 15px; border-radius: 5px; margin-top: 25px;">
                <p style="margin: 5px 0; font-size: 14px;">
                    <strong>URL:</strong> <a href="{url}" style="color: #667eea; text-decoration: none;">{url}</a>
                </p>
                <p style="margin: 5px 0; font-size: 14px;">
                    <strong>Type:</strong> {target_type.replace('_', ' ').title()}
                </p>
                <p style="margin: 5px 0; font-size: 14px;">
                    <strong>Detected:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
                </p>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="{url}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    View Target
                </a>
            </div>
            
        </div>
        
        <div style="text-align: center; margin-top: 20px; color: #9ca3af; font-size: 12px;">
            <p>This is an automated notification from your monitoring agent.</p>
            <p>Powered by LangGraph + LangChain + Gemini Pro</p>
        </div>
        
    </body>
    </html>
    """
    return html


def _create_email_text(url: str, target_type: str, severity: str, summary: str, key_changes: List[str]) -> str:
    """Create plain text email body."""
    
    text = f"""
    🔔 CHANGE DETECTION ALERT
    ========================
    
    Severity: {severity.upper()}
    
    Summary:
    {summary}
    
    """
    
    if key_changes:
        text += "Key Changes:\n"
        for change in key_changes:
            text += f"  • {change}\n"
        text += "\n"
    
    text += f"""
    Details:
    --------
    URL: {url}
    Type: {target_type.replace('_', ' ').title()}
    Detected: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
    
    View target: {url}
    
    ---
    This is an automated notification from your monitoring agent.
    Powered by LangGraph + LangChain + Gemini Pro
    """
    
    return text.strip()


# TESTING
if __name__ == "__main__":
    print("Testing Email Notification")
    print("=" * 60)
    
    # Test email
    success = send_email_notification(
        to_email="user@example.com",
        url="https://www.linkedin.com/in/williamhgates/",
        target_type="linkedin_profile",
        severity="high",
        summary="Bill Gates has changed his job title to 'Co-Chair Emeritus' and added new certifications in AI and Quantum Computing.",
        key_changes=[
            "Job title changed from 'Co-chair' to 'Co-Chair Emeritus'",
            "New certification: AI Ethics from Stanford",
            "New certification: Quantum Computing from MIT"
        ]
    )
    
    if success:
        print("✓ Test email sent successfully!")
    else:
        print("✗ Test email failed. Check your SMTP configuration.")
