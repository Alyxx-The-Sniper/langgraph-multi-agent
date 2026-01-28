import requests
import random
from airtable import Airtable
from langchain_core.tools import tool
from .config import settings

# --- Initialize Airtable Client ---
try:
    airtable_client = Airtable(
        settings.AIRTABLE_BASE_ID,
        "Tickets", 
        api_key=settings.AIRTABLE_TOKEN
    )
    print("✅ Airtable client initialized.")
except Exception as e:
    print(f"⚠️ FAILED to initialize Airtable: {e}. (Make sure your Base ID and Token are correct)")
    airtable_client = None

# ==============================================================================
# "REAL" TOOLS
# ==============================================================================

@tool
def get_order_status_tool(tracking_no: str) -> dict:
    """Retrieves the current status of the given tracking number."""
    print(f"      [TOOL]: get_order_status_tool(tracking_no={tracking_no})")
    try:
        res = requests.get(f"https://fakestoreapi.com/carts/{tracking_no}", timeout=5) 
        res.raise_for_status() 
        data = res.json()      
        return {
            "tracking_no": tracking_no,
            "status": random.choice(["processing", "shipped", "delivered"]),
            "order_date": data.get("date"),
            "products": data.get("products")
        }
    except Exception as e:    
        return {"error": f"Failed to get order: {e}"}

@tool
def get_refund_status_tool(tracking_no: str) -> dict:
    """Retrieves the status of a refund for a given tracking number."""
    print(f"      [TOOL]: get_refund_status_tool(tracking_no={tracking_no})")
    try:
        status = random.choice(["refund_requested", "refund_processed", "no_refund_found"])
        if status == "refund_processed":
            return {
                "tracking_no": tracking_no,
                "status": status,
                "amount": round(random.uniform(10, 200), 2),
            }
        else:
            return {"tracking_no": tracking_no, "status": status}
    except Exception as e:
        return {"error": f"Failed to get refund: {e}"}

@tool
def get_payment_details_tool() -> dict:
    """Retrieves the payment methods  or details."""
    customer_id = round(random.uniform(1, 5))
    print(f"      [TOOL]: get_payment_details_tool(customer_id={customer_id})")
    url = f"https://dummyjson.com/users/{customer_id}"
    try:
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()
        return {
            "customer_id": customer_id,
            "customer_name": f"{data.get('firstName')} {data.get('lastName')}",
            "payment_methods": [
                {"type": "Visa", "last_four": str(random.randint(1000, 9999))},
            ]
        }
    except Exception as e:
        return {"error": f"Failed to get payment details: {e}"}

def post_to_slack(ticket_id: str, concern: str, record_url: str):
    payload = {
        "text": f"🚨 New Ticket: {ticket_id}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "🚨 New AI-Escalated Ticket"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*ID:*\n`{ticket_id}`"},
                    {"type": "mrkdwn", "text": f"*Status:*\nNew"}
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Concern:*\n```{concern}```"}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View in Airtable"},
                        "url": record_url, # The link we built
                        "action_id": "view_record"
                    }
                ]
            }
        ]
    }
    requests.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=5)

# @tool
# def create_support_ticket_tool(customer_concern: str) -> dict:
#     """
#     Use this tool for any request that requires human intervention.
#     This includes:
#     - Any modification request (cancellation, addition, updating, deletion).
#     - Any topic not covered by other tools (e.g., account settings, complaints).
#     """

#     print(f"\n      [Tool]: create_support_ticket_tool called with concern: '{customer_concern}'")
#     ticket_id = f"T-{random.randint(1000, 9999)}"
    
#     try:
#         # --- 1. Create Ticket in Airtable ---
#         if airtable_client:
#             print("      [Tool]: Creating record in Airtable...")
#             new_record = {
#                 "TicketID": ticket_id,
#                 "Customer Concern": customer_concern,
#                 "Status": "New"
#             }
#             try:
#                 created_record = airtable_client.insert(new_record)
#                 print(f"      [Tool]: Airtable record created: {created_record['id']}")
#             except Exception as inner_e:
#                 print(f"      [Tool Error]: Airtable insert failed: {inner_e}")
#         else:
#             print("      [Tool Warning]: Airtable client not initialized. Skipping record creation.")

#         # --- 2. Send Alert to Slack ---
#         post_to_slack(ticket_id=ticket_id, concern=customer_concern)
        
#         # --- 3. Return Confirmation to the AI ---
#         return {
#             "TicketId": ticket_id,
#             "Concern": customer_concern,
#             "Status": "created",
#         }
#     except Exception as e:
#         print(f"      [Tool Error]: Failed to create ticket: {e}")
#         post_to_slack(ticket_id="--FAILED--", concern=f"TICKETING SYSTEM ERROR: {e}\nQuery: {customer_concern}")
#         return {"error": f"Failed to create ticket: {e}"}


@tool
def create_support_ticket_tool(customer_concern: str) -> dict:
    '''Use this tool for any request that requires human intervention.'''
    # Your Table ID from the browser URL
    TABLE_ID = "tbl1Ofj4TRzUzYEkP" 

    try:
        if airtable_client:
            new_record_data = {"Customer Concern": customer_concern, "Status": "New"}
            created_record = airtable_client.insert(new_record_data)

            # Capture IDs from response
            internal_id = created_record.get('id') # The 'rec...' ID
            friendly_id = created_record.get('fields', {}).get('TicketID', internal_id)
            
            # Construct the Deep Link URL
            record_url = f"https://airtable.com/{settings.AIRTABLE_BASE_ID}/{TABLE_ID}/{internal_id}"

            # Pass the link to Slack
            post_to_slack(ticket_id=friendly_id, concern=customer_concern, record_url=record_url)
            
            return {
                "TicketId": friendly_id,
                "Status": "created",
                "Link": record_url # AI can now show this to the user too
            }
        else:
            return {"error": "Airtable client not initialized."}

    except Exception as e:
        print(f"      [Tool Error]: {e}")
        return {"error": f"Failed to create ticket: {e}"}