
-- ==========================================
-- Insurance Claims Processing Workflow
-- Database schema
-- Table 1: Customers
-- ==========================================

CREATE TABLE IF NOT EXISTS customers (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id VARCHAR(30) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(15) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- Table 2: Vehicles
-- Each vehicle belongs to a customer
-- ==========================================

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    registration_number VARCHAR(20) UNIQUE NOT NULL,
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    manufacturing_year SMALLINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_vehicles_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),

    CONSTRAINT chk_manufacturing_year
        CHECK (
            manufacturing_year IS NULL
            OR manufacturing_year BETWEEN 1900 AND 2100
        )
);

-- ==========================================
-- Table 3: Policies
-- Connects a customer and vehicle to coverage
-- ==========================================

CREATE TABLE IF NOT EXISTS policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    policy_number VARCHAR(30) UNIQUE NOT NULL,
    customer_id BIGINT NOT NULL,
    vehicle_id BIGINT NOT NULL,
    coverage_details TEXT NOT NULL,
    premium_amount NUMERIC(12,2) NOT NULL,
    start_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_policies_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),

    CONSTRAINT fk_policies_vehicle
        FOREIGN KEY (vehicle_id)
        REFERENCES vehicles(vehicle_id),

    CONSTRAINT chk_premium_amount
        CHECK (premium_amount >= 0),

    CONSTRAINT chk_policy_dates
        CHECK (expiry_date > start_date),

    CONSTRAINT chk_policy_status
        CHECK (status IN ('ACTIVE', 'EXPIRED', 'CANCELLED', 'PENDING'))
);

-- ==========================================
-- Table 4: Claims
-- Records insurance claims against policies
-- ==========================================

CREATE TABLE IF NOT EXISTS claims (
    claim_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_number VARCHAR(30) UNIQUE NOT NULL,
    policy_id BIGINT NOT NULL,
    incident_date DATE NOT NULL,
    incident_description TEXT NOT NULL,
    claimed_amount NUMERIC(12,2) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'SUBMITTED',
    fraud_risk_level VARCHAR(10) NOT NULL DEFAULT 'LOW',
    fraud_risk_score NUMERIC(5,2),
    sla_deadline TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_claims_policy
        FOREIGN KEY (policy_id)
        REFERENCES policies(policy_id),

    CONSTRAINT chk_claimed_amount
        CHECK (claimed_amount > 0),

    CONSTRAINT chk_claim_status
        CHECK (status IN (
            'SUBMITTED',
            'DOCUMENTS_PENDING',
            'UNDER_REVIEW',
            'ASSESSMENT_PENDING',
            'APPROVAL_PENDING',
            'APPROVED',
            'REJECTED',
            'SETTLEMENT_PENDING',
            'SETTLED',
            'CLOSED'
        )),

    CONSTRAINT chk_fraud_risk_level
        CHECK (fraud_risk_level IN ('LOW', 'MEDIUM', 'HIGH')),

    CONSTRAINT chk_fraud_risk_score
        CHECK (
            fraud_risk_score IS NULL
            OR fraud_risk_score BETWEEN 0 AND 100
        )
);

-- ==========================================
-- Table 5: Claim Documents
-- Tracks uploaded and verified claim documents
-- ==========================================

CREATE TABLE IF NOT EXISTS claim_documents (
    document_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_id BIGINT NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    file_reference TEXT NOT NULL,
    verification_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    reviewed_by BIGINT,
    review_notes TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMPTZ,

    CONSTRAINT fk_documents_claim
        FOREIGN KEY (claim_id)
        REFERENCES claims(claim_id),

    CONSTRAINT chk_document_verification
        CHECK (verification_status IN (
            'PENDING',
            'VERIFIED',
            'REJECTED',
            'RESUBMISSION_REQUIRED'
        ))
);

