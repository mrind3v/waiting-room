# Credentials come from the environment (AWS_PROFILE=agent-toolkit), never from this repo.
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "waiting-room"
      Owner     = "mrind3v"
      ManagedBy = "terraform"
      Ephemeral = "true"
    }
  }
}
