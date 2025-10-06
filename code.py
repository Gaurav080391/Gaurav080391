pipeline {
    agent any

    environment {
        MASTER_LIST_FILE = 'jenkins_masters.txt'
        PYTHON_SCRIPT = 'check_jenkins_health.py'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm  // assuming the script and URL list is in Git
            }
        }

        stage('Check Jenkins Masters') {
            steps {
                sh '''
                echo "Checking Jenkins masters..."
                python3 ${PYTHON_SCRIPT}
                '''
            }
        }
    }

    post {
        failure {
            echo '❌ Jenkins health check pipeline failed.'
        }
        success {
            echo '✅ Jenkins health check completed.'
        }
    }
}


#####


http://jenkins-master-1.internal:8080
http://jenkins-master-2.internal:8080
http://10.0.1.5:8080
...


#####
import requests
import json
import boto3

JENKINS_LIST_FILE = "jenkins_masters.txt"
TIMEOUT = 5
FAILED = []

def check_jenkins(url):
    try:
        res = requests.get(f"{url}/login", timeout=TIMEOUT)
        return res.status_code == 200
    except:
        return False

def read_urls():
    with open(JENKINS_LIST_FILE) as f:
        return [line.strip() for line in f if line.strip()]

def send_lambda_notification(failed):
    client = boto3.client('lambda', region_name='your-region')  # example: 'us-east-1'
    payload = {
        "sender": "jenkins-monitor@yourdomain.com",
        "recipient": "team@yourdomain.com",
        "message": "🚨 Jenkins masters down:\n" + "\n".join(failed)
    }

    client.invoke(
        FunctionName="jenkins-alert-notifier",
        InvocationType="Event",
        Payload=json.dumps(payload)
    )

def main():
    urls = read_urls()
    for url in urls:
        if not check_jenkins(url):
            FAILED.append(url)

    if FAILED:
        print("❌ Jenkins Down:")
        for f in FAILED:
            print(f)
        send_lambda_notification(FAILED)
    else:
        print("✅ All Jenkins masters are UP.")

if __name__ == "__main__":
    main()



####################################


import requests
import json
import credstash
import os

REGION = os.environ.get('AWS_REGION')

def credstash_retrieve(tooling_environment):
    table = 'credential-store'
    if tooling_environment == "prod":
        tooling_environment = tooling_environment.replace('o', '')
    if tooling_environment == "pre-prod":
        tooling_environment = tooling_environment.replace('o', '').replace('-', '')

    credstash_secret_url = f'azsvc-hsbc-wpb-jenkins-jg-{tooling_environment}1-dtme-01.secret'
    credstash_app_id_url = f'azsvc-hsbc-wpb-jenkins-jg-{tooling_environment}1-dtme-01.app_id'

    app_id = credstash.getSecret(credstash_app_id_url, region=REGION, table=table)
    client_secret = credstash.getSecret(credstash_secret_url, region=REGION, table=table)
    return app_id, client_secret

def get_access_token(app_id, client_secret):
    token_url = 'https://login.microsoftonline.com/e0fd434d-ba64-497b-90d2-859c472e1a92/oauth2/token'
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': app_id,
        'client_secret': client_secret,
        'resource': 'https://graph.microsoft.com',
        'scope': 'https://graph.microsoft.com'
    }
    response = requests.post(token_url, data=token_data)
    response.raise_for_status()
    return response.json().get('access_token')

def get_group_details(token, group_name):
    url = f"https://graph.microsoft.com/v1.0/groups?$filter=displayName eq '{group_name}'"
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f"❌ Failed to fetch group {group_name}: {r.text}")
        return None
    data = r.json().get('value', [])
    if data:
        return {"name": data[0]['displayName'], "id": data[0]['id']}
    return None

def lambda_handler(event, context):
    environment = event['tooling_environment']

    ad_groups = [
        "Infodir-jenkins-dpop-admins",
        "Infodir-jenkins-dpop-users",
        "Infodir-jenkins-dpop-read_only",
        "Infodir-jenkins-myteam-users"
    ]

    app_id, client_secret = credstash_retrieve(environment)
    token = get_access_token(app_id, client_secret)

    for group_name in ad_groups:
        details = get_group_details(token, group_name)
        if details:
            print(f"Group Name: {details['name']}, Object ID: {details['id']}")



