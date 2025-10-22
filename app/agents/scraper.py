"""LinkedIn and Website scraping utilities.

This module provides three core scraping functions:
- scrape_linkedin_profile: Scrape LinkedIn profile data (Scrapingdog API)
- scrape_linkedin_company: Scrape LinkedIn company pages (Scrapingdog API)
- scrape_website: Scrape general websites with change detection support

Environment variables:
- SCRAPINGDOG_API_KEY: Required for LinkedIn scraping (profiles and companies)
- WEBSITE_USE_BROWSER: true/false (default: true)
- WEBSITE_HEADLESS: true/false (default: true)
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()  


# LINKEDIN COMPANY SCRAPING 
def scrape_linkedin_company(linkedin_url: str) -> Dict[str, Any]:
    """Scrape LinkedIn company page using Scrapingdog API.

    Args:
        linkedin_url: Full URL to LinkedIn company page
                     (e.g., https://www.linkedin.com/company/upwork/)

    Returns:
        Dict containing company data or error information
    """
    api_key = os.getenv("SCRAPINGDOG_API_KEY")
    if not api_key:
        return {
            "error": "SCRAPINGDOG_API_KEY not set",
            "hint": "Set env var: export SCRAPINGDOG_API_KEY=your_key"
        }

    company_id = _extract_linkedin_company_id(linkedin_url)
    if not company_id:
        return {"error": "Invalid LinkedIn company URL format"}

    try:
        response = requests.get(
            "https://api.scrapingdog.com/linkedin/",
            params={
                "api_key": api_key,
                "type": "company",
                "linkId": company_id
            },
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"✓ Scraped company: {company_id}")
        return data

    except requests.exceptions.HTTPError as e:
        return {
            "error": f"HTTP error: {e}",
            "status_code": response.status_code,
            "details": response.text[:500]
        }
    except json.JSONDecodeError:
        return {
            "error": "Invalid JSON response from Scrapingdog",
            "hint": "Check API key and credits",
            "raw": response.text[:500]
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}


def _extract_linkedin_company_id(linkedin_url: str) -> Optional[str]:
    """Extract company ID/slug from LinkedIn company URL.

    Examples:
        https://www.linkedin.com/company/upwork/ → upwork
        https://www.linkedin.com/company/123456/ → 123456
    """
    if not linkedin_url:
        return None
    
    try:
        parsed = urlparse(linkedin_url)
        parts = [p for p in parsed.path.split("/") if p]
        
        if "company" in parts:
            idx = parts.index("company")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        
        return parts[-1] if parts else None
    except Exception:
        return None


# LINKEDIN PROFILE SCRAPING
def _extract_linkedin_profile_id(linkedin_url: str) -> Optional[str]:
    """Extract profile ID/slug from LinkedIn profile URL.

    Examples:
        https://www.linkedin.com/in/williamhgates/ → williamhgates
        https://www.linkedin.com/in/john-doe-123456/ → john-doe-123456
    """
    if not linkedin_url:
        return None
    
    try:
        parsed = urlparse(linkedin_url)
        parts = [p for p in parsed.path.split("/") if p]
        
        if "in" in parts:
            idx = parts.index("in")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        
        return parts[-1] if parts else None
    except Exception:
        return None


def scrape_linkedin_profile(url: str, premium: bool = False) -> Dict[str, Any]:
    """Scrape LinkedIn profile using Scrapingdog API.

    Args:
        url: Full URL to LinkedIn profile (e.g., https://www.linkedin.com/in/williamhgates/)
        premium: Use premium API endpoint (default: False)

    Returns:
        Dict containing profile data or error information
    """
    if not url:
        return {"error": "linkedin_url is required"}
    
    api_key = os.getenv("SCRAPINGDOG_API_KEY")
    if not api_key:
        return {
            "error": "SCRAPINGDOG_API_KEY not set",
            "hint": "Set env var: export SCRAPINGDOG_API_KEY=your_key or add to .env file"
        }
    
    profile_id = _extract_linkedin_profile_id(url)
    if not profile_id:
        return {"error": "Invalid LinkedIn profile URL format"}
    
    params = {
        "api_key": api_key,
        "type": "profile",
        "id": profile_id,
        "premium": "true" if premium else "false"
    }
    
    try:
        response = requests.get("https://api.scrapingdog.com/profile", params=params, timeout=120)
        response.raise_for_status()
        data = response.json()
        result = data[0] if isinstance(data, list) and len(data) > 0 else data
        result["profile_id"] = profile_id
        result["scraping_method"] = "scrapingdog_api"
        
        print(f"✓ Scraped profile: {result.get('fullName', profile_id)}")
        return result
        
    except requests.exceptions.HTTPError as e:
        text = response.text if response else str(e)
        try:
            error_data = json.loads(text) if response else {}
            error_msg = error_data.get("message", "")
            
            if "will be scraped and stored" in error_msg or "try again after" in error_msg:
                return {
                    "error": "Profile is being cached",
                    "message": error_msg,
                    "profile_id": profile_id,
                    "hint": "Wait 2-3 minutes and try again",
                    "retry_after_seconds": 180
                }
        except:
            pass
        
        return {
            "error": f"HTTP error: {e}",
            "details": text[:500],
            "status": response.status_code if response else None
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response from Scrapingdog", "raw": response.text[:500]}



# GENERAL WEBSITE SCRAPING 
def scrape_website(url: str, use_browser: Optional[bool] = None, timeout: int = 30) -> Dict[str, Any]:
    """Scrape general website with intelligent change detection.

    Features:
    - Extracts clean main content (removes ads, navigation, boilerplate)
    - Generates content hash for change detection
    - Returns markdown format for LLM analysis
    - Extracts metadata, links, images
    - Automatic fallback between static/dynamic fetching

    Args:
        url: Target URL to scrape
        use_browser: Force browser rendering (default: from env WEBSITE_USE_BROWSER)
        timeout: Request timeout in seconds

    Returns:
        Dict containing:
        - url, final_url, status_code, fetched_at
        - title, meta_description, og_title, og_description
        - canonical_url, links, images
        - text (clean), content_markdown, content_hash
    """
    if not url:
        return {"error": "url is required"}

    # Get config from environment
    if use_browser is None:
        use_browser = os.getenv("WEBSITE_USE_BROWSER", "true").lower() in ("1", "true", "yes")
    headless = os.getenv("WEBSITE_HEADLESS", "true").lower() in ("1", "true", "yes")

    # Fetch HTML
    html, status, final_url = None, None, url
    try:
        if use_browser:
            html, status, final_url = _fetch_with_browser(url, headless, timeout)
        else:
            html, status, final_url = _fetch_static(url, timeout)
    except Exception as e:
        try:
            if use_browser:
                html, status, final_url = _fetch_static(url, timeout)
            else:
                html, status, final_url = _fetch_with_browser(url, headless, timeout)
        except Exception as e2:
            return {
                "error": f"Both fetch methods failed: {str(e)} | {str(e2)}",
                "url": url
            }

    if not html:
        return {"error": "Empty response", "url": url}

    # Extract all data
    metadata = _extract_metadata(html, final_url)
    content = _extract_content(html, final_url)
    content_hash = hashlib.sha256(content["text"].encode("utf-8")).hexdigest()

    result = {
        "url": url,
        "final_url": final_url,
        "status_code": status,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "html_length": len(html),
        "content_hash": content_hash,
        **metadata,
        **content,
    }

    print(f"✓ Scraped website: {url[:50]}... (hash: {content_hash[:8]})")
    return result


def _fetch_static(url: str, timeout: int) -> Tuple[str, int, str]:
    """Fetch page using requests (fast, no JS rendering)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    
    return response.text, response.status_code, str(response.url)


def _fetch_with_browser(url: str, headless: bool, timeout: int) -> Tuple[str, Optional[int], str]:
    """Fetch page using Playwright or Selenium (JS rendering support)."""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
            page = context.new_page()
            page.set_default_navigation_timeout(timeout * 1000)
            page.goto(url, wait_until="networkidle")
            
            html = page.content()
            final_url = page.url
            browser.close()
            
            return html, None, final_url
            
    except Exception as playwright_error:
        # Fallback to Selenium
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(timeout)
            driver.get(url)
            driver.implicitly_wait(3)
            
            html = driver.page_source
            final_url = driver.current_url
            driver.quit()
            
            return html, None, final_url
        except Exception:
            raise playwright_error


def _extract_metadata(html: str, base_url: str) -> Dict[str, Any]:
    """Extract page metadata, links, and images."""
    soup = BeautifulSoup(html, "lxml")
    
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    
    meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else None
    
    og_title_tag = soup.find("meta", property="og:title")
    og_title = og_title_tag.get("content", "").strip() if og_title_tag else None
    
    og_desc_tag = soup.find("meta", property="og:description")
    og_desc = og_desc_tag.get("content", "").strip() if og_desc_tag else None
    
    canonical_tag = soup.find("link", rel=lambda v: v and "canonical" in v)
    canonical = urljoin(base_url, canonical_tag["href"]) if canonical_tag and canonical_tag.get("href") else None
    
    # Extract links (absolute URLs, deduplicated, limited)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith(("javascript:", "#", "mailto:", "tel:")):
            links.append(urljoin(base_url, href))
    links = list(dict.fromkeys(links))[:500]  

    images = []
    for img in soup.find_all("img", src=True):
        images.append(urljoin(base_url, img["src"].strip()))
    images = list(dict.fromkeys(images))[:200]  # dedupe + limit
    
    return {
        "title": title,
        "meta_description": meta_desc,
        "og_title": og_title,
        "og_description": og_desc,
        "canonical_url": canonical,
        "links": links,
        "images": images,
    }


def _extract_content(html: str, url: str) -> Dict[str, Any]:
    """Extract clean main content using trafilatura.
    
    Returns both plain text (for hashing/comparison) and markdown (for analysis).
    """
    config = trafilatura.settings.use_config()
    
    # Extract clean text for change detection
    text = trafilatura.extract(
        html,
        url=url,
        favor_recall=True,
        config=config,
        output_format="txt",
    ) or ""
    
    # Extract markdown for LLM analysis
    markdown = trafilatura.extract(
        html,
        url=url,
        favor_recall=True,
        config=config,
        output_format="markdown",
    ) or ""
    
    return {
        "text": text,
        "text_length": len(text),
        "content_markdown": markdown,
    }

if __name__ == "__main__":
    import sys
    
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "company"
    
    # Default URLs for testing
    if len(sys.argv) > 2:
        url = sys.argv[2]
    else:
        defaults = {
            "company": "https://www.linkedin.com/company/upwork/",
            "profile": "https://www.linkedin.com/in/williamhgates/",
            "website": "https://www.cnbc.com/2024/10/21/stock-market-today-live-updates.html"
        }
        url = defaults.get(mode, "")
    
    # Execute scraping
    if mode == "company":
        result = scrape_linkedin_company(url)
    elif mode == "profile":
        result = scrape_linkedin_profile(url)
    elif mode == "website":
        use_browser = None
        if len(sys.argv) > 3:
            use_browser = sys.argv[3].lower() in ("1", "true", "yes")
        result = scrape_website(url, use_browser=use_browser)
    else:
        result = {
            "error": f"Unknown mode: {mode}",
            "usage": "python scraper.py [company|profile|website] [url] [use_browser]",
            "modes": {
                "company": "Scrape LinkedIn company page (Scrapingdog API)",
                "profile": "Scrape LinkedIn profile (hybrid: linkedin_scraper + Scrapingdog fallback)",
                "website": "Scrape general website"
            }
        }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))


