
import os

from datetime import date
from flask import Flask, render_template, request, session, redirect, url_for
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from services.customer_service import register_customer
from flask import request, redirect, url_for, session

from services.auth_service import (
    authenticate_customer,
    authenticate_staff,
    get_current_staff_roles,
)


from services.document_service import (
    upload_claim_document,
    get_claim_documents,
    get_staff_claim_documents,
    review_claim_document,
)
from services.vehicle_service import (
    register_vehicle,
    get_customer_vehicles,
)

from services.policy_service import (
    create_policy,
    get_customer_policies,
    get_customer_claimable_policies,
)



from services.claim_service import (
    register_claim,
    get_customer_claims,
    get_customer_claim_details,
    get_staff_claim_queue,
    get_staff_claim_details,
    create_claim_assessment,
    get_claim_assessments,
    record_claim_decision,
)
from services.rules_service import get_claim_fraud_flags

from db import get_db_connection
from services.settlement_service import (
    create_settlement,
    process_payment,
)

# Load settings from the .env file
load_dotenv()

app = Flask(__name__)

app.config["CLAIM_UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "private_uploads",
    "claims",
)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


from functools import wraps

def staff_required(*allowed_roles):
    """Require an active staff account with a currently assigned role."""
    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            user_id = session.get("staff_user_id")

            if not isinstance(user_id, int):
                return redirect(url_for("staff_login_page"))

            try:
                current_roles = get_current_staff_roles(user_id)
            except Exception:
                app.logger.exception(
                    "Failed to verify current staff permissions"
                )
                return "Staff permissions could not be verified.", 503

            if not current_roles:
                session.pop("staff_user_id", None)
                session.pop("staff_username", None)
                session.pop("staff_name", None)
                session.pop("staff_roles", None)
                return redirect(url_for("staff_login_page"))

            if not any(role in current_roles for role in allowed_roles):
                return "You do not have permission to access this page.", 403

            return view_function(*args, **kwargs)

        return wrapped_view
    return decorator

@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        try:
            register_customer(
                full_name=request.form.get("full_name", ""),
                email=request.form.get("email", ""),
                phone=request.form.get("phone", ""),
                password=request.form.get("password", ""),
            )

            return render_template("registration_success.html"), 201

        
        except ValueError as error:
            return render_template(
                "register.html",
                error_message=str(error),
            ), 400

        except Exception:
            app.logger.exception("Customer registration failed")
            return "Registration could not be completed. Please try again.", 500

    return render_template("register.html")

# Configure Flask session security
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
csrf = CSRFProtect(app)



@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        try:
            customer = authenticate_customer(email, password)

            if customer is None:
                return render_template(
                    "login.html",
                    error_message="Invalid email or password.",
                ), 401

            session.clear()
            session["customer_id"] = customer["customer_id"]
            session["customer_name"] = customer["full_name"]
            session["customer_email"] = customer["email"]

            return redirect(url_for("customer_dashboard"))

        except Exception:
            app.logger.exception("Customer login failed")
            return (
                "Login could not be completed. Please try again.",
                500,
            )

    return render_template("login.html")

@app.route("/staff/login", methods=["GET", "POST"])
def staff_login_page():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        try:
            staff = authenticate_staff(username, password)

            if staff is None:
                return render_template(
                    "staff_login.html",
                    error_message="Invalid username or password.",
                ), 401

            session.clear()
            session["staff_user_id"] = staff["user_id"]
            session["staff_username"] = staff["username"]
            session["staff_name"] = staff["full_name"]
            session["staff_roles"] = staff["roles"]

            return redirect(url_for("staff_dashboard"))

        except Exception:
            app.logger.exception("Staff login failed")
            return (
                "Login could not be completed. Please try again.",
                500,
            )

    return render_template("staff_login.html")



@app.route("/staff/dashboard")
@staff_required(
    "Claims Officer",
    "Claims Assessor",
    "Claims Approver",
    "System Administrator",
    "Finance",
)
def staff_dashboard():
    try:
        claims = get_staff_claim_queue()

        return render_template(
            "staff_dashboard.html",
            staff_name=session.get("staff_name", "Staff Member"),
            staff_roles=session.get("staff_roles", []),
            claims=claims,
        )

    except Exception:
        app.logger.exception("Failed to load staff claims queue")
        return "Staff dashboard could not be loaded. Please try again.", 500

