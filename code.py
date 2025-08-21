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

