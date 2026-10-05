from unittest.mock import patch

from flask import Flask, jsonify
from app import app as flask_app, staff_required

flask_app.config["TESTING"] = True
flask_app.config["SECRET_KEY"] = "test-only-secret"


def create_test_app():
    test_app = Flask(__name__)
    test_app.secret_key = "test-only-secret"

    # Temporary login route for the isolated test app.
    @test_app.route("/staff/login")
    def staff_login_page():
        return "Test login page", 200

    # Finance-only test route.
    @test_app.route("/finance-test")
    @staff_required("Finance")
    def finance_test():
        return jsonify({"message": "Finance access allowed"})

    return test_app


def test_unauthenticated_user_is_redirected():
    test_app = create_test_app()

    with test_app.test_client() as client:
        response = client.get("/finance-test")

    assert response.status_code == 302


def test_claims_officer_is_denied():
    test_app = create_test_app()

    with test_app.test_client() as client:
        with client.session_transaction() as sess:
            sess["staff_user_id"] = 1

        with patch("app.get_current_staff_roles", return_value=["Claims Officer"]):
            response = client.get("/finance-test")

    assert response.status_code == 403


def test_finance_user_is_allowed():
    test_app = create_test_app()

    with test_app.test_client() as client:
        with client.session_transaction() as sess:
            sess["staff_user_id"] = 4

        with patch("app.get_current_staff_roles", return_value=["Finance"]):
            response = client.get("/finance-test")

    assert response.status_code == 200
    

def test_payment_route_rejects_missing_csrf_token():
    # Use a separate test client with CSRF protection enabled.
    flask_app.config["WTF_CSRF_ENABLED"] = True

    try:
        with flask_app.test_client() as client:
            response = client.post(
                "/staff/settlements/1/payment",
                data={
                    "payment_reference": "TEST-DO-NOT-PAY",
                    "payment_method": "UPI",
                },
            )

        assert response.status_code == 400
        assert b"CSRF" in response.data

    finally:
        # Restore the setting used by the other permission tests.
        flask_app.config["WTF_CSRF_ENABLED"] = False
    
def test_claims_officer_cannot_access_actual_payment_route():
    with flask_app.test_client() as client:
        with client.session_transaction() as sess:
            sess["staff_user_id"] = 1

        with patch(
            "app.get_current_staff_roles",
            return_value=["Claims Officer"],
        ):
            response = client.post(
                "/staff/settlements/1/payment",
                data={
                    "payment_reference": "TEST-DO-NOT-PAY",
                    "payment_method": "UPI",
                },
            )

    assert response.status_code == 403
    assert b"permission" in response.data.lower()