@app.route("/staff/claims/<int:claim_id>")
@staff_required(
    "Claims Officer",
    "Claims Assessor",
    "Claims Approver",
    "System Administrator",
    "Finance",
)
def staff_claim_details_page(claim_id):
    try:
        claim = get_staff_claim_details(claim_id)

        if claim is None:
            return "Claim not found.", 404

        documents = get_staff_claim_documents(claim_id)
        assessments = get_claim_assessments(claim_id)
        fraud_flags = get_claim_fraud_flags(claim_id)

        return render_template(
    "staff_claim_details.html",
    claim=claim,
    documents=documents,
    assessments=assessments,
    fraud_flags=fraud_flags,
    staff_name=session.get("staff_name", "Staff Member"),
    staff_roles=session.get("staff_roles", []),
)

    except Exception:
        app.logger.exception("Failed to load staff claim details")
        return "Claim details could not be loaded. Please try again.", 500


@app.route(
    "/staff/claims/<int:claim_id>/assessment",
    methods=["POST"],
)
@staff_required("Claims Assessor")
def submit_claim_assessment(claim_id):
    """Submit an assessment for a claim."""
    damage_description = request.form.get(
        "damage_description", ""
    ).strip()

    estimated_repair_cost = request.form.get(
        "estimated_repair_cost", ""
    ).strip()

    recommendation = request.form.get(
        "recommendation", ""
    ).strip()

    assessment_notes = request.form.get(
        "assessment_notes", ""
    ).strip()

    if not damage_description:
        return "Damage description is required.", 400

    if not estimated_repair_cost:
        return "Estimated repair cost is required.", 400

    try:
        assessment_id = create_claim_assessment(
            claim_id=claim_id,
            assessor_id=session["staff_user_id"],
            damage_description=damage_description,
            estimated_repair_cost=estimated_repair_cost,
            recommendation=recommendation,
            assessment_notes=assessment_notes or None,
        )
    except ValueError as exc:
        return str(exc), 400
    except Exception:
        app.logger.exception(
            "Failed to save assessment for claim %s",
            claim_id,
        )
        return "Unable to save the assessment. Please try again.", 500

    app.logger.info(
        "Assessment %s created for claim %s",
        assessment_id,
        claim_id,
    )

    return redirect(
        url_for(
            "staff_claim_details_page",
            claim_id=claim_id,
        )
    )

@app.route(
    "/staff/claims/<int:claim_id>/decision",
    methods=["POST"],
)
@staff_required("Claims Approver")
def submit_claim_decision(claim_id):
    """Record the final decision made by a Claims Approver."""

    decision = request.form.get("decision", "").strip()
    reason = request.form.get("reason", "").strip()

    if not decision:
        return "A claim decision is required.", 400

    if not reason:
        return "A decision reason is required.", 400

    try:
        decision_id = record_claim_decision(
            claim_id=claim_id,
            approver_id=session["staff_user_id"],
            decision=decision,
            reason=reason,
        )

    except ValueError as exc:
        return str(exc), 400

    except Exception:
        app.logger.exception(
            "Failed to record decision for claim %s",
            claim_id,
        )
        return (
            "Unable to record the claim decision. Please try again.",
            500,
        )

    app.logger.info(
        "Decision %s recorded for claim %s",
        decision_id,
        claim_id,
    )

    return redirect(
        url_for(
            "staff_claim_details_page",
            claim_id=claim_id,
        )
    )

@app.route(
    "/staff/claims/<int:claim_id>/settlement",
    methods=["POST"],
)
@staff_required("Finance")
def create_claim_settlement_page(claim_id):
    """Create a pending settlement for an approved claim."""

    amount_text = request.form.get("approved_amount", "").strip()

    if not amount_text:
        return "An approved settlement amount is required.", 400

    try:
        settlement_id = create_settlement(
            claim_id=claim_id,
            approved_amount=amount_text,
            created_by=session["staff_user_id"],
        )

    except ValueError as exc:
        return str(exc), 400

    except Exception:
        app.logger.exception(
            "Failed to create settlement for claim %s",
            claim_id,
        )
        return (
            "Unable to create the settlement. Please try again.",
            500,
        )

    app.logger.info(
        "Settlement %s created for claim %s",
        settlement_id,
        claim_id,
    )

    return redirect(
        url_for(
            "staff_claim_details_page",
            claim_id=claim_id,
        )
    )

