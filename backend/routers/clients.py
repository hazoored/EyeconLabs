"""
EyeconBumps Web App - Client API Router
Endpoints for client portal
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from auth import require_client
from database import db

router = APIRouter(prefix="/client", tags=["Client"])

# ============ DASHBOARD ============

@router.get("/dashboard")
async def get_dashboard(current_user: dict = Depends(require_client)):
    """Get client dashboard."""
    client_id = current_user['client_id']
    client = current_user['client']
    
    # Get accounts
    accounts = db.get_client_accounts(client_id)
    
    # Get campaigns
    campaigns = db.get_client_campaigns(client_id)
    
    # Get analytics
    analytics = db.get_client_analytics(client_id, days=30)
    
    return {
        "client": {
            "id": client['id'],
            "name": client['name'],
            "subscription_type": client.get('subscription_type', 'starter'),
            "expires_at": client.get('expires_at')
        },
        "stats": {
            "total_accounts": len(accounts),
            "total_campaigns": len(campaigns),
            "active_campaigns": len([c for c in campaigns if c.get('status') == 'running']),
            "totals": analytics.get('totals', {})
        }
    }

# ============ CAMPAIGNS ============

@router.get("/campaigns")
async def list_campaigns(current_user: dict = Depends(require_client)):
    """Get client's campaigns."""
    client_id = current_user['client_id']
    campaigns = db.get_client_campaigns(client_id)
    return {"campaigns": campaigns}

@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int, current_user: dict = Depends(require_client)):
    """Get campaign details."""
    client_id = current_user['client_id']
    campaigns = db.get_client_campaigns(client_id)
    
    campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {"campaign": campaign}

class CreateClientCampaignRequest(BaseModel):
    name: str
    message_content: Optional[str] = None
    message_type: str = "text"
    delay_seconds: int = 30
    template_id: Optional[int] = None  # Use saved template
    account_ids: Optional[List[int]] = None  # Multiple accounts for campaign

@router.post("/campaigns")
async def create_campaign(data: CreateClientCampaignRequest, current_user: dict = Depends(require_client)):
    """Create a new campaign for this client."""
    client_id = current_user['client_id']
    
    # Verify accounts belong to client if specified
    if data.account_ids:
        client_accounts = db.get_client_accounts(client_id)
        client_account_ids = {acc['id'] for acc in client_accounts}
        for acc_id in data.account_ids:
            if acc_id not in client_account_ids:
                raise HTTPException(status_code=400, detail=f"Invalid account ID: {acc_id}")
    
    # Verify template belongs to client if specified
    if data.template_id:
        template = db.get_template_by_id(data.template_id)
        if not template or template.get('client_id') != client_id:
            raise HTTPException(status_code=400, detail="Invalid template")
    
    # For multi-account, store account_ids as JSON or use first account
    account_id = data.account_ids[0] if data.account_ids and len(data.account_ids) == 1 else None
    
    campaign = db.create_campaign(
        client_id=client_id,
        name=data.name,
        target_groups=[],
        message_type=data.message_type,
        message_content=data.message_content,
        delay_seconds=data.delay_seconds,
        account_id=account_id,
        template_id=data.template_id
    )
    
    # If multiple accounts, store the account IDs with the campaign
    if data.account_ids and len(data.account_ids) > 1:
        # Store multiple account IDs in campaign metadata or separate table
        # For now, update the campaign to indicate multiple accounts
        import json
        db.update_campaign({
            'id': campaign['id'],
            'account_ids_json': json.dumps(data.account_ids)
        })
    
    return {"message": "Campaign created", "campaign": campaign}

@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: int, current_user: dict = Depends(require_client)):
    """Start a client campaign."""
    from broadcaster import get_broadcaster
    
    client_id = current_user['client_id']
    campaigns = db.get_client_campaigns(client_id)
    
    if not any(c['id'] == campaign_id for c in campaigns):
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign = db.get_campaign_by_id(campaign_id)
    if campaign.get('status') == 'running':
        raise HTTPException(status_code=400, detail="Campaign already running")
    
    broadcaster = get_broadcaster(db)
    await broadcaster.start_campaign_async(campaign_id)  # parallel=True by default
    
    return {"message": "Campaign started"}

