.PHONY: help plan deploy destroy test lint clean package

# Default target
help:
	@echo "Available commands:"
	@echo "  make plan     - Run terraform plan"
	@echo "  make deploy   - Deploy infrastructure with terraform apply"
	@echo "  make destroy  - Destroy infrastructure with terraform destroy"
	@echo "  make test     - Run all tests"
	@echo "  make lint     - Run code quality checks"
	@echo "  make clean    - Clean build artifacts"
	@echo "  make package  - Package Lambda function"
	@echo "  make help     - Show this help message"

# Terraform commands
plan:
	cd infra && terraform init && terraform plan

deploy:
	cd infra && terraform init && terraform apply

destroy:
	cd infra && terraform destroy

# Testing
test:
	cd tests && python -m pytest -v --tb=short

test-coverage:
	cd tests && python -m pytest --cov=../app --cov-report=html --cov-report=term

# Code quality
lint:
	cd app && python -m ruff check .
	cd app && python -m ruff format --check .

format:
	cd app && python -m ruff format .

# Package Lambda
package:
	mkdir -p dist
	cd app && zip -r ../dist/lambda.zip . -x "__pycache__/*" "*.pyc" ".pytest_cache/*"

# Clean
clean:
	rm -rf dist/
	rm -rf app/__pycache__/
	rm -rf tests/__pycache__/
	rm -rf tests/.pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Development setup
setup:
	pip install -r app/requirements.txt
	pip install pytest pytest-cov ruff boto3-stubs

# Infrastructure helpers
tf-init:
	cd infra && terraform init

tf-validate:
	cd infra && terraform validate

tf-fmt:
	cd infra && terraform fmt

# AWS helpers
secrets-get:
	aws secretsmanager get-secret-value --secret-id $$(cd infra && terraform output -raw secrets_name) --query SecretString --output text | jq .

logs:
	aws logs tail /aws/lambda/$$(cd infra && terraform output -raw lambda_function_name) --follow

# Quick deployment with validation
deploy-safe: tf-validate lint test deploy

# Show outputs
outputs:
	cd infra && terraform output