@app.route(
    "/staff/settlements/<int:settlement_id>/payment",
    methods=["POST"],
)
@staff_required("Finance")
def process_settlement_payment_page(settlement_id):
    payment_reference = request.form.get(
        "payment_reference", ""
    ).strip()

    payment_method = request.form.get(
        "payment_method", ""
    ).strip()

    if not payment_reference or not payment_method:
        return "Payment reference and method are required.", 400

    # Find the claim before recording payment.
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT claim_id
                    FROM settlements
                    WHERE settlement_id = %s
                    """,
                    (settlement_id,),
                )
                row = cur.fetchone()

        if row is None:
            return "Settlement not found.", 404

        claim_id = row[0]

        process_payment(
            settlement_id=settlement_id,
            payment_reference=payment_reference,
            payment_method=payment_method,
            processed_by=session["staff_user_id"],
        )

    except ValueError as exc:
        return str(exc), 400
    except Exception:
        app.logger.exception(
            "Failed to process payment for settlement %s",
            settlement_id,
        )
        return (
            "Unable to record the payment. Please try again.",
            500,
        )

    app.logger.info(
        "Payment recorded for settlement %s",
        settlement_id,
    )

    return redirect(
        url_for("staff_claim_details_page", claim_id=claim_id)
    )

@app.route(
    "/staff/claims/<int:claim_id>/documents/<int:document_id>/review",
    methods=["POST"],
)
@staff_required("Claims Officer", "Claims Assessor")
def review_claim_document_page(claim_id, document_id):
    verification_status = request.form.get(
        "verification_status", ""
    ).strip()

    review_notes = request.form.get("review_notes", "").strip()

    if verification_status not in {
        "VERIFIED",
        "REJECTED",
        "RESUBMISSION_REQUIRED",
    }:
        return "Invalid document verification status.", 400

    if len(review_notes) > 2000:
        return "Review notes must be 2000 characters or fewer.", 400

    try:
        claim = get_staff_claim_details(claim_id)

        if claim is None:
            return "Claim not found.", 404

        documents = get_staff_claim_documents(claim_id)

        document_exists = any(
            document["document_id"] == document_id
            for document in documents
        )

        if not document_exists:
            return "Document not found for this claim.", 404

        review_claim_document(
            document_id=document_id,
            reviewer_id=session["staff_user_id"],
            verification_status=verification_status,
            review_notes=review_notes or None,
        )

        return redirect(
            url_for(
                "staff_claim_details_page",
                claim_id=claim_id,
            )
        )

    except ValueError as exc:
        return str(exc), 400
    except Exception:
        app.logger.exception("Failed to review claim document")
        return "Document review could not be completed.", 500


@app.route("/staff/logout")
def staff_logout_page():
    session.pop("staff_user_id", None)
    session.pop("staff_username", None)
    session.pop("staff_name", None)
    session.pop("staff_roles", None)

    return redirect(url_for("staff_login_page"))


@app.route("/dashboard")
def customer_dashboard():
    if "customer_id" not in session:
        return redirect(url_for("login_page"))

    try:
        customer_id = session["customer_id"]

        vehicles = get_customer_vehicles(customer_id)
        policies = get_customer_policies(customer_id)
        claims = get_customer_claims(customer_id)

        return render_template(
            "dashboard.html",
            customer_name=session["customer_name"],
            customer_email=session["customer_email"],
            vehicles=vehicles,
            policies=policies,
            claims=claims,
        )

    except Exception:
        app.logger.exception("Failed to load customer dashboard")
        return "Dashboard could not be loaded. Please try again.", 500
@app.route("/vehicles/register", methods=["GET", "POST"])
def vehicle_registration_page():
    if "customer_id" not in session:
        return redirect(url_for("login_page"))

    if request.method == "POST":
        try:
            year_input = request.form.get("manufacturing_year", "").strip()

            vehicle = register_vehicle(
                customer_id=session["customer_id"],
                registration_number=request.form.get(
                    "registration_number", ""
                ),
                make=request.form.get("make", ""),
                model=request.form.get("model", ""),
                manufacturing_year=year_input or None,
            )

            return (
                "Vehicle registered successfully! "
                f"Registration number: {vehicle['registration_number']}"
            ), 201

        except ValueError as error:
            return render_template(
                "vehicle_register.html",
                error_message=str(error),
            ), 400

        except Exception:
            app.logger.exception("Vehicle registration failed")
            return (
                "Vehicle registration could not be completed. "
                "Please try again.",
                500,
            )

    return render_template("vehicle_register.html")

@app.route("/policies/create", methods=["GET", "POST"])
def policy_creation_page():
    if "customer_id" not in session:
        return redirect(url_for("login_page"))

    customer_id = session["customer_id"]

    try:
        vehicles = get_customer_vehicles(customer_id)

        if request.method == "POST":
            try:
                vehicle_id = int(request.form.get("vehicle_id", ""))

                policy = create_policy(
                    customer_id=customer_id,
                    vehicle_id=vehicle_id,
                    coverage_details=request.form.get(
                        "coverage_details", ""
                    ),
                    premium_amount=request.form.get(
                        "premium_amount", ""
                    ),
                    start_date=request.form.get("start_date", ""),
                    expiry_date=request.form.get("expiry_date", ""),
                )

                return (
                    "Policy created successfully! "
                    f"Policy number: {policy['policy_number']} "
                    f"Status: {policy['status']}"
                ), 201

            except ValueError as error:
                return render_template(
                    "policy_create.html",
                    vehicles=vehicles,
                    error_message=str(error),
                ), 400

        return render_template(
            "policy_create.html",
            vehicles=vehicles,
        )

    except Exception:
        app.logger.exception("Policy creation failed")
        return (
            "Policy creation could not be completed. Please try again.",
            500,
        )
    
@app.route("/claims/register", methods=["GET", "POST"])
def claim_registration_page():
    if "customer_id" not in session:
        return redirect(url_for("login_page"))

    customer_id = session["customer_id"]

    try:
        policies = get_customer_claimable_policies(customer_id)

        if request.method == "POST":
            try:
                policy_id = int(request.form.get("policy_id", ""))

                claim = register_claim(
                    customer_id=customer_id,
                    policy_id=policy_id,
                    incident_date=request.form.get("incident_date", ""),
                    incident_description=request.form.get(
                        "incident_description", ""
                    ),
                    claimed_amount=request.form.get("claimed_amount", ""),
                )

                return (
                    "Claim registered successfully! "
                    f"Claim number: {claim['claim_number']} "
                    f"Status: {claim['status']}"
                ), 201

            except (ValueError, TypeError) as error:
                return render_template(
                    "claim_register.html",
                    policies=policies,
                    error_message=str(error),
                    now_date=date.today().isoformat(),
                ), 400

        return render_template(
            "claim_register.html",
            policies=policies,
            now_date=date.today().isoformat(),
        )

    except Exception:
        app.logger.exception("Claim registration failed")
        return (
            "Claim registration could not be completed. Please try again.",
            500,
        )
    
@app.route("/claims/<int:claim_id>")
def claim_details_page(claim_id):
    if "customer_id" not in session:
        return redirect(url_for("login_page"))

    try:
        customer_id = session["customer_id"]

        claim = get_customer_claim_details(
            customer_id=customer_id,
            claim_id=claim_id,
        )
        documents = get_claim_documents(
    customer_id=customer_id,
    claim_id=claim_id,
)

        if claim is None:
            return "Claim not found.", 404

        return render_template(
            "claim_details.html",
            claim=claim,
            customer_name=session["customer_name"],
            documents=documents,
        )

    except Exception:
        app.logger.exception("Failed to load claim details")
        return "Claim details could not be loaded. Please try again.", 500


@app.route(
    "/claims/<int:claim_id>/documents/upload",
    methods=["POST"],
)
def upload_claim_document_page(claim_id):
    if "customer_id" not in session:
        return redirect(url_for("login_page"))

    uploaded_file = request.files.get("document")
    document_type = request.form.get("document_type", "")

    try:
        result = upload_claim_document(
            customer_id=session["customer_id"],
            claim_id=claim_id,
            document_type=document_type,
            uploaded_file=uploaded_file,
            upload_folder=app.config["CLAIM_UPLOAD_FOLDER"],
        )

        return redirect(
            url_for("claim_details_page", claim_id=claim_id)
        )

    except ValueError as error:
        app.logger.warning("Document upload rejected: %s", error)

        return (
            str(error),
            400,
        )

    except Exception:
        app.logger.exception("Document upload failed")
        return "Document upload failed. Please try again.", 500

@app.route("/logout", methods=["GET", "POST"])
def logout_page():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/")
def home():
        return render_template("home.html")


@app.route("/health/db")
def database_health():
    try:
        with get_db_connection() as connection:
            connection.execute("SELECT 1")

        return {"database": "connected"}, 200

    except Exception:
        app.logger.exception("Database health check failed")
        return {"database": "unavailable"}, 503



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)