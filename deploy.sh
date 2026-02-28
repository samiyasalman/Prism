#!/usr/bin/env bash
#
# deploy.sh — Deploy Prism to IBM Cloud Code Engine
#
# Prerequisites:
#   - ibmcloud CLI installed with ce, cr plugins
#   - Docker installed and running
#   - Logged in: ibmcloud login
#
# Usage:
#   ./deploy.sh                  # Full deploy
#   ./deploy.sh --skip-db        # Skip DB provisioning (already exists)
#   ./deploy.sh --backend-only   # Rebuild and redeploy backend only
#   ./deploy.sh --frontend-only  # Rebuild and redeploy frontend only

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
PROJECT_NAME="prism"
REGION="us-south"
RESOURCE_GROUP="Default"
DB_INSTANCE="trustbridge-db"
REGISTRY="us.icr.io"
NAMESPACE="prism"
BACKEND_IMAGE="${REGISTRY}/${NAMESPACE}/backend"
FRONTEND_IMAGE="${REGISTRY}/${NAMESPACE}/frontend"
BACKEND_APP="prism-backend"
FRONTEND_APP="prism-frontend"

# ─── Parse flags ─────────────────────────────────────────────────────────────
SKIP_DB=false
BACKEND_ONLY=false
FRONTEND_ONLY=false

for arg in "$@"; do
    case $arg in
        --skip-db)       SKIP_DB=true ;;
        --backend-only)  BACKEND_ONLY=true ;;
        --frontend-only) FRONTEND_ONLY=true ;;
        *) echo "Unknown flag: $arg"; exit 1 ;;
    esac
done

# ─── Helper functions ────────────────────────────────────────────────────────
info()  { echo -e "\n\033[1;34m▶ $1\033[0m"; }
ok()    { echo -e "\033[1;32m✓ $1\033[0m"; }
warn()  { echo -e "\033[1;33m⚠ $1\033[0m"; }
fail()  { echo -e "\033[1;31m✗ $1\033[0m"; exit 1; }

wait_for_db() {
    info "Waiting for database to be ready (this can take 10-15 minutes)..."
    local max_attempts=60
    for i in $(seq 1 $max_attempts); do
        local status
        status=$(ibmcloud resource service-instance "$DB_INSTANCE" --output json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['state'])" 2>/dev/null || echo "provisioning")
        if [ "$status" = "active" ]; then
            ok "Database is active"
            return 0
        fi
        echo "  Attempt $i/$max_attempts — status: $status"
        sleep 30
    done
    fail "Database did not become active within 30 minutes"
}

# ─── Step 1: Provision PostgreSQL ────────────────────────────────────────────
provision_database() {
    if [ "$SKIP_DB" = true ]; then
        warn "Skipping database provisioning (--skip-db)"
        return
    fi

    info "Provisioning IBM Cloud Databases for PostgreSQL..."

    # Check if instance already exists
    if ibmcloud resource service-instance "$DB_INSTANCE" &>/dev/null; then
        warn "Database instance '$DB_INSTANCE' already exists, skipping creation"
    else
        ibmcloud resource service-instance-create "$DB_INSTANCE" \
            databases-for-postgresql standard "$REGION" \
            --service-endpoints public \
            || fail "Failed to create database instance"
        ok "Database instance created"
    fi

    wait_for_db
}