@router.post("/campaigns/{campaign_id}/stop")
async def stop_campaign(campaign_id: int, current_user: dict = Depends(require_client)):
    """Stop a client campaign."""
    from broadcaster import get_broadcaster
    
    client_id = current_user['client_id']
    campaigns = db.get_client_campaigns(client_id)
    
    if not any(c['id'] == campaign_id for c in campaigns):
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    broadcaster = get_broadcaster(db)
    broadcaster.stop_campaign(campaign_id)
    db.update_campaign_status(campaign_id, "stopped")
    
    return {"message": "Campaign stopped"}

@router.get("/templates")
async def list_templates(current_user: dict = Depends(require_client)):
    """Get client's message templates."""
    client_id = current_user['client_id']
    templates = db.get_client_templates(client_id)
    return {"templates": templates}

# ============ ANALYTICS ============

@router.get("/analytics")
async def get_analytics(days: int = 30, current_user: dict = Depends(require_client)):
    """Get client's comprehensive analytics."""
    client_id = current_user['client_id']
    
    # Get all analytics data
    basic_analytics = db.get_client_analytics(client_id, days=days)
    group_stats = db.get_client_group_stats(client_id, days=days)
    account_stats = db.get_client_account_stats(client_id, days=days)
    hourly_stats = db.get_client_hourly_stats(client_id, days=min(days, 7))
    campaign_history = db.get_client_campaign_history(client_id)
    
    return {
        **basic_analytics,
        "groups": group_stats,
        "accounts": account_stats,
        "hourly": hourly_stats,
        "campaigns": campaign_history
    }

# ============ ACCOUNTS ============

class AddClientAccountRequest(BaseModel):
    phone_number: str
    session_string: str
    display_name: Optional[str] = None
    is_premium: bool = False

@router.get("/accounts")
async def list_accounts(current_user: dict = Depends(require_client)):
    """Get client's accounts."""
    client_id = current_user['client_id']
    accounts = db.get_client_accounts(client_id)
    
    # Return account info (with full phone for their own accounts)
    client_accounts = [
        {
            "id": acc['id'],
            "phone_number": acc['phone_number'],
            "display_name": acc.get('display_name'),
            "is_premium": acc.get('is_premium', 0),
            "is_active": acc.get('is_active', 1),
            "created_at": acc.get('created_at')
        }
        for acc in accounts
    ]
    
    return {"accounts": client_accounts}

@router.post("/accounts")
async def add_account(data: AddClientAccountRequest, current_user: dict = Depends(require_client)):
    """Add an account for this client."""
    client_id = current_user['client_id']
    
    account = db.add_account(
        phone_number=data.phone_number,
        session_string=data.session_string,
        display_name=data.display_name,
        is_premium=data.is_premium,
        client_id=client_id  # Always assign to current client
    )
    
    return {"message": "Account added successfully", "account": account}

@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, current_user: dict = Depends(require_client)):
    """Delete an account (only if owned by this client)."""
    client_id = current_user['client_id']
    
    # Verify account belongs to this client
    accounts = db.get_client_accounts(client_id)
    if not any(acc['id'] == account_id for acc in accounts):
        raise HTTPException(status_code=404, detail="Account not found")
    
    success = db.delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return {"message": "Account deleted"}

# ============ PROFILE ============

@router.get("/profile")
async def get_profile(current_user: dict = Depends(require_client)):
    """Get client profile."""
    client = current_user['client']
    return {
        "id": client['id'],
        "name": client['name'],
        "telegram_username": client.get('telegram_username'),
        "subscription_type": client.get('subscription_type', 'starter'),
        "expires_at": client.get('expires_at'),
        "created_at": client.get('created_at')
    }