################################################################


import requests
import credstash
import os

REGION = os.environ.get('AWS_REGION')

def credstash_retrieve(tooling_environment):
    table = 'credential-store'
    if tooling_environment == "prod":
        tooling_environment = tooling_environment.replace('o', '')
    if tooling_environment == "pre-prod":
        tooling_environment = tooling_environment.replace('o', '').replace('-', '')

    credstash_secret_url = f'azsvc-hsbc-wpb-jenkins-jg-{tooling_environment}1-dtme-01.secret'
    credstash_app_id_url = f'azsvc-hsbc-wpb-jenkins-jg-{tooling_environment}1-dtme-01.app_id'

    app_id = credstash.getSecret(credstash_app_id_url, region=REGION, table=table)
    client_secret = credstash.getSecret(credstash_secret_url, region=REGION, table=table)
    return app_id, client_secret

def get_access_token(app_id, client_secret):
    token_url = 'https://login.microsoftonline.com/e0fd434d-ba64-497b-90d2-859c472e1a92/oauth2/token'
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': app_id,
        'client_secret': client_secret,
        'resource': 'https://graph.microsoft.com',
        'scope': 'https://graph.microsoft.com'
    }
    response = requests.post(token_url, data=token_data)
    response.raise_for_status()
    return response.json().get('access_token')

def add_app_to_group(token, app_object_id, group_id):
    url = f"https://graph.microsoft.com/v1.0/groups/{group_id}/members/$ref"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    body = {
        "@odata.id": f"https://graph.microsoft.com/v1.0/directoryObjects/{app_object_id}"
    }
    r = requests.post(url, headers=headers, json=body)
    if r.status_code in (204, 201):
        print(f"✅ Added App {app_object_id} to Group {group_id}")
    else:
        print(f"❌ Failed to add App {app_object_id} to Group {group_id}: {r.text}")

def lambda_handler(event, context):
    environment = event['tooling_environment']
    app_object_id = event['app_object_id']  # Azure Application (Service Principal) Object ID
    group_ids = event['group_ids']  # List of Azure AD Group Object IDs

    app_id, client_secret = credstash_retrieve(environment)
    token = get_access_token(app_id, client_secret)

    for gid in group_ids:
        add_app_to_group(token, app_object_id, gid)



##########################

{
  "tooling_environment": "pre-prod",
  "app_object_id": "11111111-2222-3333-4444-555555555555",
  "group_ids": [
    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj"
  ]
}



curl -s http://169.254.169.254/latest/meta-data/iam/info

curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/


curl -s http://169.254.169.254/latest/meta-data/iam/info | jq



###################################
# VPC Endpoints
###################################
resource "aws_vpc_endpoint" "vpc_endpoints" {
  provider = aws.secondary

  for_each = {
    for service in local.vpc_endpoint_services :
    service.service_name => service
  }

  vpc_id            = var.eu_west_1_vpc_id
  vpc_endpoint_type = "Interface"
  service_name      = each.value.service_name

  # Use provided subnets if given, else fallback to default subnets
  subnet_ids = try(
    each.value.subnets,
    module.network.subnets["eu-west-1"].private_subnets[*].id
  )

  # Default SG with additional ones if passed
  security_group_ids = concat(
    [aws_security_group.sg[0].id],
    try(each.value.security_groups, [])
  )

  private_dns_enabled = false

  tags = merge(
    {
      Name        = "${each.value.service_name}-endpoint"
      Environment = var.environment
    },
    var.tags
  )
}

###################################
# Hosted Zone (fixed)
###################################
# Since you always use ONE hosted zone, no need for data lookup.
# Just hardcode or make a variable for zone_id.
variable "hosted_zone_id" {
  description = "Fixed hosted zone ID for VPC endpoint DNS records"
  type        = string
  default     = "Z020880123ZGZ59VO"  # <-- replace with your actual hosted zone ID
}