-- ==========================================
-- Table 6: Assessments
-- Stores claim assessment findings
-- ==========================================

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_id BIGINT NOT NULL,
    assessor_id BIGINT,
    damage_description TEXT NOT NULL,
    estimated_repair_cost NUMERIC(12,2) NOT NULL,
    recommendation VARCHAR(40) NOT NULL,
    assessment_notes TEXT,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_assessments_claim
        FOREIGN KEY (claim_id)
        REFERENCES claims(claim_id),

    CONSTRAINT chk_repair_cost
        CHECK (estimated_repair_cost >= 0),

    CONSTRAINT chk_assessment_recommendation
        CHECK (recommendation IN (
            'RECOMMEND_APPROVAL',
            'RECOMMEND_REJECTION',
            'MORE_INFORMATION_REQUIRED'
        ))
);

-- ==========================================
-- Table 7: Claim Decisions
-- Records approval or rejection decisions
-- ==========================================

CREATE TABLE IF NOT EXISTS claim_decisions (
    decision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_id BIGINT NOT NULL,
    approver_id BIGINT,
    decision VARCHAR(30) NOT NULL,
    reason TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_decisions_claim
        FOREIGN KEY (claim_id)
        REFERENCES claims(claim_id),

    CONSTRAINT chk_claim_decision
        CHECK (decision IN (
            'APPROVED',
            'REJECTED',
            'MORE_INFORMATION_REQUIRED'
        ))
);

-- ==========================================
-- Table 8: Settlements
-- Tracks claim payment processing
-- ==========================================

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_id BIGINT NOT NULL UNIQUE,
    approved_amount NUMERIC(12,2) NOT NULL,
    payment_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    payment_reference VARCHAR(100) UNIQUE,
    payment_method VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMPTZ,

    CONSTRAINT fk_settlements_claim
        FOREIGN KEY (claim_id)
        REFERENCES claims(claim_id),

    CONSTRAINT chk_approved_amount
        CHECK (approved_amount >= 0),

    CONSTRAINT chk_payment_status
        CHECK (payment_status IN (
            'PENDING',
            'PROCESSING',
            'PAID',
            'FAILED',
            'CANCELLED'
        ))
);

-- ==========================================
-- Table 9: Claim Status History
-- Tracks changes to claim status over time
-- ==========================================

CREATE TABLE IF NOT EXISTS claim_status_history (
    history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_id BIGINT NOT NULL,
    previous_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    changed_by BIGINT,
    change_reason TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_status_history_claim
        FOREIGN KEY (claim_id)
        REFERENCES claims(claim_id),

    CONSTRAINT chk_previous_status
        CHECK (
            previous_status IS NULL
            OR previous_status IN (
                'SUBMITTED',
                'DOCUMENTS_PENDING',
                'UNDER_REVIEW',
                'ASSESSMENT_PENDING',
                'APPROVAL_PENDING',
                'APPROVED',
                'REJECTED',
                'SETTLEMENT_PENDING',
                'SETTLED',
                'CLOSED'
            )
        ),

    CONSTRAINT chk_new_status
        CHECK (new_status IN (
            'SUBMITTED',
            'DOCUMENTS_PENDING',
            'UNDER_REVIEW',
            'ASSESSMENT_PENDING',
            'APPROVAL_PENDING',
            'APPROVED',
            'REJECTED',
            'SETTLEMENT_PENDING',
            'SETTLED',
            'CLOSED'
        ))
);

-- ==========================================
-- Table 10: Users
-- Stores employee login accounts
-- ==========================================

 CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- Table 11: Roles
-- Defines employee permission categories
-- ==========================================