# ─── Step 2: Create service credentials and extract connection info ──────────
setup_db_credentials() {
    info "Setting up database credentials..."

    local cred_name="trustbridge-db-creds"

    # Create credentials if they don't exist
    if ! ibmcloud resource service-key "$cred_name" &>/dev/null; then
        ibmcloud resource service-key-create "$cred_name" Administrator \
            --instance-name "$DB_INSTANCE" \
            || fail "Failed to create service credentials"
        ok "Service credentials created"
    else
        warn "Credentials '$cred_name' already exist"
    fi

    # Extract connection details
    info "Extracting connection details..."
    local creds_json
    creds_json=$(ibmcloud resource service-key "$cred_name" --output json)

    # Extract the PostgreSQL connection string and CA cert
    DB_CONN=$(echo "$creds_json" | python3 -c "
import sys, json
creds = json.load(sys.stdin)[0]['credentials']
pg = creds['connection']['postgres']
composed = pg['composed'][0]
print(composed)
")

    DB_CA_CERT=$(echo "$creds_json" | python3 -c "
import sys, json, base64
creds = json.load(sys.stdin)[0]['credentials']
cert_b64 = creds['connection']['postgres']['certificate']['certificate_base64']
print(base64.b64decode(cert_b64).decode())
")

    # Build async (asyncpg) and sync (psycopg2) URLs
    # IBM returns: postgres://user:pass@host:port/dbname
    # asyncpg needs: postgresql+asyncpg://...?ssl=verify-full
    # psycopg2 needs: postgresql://...?sslmode=verify-full
    DB_URL_ASYNC=$(echo "$DB_CONN" | sed 's|^postgres://|postgresql+asyncpg://|')
    DB_URL_ASYNC="${DB_URL_ASYNC}?ssl=verify-full"

    DB_URL_SYNC=$(echo "$DB_CONN" | sed 's|^postgres://|postgresql://|')
    DB_URL_SYNC="${DB_URL_SYNC}?sslmode=verify-full"

    ok "Database URLs extracted"

    # Write CA cert to a temp file for reference
    echo "$DB_CA_CERT" > /tmp/trustbridge-db-ca.crt
    ok "CA certificate saved to /tmp/trustbridge-db-ca.crt"
}

# ─── Step 3: Create Code Engine project ─────────────────────────────────────
setup_code_engine() {
    info "Setting up Code Engine project..."

    if ibmcloud ce project get --name "$PROJECT_NAME" &>/dev/null; then
        warn "Project '$PROJECT_NAME' already exists"
    else
        ibmcloud ce project create --name "$PROJECT_NAME" \
            || fail "Failed to create Code Engine project"
        ok "Code Engine project created"
    fi

    ibmcloud ce project select --name "$PROJECT_NAME"
    ok "Selected project '$PROJECT_NAME'"
}

# ─── Step 4: Create container registry namespace ────────────────────────────
setup_registry() {
    info "Setting up container registry..."

    ibmcloud cr region-set "$REGION"

    if ibmcloud cr namespace-list | grep -q "$NAMESPACE"; then
        warn "Registry namespace '$NAMESPACE' already exists"
    else
        ibmcloud cr namespace-add "$NAMESPACE" \
            || fail "Failed to create registry namespace"
        ok "Registry namespace created"
    fi

    # Log Docker into IBM Container Registry
    ibmcloud cr login
    ok "Docker logged into IBM Container Registry"
}

# ─── Step 5: Generate RSA keys ──────────────────────────────────────────────
generate_rsa_keys() {
    info "Generating RSA key pair for credential signing..."

    if [ -f /tmp/prism-rsa-private.pem ]; then
        warn "RSA keys already exist at /tmp/prism-rsa-*.pem, reusing"
    else
        openssl genrsa -out /tmp/prism-rsa-private.pem 2048
        openssl rsa -in /tmp/prism-rsa-private.pem -pubout -out /tmp/prism-rsa-public.pem
        ok "RSA key pair generated"
    fi

    RSA_PRIVATE_B64=$(base64 -w 0 /tmp/prism-rsa-private.pem)
    RSA_PUBLIC_B64=$(base64 -w 0 /tmp/prism-rsa-public.pem)
}

# ─── Step 6: Create secrets and configmaps ───────────────────────────────────
create_secrets() {
    info "Creating Code Engine secrets..."

    # Generate JWT secret if not set
    JWT_SECRET=${TB_JWT_SECRET:-$(openssl rand -hex 32)}

    # Read WXO credentials from environment (must be set before running)
    WXO_MCSP_APIKEY=${TB_WXO_MCSP_APIKEY:-""}
    WXO_INSTANCE_URL=${TB_WXO_INSTANCE_URL:-""}
    WXO_AGENT_ID=${TB_WXO_AGENT_ID:-""}

    # COS credentials
    COS_API_KEY=${TB_COS_API_KEY:-""}
    COS_INSTANCE_ID=${TB_COS_INSTANCE_ID:-""}

    # Delete existing secret if it exists, then create
    ibmcloud ce secret delete --name prism-backend-secrets --force 2>/dev/null || true

    ibmcloud ce secret create --name prism-backend-secrets \
        --from-literal "TB_DATABASE_URL=${DB_URL_ASYNC}" \
        --from-literal "TB_DATABASE_URL_SYNC=${DB_URL_SYNC}" \
        --from-literal "TB_JWT_SECRET=${JWT_SECRET}" \
        --from-literal "TB_WXO_MCSP_APIKEY=${WXO_MCSP_APIKEY}" \
        --from-literal "TB_WXO_INSTANCE_URL=${WXO_INSTANCE_URL}" \
        --from-literal "TB_WXO_AGENT_ID=${WXO_AGENT_ID}" \
        --from-literal "TB_RSA_PRIVATE_KEY_B64=${RSA_PRIVATE_B64}" \
        --from-literal "TB_RSA_PUBLIC_KEY_B64=${RSA_PUBLIC_B64}" \
        --from-literal "TB_COS_API_KEY=${COS_API_KEY}" \
        --from-literal "TB_COS_INSTANCE_ID=${COS_INSTANCE_ID}" \
        || fail "Failed to create secrets"

    ok "Backend secrets created"

    # Configmap for non-sensitive config
    ibmcloud ce configmap delete --name prism-backend-config --force 2>/dev/null || true

    ibmcloud ce configmap create --name prism-backend-config \
        --from-literal "TB_APP_NAME=Prism" \
        --from-literal "TB_COS_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud" \
        --from-literal "TB_COS_BUCKET=trustbridge-documents" \
        --from-literal "TB_WATSONX_URL=https://us-south.ml.cloud.ibm.com" \
        || fail "Failed to create configmap"

    ok "Backend configmap created"
}

# ─── Step 7: Build and deploy backend ────────────────────────────────────────
deploy_backend() {
    info "Building backend Docker image..."
    docker build -t "${BACKEND_IMAGE}:latest" ./backend \
        || fail "Backend Docker build failed"
    ok "Backend image built"

    info "Pushing backend image to IBM Container Registry..."
    docker push "${BACKEND_IMAGE}:latest" \
        || fail "Failed to push backend image"
    ok "Backend image pushed"

    info "Deploying backend to Code Engine..."

    if ibmcloud ce app get --name "$BACKEND_APP" &>/dev/null; then
        ibmcloud ce app update --name "$BACKEND_APP" \
            --image "${BACKEND_IMAGE}:latest" \
            --env-from-secret prism-backend-secrets \
            --env-from-configmap prism-backend-config \
            || fail "Failed to update backend app"
        ok "Backend app updated"
    else
        ibmcloud ce app create --name "$BACKEND_APP" \
            --image "${BACKEND_IMAGE}:latest" \
            --port 5555 \
            --min-scale 1 \
            --max-scale 3 \
            --cpu 0.5 \
            --memory 1G \
            --env-from-secret prism-backend-secrets \
            --env-from-configmap prism-backend-config \
            || fail "Failed to create backend app"
        ok "Backend app created"
    fi

    # Get backend URL
    BACKEND_URL=$(ibmcloud ce app get --name "$BACKEND_APP" --output json | python3 -c "
import sys, json
app = json.load(sys.stdin)
print(app['status']['url'])
")
    ok "Backend URL: $BACKEND_URL"
}

# ─── Step 8: Run database migrations ────────────────────────────────────────
run_migrations() {
    info "Running database migrations..."

    # Delete previous job run if exists
    ibmcloud ce jobrun delete --name prism-migrate --force 2>/dev/null || true
    ibmcloud ce job delete --name prism-migrate --force 2>/dev/null || true

    ibmcloud ce job create --name prism-migrate \
        --image "${BACKEND_IMAGE}:latest" \
        --env-from-secret prism-backend-secrets \
        --env-from-configmap prism-backend-config \
        --command "alembic" \
        --argument "upgrade" \
        --argument "head" \
        || fail "Failed to create migration job"

    ibmcloud ce jobrun submit --job prism-migrate --name prism-migrate \
        || fail "Failed to submit migration job"

    # Wait for migration to complete
    info "Waiting for migrations to complete..."
    local max_attempts=20
    for i in $(seq 1 $max_attempts); do
        local status
        status=$(ibmcloud ce jobrun get --name prism-migrate --output json 2>/dev/null | python3 -c "
import sys, json
jr = json.load(sys.stdin)
conditions = jr.get('status', {}).get('conditions', [])
for c in conditions:
    if c['type'] == 'Complete' and c['status'] == 'True':
        print('complete')
        sys.exit(0)
    if c['type'] == 'Failed' and c['status'] == 'True':
        print('failed')
        sys.exit(0)
print('running')
" 2>/dev/null || echo "running")

        if [ "$status" = "complete" ]; then
            ok "Migrations completed successfully"
            return 0
        elif [ "$status" = "failed" ]; then
            fail "Migration job failed. Check logs: ibmcloud ce jobrun logs --name prism-migrate"
        fi
        echo "  Attempt $i/$max_attempts — status: $status"
        sleep 15
    done
    fail "Migration job timed out"
}

# ─── Step 9: Build and deploy frontend ──────────────────────────────────────
deploy_frontend() {
    info "Building frontend Docker image..."
    docker build -t "${FRONTEND_IMAGE}:latest" ./frontend \
        || fail "Frontend Docker build failed"
    ok "Frontend image built"

    info "Pushing frontend image to IBM Container Registry..."
    docker push "${FRONTEND_IMAGE}:latest" \
        || fail "Failed to push frontend image"
    ok "Frontend image pushed"

    info "Deploying frontend to Code Engine..."

    if ibmcloud ce app get --name "$FRONTEND_APP" &>/dev/null; then
        ibmcloud ce app update --name "$FRONTEND_APP" \
            --image "${FRONTEND_IMAGE}:latest" \
            --env "BACKEND_URL=${BACKEND_URL}" \
            --env "NEXT_PUBLIC_API_URL=/api" \
            || fail "Failed to update frontend app"
        ok "Frontend app updated"
    else
        ibmcloud ce app create --name "$FRONTEND_APP" \
            --image "${FRONTEND_IMAGE}:latest" \
            --port 3000 \
            --min-scale 1 \
            --max-scale 3 \
            --cpu 0.5 \
            --memory 1G \
            --env "BACKEND_URL=${BACKEND_URL}" \
            --env "NEXT_PUBLIC_API_URL=/api" \
            || fail "Failed to create frontend app"
        ok "Frontend app created"
    fi

    # Get frontend URL
    FRONTEND_URL=$(ibmcloud ce app get --name "$FRONTEND_APP" --output json | python3 -c "
import sys, json
app = json.load(sys.stdin)
print(app['status']['url'])
")
    ok "Frontend URL: $FRONTEND_URL"
}

# ─── Step 10: Update backend with frontend URL ──────────────────────────────
update_backend_frontend_url() {
    info "Updating backend with frontend URL..."

    ibmcloud ce app update --name "$BACKEND_APP" \
        --env "TB_FRONTEND_URL=${FRONTEND_URL}" \
        || fail "Failed to update backend with frontend URL"

    ok "Backend updated with TB_FRONTEND_URL=${FRONTEND_URL}"
}

# ─── Step 11: Verify deployment ─────────────────────────────────────────────
verify_deployment() {
    info "Verifying deployment..."

    echo ""
    echo "  Backend:  $BACKEND_URL"
    echo "  Frontend: $FRONTEND_URL"
    echo ""

    # Backend health check
    local backend_health
    backend_health=$(curl -s "${BACKEND_URL}/health" 2>/dev/null || echo "unreachable")
    if echo "$backend_health" | grep -q '"status":"ok"'; then
        ok "Backend health check passed"
    else
        warn "Backend health check: $backend_health"
    fi

    # Frontend health check
    local frontend_status
    frontend_status=$(curl -s -o /dev/null -w "%{http_code}" "${FRONTEND_URL}" 2>/dev/null || echo "000")
    if [ "$frontend_status" = "200" ]; then
        ok "Frontend returns 200"
    else
        warn "Frontend returned HTTP $frontend_status"
    fi

    # API proxy check
    local proxy_health
    proxy_health=$(curl -s "${FRONTEND_URL}/api/health" 2>/dev/null || echo "unreachable")
    if echo "$proxy_health" | grep -q '"status":"ok"'; then
        ok "API proxy working (frontend → backend)"
    else
        warn "API proxy check: $proxy_health"
    fi

    echo ""
    info "Deployment complete!"
    echo ""
    echo "  🌐 Frontend: $FRONTEND_URL"
    echo "  🔧 Backend:  $BACKEND_URL"
    echo "  📊 Health:    ${BACKEND_URL}/health"
    echo ""
    echo "  Next steps:"
    echo "    1. Visit $FRONTEND_URL"
    echo "    2. Sign up, log in, upload a document, analyze"
    echo "    3. Check dashboard, issue credential, verify link"
    echo ""
}

# ─── Main ────────────────────────────────────────────────────────────────────
main() {
    info "Deploying Prism to IBM Cloud Code Engine"
    echo "  Region: $REGION | Project: $PROJECT_NAME"
    echo ""

    if [ "$FRONTEND_ONLY" = true ]; then
        setup_code_engine
        setup_registry
        # Need backend URL for frontend env
        BACKEND_URL=$(ibmcloud ce app get --name "$BACKEND_APP" --output json | python3 -c "
import sys, json
app = json.load(sys.stdin)
print(app['status']['url'])
")
        deploy_frontend
        update_backend_frontend_url
        verify_deployment
        return
    fi

    if [ "$BACKEND_ONLY" = true ]; then
        setup_code_engine
        setup_registry
        deploy_backend
        run_migrations
        verify_deployment
        return
    fi

    # Full deployment
    provision_database
    setup_db_credentials
    setup_code_engine
    setup_registry
    generate_rsa_keys
    create_secrets
    deploy_backend
    run_migrations
    deploy_frontend
    update_backend_frontend_url
    verify_deployment
}

main "$@"
