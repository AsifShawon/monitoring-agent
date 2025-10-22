"""AI-powered change analyzer using LangChain."""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()

# Configure LangChain with Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


class ChangeAnalysis(BaseModel):
    """Structured output for change analysis."""
    has_changes: bool = Field(description="Whether changes were detected")
    severity: str = Field(description="Severity level: high, medium, low, or none")
    summary: str = Field(description="Brief human-readable summary of changes")
    key_changes: List[str] = Field(description="List of specific changes detected")
    impact: Optional[str] = Field(default="", description="Assessment of change significance")


# Initialize LangChain model
if GEMINI_API_KEY:
    llm = ChatGoogleGenerativeAI(
        model="gemini-pro",
        google_api_key=GEMINI_API_KEY,
        temperature=0.3,
        convert_system_message_to_human=True
    )
    parser = JsonOutputParser(pydantic_object=ChangeAnalysis)
    print("✓ LangChain + Gemini Pro initialized")
else:
    llm = None
    parser = None
    print("⚠ GEMINI_API_KEY not found. Using fallback analysis.")


def analyze_changes(old_data, new_data, data_type):
    """Analyze changes using LangChain + Gemini."""
    if not old_data or not new_data:
        return {"has_changes": False, "error": "Missing data"}
    
    if old_data == new_data:
        return {
            "has_changes": False,
            "severity": "none",
            "summary": "No changes detected",
            "key_changes": [],
            "impact": "Data is identical"
        }
    
    if not llm:
        return _fallback_analysis(old_data, new_data, data_type)
    
    try:
        # Build prompt with LangChain
        prompt = _build_langchain_prompt(old_data, new_data, data_type)
        
        # Create chain
        chain = prompt | llm | parser
        
        # Invoke chain
        result = chain.invoke({
            "data_type": data_type,
            "old_data": json.dumps(old_data, indent=2)[:3000],
            "new_data": json.dumps(new_data, indent=2)[:3000]
        })
        
        # Add metadata
        result["analyzed_at"] = datetime.utcnow().isoformat()
        result["analyzer"] = "langchain-gemini-pro"
        
        return result
        
    except Exception as e:
        print(f"LangChain analysis failed: {e}")
        return _fallback_analysis(old_data, new_data, data_type)


def _build_langchain_prompt(old_data, new_data, data_type):
    """Build LangChain prompt template."""
    
    if data_type == "profile":
        system_msg = """You are an expert LinkedIn profile analyzer. 
Compare old and new profile data to detect career changes, new positions, certifications, education, and location changes.

Focus on:
- New jobs or job title changes (HIGH severity)
- New certifications or education (MEDIUM severity)  
- Headline or bio changes (LOW severity)

{format_instructions}"""
    
    elif data_type == "company":
        system_msg = """You are an expert LinkedIn company analyzer.
Compare old and new company data to detect updates, growth, new posts, and changes.

Focus on:
- Employee count or location changes (HIGH severity)
- New posts or updates (MEDIUM severity)
- Follower count changes (LOW severity)

{format_instructions}"""
    
    elif data_type == "website":
        system_msg = """You are an expert web content analyzer.
Compare old and new website data to detect content changes and updates.

Focus on:
- Major content changes (HIGH severity)
- New sections or articles (MEDIUM severity)
- Title or metadata changes (LOW severity)

{format_instructions}"""
    
    else:
        system_msg = """You are a data change analyzer. Compare the old and new data carefully.

{format_instructions}"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("human", """Analyze these {data_type} changes:

OLD DATA:
{old_data}

NEW DATA:
{new_data}

Provide a structured analysis.""")
    ])
    
    return prompt.partial(format_instructions=parser.get_format_instructions())


def _fallback_analysis(old_data, new_data, data_type):
    """Simple fallback analysis."""
    changes = []
    severity = "none"
    
    if data_type == "profile":
        if old_data.get("headline") != new_data.get("headline"):
            changes.append("Headline changed")
        if len(new_data.get("experience", [])) > len(old_data.get("experience", [])):
            changes.append("New job added")
            severity = "high"
    
    return {
        "has_changes": len(changes) > 0,
        "severity": severity,
        "summary": "; ".join(changes) if changes else "No changes",
        "key_changes": changes
    }


if __name__ == "__main__":
    # Test
    old = {"fullName": "John", "headline": "Engineer"}
    new = {"fullName": "John", "headline": "Senior Engineer"}
    result = analyze_changes(old, new, "profile")
    print(json.dumps(result, indent=2))
