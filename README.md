# Insurance Claims Processing Workflow

## 1. Project Overview

The Insurance Claims Processing Workflow is a web application for managing insurance claims from initial submission through assessment, approval, and settlement.

The application supports customer and staff workflows, database-backed claim management, event-driven processing, and service-level agreement (SLA) monitoring.

## 2. Technology Stack

- Backend: Python and Flask
- Database: PostgreSQL
- Message broker: RabbitMQ
- Frontend: HTML, CSS, Jinja templates, and Bootstrap where configured
- Deployment: Docker and Docker Compose
- CI/CD: GitHub Actions
- Cloud hosting: AWS EC2
- Automated testing: pytest and pytest-cov

## 3. Main Features

- Customer registration and authentication
- Staff authentication and role-based access
- Insurance policy management
- Claim registration and status tracking
- Claim assessment and configurable business rules
- Fraud-flag recording
- Claim approval and decision workflows
- Document upload and review
- Settlement and payment processing
- SLA tracking and background monitoring
- Transactional outbox for claim events
- RabbitMQ event consumption and retry handling
- Claim status history and audit information

Feature availability depends on the configured roles and application workflow.

## 4. User Roles

The application is designed to support the following roles:

- Policyholder: registers claims, submits documents, and tracks claim status.
- Claims Assessor: reviews claim information and supporting documents.
- Claims Approver: reviews claims and records approval decisions.
- Finance Staff: handles settlement and payment activities.
- Claims Supervisor: oversees claim assignments, workflow exceptions, and SLA monitoring where configured.

Access is controlled by the application's authentication and authorization logic.

## 5. Application Architecture

The application uses a Flask web application supported by service modules and background processes.

- `app.py`: web routes and request handling.
- `services/`: business logic for claims, policies, assessments, decisions, payments, events, and SLAs.
- `routes/`: route modules where applicable.
- `templates/`: HTML templates rendered by Flask.
- `db.py`: database connection utilities.
- `schema.sql`: database schema.
- `migrations/`: database migration configuration and revisions.
- `outbox_publisher.py`: publishes pending transactional outbox events.
- `event_consumer.py`: consumes claim events from RabbitMQ.
- `sla_worker.py`: runs background SLA-related processing.
- `compose.yaml`: container and service configuration.
- `Dockerfile`: application image build instructions.
- `.github/workflows/ci.yml`: automated testing, image build, and deployment workflow.
- `tests/`: automated tests for application services, routes, templates, and event processing.

### Event processing

Claim events are recorded in the PostgreSQL outbox within the transaction that creates the corresponding claim. A background publisher sends pending events to RabbitMQ, and the event consumer records processing outcomes.

The event consumer currently contains a placeholder for business actions such as notifications; do not assume those integrations are implemented.

## 6. Repository Structure

```text
.
├── app.py
├── db.py
├── schema.sql
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── routes/
├── services/
├── templates/
├── migrations/
├── tests/
├── event_consumer.py
├── outbox_publisher.py
├── sla_worker.py
└── .github/
    └── workflows/
        └── ci.yml

## 7. Environment Configuration

Configure database connectivity, Flask settings, and supporting services using environment variables. Keep production credentials and secret keys private. Never commit `.env.aws` or other files containing secrets.

## 8. Running with Docker Compose

On a configured deployment host:

1. Install Docker and the Docker Compose plugin.
2. Obtain the project repository.
3. Configure the required environment variables.
4. Review `compose.yaml` and the environment configuration.
5. Follow the approved deployment procedure.
6. Verify application access, database connectivity, and background-worker status.

**Warning:** Rebuilding or recreating production services can interrupt the application. Take and verify a database backup before an approved deployment.

## 9. Automated Tests

The repository contains tests for authentication, customers, policies, claims, assessment, decisions, settlement, documents, rules, SLA processing, and event handling.

The GitHub Actions workflow installs dependencies, runs pytest with service coverage reporting, builds the Docker image, and deploys to AWS when the main-branch conditions are met.

A previous test run passed 324 tests. Run CI again before release to verify the current revision.

## 10. CI/CD and Deployment

The workflow is defined in `.github/workflows/ci.yml`. It runs on pushes and pull requests targeting `main`. A push to `main` can trigger automatic AWS deployment.

Before merging or deploying:

- Confirm automated tests pass.
- Review the code changes.
- Verify deployment secrets are configured in GitHub Actions.
- Take and verify a database backup.
- Review rollback procedures.
- Check application and worker health after deployment.

Never store deployment credentials in the repository.

## 11. Operational Checks

Routine operational checks include:

- Container status and health.
- Application landing-page availability.
- Database connectivity.
- Pending outbox events and publication errors.
- RabbitMQ queue depth and consumer count.
- Event-processing failures.
- SLA worker logs.
- Claim status history and settlement records.

Prefer read-only database queries for routine inspection.

## 12. Backup and Security

- Back up the database before schema changes or deployments.
- Verify backups can be restored in a safe environment.
- Restrict access to production credentials and customer documents.
- Apply least-privilege access to customer and staff accounts.
- Avoid logging sensitive personal information.
- Keep secrets, private keys, database dumps, and temporary backup files out of Git.

## 13. Project Status and Limitations

The application has been deployed to AWS. The landing page and customer claim-registration form have been checked manually.

Successful event publication alone does not prove that every downstream business action has completed. Verify the complete claim-to-payment lifecycle and any notification integrations separately before declaring production acceptance.

## 14. Future Improvements

Potential improvements include:

- Complete and verify notification integrations.
- Improve monitoring for failed or stuck events.
- Expand end-to-end acceptance tests.
- Document backup restoration and rollback procedures.
- Publish a detailed user guide and architecture diagram.
- Review security, access controls, and document handling before release.
