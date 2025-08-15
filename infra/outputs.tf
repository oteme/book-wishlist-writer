output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.api.api_endpoint
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.app.function_name
}

output "secrets_name" {
  description = "Secrets Manager secret name"
  value       = aws_secretsmanager_secret.app_secrets.name
}

output "secrets_arn" {
  description = "Secrets Manager secret ARN"
  value       = aws_secretsmanager_secret.app_secrets.arn
}

output "api_invoke_url" {
  description = "Full URL to invoke the API"
  value       = "${aws_apigatewayv2_api.api.api_endpoint}/ingest"
}