###################################
# Route53 Record (Conditional)
###################################
resource "aws_route53_record" "endpoint_dns" {
  for_each = {
    for svc in local.vpc_endpoint_services : svc.service_name => svc
    if try(svc.dns_name, null) != null
  }

  zone_id = var.hosted_zone_id
  name    = each.value.dns_name
  type    = "A"

  alias {
    name                   = aws_vpc_endpoint.vpc_endpoints[each.key].dns_entries[0].dns_name
    zone_id                = aws_vpc_endpoint.vpc_endpoints[each.key].dns_entries[0].hosted_zone_id
    evaluate_target_health = true
  }
}



#########


resource "aws_vpc_endpoint" "vpc_endpoints" {
  for_each          = var.vpc_endpoints
  vpc_id            = module.centre-vpc[0].vpc_id
  service_name      = "com.amazonaws.${var.region}.${each.value.service_name}"
  vpc_endpoint_type = each.value.type
  subnet_ids        = each.value.subnets
  security_group_ids = each.value.security_groups != null ? each.value.security_groups : []
}

# Create Route53 record if dns_name is defined
resource "aws_route53_record" "vpc_endpoint_dns" {
  for_each = {
    for k, v in var.vpc_endpoints : k => v
    if try(v.dns_name, null) != null
  }

  zone_id = each.value.zone_id                 # pass zone_id in input variable
  name    = each.value.dns_name                # the custom DNS name you want
  type    = "CNAME"
  ttl     = 300
  records = [aws_vpc_endpoint.vpc_endpoints[each.key].dns_entry[0].dns_name]
}


#####


resource "aws_vpc_endpoint" "vpc_endpoints" {
  for_each = {
    for region, envs in var.vpc_endpoints :
    region => envs
  }

  vpc_id            = module.centre-vpc[0].vpc_id
  service_name      = each.value.service_name
  vpc_endpoint_type = "Interface"
  subnet_ids        = each.value.subnets
  security_group_ids = try(each.value.security_groups, [])
}

# Create Route53 record if dns_name is defined
resource "aws_route53_record" "vpc_endpoint_dns" {
  for_each = {
    for region, envs in var.vpc_endpoints :
    region => envs
    if try(envs[0].dns_name, null) != null
  }

  zone_id = "Z028038Z8326TZ59JY0"                   # Hosted zone id from input
  name    = each.value[0].dns_name                  # From input file
  type    = "A"

  alias {
    name                   = aws_vpc_endpoint.vpc_endpoints[each.key].dns_entry[0].dns_name
    zone_id                = aws_vpc_endpoint.vpc_endpoints[each.key].dns_entry[0].hosted_zone_id
    evaluate_target_health = true
  }
}


#######


# Create DNS record for VPC Endpoint only if dns_name is provided
resource "aws_route53_record" "vpce_dns" {
  for_each = {
    for k, v in var.vpc_endpoints[var.region] : k => v
    if contains(keys(v), "dns_name") && v.dns_name != null && v.dns_name != ""
  }

  zone_id = data.aws_route53_zone.selected.zone_id
  name    = each.value.dns_name
  type    = "CNAME"
  ttl     = 300

  # Point to the VPC endpoint's DNS entry
  records = [aws_vpc_endpoint.this[each.key].dns_entry[0].dns_name]
}

# Get hosted zone (replace with your zone name or param)
data "aws_route53_zone" "selected" {
  name         = var.hosted_zone_name
  private_zone = false
}


######


resource "aws_route53_record" "custom_service_dns" {
  for_each = {
    for service in local.vpcendpoint_custom_services :
    service.service_name => service
    if try(service.dns_name, null) != null
  }

  zone_id = aws_route53_zone.hosted_zone[each.value.hosted_zone].zone_id
  name    = each.value.dns_name
  type    = "A"

  alias {
    name                   = each.value.route_to_hz
    zone_id                = each.value.zone_id
    evaluate_target_health = true
  }
}


####


variable "route53_zone_id" {
  description = "Global hosted zone ID for VPC endpoint DNS records"
  type        = string
}

locals {
  vpc_endpoints = try(var["vpc_endpoints_${var.region}"], [])
}

# Lookup endpoint service (needed to get alias target + hosted zone)
data "aws_vpc_endpoint_service" "custom" {
  for_each     = {
    for svc in local.vpc_endpoints :
    svc.service_name => svc
    if try(svc.dns_name, null) != null
  }
  service_name = each.key
}

