#!/bin/bash -x

# Check for dev flag
IS_DEV=false
if [ "$1" = "--dev" ]; then
    IS_DEV=true
fi

date=$(date +"%Y-%m-%d")

# ── Service definitions ──────────────────────────────────────────────────────
# Each service: name, source dir/files, Dockerfile path, build context
SERVICES=("cribl-framework" "cribl-service" "ece-service" "etn-onboarding")

# ── Read version from Build.yml ──────────────────────────────────────────────
PACKAGE_VERSION=$(grep 'VersionID' Build.yml | sed -E 's/.*VersionID: *([0-9.]+)(-SNAPSHOT)?/\1/' | head -n 1)
if [ $? -ne 0 ] || [ -z "$PACKAGE_VERSION" ]; then
    echo "Failed to extract version from Build.yml"
    exit 1
fi

echo "==> Building version: ${PACKAGE_VERSION}-SNAPSHOT"

# ── Clean previous build ─────────────────────────────────────────────────────
rm -rf ./build
mkdir -p ./build

# ── 1. cribl-framework (root service) ────────────────────────────────────────
echo "==> Packaging cribl-framework"
mkdir -p ./build/cribl-framework

cp requirements.txt              ./build/cribl-framework/
cp Dockerfile                    ./build/cribl-framework/
cp app.py                        ./build/cribl-framework/
cp cribl_api.py                  ./build/cribl-framework/
cp cribl_config.py               ./build/cribl-framework/
cp cribl_logger.py               ./build/cribl-framework/
cp cribl_utils.py                ./build/cribl-framework/
cp _validate.py                  ./build/cribl-framework/
cp -r templates/                 ./build/cribl-framework/templates/
cp *.json                        ./build/cribl-framework/ 2>/dev/null || true

# ── 2. cribl_service ─────────────────────────────────────────────────────────
echo "==> Packaging cribl-service"
mkdir -p ./build/cribl-service

cp -r cribl_service/             ./build/cribl-service/cribl_service/
cp cribl_service/requirements.txt ./build/cribl-service/requirements.txt
cp cribl_service/Dockerfile      ./build/cribl-service/Dockerfile
# shared modules needed by cribl_service
cp cribl_api.py                  ./build/cribl-service/
cp cribl_config.py               ./build/cribl-service/
cp cribl_logger.py               ./build/cribl-service/
cp cribl_utils.py                ./build/cribl-service/
cp otel_setup.py                 ./build/cribl-service/

# ── 3. ece_service ───────────────────────────────────────────────────────────
echo "==> Packaging ece-service"
mkdir -p ./build/ece-service

cp -r ece_service/               ./build/ece-service/ece_service/
cp ece_service/requirements.txt  ./build/ece-service/requirements.txt
cp ece_service/Dockerfile        ./build/ece-service/Dockerfile
# shared modules needed by ece_service
cp role_rm.py                    ./build/ece-service/
cp cribl_api.py                  ./build/ece-service/
cp cribl_config.py               ./build/ece-service/
cp cribl_logger.py               ./build/ece-service/
cp cribl_utils.py                ./build/ece-service/
cp otel_setup.py                 ./build/ece-service/

# ── 4. etn_onboarding ───────────────────────────────────────────────────────
echo "==> Packaging etn-onboarding"
mkdir -p ./build/etn-onboarding

cp -r etn_onboarding/            ./build/etn-onboarding/etn_onboarding/
cp etn_onboarding/requirements.txt ./build/etn-onboarding/requirements.txt
cp etn_onboarding/Dockerfile     ./build/etn-onboarding/Dockerfile

# ── Clean up Python artifacts from all build dirs ────────────────────────────
find ./build -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find ./build -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find ./build -type f -name "*.pyc" -delete 2>/dev/null || true

# ── Create zip artifacts and sign each ───────────────────────────────────────
for service in "${SERVICES[@]}"; do
    appfullname="${service}-${PACKAGE_VERSION}-SNAPSHOT.zip"
    echo "==> Creating artifact: ${appfullname}"

    rm -f ./${appfullname}

    cd ./build/${service}
    zip -r ../../${appfullname} .
    cd ../..

    # Code signing
    echo "==> Signing: ${appfullname}"
    jarsigner -storetype PKCS11 \
              -storepass placeholder \
              -providerclass sun.security.pkcs11.SunPKCS11 \
              -providerarg $WORKSPACE/venafi.conf \
              -tsa http://timestamp.hcsc.net/timestamp \
              ./${appfullname} $CERTIFICATE_LABEL

    if [ "$IS_DEV" = true ]; then
        # Dev mode: move zip to target
        mkdir -p ./target
        mv ./${appfullname} ./target/${service}.zip
        echo "==> Dev artifact: ./target/${service}.zip"
    else
        # Production mode: deploy to Nexus and cleanup
        echo "==> Deploying ${appfullname} to Nexus"
        mvn deploy:deploy-file \
            -Durl=http://nexus.XXXXXXXX.com/repository/snapshots \
            -DrepositoryId=snapshots \
            -DgroupId=com.hcsc.digital.cribl-elk-psql \
            -DartifactId=${service} \
            -Dversion=${PACKAGE_VERSION}-SNAPSHOT \
            -Dpackaging=zip \
            -Dfile=${appfullname}
        rm -f ${appfullname}
    fi
done

# ── Cleanup ──────────────────────────────────────────────────────────────────
rm -rf ./build
echo "==> Build complete (${date})"
