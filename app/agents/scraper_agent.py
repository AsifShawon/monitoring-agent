from celery import shared_task
from datetime import datetime
from app.database import Database
from bson import ObjectId
from app.agents.coordinator import run_monitoring_workflow
import json
import time

@shared_task(bind=True, max_retries=3)
def scrape_target(self, target_id: str, url: str, target_type: str):
    """Trigger monitoring workflow using LangGraph coordinator.
    
    For LinkedIn profiles, will auto-retry if profile needs caching.
    """
    print(f"🔍 Starting monitoring workflow for {url} ({target_type})")
    db = Database.get_sync_db()
    
    try:
        target = db.targets.find_one({"_id": ObjectId(target_id)})
        if not target:
            print(f"⚠️ Target {target_id} not found")
            return
        
        user_id = target.get("user_id")
        user = db.users.find_one({"_id": ObjectId(user_id)}) if user_id else None
        user_email = user.get("email") if user else None
        
        old_content = target.get("last_content")
        old_data = json.loads(old_content) if old_content else None
        
        result = run_monitoring_workflow(
            target_id=target_id,
            url=url,
            target_type=target_type,
            user_email=user_email,
            old_data=old_data
        )
        
        if not result["scrape_success"] and target_type == "linkedin_profile":
            error_msg = result.get("scrape_error", "")
            
            is_caching_error = (
                "being cached" in error_msg.lower() or 
                "try again after" in error_msg.lower() or
                "400 client error" in error_msg.lower() or
                "bad request" in error_msg.lower()
            )
            
            if is_caching_error:
                retry_after = 180  
                
                print(f"⏳ LinkedIn profile is being cached. Retrying in {retry_after} seconds...")
                print(f"   Error: {error_msg}")
                print(f"   Retry attempt: {self.request.retries + 1}/{self.max_retries}")
                
                raise self.retry(countdown=retry_after, exc=Exception(error_msg))
        
        if result["scrape_success"]:
            new_content = json.dumps(result["new_data"], sort_keys=True)
            
            db.targets.update_one(
                {"_id": ObjectId(target_id)},
                {"$set": {
                    "last_checked": datetime.utcnow(),
                    "last_content": new_content
                }}
            )
            
            if result["has_changes"]:
                db.changes.insert_one({
                    "target_id": ObjectId(target_id),
                    "timestamp": datetime.utcnow(),
                    "change_type": "content_update",
                    "severity": result["severity"],
                    "summary": result["summary"],
                    "key_changes": result["key_changes"],
                    "before": old_content[:500] if old_content else None,
                    "after": new_content[:500],
                    "notified": result["notification_sent"]
                })
                print(f"🔔 Change detected and logged for {url}")
            else:
                print(f"✓ No changes detected for {url}")
        else:
            print(f"❌ Scraping failed for {url}: {result.get('scrape_error')}")
        
        print("\n📝 Workflow Messages:")
        for msg in result.get("messages", []):
            print(f"  {msg.content}")
        
        print(f"\n✅ Monitoring workflow complete for {url}")

    except Exception as e:
        print(f"❌ Error in monitoring workflow for {url}: {e}")
        import traceback
        traceback.print_exc()
