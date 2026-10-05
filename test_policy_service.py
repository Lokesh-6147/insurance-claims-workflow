
from services.policy_service import create_policy


try:
    policy = create_policy(
        customer_id=2,
        vehicle_id=1,
        coverage_details="Sample comprehensive vehicle coverage",
        premium_amount="15000.00",
        start_date="2026-10-03",
        expiry_date="2027-10-03",
    )

    print("Policy created successfully!")
    print("Policy number:", policy["policy_number"])
    print("Customer ID:", policy["customer_id"])
    print("Vehicle ID:", policy["vehicle_id"])
    print("Premium:", policy["premium_amount"])
    print("Status:", policy["status"])

except ValueError as error:
    print("Validation error:", error)

except Exception as error:
    print("Unexpected error:", error)