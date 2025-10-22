"""LangGraph coordinator for monitoring workflow.

This module orchestrates the entire monitoring workflow:
1. Scraper Agent: Fetches data from LinkedIn/websites
2. Analyzer Agent: Detects and analyzes changes using LLM
3. Notifier Agent: Sends email alerts for significant changes
"""

import json
from datetime import datetime
from typing import TypedDict, Annotated, Literal
from operator import add

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.scraper import (
    scrape_linkedin_profile,
    scrape_linkedin_company,
    scrape_website
)
from app.agents.analyzer import analyze_changes
from app.agents.notifier import send_email_notification


# STATE DEFINITION
class MonitoringState(TypedDict):
    """State for the monitoring workflow."""
    target_id: str
    url: str
    target_type: str  # linkedin_profile, linkedin_company, website
    user_email: str
    
    # Scraping results
    old_data: dict
    new_data: dict
    scrape_success: bool
    scrape_error: str
    
    # Analysis results
    has_changes: bool
    severity: str
    summary: str
    key_changes: list
    analysis_error: str
    
    # Notification results
    notification_sent: bool
    notification_error: str
    
    # Workflow control
    messages: Annotated[list, add]
    next_step: str


# AGENT NODES
def scraper_node(state: MonitoringState) -> MonitoringState:
    """Scrape data from the target URL."""
    url = state["url"]
    target_type = state["target_type"]
    
    state["messages"].append(HumanMessage(content=f"🔍 Scraping {target_type}: {url}"))
    
    try:
        if target_type == "linkedin_profile":
            result = scrape_linkedin_profile(url)
        elif target_type in ["linkedin_company", "linkedin_page"]:
            result = scrape_linkedin_company(url)
        else:  # website
            result = scrape_website(url)
        
        if "error" in result:
            state["scrape_success"] = False
            state["scrape_error"] = result.get("error", "Unknown error")
            state["messages"].append(AIMessage(content=f"❌ Scraping failed: {state['scrape_error']}"))
            state["next_step"] = "end"
            return state
        
        # Store new data
        state["new_data"] = result
        state["scrape_success"] = True
        state["messages"].append(AIMessage(content=f"✓ Successfully scraped {target_type}"))
        state["next_step"] = "analyzer"
        
    except Exception as e:
        state["scrape_success"] = False
        state["scrape_error"] = str(e)
        state["messages"].append(AIMessage(content=f"❌ Exception during scraping: {e}"))
        state["next_step"] = "end"
    
    return state


def analyzer_node(state: MonitoringState) -> MonitoringState:
    """Analyze changes between old and new data."""
    state["messages"].append(HumanMessage(content="🔬 Analyzing changes with LLM..."))
    
    try:
        old_data = state.get("old_data", {})
        new_data = state.get("new_data", {})
        
        if not old_data:
            state["has_changes"] = False
            state["severity"] = "none"
            state["summary"] = "First scrape - no baseline to compare"
            state["key_changes"] = []
            state["messages"].append(AIMessage(content="ℹ️ First scrape - baseline established"))
            state["next_step"] = "end"
            return state
        
        # Map target type to analyzer type
        type_mapping = {
            "linkedin_profile": "profile",
            "linkedin_company": "company",
            "linkedin_page": "company",
            "website": "website"
        }
        data_type = type_mapping.get(state["target_type"], "website")
        
        result = analyze_changes(old_data, new_data, data_type)
        
        state["has_changes"] = result.get("has_changes", False)
        state["severity"] = result.get("severity", "none")
        state["summary"] = result.get("summary", "No summary available")
        state["key_changes"] = result.get("key_changes", [])
        
        if state["has_changes"]:
            state["messages"].append(AIMessage(
                content=f"🔔 Changes detected! Severity: {state['severity']}\n{state['summary']}"
            ))
            if state["severity"] in ["high", "medium"]:
                state["next_step"] = "notifier"
            else:
                state["next_step"] = "end"
        else:
            state["messages"].append(AIMessage(content="✓ No changes detected"))
            state["next_step"] = "end"
        
    except Exception as e:
        state["analysis_error"] = str(e)
        state["messages"].append(AIMessage(content=f"❌ Analysis failed: {e}"))
        state["next_step"] = "end"
    
    return state


