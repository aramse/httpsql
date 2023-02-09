import static io.aramse.f8.Utils.*

def mainBranches = ["master", "main"]
def mergedBranch

pipeline {
  agent any
  options {
    disableConcurrentBuilds()
  }
  environment {
    COMMIT_HASH = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
    F8_TAG = "$BRANCH_NAME-$BUILD_ID-$COMMIT_HASH"
    F8_ENVIRONMENT = "$BRANCH_NAME"
    F8_ENV_TYPE = "${mainBranches.contains(env.BRANCH_NAME) ? 'prod' : env.BRANCH_NAME}"
    F8_LOG_LINKS = "true"

    BUILD_CMD = "f8 build --push"
    DEPLOY_CMD = "f8 deploy"
    TEST_CMD = "f8 test"
  }

  stages {
    stage('Build') {
      steps {
        script {
          mergedBranch = getMergedBranch(this)
          if (env.REG_USER != "") { 
            docker.withRegistry(env.REG_AUTH_URL, env.REG_CREDS_ID) {
              sh env.BUILD_CMD
            }
          } else {
            sh env.BUILD_CMD
          }
        }
      }
    }
    stage('Deploy') {
      steps {
        sh env.DEPLOY_CMD
      }
    }
    stage('Test') {
      steps {
        sh env.TEST_CMD
      }
    }
    stage('Delete Merged Env') {
      when {
        expression {
          mainBranches.contains(env.BRANCH_NAME) && mergedBranch
        }
      }
      steps {
        sh 'f8 delete --env ' + mergedBranch
      }
    }
  }
  post {
    always {
      script {
        if (env.SLACK_ENABLED == 'true') {
          slackNotify(this, currentBuild.result)
        }
      }
    }
  }
}