# Create Route53 records only if dns_name is defined
resource "aws_route53_record" "custom_service_dns" {
  for_each = {
    for svc in local.vpc_endpoints :
    svc.service_name => svc
    if try(svc.dns_name, null) != null
  }

  zone_id = var.route53_zone_id
  name    = each.value.dns_name
  type    = "A"

  alias {
    name                   = data.aws_vpc_endpoint_service.custom[each.key].dns_name_configuration[0].dns_name
    zone_id                = data.aws_vpc_endpoint_service.custom[each.key].dns_name_configuration[0].hosted_zone_id
    evaluate_target_health = true
  }
}



######


# Hardcoded hosted zone configuration in main.tf
locals {
  hosted_zone_config = {
    zone_id = "Z026488524KME623P1M2M"
    name    = "digital-tools.euw1.uat.aws.cloud.hsbc"
  }
}

resource "aws_vpc_endpoint" "vpc_endpoints" {
  provider = aws.secondary
  for_each = {
    for service in local.vpc_endpoint_services :
    "${service.group_name}-${var.region}-${replace(service.service_name, "com.amazonaws.vpce.${var.region}.", "")}" => {
      group_name      = service.group_name
      service_name    = service.service_name
      subnets         = service.subnets
      security_groups = service.security_groups
      label           = service.label
      dns_name        = service.dns_name  # This will contain the full DNS name like "admin-dev-ebw1-kong.digital-tools.euw1.uat.aws.cloud.hsbc"
    }
  }

  vpc_endpoint_type = "Interface"
  vpc_id            = var.region != "eu-west-1" ? module.dtime-vpc[0].vpc_id : var.eu_west_1_vpc_id

  # Merge default security group with additional ones
  security_group_ids = concat(
    var.region != "eu-west-1" ? [
      aws_security_group.vpc-endpoints-sg[0].id
    ] : [
      aws_security_group.dynamic_sg["jenkins-node-${each.value.group_name}"].id
    ],
    each.value.security_groups != null ? each.value.security_groups : []
  )

  service_name = each.value.service_name

  # Use provided subnets or fall back to default subnets
  subnet_ids = var.region != "eu-west-1" ? (
    length(each.value.subnets) > 0 ? [
      for i in each.value.subnets : module.dtime-vpc[0].subnet_private_ids[0][i]
    ] : module.dtime-vpc[0].subnet_private_ids[0]
  ) : (
    length(each.value.subnets) > 0 ? [
      for i in each.value.subnets : var.eu_west_1_private_subnet_ids[i]
    ] : var.eu_west_1_private_subnet_ids
  )

  tags = merge(
    each.value.label != null && each.value.label != "-" ? {
      Name = each.value.label
    } : {
      Name = "${each.value.group_name}-vpc-endpoint"
    },
    {
      environment   = var.tooling_environment
      controlled_by = "terraform"
      Used_by_team  = "${each.value.group_name}@1"
      Jenkins_team_id = each.value.group_name
      Type          = "Interface"
    }
  )
}

# Create DNS records for endpoints when dns_name is specified
resource "aws_route53_record" "vpc_endpoint_dns" {
  for_each = {
    for key, endpoint in aws_vpc_endpoint.vpc_endpoints : key => endpoint
    if try(each.value.dns_name, null) != null
  }

  provider = aws.secondary
  
  zone_id = local.hosted_zone_config.zone_id
  name    = each.value.dns_name  # Use the full DNS name from the configuration
  type    = "A"

  alias {
    name                   = each.value.dns_entry[0].dns_name
    zone_id                = each.value.dns_entry[0].hosted_zone_id
    evaluate_target_health = true
  }
}


####


