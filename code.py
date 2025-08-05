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


