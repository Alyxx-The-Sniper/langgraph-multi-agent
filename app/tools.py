# app/tools.py
import requests
import random
from airtable import Airtable
from langchain_core.tools import tool

# Import the settings instance
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
    print(f"🔥 FAILED to initialize Airtable: {e}")
    airtable_client = None

# ==============================================================================
# "REAL" TOOLS
# ==============================================================================

@tool
def get_order_status_tool(tracking_no: str) -> dict:
    """Retrieves the current status of the given tracking number."""

    print(f"      [TOOL]: get_order_status_tool(tracking_no={tracking_no})")
    try:
        res = requests.get(f"https://fakestoreapi.com/carts/{tracking_no}", timeout=5) # timeout 5 / wait 5 seconds to response
        res.raise_for_status() # Checks if the HTTP request was successful (status codes 200-299)
                               # If not, it raises an exception, which is caught by the except block.
        data = res.json()      # Converts the successful HTTP response content (which is expected to be JSON) into a Python dictionary.
        return {
            "tracking_no": tracking_no,
            "status": random.choice(["processing", "shipped", "delivered"]),
            "order_date": data.get("date"),
            "products": data.get("products")
        }
    except Exception as e:     # Handles any errors (e.g., network timeout, invalid URL, or HTTP errors caught by raise_for_status).
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

    # generate a random dummy customer ID
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

def post_to_slack(ticket_id: str, concern: str):
    """Helper function to send the alert to Slack."""
    try:
        payload = {
            "text": f"🚨 New Support Ticket: {ticket_id}",
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": "🚨 *New AI-Escalated Support Ticket* 🚨"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Ticket ID:*\n`{ticket_id}`"},
                    {"type": "mrkdwn", "text": f"*Status:*\nNew (View in Airtable)"}
                ]},
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Customer Concern:*\n```{concern}```"}}
            ]
        }
        requests.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=5)
        print("      [Tool]: Slack alert sent successfully.")
    except Exception as e:
        print(f"      [Tool Warning]: Failed to send Slack alert: {e}")

@tool
def create_support_ticket_tool(customer_concern: str) -> dict:
    """
    Use this tool for any request that requires human intervention.
    This includes:
    - Any modification request (cancellation, addition, updating, deletion).
    - Any topic not covered by other tools (e.g., account settings, complaints).
    """

    print(f"\n      [Tool]: create_support_ticket_tool called with concern: '{customer_concern}'")
    ticket_id = f"T-{random.randint(1000, 9999)}"
    
    try:
        # --- 1. Create Ticket in Airtable ---
        if airtable_client:
            print("      [Tool]: Creating record in Airtable...")
            new_record = {
                "TicketID": ticket_id,
                "Customer Concern": customer_concern,
                "Status": "New"
            }
            created_record = airtable_client.insert(new_record)
            print(f"      [Tool]: Airtable record created: {created_record['id']}")
        else:
            print("      [Tool Warning]: Airtable client not initialized. Skipping record creation.")

        # --- 2. Send Alert to Slack ---
        post_to_slack(ticket_id=ticket_id, concern=customer_concern)
        
        # --- 3. Return Confirmation to the AI ---
        return {
            "TicketId": ticket_id,
            "Concern": customer_concern,
            "Status": "created",
        }
    except Exception as e:
        print(f"      [Tool Error]: Failed to create ticket: {e}")
        post_to_slack(ticket_id="--FAILED--", concern=f"TICKETING SYSTEM ERROR: {e}\nQuery: {customer_concern}")
        return {"error": f"Failed to create ticket: {e}"}