CREATE TABLE IF NOT EXISTS roles (
    role_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- Table 12: User Roles
-- Connects employee accounts to their roles
-- ==========================================

CREATE TABLE IF NOT EXISTS user_roles (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_user_roles
        PRIMARY KEY (user_id, role_id),

    CONSTRAINT fk_user_roles_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_user_roles_role
        FOREIGN KEY (role_id)
        REFERENCES roles(role_id)
        ON DELETE CASCADE
);

-- ==========================================
-- Table 13: Fraud Flags
-- Records potential claim risk indicators
-- ==========================================

CREATE TABLE IF NOT EXISTS fraud_flags (
    fraud_flag_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_id BIGINT NOT NULL,
    flag_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    risk_level VARCHAR(10) NOT NULL DEFAULT 'LOW',
    review_status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    reviewed_by BIGINT,
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMPTZ,

    CONSTRAINT fk_fraud_flags_claim
        FOREIGN KEY (claim_id)
        REFERENCES claims(claim_id),

    CONSTRAINT fk_fraud_flags_reviewer
        FOREIGN KEY (reviewed_by)
        REFERENCES users(user_id),

    CONSTRAINT chk_fraud_flag_risk_level
        CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),

    CONSTRAINT chk_fraud_flag_review_status
        CHECK (review_status IN (
            'OPEN',
            'UNDER_REVIEW',
            'RESOLVED',
            'ESCALATED'
        ))
);

-- ==========================================
-- Table 14: Claim SLA Tracking
-- Tracks deadlines for claim-processing stages
-- ==========================================

CREATE TABLE IF NOT EXISTS claim_sla_tracking (
    sla_tracking_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_id BIGINT NOT NULL,
    stage_name VARCHAR(40) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deadline_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    sla_status VARCHAR(20) NOT NULL DEFAULT 'IN_PROGRESS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_sla_claim
        FOREIGN KEY (claim_id)
        REFERENCES claims(claim_id),

    CONSTRAINT chk_sla_deadline
        CHECK (deadline_at > started_at),

    CONSTRAINT chk_sla_completion
        CHECK (
            completed_at IS NULL
            OR completed_at >= started_at
        ),

    CONSTRAINT chk_sla_status
        CHECK (sla_status IN (
            'IN_PROGRESS',
            'COMPLETED_ON_TIME',
            'BREACHED',
            'CANCELLED'
        ))
);

-- ==========================================
-- Table 15: Event Outbox
-- Stores events waiting to be published
-- ==========================================

CREATE TABLE IF NOT EXISTS event_outbox (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id BIGINT NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMPTZ,
    publish_attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,

    CONSTRAINT chk_publish_attempts
        CHECK (publish_attempts >= 0)
);

CREATE INDEX IF NOT EXISTS idx_event_outbox_unpublished
    ON event_outbox (created_at)
    WHERE published_at IS NULL;
    
-- ==========================================
-- Table 16: Event Processing
-- Tracks background event processing
-- ==========================================

CREATE TABLE IF NOT EXISTS event_processing (
    event_id BIGINT NOT NULL,
    consumer_name VARCHAR(100) NOT NULL,
    processing_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    processing_attempts INTEGER NOT NULL DEFAULT 0,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ,
    last_error TEXT,

    CONSTRAINT pk_event_processing
        PRIMARY KEY (event_id, consumer_name),

    CONSTRAINT fk_event_processing_outbox
        FOREIGN KEY (event_id)
        REFERENCES event_outbox(event_id),

    CONSTRAINT chk_event_processing_status
        CHECK (processing_status IN (
            'PENDING',
            'PROCESSING',
            'COMPLETED',
            'FAILED'
        )),

    CONSTRAINT chk_processing_attempts
        CHECK (processing_attempts >= 0)
);
-- ==========================================
-- Employee foreign-key constraints
-- Added after all referenced tables exist
-- ==========================================

ALTER TABLE claim_documents
    ADD CONSTRAINT fk_claim_documents_reviewed_by
    FOREIGN KEY (reviewed_by)
    REFERENCES users(user_id);

ALTER TABLE assessments
    ADD CONSTRAINT fk_assessments_assessor
    FOREIGN KEY (assessor_id)
    REFERENCES users(user_id);

ALTER TABLE claim_decisions
    ADD CONSTRAINT fk_claim_decisions_approver
    FOREIGN KEY (approver_id)
    REFERENCES users(user_id);

ALTER TABLE claim_status_history
    ADD CONSTRAINT fk_claim_status_history_changed_by
    FOREIGN KEY (changed_by)
    REFERENCES users(user_id);
    
-- Customer login accounts
CREATE TABLE IF NOT EXISTS customer_accounts (
    customer_account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL UNIQUE
        REFERENCES customers(customer_id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);