variable "project_id" {
  description = "Google Cloud project hosting the Bacen Fintech Advisor."
  type        = string
}

variable "region" {
  description = "Region for Agent Runtime, buckets and Model Armor."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name used in resource labels (e.g. dev, prod)."
  type        = string
  default     = "dev"
}

variable "mcp_service_name" {
  description = "Existing Cloud Run service hosting the Bacen MCP server."
  type        = string
  default     = "mcp-bacen"
}

variable "mcp_region" {
  description = "Region of the MCP Cloud Run service."
  type        = string
  default     = "us-central1"
}

variable "iam_scope" {
  description = <<-EOT
    Where to grant resource-scoped roles (run.invoker, secretAccessor, serviceAccountUser,
    OpenID token creator):
      "resource" - least privilege, binding on the exact resource (recommended);
      "project"  - fallback for operators without setIamPolicy on individual resources.
  EOT
  type        = string
  default     = "resource"
  validation {
    condition     = contains(["resource", "project"], var.iam_scope)
    error_message = "iam_scope must be \"resource\" or \"project\"."
  }
}

variable "enable_github_wif" {
  description = "Create the Workload Identity Federation pool/provider for GitHub Actions."
  type        = bool
  default     = true
}

variable "github_repository" {
  description = "owner/repo allowed to impersonate the deployer SA via WIF."
  type        = string
  default     = "Faray-luiz/bacen-fintech-advisor"
}

variable "alert_email" {
  description = "Email for Cloud Monitoring alerts. Empty disables the notification channel."
  type        = string
  default     = ""
}

variable "billing_account_id" {
  description = "Billing account (XXXXXX-XXXXXX-XXXXXX) for the budget alert. Empty disables it."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Monthly budget amount in USD for the budget alert."
  type        = number
  default     = 200
}

variable "force_destroy_buckets" {
  description = "Allow `terraform destroy` to delete non-empty buckets (disposable envs only)."
  type        = bool
  default     = false
}

variable "reports_retention_days" {
  description = "Delete exported reports after N days (data minimization)."
  type        = number
  default     = 90
}