# r-eu-west-1.auto.tfvars
vpc_endpoints = {
  eu_west_1 = [
    {
      service_name    = "com.amazonaws.vpce.eu-west-1.vpce-svc-8a8738766e24a3b9"
      security_groups = ["sg-8848443261c9496d8"]
      group_name      = "dynp"
      dns_name        = "dynp-service.digital-tools.euw1.uat.aws.cloud.hsbc"
    },
    {
      service_name    = "com.amazonaws.vpce.eu-west-1.vpce-svc-874786ee62a38819"
      security_groups = ["sg-8707441879914del0", "sg-87818765e16c2877"]
      group_name      = "ship"
      dns_name        = "shipping-api.digital-tools.euw1.uat.aws.cloud.hsbc"
    },
    {
      service_name    = "com.amazonaws.vpce.eu-west-1.vpce-svc-8a1bcab81cb2754b9"
      security_groups = []
      group_name      = "kong"
      dns_name        = "admin-dev-ebw1-kong.digital-tools.euw1.uat.aws.cloud.hsbc"
    }
  ]
}

# r-us-east-1.auto.tfvars
vpc_endpoints = {
  us_east_1 = [
    {
      service_name    = "com.amazonaws.vpce.us-east-1.vpce-svc-1234567890"
      security_groups = ["sg-1234567890"]
      group_name      = "api"
      dns_name        = "us-east-api.digital-tools.euw1.uat.aws.cloud.hsbc"
    }
  ]
}



######


provider "aws" {
  region  = var.region
  profile = "saml"
}

locals {
  # Hardcoded hosted zone configuration
  hosted_zone_config = {
    zone_id = "Z026488524KME623P1M2M"
    name    = "digital-tools.euw1.uat.aws.cloud.hsbc"
  }

  # Flatten the vpc_endpoints variable into a map of services
  vpc_endpoint_services = flatten([
    for group_name, services in var.vpc_endpoints : [
      for service in services : {
        group_name      = group_name
        service_name    = service.service_name
        subnets         = try(service.subnets, null)
        security_groups = try(service.security_groups, null)
        label           = try(service.label, null)
        dns_name        = try(service.dns_name, null)
      }
    ]
  ])

  # Create a map for easy iteration in resources
  vpc_endpoint_services_map = {
    for service in local.vpc_endpoint_services :
    "${service.group_name}-${var.region}-${replace(service.service_name, "com.amazonaws.vpce.${var.region}.", "")}" => service
  }
}

resource "aws_vpc_endpoint" "vpc_endpoints" {
  provider = aws.secondary
  for_each = local.vpc_endpoint_services_map

  vpc_endpoint_type = "Interface"
  vpc_id            = var.region != "eu-west-1" ? module.dtime-vpc[0].vpc_id : var.eu_west_1_vpc_id

  # Merge default security group with additional ones
  security_group_ids = concat(
    var.region != "eu-west-1" ? [
      aws_security_group.vpc-endpoints-sg[0].id
    ] : [
      aws_security_group.dynamic_sg["jenkins-node-${each.value.group_name}"].id
    ],
    each.value.security_groups != null ? each.value.security_groups : []
  )

  service_name = each.value.service_name

  # Use provided subnets or fall back to default subnets
  subnet_ids = var.region != "eu-west-1" ? (
    length(each.value.subnets) > 0 ? [
      for i in each.value.subnets : module.dtime-vpc[0].subnet_private_ids[0][i]
    ] : module.dtime-vpc[0].subnet_private_ids[0]
  ) : (
    length(each.value.subnets) > 0 ? [
      for i in each.value.subnets : var.eu_west_1_private_subnet_ids[i]
    ] : var.eu_west_1_private_subnet_ids
  )

  tags = merge(
    each.value.label != null && each.value.label != "-" ? {
      Name = each.value.label
    } : {
      Name = "${each.value.group_name}-vpc-endpoint"
    },
    {
      environment   = var.tooling_environment
      controlled_by = "terraform"
      Used_by_team  = "${each.value.group_name}@1"
      Jenkins_team_id = each.value.group_name
      Type          = "Interface"
    }
  )
}

# Create DNS records for endpoints when dns_name is specified
resource "aws_route53_record" "vpc_endpoint_dns" {
  for_each = {
    for key, endpoint in aws_vpc_endpoint.vpc_endpoints : key => endpoint
    if local.vpc_endpoint_services_map[key].dns_name != null
  }

  provider = aws.secondary
  
  zone_id = local.hosted_zone_config.zone_id
  name    = local.vpc_endpoint_services_map[each.key].dns_name
  type    = "A"

  alias {
    name                   = each.value.dns_entry[0].dns_name
    zone_id                = each.value.dns_entry[0].hosted_zone_id
    evaluate_target_health = true
  }
}