def notifier_node(state: MonitoringState) -> MonitoringState:
    """Send email notification about changes."""
    state["messages"].append(HumanMessage(content="📧 Sending email notification..."))
    
    try:
        email = state.get("user_email")
        if not email:
            state["notification_sent"] = False
            state["notification_error"] = "No email address provided"
            state["messages"].append(AIMessage(content="⚠️ No email address - skipping notification"))
            state["next_step"] = "end"
            return state
        
        # Send notification
        success = send_email_notification(
            to_email=email,
            url=state["url"],
            target_type=state["target_type"],
            severity=state["severity"],
            summary=state["summary"],
            key_changes=state["key_changes"]
        )
        
        state["notification_sent"] = success
        if success:
            state["messages"].append(AIMessage(content=f"✓ Email sent to {email}"))
        else:
            state["messages"].append(AIMessage(content="⚠️ Email sending failed"))
        
    except Exception as e:
        state["notification_sent"] = False
        state["notification_error"] = str(e)
        state["messages"].append(AIMessage(content=f"❌ Notification failed: {e}"))
    
    state["next_step"] = "end"
    return state


def should_continue(state: MonitoringState) -> Literal["analyzer", "notifier", "end"]:
    """Decide the next step in the workflow."""
    return state.get("next_step", "end")

# graph
def build_monitoring_graph() -> StateGraph:
    """Build the LangGraph workflow for monitoring."""
    
    workflow = StateGraph(MonitoringState)
    
    workflow.add_node("scraper", scraper_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("notifier", notifier_node)
    
    workflow.set_entry_point("scraper")
    workflow.add_conditional_edges(
        "scraper",
        should_continue,
        {
            "analyzer": "analyzer",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "analyzer",
        should_continue,
        {
            "notifier": "notifier",
            "end": END
        }
    )
    
    workflow.add_edge("notifier", END)
    
    return workflow.compile()


monitoring_graph = build_monitoring_graph()


# MAIN EXECUTION FUNCTION
def run_monitoring_workflow(
    target_id: str,
    url: str,
    target_type: str,
    user_email: str,
    old_data: dict = None
) -> dict:
    """Run the complete monitoring workflow.
    
    Args:
        target_id: Database ID of the monitoring target
        url: URL to monitor
        target_type: Type (linkedin_profile, linkedin_company, website)
        user_email: Email for notifications
        old_data: Previous scraped data for comparison
    
    Returns:
        Final state with all results
    """
    initial_state = {
        "target_id": target_id,
        "url": url,
        "target_type": target_type,
        "user_email": user_email,
        "old_data": old_data or {},
        "new_data": {},
        "scrape_success": False,
        "scrape_error": "",
        "has_changes": False,
        "severity": "none",
        "summary": "",
        "key_changes": [],
        "analysis_error": "",
        "notification_sent": False,
        "notification_error": "",
        "messages": [],
        "next_step": "scraper"
    }
    
    final_state = monitoring_graph.invoke(initial_state)
    
    return final_state



if __name__ == "__main__":
    print("Testing LangGraph Monitoring Workflow")
    print("=" * 60)
    
    # Test profile monitoring
    result = run_monitoring_workflow(
        target_id="test_123",
        url="https://www.linkedin.com/in/williamhgates/",
        target_type="linkedin_profile",
        user_email="user@example.com",
        old_data=None  # First scrape
    )
    
    print("\n📊 Workflow Results:")
    print(f"Scrape Success: {result['scrape_success']}")
    print(f"Has Changes: {result['has_changes']}")
    print(f"Severity: {result['severity']}")
    print(f"Summary: {result['summary']}")
    print(f"Notification Sent: {result['notification_sent']}")
    
    print("\n📝 Messages:")
    for msg in result["messages"]:
        print(f"  {msg.content}")
