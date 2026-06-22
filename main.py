# ─────────────────────────────────────────────────────────────
# main.py — Run this to see everything work end-to-end
# ─────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()  # noqa
from dynamic_email import (
    create_conversation,
    send_rfq_email,
    build_dynamic_email,
    parse_dynamic_email,
)

# Simulate: User 42 wants to source Bluetooth Speakers

user_id = "42"
supplier_email = "purchasing@acme-electronics.com"
supplier_name = "Acme Electronics"

# 1. Create a new conversation → gets its own email address
conversation = create_conversation(user_id, supplier_email)

conv_id = conversation["conv_id"]
email_address = conversation["email_address"]

print(f"\nConversation created:")
print(f"  Address: {email_address}")
# → usr42_conv3fa9c1b2@mail.yourdomain.com

# 2. Send the RFQ from that dynamic address
result = send_rfq_email(
    user_id=user_id,
    conv_id=conv_id,
    supplier_email=supplier_email,
    supplier_name=supplier_name,
    product_name="Bluetooth Speaker Model X200",
    quantity=500,
    target_price="$12.00",
)

print(f"\nEmail sent:")
print(f"  From:   {result['from']}")
print(f"  To:     {result['to']}")
print(f"  Status: {result['status_code']}")

# 3. When supplier hits Reply:
#    - Their reply goes to: usr42_conv3fa9c1b2@mail.yourdomain.com
#    - SendGrid catches it (via MX record)
#    - SendGrid POSTs to: https://yourapp.com/webhooks/inbound
#    - Your webhook parses user_id=42, conv_id=3fa9c1b2
#    - Triggers negotiation agent

# 4. Parse test — verify your regex works correctly
test_address = f"usr{user_id}_conv{conv_id}@mail.yourdomain.com"
parsed = parse_dynamic_email(test_address)

print(f"\nParse test:")
print(f"  Input:   {test_address}")
print(f"  user_id: {parsed['user_id']}")  # → 42
print(f"  conv_id: {parsed['conv_id']}")  # → 3fa9c1b2


# ─────────────────────────────────────────────────────────────
# Start the FastAPI server (receives inbound emails from SendGrid)
# ─────────────────────────────────────────────────────────────

# Run with:
# uvicorn main:app --host 0.0.0.0 --port 8000 --reload