####


provider "aws" {
  version = "5.60.0"
  alias    = "secondary"
  region   = var.region
  profile  = "saml"
}

locals {
  # Hardcoded hosted zone configuration
  hosted_zone_config = {
    zone_id = "Z026488524KME623P1M2M"
    name    = "digital-tools.euw1.uat.aws.cloud.hsbc"
  }

  # Flatten the vpc_endpoints variable into a list of services
  vpc_endpoint_services = flatten([
    for group_name, services in var.vpc_endpoints : [
      for service in services : {
        group_name      = group_name
        service_name    = service.service_name
        subnets         = try(service.subnets, null)
        security_groups = try(service.security_groups, null)
        label           = try(service.label, null)
        dns_name        = try(service.dns_name, null)
      }
    ]
  ])
}

resource "aws_vpc_endpoint" "vpc_endpoints" {
  provider = aws.secondary
  for_each = {
    for service in local.vpc_endpoint_services :
    "${service.group_name}-${var.region}-${replace(service.service_name, "com.amazonaws.vpce.${var.region}.", "")}" => service
  }

  vpc_endpoint_type = "Interface"
  vpc_id            = var.region != "eu-west-1" ? module.dtime-vpc[0].vpc_id : var.eu_west_1_vpc_id

  # Merge default security group with additional ones
  security_group_ids = concat(
    var.region != "eu-west-1" ? [
      aws_security_group.vpc-endpoints-sg[0].id
    ] : [
      aws_security_group.dynamic_sg["jenkins-node-${each.value.group_name}"].id
    ],
    each.value.security_groups != null ? each.value.security_groups : []
  )

  service_name = each.value.service_name

  # Use provided subnets or fall back to default subnets
  subnet_ids = var.region != "eu-west-1" ? (
    length(each.value.subnets) > 0 ? [
      for i in each.value.subnets : module.dtime-vpc[0].subnet_private_ids[0][i]
    ] : module.dtime-vpc[0].subnet_private_ids[0]
  ) : (
    length(each.value.subnets) > 0 ? [
      for i in each.value.subnets : var.eu_west_1_private_subnet_ids[i]
    ] : var.eu_west_1_private_subnet_ids
  )

  tags = merge(
    each.value.label != null && each.value.label != "-" ? {
      Name = each.value.label
    } : {
      Name = "${each.value.group_name}-vpc-endpoint"
    },
    {
      environment   = var.tooling_environment
      controlled_by = "terraform"
      Used_by_team  = "${each.value.group_name}@1"
      Jenkins_team_id = each.value.group_name
      Type          = "Interface"
    }
  )
}

# Create DNS records for endpoints when dns_name is specified
resource "aws_route53_record" "vpc_endpoint_dns" {
  for_each = {
    for service in local.vpc_endpoint_services :
    "${service.group_name}-${var.region}-${replace(service.service_name, "com.amazonaws.vpce.${var.region}.", "")}" => service
    if service.dns_name != null
  }

  provider = aws.secondary
  
  zone_id = local.hosted_zone_config.zone_id
  name    = each.value.dns_name
  type    = "A"

  alias {
    name                   = aws_vpc_endpoint.vpc_endpoints[each.key].dns_entry[0].dns_name
    zone_id                = aws_vpc_endpoint.vpc_endpoints[each.key].dns_entry[0].hosted_zone_id
    evaluate_target_health = true
  }
}


##########


