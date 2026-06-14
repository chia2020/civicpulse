#!/bin/bash
FEATURE_SPEC=$(cat .specify/feature.json | grep -oP '"feature_directory":\s*"\K[^"]+')/spec.md
FEATURE_DIR=$(cat .specify/feature.json | grep -oP '"feature_directory":\s*"\K[^"]+')
IMPL_PLAN="$FEATURE_DIR/plan.md"
BRANCH=$(git branch --show-current)

# Copy template if plan doesn't exist
if [ ! -f "$IMPL_PLAN" ]; then
    cp .specify/templates/plan-template.md "$IMPL_PLAN"
fi

echo "{\"FEATURE_SPEC\": \"$FEATURE_SPEC\", \"IMPL_PLAN\": \"$IMPL_PLAN\", \"SPECS_DIR\": \"$FEATURE_DIR\", \"BRANCH\": \"$BRANCH\"}"