pipeline {
    agent any
    environment {
        AWS_DEFAULT_REGION = "us-east-1"  // change region
    }
    stages {
        stage('Fetch HAProxy Instances') {
            steps {
                script {
                    INSTANCE_IDS = sh(
                        script: '''
                        aws ec2 describe-instances \
                          --filters "Name=tag:Role,Values=haproxy" "Name=instance-state-name,Values=running" \
                          --query "Reservations[*].Instances[*].InstanceId" \
                          --output text
                        ''',
                        returnStdout: true
                    ).trim()
                    
                    if (INSTANCE_IDS == "") {
                        error "No HAProxy instances found!"
                    } else {
                        echo "Found HAProxy Instances: ${INSTANCE_IDS}"
                    }
                }
            }
        }
        
        stage('Check HAProxy Config') {
            steps {
                script {
                    COMMAND_ID = sh(
                        script: '''
                        aws ssm send-command \
                          --targets "Key=tag:Role,Values=haproxy" \
                          --document-name "AWS-RunShellScript" \
                          --comment "Check HAProxy config" \
                          --parameters 'commands=["haproxy -c -f /etc/haproxy/haproxy.cfg"]' \
                          --query "Command.CommandId" --output text
                        ''',
                        returnStdout: true
                    ).trim()
                    
                    sleep 10 // wait for command execution
                    
                    OUTPUT = sh(
                        script: "aws ssm list-command-invocations --command-id ${COMMAND_ID} --details --output text",
                        returnStdout: true
                    ).trim()
                    
                    echo "SSM Output: ${OUTPUT}"
                    
                    if (!OUTPUT.contains("Configuration file is valid")) {
                        echo "HAProxy config check failed!"
                        // 🔔 Call your notification Lambda here
                        sh '''
                        aws lambda invoke \
                          --function-name sendNotificationLambda \
                          --payload '{"message":"HAProxy config check failed!"}' \
                          response.json
                        '''
                        error "Stopping pipeline due to HAProxy config error"
                    } else {
                        echo "HAProxy config is valid ✅"
                    }
                }
            }
        }
    }
}


#######


pipeline {
    agent any
    environment {
        AWS_DEFAULT_REGION = "us-east-1"   // change to your AWS region
        HAPROXY_TAG_KEY    = "Role"
        HAPROXY_TAG_VALUE  = "haproxy"
        NOTIFY_LAMBDA      = "sendNotificationLambda"  // your lambda name
    }
    stages {
        stage('Get HAProxy Instance') {
            steps {
                script {
                    INSTANCE_ID = sh(
                        script: """
                        aws ec2 describe-instances \
                          --filters "Name=tag:${HAPROXY_TAG_KEY},Values=${HAPROXY_TAG_VALUE}" "Name=instance-state-name,Values=running" \
                          --query "Reservations[0].Instances[0].InstanceId" \
                          --output text
                        """,
                        returnStdout: true
                    ).trim()

                    if (INSTANCE_ID == "" || INSTANCE_ID == "None") {
                        error "No running HAProxy instance found!"
                    } else {
                        echo "Selected HAProxy Instance: ${INSTANCE_ID}"
                    }
                }
            }
        }

        stage('Check HAProxy Config') {
            steps {
                script {
                    COMMAND_ID = sh(
                        script: """
                        aws ssm send-command \
                          --targets "Key=instanceIds,Values=${INSTANCE_ID}" \
                          --document-name "AWS-RunShellScript" \
                          --comment "Check HAProxy config" \
                          --parameters 'commands=["haproxy -c -f /etc/haproxy/haproxy.cfg"]' \
                          --query "Command.CommandId" \
                          --output text
                        """,
                        returnStdout: true
                    ).trim()

                    sleep 10  // wait for command execution

                    OUTPUT = sh(
                        script: "aws ssm list-command-invocations --command-id ${COMMAND_ID} --details --output text",
                        returnStdout: true
                    ).trim()

                    echo "SSM Output: ${OUTPUT}"

                    if (!OUTPUT.contains("Configuration file is valid")) {
                        echo "HAProxy config check failed on ${INSTANCE_ID}"

                        // 🔔 Send notification via Lambda
                        sh """
                        aws lambda invoke \
                          --function-name ${NOTIFY_LAMBDA} \
                          --payload '{"sender":"jenkins@company.com","recipient":"team@company.com","message":"HAProxy config check failed on instance ${INSTANCE_ID}"}' \
                          response.json
                        """

                        error "Stopping pipeline due to HAProxy config error"
                    } else {
                        echo "HAProxy config is valid ✅"
                    }
                }
            }
        }
    }
}


We are using the same mailbox for all certificate alerts. I’ll update the email distribution and take care of this.